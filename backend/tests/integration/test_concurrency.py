import threading
import time

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import ConflictError
from app.models import Transaction, World, WorldEvent, WorldSnapshot
from app.repositories.sqlalchemy import SqlAlchemyUnitOfWork
from app.repositories.sqlalchemy import repositories as repo_mod
from app.schemas.world import PolicyUpdate, TickAdvanceRequest, WorldCreate
from app.services.world_service import WorldService
from tests.integration.conftest import http_pause, pause_world
from app.simulation.engine_adapter import SimulationEngineAdapter

pytestmark = pytest.mark.integration

BUSY_OR_MISMATCH = {"WORLD_BUSY", "TICK_MISMATCH"}


def new_world(make_service, seed=42):
    w = make_service().create_world(WorldCreate(name="w", seed=seed))
    pause_world(make_service, w.id)
    return make_service().get_world(w.id)


def counts(session_factory, wid):
    s = session_factory()
    s.rollback()  # fresh view
    c = (
        s.scalar(select(func.count()).select_from(WorldEvent).where(WorldEvent.world_id == wid)),
        s.scalar(select(func.count()).select_from(Transaction).where(Transaction.world_id == wid)),
        s.scalar(select(func.count()).select_from(WorldSnapshot).where(WorldSnapshot.world_id == wid)),
    )
    w = s.get(World, wid)
    s.rollback()
    return c + (w.current_tick, w.version)


def advance_req(n, tick):
    return TickAdvanceRequest(count=n, expected_tick=tick)


def hold_lock(session_factory, wid):
    s = session_factory()
    s.execute(select(World).where(World.id == wid).with_for_update())
    return s


def race(fns):
    """Run callables simultaneously behind a barrier; return per-fn ('ok', value) or ('err', exc)."""
    barrier = threading.Barrier(len(fns))
    out = [None] * len(fns)

    def run(i):
        barrier.wait(timeout=30)
        try:
            out[i] = ("ok", fns[i]())
        except BaseException as e:  # noqa: BLE001 - we assert on the exact type
            out[i] = ("err", e)

    ts = [threading.Thread(target=run, args=(i,)) for i in range(len(fns))]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=60)
        assert not t.is_alive(), "thread hung"
    return out


# ---- AC2 ----
@pytest.mark.parametrize("round_", range(5))
def test_parallel_advance_exactly_one_succeeds_and_one_batch_written(make_service, session_factory, round_):
    base = new_world(make_service)
    make_service().advance_ticks(base.id, advance_req(10, 0))
    base_counts = counts(session_factory, base.id)

    w = new_world(make_service)
    before = counts(session_factory, w.id)
    svcs = [make_service(), make_service()]
    res = race([lambda s=s: s.advance_ticks(w.id, advance_req(10, 0)) for s in svcs])

    oks = [r for k, r in res if k == "ok"]
    errs = [r for k, r in res if k == "err"]
    assert len(oks) == 1
    assert len(errs) == 1 and type(errs[0]) is ConflictError
    assert errs[0].code in BUSY_OR_MISMATCH
    after = counts(session_factory, w.id)
    assert after[3] == 10
    # same seed -> same batch size as the single-run baseline
    assert after[:3] == base_counts[:3] and after[:3] != before[:3]
    s = session_factory()
    snap = s.scalar(select(WorldSnapshot).where(WorldSnapshot.world_id == w.id).order_by(WorldSnapshot.tick.desc()))
    max_seq = s.scalar(select(func.max(WorldEvent.sequence)).where(WorldEvent.world_id == w.id))
    assert snap.tick == 10 and snap.last_event_sequence == max_seq == oks[0].last_event_sequence


def test_parallel_http_advance_exactly_one_200_no_500(client, make_service, session_factory):
    # TestClient shares one app/anyio portal per call and each request opens its own session via the
    # get_db override (session_factory is a list.append, thread-safe under the GIL), so threads work.
    wid = http_pause(client, client.post("/api/v1/worlds", json={"name": "w", "seed": 3}).json()["id"])
    url = f"/api/v1/worlds/{wid}/ticks"
    res = race([lambda: client.post(url, json={"count": 10, "expected_tick": 0}) for _ in range(2)])
    assert all(k == "ok" for k, _ in res), res
    codes = sorted(r.status_code for _, r in res)
    assert codes == [200, 409]
    loser = next(r for _, r in res if r.status_code == 409)
    assert loser.json()["error"]["code"] in BUSY_OR_MISMATCH
    assert client.get(f"/api/v1/worlds/{wid}").json()["current_tick"] == 10


# ---- AC3 ----
def test_advance_while_row_locked_returns_world_busy_fast_and_writes_nothing(make_service, session_factory):
    w = new_world(make_service)
    before = counts(session_factory, w.id)
    s1 = hold_lock(session_factory, w.id)
    try:
        t0 = time.monotonic()
        with pytest.raises(ConflictError) as ei:
            make_service().advance_ticks(w.id, advance_req(10, 0))
        assert time.monotonic() - t0 < 1.0
        assert ei.value.code == "WORLD_BUSY"
    finally:
        s1.rollback()
    assert counts(session_factory, w.id) == before


