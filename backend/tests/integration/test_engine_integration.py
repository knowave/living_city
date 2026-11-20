import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError
from app.models import (
    Account,
    Building,
    Citizen,
    Company,
    Employment,
    LedgerEntry,
    Transaction,
    World,
    WorldEvent,
    WorldMetric,
    WorldPolicy,
    WorldSnapshot,
)
from app.repositories.sqlalchemy import repositories as repo_mod
from app.schemas.world import PolicyUpdate, TickAdvanceRequest, WorldCreate
from tests.integration.conftest import http_pause, pause_world
from simulation_engine.world.snapshot import WorldSnapshot as EngineSnapshot
from simulation_engine.world.state import WorldState

pytestmark = pytest.mark.integration


def count(s, model, world_id, *where):
    return s.scalar(select(func.count()).select_from(model).where(model.world_id == world_id, *where))


def create(make_service, seed=42, name="w"):
    w = make_service().create_world(WorldCreate(name=name, seed=seed))
    pause_world(make_service, w.id)
    return make_service().get_world(w.id)


def advance(make_service, world_id, n):
    tick = make_service().get_world(world_id).current_tick
    return make_service().advance_ticks(world_id, TickAdvanceRequest(count=n, expected_tick=tick))


def latest_snapshot(s, world_id):
    return s.scalar(
        select(WorldSnapshot).where(WorldSnapshot.world_id == world_id).order_by(WorldSnapshot.tick.desc())
    )


def totals(s, world_id):
    return s.scalar(select(func.coalesce(func.sum(Account.balance), 0)).where(Account.world_id == world_id))


def strip_ids(v):
    if isinstance(v, dict):
        return {k: strip_ids(x) for k, x in v.items() if not k.endswith("_id")}
    if isinstance(v, list):
        return [strip_ids(x) for x in v]
    return v


# ---- AC3 ----
def test_create_world_persists_engine_output(make_service, session_factory):
    w = create(make_service)
    s = session_factory()
    assert count(s, Building, w.id) == 21
    assert count(s, Citizen, w.id) == 100
    assert count(s, Company, w.id) == 10
    assert count(s, Employment, w.id, Employment.status == "ACTIVE") == 88
    assert count(s, Transaction, w.id, Transaction.transaction_type == "OPENING_BALANCE") == 111
    assert totals(s, w.id) == 0
    assert latest_snapshot(s, w.id).tick == 0


def test_get_state_after_create_returns_engine_policy(client):
    wid = client.post("/api/v1/worlds", json={"name": "w", "seed": 7}).json()["id"]
    body = client.get(f"/api/v1/worlds/{wid}/state").json()
    assert body["current_policy"]["welfare_amount"] == 1_000_000
    assert body["current_tick"] == 0


# ---- AC4 ----
def test_two_worlds_same_seed_both_persist_with_same_content(make_service, session_factory):
    a, b = create(make_service, 5, "a"), create(make_service, 5, "b")
    s = session_factory()
    for model in (Building, Citizen, Company, Employment, Account, Transaction, LedgerEntry):
        assert count(s, model, a.id) == count(s, model, b.id) > 0

    def citizens(wid):
        return s.execute(
            select(Citizen.name, Citizen.age).where(Citizen.world_id == wid).order_by(Citizen.name, Citizen.age)
        ).all()

    assert citizens(a.id) == citizens(b.id)


# ---- AC5 ----
def test_advance_persists_contiguous_events_and_snapshot(make_service, session_factory):
    w = create(make_service)
    r1 = advance(make_service, w.id, 24)
    r2 = advance(make_service, w.id, 1)
    s = session_factory()
    assert (r1.from_tick, r1.to_tick, r2.from_tick, r2.to_tick) == (0, 24, 24, 25)
    assert s.get(World, w.id).current_tick == 25
    seqs = list(s.scalars(select(WorldEvent.sequence).where(WorldEvent.world_id == w.id).order_by(WorldEvent.sequence)))
    assert seqs == list(range(1, len(seqs) + 1)) and seqs
    snap = latest_snapshot(s, w.id)
    assert snap.tick == 25 and snap.last_event_sequence == max(seqs) == r2.last_event_sequence


def test_advance_ledger_balances_per_transaction_and_total_is_zero(make_service, session_factory):
    w = create(make_service)
    advance(make_service, w.id, 24)
    s = session_factory()
    bad = s.execute(
        select(LedgerEntry.transaction_id)
        .where(LedgerEntry.world_id == w.id)
        .group_by(LedgerEntry.transaction_id)
        .having(func.sum(LedgerEntry.amount) != 0)
    ).all()
    assert bad == []
    assert totals(s, w.id) == 0


