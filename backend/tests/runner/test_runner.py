import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from app.core.exceptions import ConflictError, DomainError, InvalidStateError, NotFoundError
from app.runner.interfaces import OwnershipHandle, OwnershipLock
from app.runner.manager import RunnerManager
from app.runner.world_runner import WorldRunner


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)


class FakeUseCase:
    """script: list of results/exceptions consumed per advance_running call; then stop via NotFoundError."""

    def __init__(self, script, tick=0, clock=None, cost=0.0):
        self.script = list(script)
        self.tick = tick
        self.calls: list[int] = []
        self.clock = clock
        self.cost = cost
        self.world_ids: list = []

    def get_world(self, world_id):
        return SimpleNamespace(current_tick=self.tick)

    def advance_running(self, world_id, expected_tick):
        self.calls.append(expected_tick)
        if self.clock:
            self.clock.now += self.cost
        item = self.script.pop(0) if self.script else NotFoundError("WORLD_NOT_FOUND")
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(
            from_tick=expected_tick, to_tick=expected_tick + 1, compute_ms=1.0, persist_ms=2.0
        )

    def list_running_world_ids(self):
        return self.world_ids


def scope_for(uc):
    @contextmanager
    def scope():
        yield uc

    return scope


def run_runner(script, tick=0, interval_ms=1000, cost=0.0, backoff_max_ms=30000):
    clock = FakeClock()
    uc = FakeUseCase(script, tick, clock, cost)
    runner = WorldRunner(uuid4(), scope_for(uc), interval_ms, backoff_max_ms, clock, clock.sleep)
    asyncio.run(runner.run())
    return runner, uc, clock


def test_expected_tick_progresses_and_status_recorded():
    runner, uc, clock = run_runner([None, None], tick=5)
    assert uc.calls == [5, 6, 7]
    assert clock.sleeps == [1.0, 1.0]
    s = runner.status
    assert (s.state, s.last_tick, s.last_compute_ms, s.last_persist_ms) == ("stopped", 7, 1.0, 2.0)


def test_no_catch_up_when_cycle_is_slow():
    _, uc, clock = run_runner([None, None], interval_ms=1000, cost=2.5)
    assert uc.calls == [0, 1, 2]
    assert clock.sleeps == []  # always late: start immediately, never burst to catch up


def test_tick_mismatch_resyncs_without_failure():
    err = ConflictError("TICK_MISMATCH", details={"current_tick": 40})
    runner, uc, clock = run_runner([err, None], tick=0)
    assert uc.calls == [0, 40, 41]
    assert runner.status.consecutive_failures == 0


def test_stop_codes():
    for exc in [
        InvalidStateError("WORLD_NOT_RUNNING"),
        InvalidStateError("WORLD_NOT_RUNNABLE"),
        NotFoundError("WORLD_NOT_FOUND"),
    ]:
        runner, uc, _ = run_runner([exc, None])
        assert len(uc.calls) == 1 and runner.status.state == "stopped"
        assert runner.status.last_error is None


def test_fatal_codes_stop_with_last_error():
    for code in ["SNAPSHOT_MISMATCH", "SIMULATION_FAILED"]:
        runner, uc, _ = run_runner([ConflictError(code), None])
        assert len(uc.calls) == 1
        assert runner.status.state == "stopped" and runner.status.last_error == code


def test_transient_backoff_doubles_caps_and_recovers():
    errs = [ConflictError("WORLD_BUSY")] + [RuntimeError("db down")] * 5
    runner, uc, clock = run_runner(errs + [None], backoff_max_ms=8000)
    assert clock.sleeps[:6] == [1.0, 2.0, 4.0, 8.0, 8.0, 8.0]
    assert runner.status.consecutive_failures == 0  # recovered by the success
    assert uc.calls == [0] * 7 + [1]  # same tick retried, then progresses


def test_transient_status_while_retrying():
    clock = FakeClock()
    uc = FakeUseCase([DomainError("CONCURRENT_UPDATE")], clock=clock)

    async def block(_):
        await asyncio.Event().wait()

    runner = WorldRunner(uuid4(), scope_for(uc), 1000, 30000, clock, block)

    async def go():
        task = asyncio.create_task(runner.run())
        await asyncio.sleep(0.1)  # let the worker thread run the failing call
        seen = runner.status
        runner.stop()
        await task
        return seen

    seen = asyncio.run(go())
    assert seen.state == "retrying" and seen.consecutive_failures == 1
    assert seen.last_error == "CONCURRENT_UPDATE"


class FakeHandle(OwnershipHandle):
    def __init__(self):
        self.released = False

    def release(self):
        self.released = True


class FakeOwnership(OwnershipLock):
    def __init__(self, shared_held=None):
        self.held = shared_held if shared_held is not None else set()
        self.handles: dict = {}
        self.acquires = 0

    def try_acquire(self, world_id):
        self.acquires += 1
        if world_id in self.held:
            return None
        self.held.add(world_id)
        h = FakeHandle()
        orig = h.release

        def release():
            self.held.discard(world_id)
            orig()

        h.release = release
        self.handles[world_id] = h
        return h


def make_manager(uc, ownership, clock):
    return RunnerManager(scope_for(uc), ownership, 1000, 1000, 30000, 1000, clock, clock.sleep)


async def spin(n=20):
    for _ in range(n):
        await asyncio.sleep(0)


def test_manager_acquires_once_and_reports_status():
    clock = FakeClock()
    wid = uuid4()
    uc = FakeUseCase([None] * 1000, clock=clock)
    uc.world_ids = [wid]
    own = FakeOwnership()
    m = make_manager(uc, own, clock)

    async def go():
        m.start()
        await spin(200)
        st = m.get(wid)
        await m.stop()
        return st

    st = asyncio.run(go())
    assert own.acquires == 1
    assert st.state == "running" and st.last_tick and st.last_tick > 0
    assert own.handles[wid].released
    assert m.get(wid).state == "stopped"
    assert m.get(uuid4()) is None


def test_second_manager_does_not_run_when_owned_elsewhere():
    clock = FakeClock()
    wid = uuid4()
    uc = FakeUseCase([None] * 100, clock=clock)
    uc.world_ids = [wid]
    own = FakeOwnership(shared_held={wid})
    m = make_manager(uc, own, clock)

    async def go():
        m.start()
        await spin(100)
        await m.stop()

    asyncio.run(go())
    assert own.acquires > 1 and uc.calls == [] and m.get(wid) is None


def test_runner_end_releases_handle_and_world_is_rediscovered():
    clock = FakeClock()
    wid = uuid4()
    uc = FakeUseCase([InvalidStateError("WORLD_NOT_RUNNING"), None, None], clock=clock)
    uc.world_ids = [wid]
    own = FakeOwnership()
    m = make_manager(uc, own, clock)

    async def go():
        m.start()
        await spin(200)
        await m.stop()

    asyncio.run(go())
    assert own.acquires >= 2  # released after stop, then reacquired on next discovery