# ---- AC4 ----
def test_resending_same_advance_returns_tick_mismatch_with_current_tick_and_writes_nothing(
    make_service, session_factory
):
    w = new_world(make_service)
    make_service().advance_ticks(w.id, advance_req(10, 0))
    after_first = counts(session_factory, w.id)
    with pytest.raises(ConflictError) as ei:
        make_service().advance_ticks(w.id, advance_req(10, 0))
    assert ei.value.code == "TICK_MISMATCH"
    assert ei.value.details == {"current_tick": 10}
    assert counts(session_factory, w.id) == after_first


def test_http_advance_without_expected_tick_is_422(client):
    wid = http_pause(client, client.post("/api/v1/worlds", json={"name": "w", "seed": 1}).json()["id"])
    assert client.post(f"/api/v1/worlds/{wid}/ticks", json={"count": 1}).status_code == 422


def test_http_advance_with_wrong_expected_tick_is_409_with_current_tick(client):
    wid = http_pause(client, client.post("/api/v1/worlds", json={"name": "w", "seed": 1}).json()["id"])
    r = client.post(f"/api/v1/worlds/{wid}/ticks", json={"count": 1, "expected_tick": 5})
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "TICK_MISMATCH" and err["details"]["current_tick"] == 0


# ---- AC5 ----
def test_policy_patch_waits_for_lock_release_then_uses_committed_tick(make_service, session_factory):
    w = new_world(make_service)
    make_service().advance_ticks(w.id, advance_req(5, 0))
    s1 = hold_lock(session_factory, w.id)
    box = {}

    def patch():
        try:
            box["r"] = make_service().change_policy(w.id, PolicyUpdate(income_tax_rate=1500))
        except BaseException as e:  # noqa: BLE001
            box["e"] = e

    t = threading.Thread(target=patch)
    t.start()
    time.sleep(1.0)
    assert t.is_alive(), "PATCH should be waiting on the lock"
    s1.rollback()
    t.join(timeout=30)
    assert not t.is_alive()
    assert "e" not in box, box.get("e")
    assert box["r"].effective_tick == 6


def test_policy_patch_times_out_with_world_busy_when_lock_held_longer_than_timeout(
    session_factory, make_service
):
    w = new_world(make_service)
    svc = WorldService(
        SqlAlchemyUnitOfWork(session_factory()), SimulationEngineAdapter(), settings.ENGINE_VERSION,
        lock_timeout_ms=500,
    )
    s1 = hold_lock(session_factory, w.id)
    try:
        t0 = time.monotonic()
        with pytest.raises(ConflictError) as ei:
            svc.change_policy(w.id, PolicyUpdate(welfare_amount=5))
        assert 0.4 <= time.monotonic() - t0 < 3.0
        assert ei.value.code == "WORLD_BUSY"
    finally:
        s1.rollback()


def test_interleaved_advance_and_policy_patch_keeps_world_running_and_applies_policy(
    make_service, session_factory
):
    w = new_world(make_service)
    make_service().advance_ticks(w.id, advance_req(3, 0))
    p = make_service().change_policy(w.id, PolicyUpdate(income_tax_rate=2000))
    make_service().advance_ticks(w.id, advance_req(3, 3))
    make_service().change_policy(w.id, PolicyUpdate(welfare_amount=123))
    make_service().advance_ticks(w.id, advance_req(3, 6))
    s = session_factory()
    row = s.get(World, w.id)
    assert row.status != "FAILED" and row.current_tick == 9
    assert p.effective_tick == 4
    state = make_service().get_world_state(w.id)
    assert state.current_policy.income_tax_rate == 2000 and state.current_policy.welfare_amount == 123
    types = set(s.scalars(select(WorldEvent.type).where(WorldEvent.world_id == w.id)))
    assert any("polic" in t for t in types), types


# ---- AC6 (stale version -> CONCURRENT_UPDATE is covered by
# test_engine_integration.test_stale_version_advance_tick_conflicts_and_writes_nothing) ----
def test_integrity_error_during_save_becomes_concurrent_update_and_persists_nothing(
    make_service, session_factory, monkeypatch
):
    w = new_world(make_service)
    before = counts(session_factory, w.id)

    def boom(self, model, rows):
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    monkeypatch.setattr(repo_mod.SqlSimulationPersistence, "_insert", boom)
    with pytest.raises(ConflictError) as ei:
        make_service().advance_ticks(w.id, advance_req(10, 0))
    assert ei.value.code == "CONCURRENT_UPDATE"
    monkeypatch.undo()
    assert counts(session_factory, w.id) == before