def test_advance_month_end_writes_metrics_and_salary(make_service, session_factory):
    w = create(make_service)
    advance(make_service, w.id, 720)
    s = session_factory()
    assert count(s, WorldMetric, w.id) > 0
    assert count(s, Transaction, w.id, Transaction.transaction_type == "SALARY") > 0
    assert totals(s, w.id) == 0


# ---- AC6 ----
def test_pending_policy_applied_as_engine_row_and_event(make_service, session_factory):
    w = create(make_service)
    advance(make_service, w.id, 24)
    pending = make_service().change_policy(w.id, PolicyUpdate(welfare_amount=555_000))
    advance(make_service, w.id, 2)
    s = session_factory()
    rows = list(s.scalars(select(WorldPolicy).where(WorldPolicy.world_id == w.id, WorldPolicy.effective_tick == pending.effective_tick)))
    assert len(rows) == 1 and rows[0].welfare_amount == 555_000
    assert count(s, WorldEvent, w.id, WorldEvent.type == "policy.updated") == 1
    cur = make_service().get_world_state(w.id).current_policy
    assert cur.welfare_amount == 555_000


def test_second_patch_in_same_tick_overwrites_pending_row(make_service, session_factory):
    w = create(make_service)
    make_service().change_policy(w.id, PolicyUpdate(welfare_amount=1))
    p2 = make_service().change_policy(w.id, PolicyUpdate(welfare_amount=2))
    s = session_factory()
    assert count(s, WorldPolicy, w.id, WorldPolicy.effective_tick == p2.effective_tick) == 1


# ---- AC7 ----
def test_failure_mid_batch_persists_nothing(make_service, session_factory, monkeypatch):
    w = create(make_service)
    advance(make_service, w.id, 24)
    s0 = session_factory()
    before = (
        count(s0, WorldEvent, w.id), count(s0, Transaction, w.id),
        s0.get(World, w.id).current_tick, s0.get(World, w.id).version,
        latest_snapshot(s0, w.id).tick,
    )
    s0.rollback()

    orig = repo_mod.SqlSimulationPersistence._insert

    def boom(self, model, rows):
        if model is WorldSnapshot:
            raise RuntimeError("injected")
        return orig(self, model, rows)

    monkeypatch.setattr(repo_mod.SqlSimulationPersistence, "_insert", boom)
    with pytest.raises(RuntimeError, match="injected"):
        advance(make_service, w.id, 24)
    monkeypatch.undo()

    s = session_factory()
    after = (
        count(s, WorldEvent, w.id), count(s, Transaction, w.id),
        s.get(World, w.id).current_tick, s.get(World, w.id).version,
        latest_snapshot(s, w.id).tick,
    )
    assert after == before


# ---- AC8 ----
def test_stale_version_advance_tick_conflicts_and_writes_nothing(make_service, session_factory):
    w = create(make_service)
    uow_stale = make_service()._uow
    stale = uow_stale.worlds.get(w.id)
    advance(make_service, w.id, 1)
    with pytest.raises(ConflictError) as ei:
        uow_stale.worlds.advance_tick(w.id, new_tick=99, expected_version=stale.version)
    assert ei.value.code == "CONCURRENT_UPDATE"
    uow_stale.rollback()
    assert session_factory().get(World, w.id).current_tick == 1


def test_duplicate_event_sequence_rejected(make_service, session_factory):
    w = create(make_service)
    advance(make_service, w.id, 24)
    s = session_factory()
    seq = s.scalar(select(func.max(WorldEvent.sequence)).where(WorldEvent.world_id == w.id))
    assert seq
    with pytest.raises(IntegrityError):
        s.execute(
            WorldEvent.__table__.insert().values(
                id=uuid.uuid4(), world_id=w.id, sequence=seq, tick=1, type="x", payload={}, schema_version=1
            )
        )


def test_duplicate_idempotency_key_rejected(make_service, session_factory):
    w = create(make_service)
    s = session_factory()
    key = s.scalar(select(Transaction.idempotency_key).where(Transaction.world_id == w.id).limit(1))
    with pytest.raises(IntegrityError):
        s.execute(
            Transaction.__table__.insert().values(
                id=uuid.uuid4(), world_id=w.id, transaction_type="OPENING_BALANCE", tick=0,
                idempotency_key=key, metadata={},
            )
        )


# ---- AC9 ----
def _history(s, wid):
    events = [
        (e.sequence, e.type, strip_ids(e.payload))
        for e in s.scalars(select(WorldEvent).where(WorldEvent.world_id == wid).order_by(WorldEvent.sequence))
    ]
    txs = [
        (t.idempotency_key, t.transaction_type, t.tick)
        for t in s.scalars(select(Transaction).where(Transaction.world_id == wid).order_by(Transaction.idempotency_key))
    ]
    amounts = s.execute(
        select(Transaction.idempotency_key, func.sum(func.abs(LedgerEntry.amount)))
        .join(LedgerEntry, LedgerEntry.transaction_id == Transaction.id)
        .where(Transaction.world_id == wid)
        .group_by(Transaction.idempotency_key)
        .order_by(Transaction.idempotency_key)
    ).all()
    state = dict(latest_snapshot(s, wid).state_data)
    # backend-owned world fields (id, name) legitimately differ between the two worlds
    state["world"] = {k: v for k, v in state["world"].items() if k not in ("id", "name")}
    return events, txs, amounts, state


