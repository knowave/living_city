import uuid

import pytest

from app.simulation.interfaces import PolicyCommandInput, SimulationEngineError
from app.core.exceptions import ConflictError, DomainValidationError, InvalidStateError, NotFoundError
from app.repositories.interfaces import NewPolicy
from app.schemas.enums import WorldStatus as S
from app.repositories.interfaces import SnapshotRecord
from app.schemas.world import PolicyUpdate, SimulationUpdate, TickAdvanceRequest, WorldCreate
from app.services import WorldService
from tests.maps.helpers import BLOCKED
from tests.services.fakes import FakeEnginePort, FakeUnitOfWork, make_batch


@pytest.fixture
def uow():
    return FakeUnitOfWork()


@pytest.fixture
def engine():
    return FakeEnginePort()


@pytest.fixture
def svc(uow, engine):
    return WorldService(uow, engine, "9.9.9")


def make(svc, uow, status=S.INITIALIZED, tick=0, speed=1):
    w = svc.create_world(WorldCreate(name="w"))
    uow.worlds.items[w.id] = w.model_copy(
        update={"status": status, "current_tick": tick, "speed": speed}
    )
    uow.policies.add(NewPolicy(w.id, 1500, 0, 0, 1))  # engine policy as persisted by generation
    uow.snapshots.items[w.id] = SnapshotRecord(tick, 0, {"tick": tick})
    uow.commits = 0
    return w.id


def code(exc):
    return exc.value.code


def test_create_defaults(svc, uow, engine):
    w = svc.create_world(WorldCreate(name="a"))
    assert (w.status, w.current_tick, w.speed) == (S.INITIALIZED, 0, 1)
    assert w.engine_version == "9.9.9"
    assert 0 <= w.seed < 2**63
    assert uow.policies.items == []  # backend creates no policy; engine's is saved by persistence
    assert engine.generated == [(w.seed, "a")]
    assert [wid for wid, _ in uow.simulation.generations] == [w.id]
    assert uow.commits == 1
    assert uow.chunks.count(w.id) == 256


def test_create_map_validation_failure_persists_nothing(svc, uow, engine):
    engine.batch.buildings = BLOCKED
    with pytest.raises(ConflictError) as e:
        svc.create_world(WorldCreate(name="a"))
    assert code(e) == "WORLD_GENERATION_FAILED"
    assert uow.worlds.items == {} and uow.chunks.saved == [] and uow.commits == 0


def test_create_engine_failure_persists_nothing(svc, uow, engine):
    engine.error = SimulationEngineError("boom")
    with pytest.raises(ConflictError) as e:
        svc.create_world(WorldCreate(name="a"))
    assert code(e) == "WORLD_GENERATION_FAILED"
    assert uow.worlds.items == {} and uow.simulation.generations == [] and uow.commits == 0


def test_create_explicit_seed_and_engine(svc):
    w = svc.create_world(WorldCreate(name="a", seed=0, engine_version="1.2.3"))
    assert (w.seed, w.engine_version) == (0, "1.2.3")


def test_create_random_seeds_differ(svc):
    assert svc.create_world(WorldCreate(name="a")).seed != svc.create_world(WorldCreate(name="a")).seed


def test_get_world_and_not_found(svc, uow):
    wid = make(svc, uow)
    assert svc.get_world(wid).id == wid
    with pytest.raises(NotFoundError) as e:
        svc.get_world(uuid.uuid4())
    assert code(e) == "WORLD_NOT_FOUND"
    with pytest.raises(NotFoundError):
        svc.get_world_state(uuid.uuid4())


def test_state_cursor_and_current_policy(svc, uow):
    wid = make(svc, uow, tick=5)
    uow.events.seq[wid] = 42
    uow.policies.add(NewPolicy(wid, 2000, 5, 3, 2))
    uow.policies.add(NewPolicy(wid, 3000, 9, 10, 3))  # future
    st = svc.get_world_state(wid)
    assert st.event_cursor == 42
    assert st.current_policy.version == 2
    assert st.current_tick == 5


def test_state_cursor_zero(svc, uow):
    wid = make(svc, uow)
    st = svc.get_world_state(wid)
    assert st.event_cursor == 0 and st.current_policy.version == 1
    assert uow.commits == 0


ALLOWED = [
    (S.INITIALIZED, S.RUNNING), (S.RUNNING, S.PAUSED), (S.PAUSED, S.RUNNING),
    (S.INITIALIZED, S.ARCHIVED), (S.RUNNING, S.ARCHIVED), (S.PAUSED, S.ARCHIVED),
]
DENIED = [
    (S.INITIALIZED, S.PAUSED), (S.RUNNING, S.INITIALIZED), (S.PAUSED, S.INITIALIZED),
    (S.ARCHIVED, S.RUNNING), (S.ARCHIVED, S.PAUSED), (S.ARCHIVED, S.INITIALIZED),
    (S.FAILED, S.RUNNING), (S.FAILED, S.ARCHIVED),
    (S.INITIALIZED, S.FAILED), (S.RUNNING, S.FAILED), (S.PAUSED, S.FAILED),
]


