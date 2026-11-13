import uuid

import pytest

from app.core.exceptions import ConflictError, DomainValidationError, InvalidStateError, NotFoundError
from app.repositories.interfaces import NewPolicy
from app.schemas.enums import WorldStatus as S
from app.schemas.world import PolicyUpdate, SimulationUpdate, WorldCreate
from app.services import WorldService
from tests.services.fakes import FakeUnitOfWork


@pytest.fixture
def uow():
    return FakeUnitOfWork()


@pytest.fixture
def svc(uow):
    return WorldService(uow, "9.9.9")


def make(svc, uow, status=S.INITIALIZED, tick=0, speed=1):
    w = svc.create_world(WorldCreate(name="w"))
    uow.worlds.items[w.id] = w.model_copy(
        update={"status": status, "current_tick": tick, "speed": speed}
    )
    uow.commits = 0
    return w.id


def code(exc):
    return exc.value.code


def test_create_defaults(svc, uow):
    w = svc.create_world(WorldCreate(name="a"))
    assert (w.status, w.current_tick, w.speed) == (S.INITIALIZED, 0, 1)
    assert w.engine_version == "9.9.9"
    assert 0 <= w.seed < 2**63
    p = uow.policies.latest(w.id)
    assert (p.income_tax_rate, p.welfare_amount, p.effective_tick, p.version) == (1500, 0, 0, 1)
    assert uow.commits == 1


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