def test_split_advance_equals_single_advance(make_service, session_factory):
    a, b = create(make_service, 11, "a"), create(make_service, 11, "b")
    advance(make_service, a.id, 48)
    advance(make_service, b.id, 20)
    advance(make_service, b.id, 28)
    s = session_factory()
    assert _history(s, a.id) == _history(s, b.id)


# ---- AC10 ----
def test_latest_snapshot_round_trips_through_engine(make_service, session_factory):
    w = create(make_service)
    advance(make_service, w.id, 24)
    s = session_factory()
    snap = latest_snapshot(s, w.id)
    es = EngineSnapshot(
        id=uuid.UUID(int=0), tick=snap.tick, last_event_sequence=snap.last_event_sequence,
        engine_version=snap.engine_version, state_data=snap.state_data,
    )
    state = WorldState.from_snapshot(es)
    assert state.to_snapshot().state_data == snap.state_data
    max_seq = s.scalar(select(func.max(WorldEvent.sequence)).where(WorldEvent.world_id == w.id))
    assert snap.last_event_sequence == max_seq


# ---- AC11 ----
def test_engine_failure_marks_world_failed_and_blocks_further_advance(make_service, session_factory):
    w = create(make_service)
    s = session_factory()
    snap = latest_snapshot(s, w.id)
    snap.state_data = {**snap.state_data, "format_version": 999}
    s.commit()
    n_events = count(s, WorldEvent, w.id)

    with pytest.raises(ConflictError) as ei:
        advance(make_service, w.id, 1)
    assert ei.value.code == "SIMULATION_FAILED"

    s2 = session_factory()
    assert s2.get(World, w.id).status == "FAILED"
    assert count(s2, WorldEvent, w.id) == n_events
    assert s2.get(World, w.id).current_tick == 0
    with pytest.raises(Exception) as ei2:
        advance(make_service, w.id, 1)
    assert ei2.value.code == "WORLD_NOT_PAUSED"


def test_archived_world_cannot_advance(make_service):
    from app.schemas.enums import WorldStatus
    from app.schemas.world import SimulationUpdate

    w = create(make_service)
    make_service().change_simulation(w.id, SimulationUpdate(status=WorldStatus.ARCHIVED))
    with pytest.raises(Exception) as ei:
        advance(make_service, w.id, 1)
    assert ei.value.code == "WORLD_NOT_PAUSED"


# ---- HTTP ----
def test_http_flow_create_advance_patch_advance_and_conflict_envelope(client):
    r = client.post("/api/v1/worlds", json={"name": "h", "seed": 3})
    assert r.status_code == 201
    wid = r.json()["id"]
    http_pause(client, wid)
    r = client.post(f"/api/v1/worlds/{wid}/ticks", json={"count": 2, "expected_tick": 0})
    assert r.status_code == 200 and r.json()["to_tick"] == 2
    assert client.patch(f"/api/v1/worlds/{wid}/policies", json={"welfare_amount": 7}).status_code == 200
    r = client.post(f"/api/v1/worlds/{wid}/ticks", json={"count": 2, "expected_tick": 2})
    assert r.status_code == 200 and r.json()["to_tick"] == 4
    client.patch(f"/api/v1/worlds/{wid}/simulation", json={"status": "ARCHIVED"})
    r = client.post(f"/api/v1/worlds/{wid}/ticks", json={"count": 1, "expected_tick": 4})
    assert r.status_code == 409 and r.json()["error"]["code"] == "WORLD_NOT_PAUSED"


@pytest.mark.integration
def test_http_create_world_engine_failure_returns_409_and_persists_nothing(client, session_factory, monkeypatch):
    from app.models import World
    from app.simulation import engine_adapter

    def boom(*args, **kwargs):
        raise ValueError("engine exploded")

    # 엔진 내부 실패를 흉내낸다: adapter가 SimulationEngineError로 감싸야 한다.
    monkeypatch.setattr(engine_adapter, "generate_world", boom)
    with session_factory() as s:
        before = s.scalar(select(func.count()).select_from(World))

    r = client.post("/api/v1/worlds", json={"name": "broken", "seed": 987654})

    assert r.status_code == 409
    assert r.json()["error"]["code"] == "WORLD_GENERATION_FAILED"
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(World)) == before