@pytest.mark.parametrize("src,dst", ALLOWED)
def test_transition_allowed(svc, uow, src, dst):
    wid = make(svc, uow, status=src)
    w = svc.change_simulation(wid, SimulationUpdate(status=dst))
    assert w.status == dst and uow.commits == 1


@pytest.mark.parametrize("src,dst", DENIED)
def test_transition_denied(svc, uow, src, dst):
    wid = make(svc, uow, status=src)
    with pytest.raises(InvalidStateError) as e:
        svc.change_simulation(wid, SimulationUpdate(status=dst))
    assert code(e) == "INVALID_STATE_TRANSITION" and uow.commits == 0


def test_same_status_is_noop(svc, uow):
    wid = make(svc, uow, status=S.RUNNING)
    assert svc.change_simulation(wid, SimulationUpdate(status=S.RUNNING)).status == S.RUNNING


@pytest.mark.parametrize("speed", [1, 4, 16])
def test_speed_ok_and_keeps_status(svc, uow, speed):
    wid = make(svc, uow, status=S.RUNNING)
    w = svc.change_simulation(wid, SimulationUpdate(speed=speed))
    assert (w.speed, w.status) == (speed, S.RUNNING)


def test_status_and_speed_together(svc, uow):
    wid = make(svc, uow)
    w = svc.change_simulation(wid, SimulationUpdate(status=S.RUNNING, speed=4))
    assert (w.status, w.speed) == (S.RUNNING, 4)


@pytest.mark.parametrize("speed", [0, 2, -1, 32])
def test_speed_invalid(svc, uow, speed):
    wid = make(svc, uow)
    with pytest.raises(DomainValidationError) as e:
        svc.change_simulation(wid, SimulationUpdate(speed=speed))
    assert code(e) == "INVALID_SPEED" and uow.commits == 0


def test_empty_simulation_update(svc, uow):
    wid = make(svc, uow)
    with pytest.raises(DomainValidationError) as e:
        svc.change_simulation(wid, SimulationUpdate())
    assert code(e) == "INVALID_SIMULATION_UPDATE"


@pytest.mark.parametrize("st", [S.ARCHIVED, S.FAILED])
def test_speed_on_terminal_world(svc, uow, st):
    wid = make(svc, uow, status=st)
    with pytest.raises(InvalidStateError):
        svc.change_simulation(wid, SimulationUpdate(speed=4))


def test_simulation_not_found(svc):
    with pytest.raises(NotFoundError):
        svc.change_simulation(uuid.uuid4(), SimulationUpdate(speed=4))


def test_simulation_conflict_propagates(svc, uow):
    wid = make(svc, uow)
    uow.worlds.stale = True
    with pytest.raises(ConflictError) as e:
        svc.change_simulation(wid, SimulationUpdate(speed=4))
    assert code(e) == "CONCURRENT_UPDATE" and uow.commits == 0


def test_policy_versioning_and_copy(svc, uow):
    wid = make(svc, uow, tick=7)
    p = svc.change_policy(wid, PolicyUpdate(income_tax_rate=2000))
    assert (p.version, p.effective_tick, p.income_tax_rate, p.welfare_amount) == (2, 8, 2000, 0)
    p = svc.change_policy(wid, PolicyUpdate(welfare_amount=300))
    assert (p.version, p.income_tax_rate, p.welfare_amount) == (3, 2000, 300)
    assert uow.commits == 2


@pytest.mark.parametrize("body", [
    PolicyUpdate(income_tax_rate=-1), PolicyUpdate(income_tax_rate=10001),
    PolicyUpdate(welfare_amount=-1), PolicyUpdate(),
])
def test_policy_invalid(svc, uow, body):
    wid = make(svc, uow)
    with pytest.raises(DomainValidationError) as e:
        svc.change_policy(wid, body)
    assert code(e) == "INVALID_POLICY" and uow.commits == 0


@pytest.mark.parametrize("rate", [0, 10000])
def test_policy_bounds_inclusive(svc, uow, rate):
    wid = make(svc, uow)
    assert svc.change_policy(wid, PolicyUpdate(income_tax_rate=rate)).income_tax_rate == rate


def test_policy_archived(svc, uow):
    wid = make(svc, uow, status=S.ARCHIVED)
    with pytest.raises(InvalidStateError):
        svc.change_policy(wid, PolicyUpdate(income_tax_rate=1))


def test_policy_not_found(svc):
    with pytest.raises(NotFoundError) as e:
        svc.change_policy(uuid.uuid4(), PolicyUpdate(income_tax_rate=1))
    assert code(e) == "WORLD_NOT_FOUND"


def advance(svc, wid, count=3, expected_tick=None, paused=True):
    w = svc._uow.worlds.items.get(wid)
    if paused and w:  # manual /ticks requires PAUSED
        svc._uow.worlds.items[wid] = w.model_copy(update={"status": S.PAUSED})
    if expected_tick is None:
        expected_tick = w.current_tick if w else 0
    return svc.advance_ticks(wid, TickAdvanceRequest(count=count, expected_tick=expected_tick))


def test_advance_happy(svc, uow, engine):
    wid = make(svc, uow, status=S.RUNNING)
    uow.policies.add(NewPolicy(wid, 2000, 5, 1, 2))
    engine.batch = make_batch(0, 3, events=7, txs=4, seq=9)
    r = advance(svc, wid)
    assert r.model_dump(exclude={"compute_ms", "persist_ms"}) == dict(
        from_tick=0, to_tick=3, event_count=7, last_event_sequence=9, transaction_count=4
    )
    assert r.compute_ms >= 0 and r.persist_ms >= 0
    assert uow.worlds.items[wid].current_tick == 3
    assert uow.commits == 1 and len(uow.simulation.advances) == 1
    state, policies, count = engine.advance_calls[0]
    assert state == {"tick": 0} and count == 3
    assert policies == [PolicyCommandInput(1500, 0, 0, 1), PolicyCommandInput(2000, 5, 1, 2)]


def test_advance_not_found(svc):
    with pytest.raises(NotFoundError) as e:
        advance(svc, uuid.uuid4())
    assert code(e) == "WORLD_NOT_FOUND"


@pytest.mark.parametrize("st", [S.INITIALIZED, S.RUNNING, S.FAILED, S.ARCHIVED])
def test_advance_requires_paused(svc, uow, engine, st):
    wid = make(svc, uow, status=st)
    with pytest.raises(InvalidStateError) as e:
        advance(svc, wid, paused=False)
    assert code(e) == "WORLD_NOT_PAUSED" and not engine.advance_calls and uow.commits == 0


def test_advance_missing_snapshot(svc, uow):
    wid = make(svc, uow)
    del uow.snapshots.items[wid]
    with pytest.raises(ConflictError) as e:
        advance(svc, wid)
    assert code(e) == "SNAPSHOT_MISMATCH"


def test_advance_snapshot_tick_mismatch(svc, uow):
    wid = make(svc, uow, tick=5)
    uow.snapshots.items[wid] = SnapshotRecord(4, 0, {})
    with pytest.raises(ConflictError) as e:
        advance(svc, wid)
    assert code(e) == "SNAPSHOT_MISMATCH" and uow.commits == 0


def test_advance_stale_version_no_commit(svc, uow, engine):
    wid = make(svc, uow)
    engine.batch = make_batch(0, 1)
    uow.worlds.stale = True
    with pytest.raises(ConflictError) as e:
        advance(svc, wid)
    assert code(e) == "CONCURRENT_UPDATE" and uow.commits == 0


def test_advance_engine_error_marks_failed(svc, uow, engine):
    wid = make(svc, uow)
    engine.error = SimulationEngineError("boom")
    with pytest.raises(ConflictError) as e:
        advance(svc, wid)
    assert code(e) == "SIMULATION_FAILED"
    assert uow.rollbacks == 1 and uow.commits == 1
    assert uow.worlds.items[wid].status == S.FAILED
    assert not uow.simulation.advances


def test_advance_persistence_error_no_commit(svc, uow, engine):
    wid = make(svc, uow)
    engine.batch = make_batch(0, 1)
    uow.simulation.error = RuntimeError("db")
    with pytest.raises(RuntimeError):
        advance(svc, wid)
    assert uow.commits == 0 and uow.worlds.items[wid].current_tick == 0


def test_policy_same_tick_overwrites(svc, uow):
    wid = make(svc, uow, tick=7)
    p1 = svc.change_policy(wid, PolicyUpdate(income_tax_rate=2000))
    p2 = svc.change_policy(wid, PolicyUpdate(welfare_amount=300))
    assert (p1.version, p2.version) == (2, 3)
    pending = [p for p in uow.policies.items if p.effective_tick == 8]
    assert len(pending) == 1
    assert (pending[0].version, pending[0].income_tax_rate, pending[0].welfare_amount) == (3, 2000, 300)


def test_advance_locks_nowait_first_and_passes_expected_tick(svc, uow, engine):
    wid = make(svc, uow, status=S.RUNNING, tick=4)
    uow.snapshots.items[wid] = SnapshotRecord(4, 0, {"tick": 4})
    engine.batch = make_batch(4, 6)
    assert advance(svc, wid, 2, expected_tick=4).to_tick == 6
    assert uow.worlds.lock_calls == [(True, None)]


def test_advance_busy_no_engine_no_commit(svc, uow, engine):
    wid = make(svc, uow, status=S.RUNNING)
    uow.worlds.busy = True
    with pytest.raises(ConflictError) as e:
        advance(svc, wid)
    assert code(e) == "WORLD_BUSY" and not engine.advance_calls and uow.commits == 0


def test_advance_tick_mismatch_details(svc, uow, engine):
    wid = make(svc, uow, status=S.RUNNING, tick=5)
    with pytest.raises(ConflictError) as e:
        advance(svc, wid, expected_tick=3)
    assert code(e) == "TICK_MISMATCH" and e.value.details == {"current_tick": 5}
    assert not engine.advance_calls and uow.commits == 0


def test_advance_engine_failure_relocks_wait_mode(svc, uow, engine):
    wid = make(svc, uow, status=S.RUNNING)
    engine.error = SimulationEngineError("boom")
    with pytest.raises(ConflictError):
        advance(svc, wid)
    assert uow.worlds.lock_calls == [(True, None), (False, 5000)]
    assert uow.worlds.items[wid].status == S.FAILED


def test_change_policy_locks_wait_mode(svc, uow):
    wid = make(svc, uow)
    svc.change_policy(wid, PolicyUpdate(income_tax_rate=1))
    assert uow.worlds.lock_calls == [(False, 5000)]


def test_change_simulation_locks_wait_mode(svc, uow):
    wid = make(svc, uow)
    svc.change_simulation(wid, SimulationUpdate(speed=4))
    assert uow.worlds.lock_calls == [(False, 5000)]


def test_change_policy_and_simulation_busy(svc, uow):
    wid = make(svc, uow)
    uow.worlds.busy = True
    with pytest.raises(ConflictError) as e:
        svc.change_policy(wid, PolicyUpdate(income_tax_rate=1))
    assert code(e) == "WORLD_BUSY"
    with pytest.raises(ConflictError) as e:
        svc.change_simulation(wid, SimulationUpdate(speed=4))
    assert code(e) == "WORLD_BUSY" and uow.commits == 0


def test_schema_requires_expected_tick():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TickAdvanceRequest(count=1)
    with pytest.raises(ValidationError):
        TickAdvanceRequest(count=1, expected_tick=-1)


def test_advance_running_uses_speed(svc, uow, engine):
    wid = make(svc, uow, status=S.RUNNING, speed=4)
    engine.batch = make_batch(0, 4)
    r = svc.advance_running(wid, 0)
    assert engine.advance_calls[0][2] == 4
    assert (r.from_tick, r.to_tick) == (0, 4)
    assert r.compute_ms >= 0 and r.persist_ms >= 0
    assert uow.commits == 1 and uow.worlds.lock_calls[0][0] is True


@pytest.mark.parametrize("st", [S.INITIALIZED, S.PAUSED, S.FAILED, S.ARCHIVED])
def test_advance_running_not_running(svc, uow, engine, st):
    wid = make(svc, uow, status=st)
    with pytest.raises(InvalidStateError) as e:
        svc.advance_running(wid, 0)
    assert code(e) == "WORLD_NOT_RUNNING" and not engine.advance_calls


def test_advance_running_tick_mismatch(svc, uow):
    wid = make(svc, uow, status=S.RUNNING, tick=2)
    with pytest.raises(ConflictError) as e:
        svc.advance_running(wid, 0)
    assert code(e) == "TICK_MISMATCH" and e.value.details == {"current_tick": 2}


def test_list_running_world_ids(svc, uow):
    a = make(svc, uow, status=S.RUNNING)
    make(svc, uow, status=S.PAUSED)
    assert svc.list_running_world_ids() == [a]


def test_state_runner_status(uow, engine):
    from app.runner.interfaces import RunnerStatusProvider
    from app.schemas.world import RunnerStatusRead

    status = RunnerStatusRead(state="running", consecutive_failures=0)

    class Provider(RunnerStatusProvider):
        def get(self, world_id):
            return status

    wid = make(WorldService(uow, engine, "9.9.9"), uow)
    assert WorldService(uow, engine, "9.9.9").get_world_state(wid).runner is None
    assert WorldService(uow, engine, "9.9.9", runner_status=Provider()).get_world_state(wid).runner == status


@pytest.mark.parametrize("count", [0, 721])
def test_advance_count_out_of_range_422(count):
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).post(
        f"/api/v1/worlds/{uuid.uuid4()}/ticks", json={"count": count, "expected_tick": 0}
    )
    assert r.status_code == 422
