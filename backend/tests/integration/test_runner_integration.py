"""RunnerManager against a real PostgreSQL (AC2-AC9, AC11).

Managers run inside asyncio.run() (no pytest-asyncio). Each manager gets its own
ownership engine (NullPool), so two managers behave like two processes.

Soak: `@pytest.mark.soak` tests are skipped by default via pyproject `addopts = -m "not soak"`;
run them with `uv run pytest -q -m soak -s`.
"""

import asyncio
import resource
import sys
import uuid
import time
from contextlib import asynccontextmanager, contextmanager

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from simulation_engine.world.snapshot import WorldSnapshot as EngineSnapshot  # noqa: F401
from simulation_engine.world.state import WorldState

from app.core.config import settings
from app.models import LedgerEntry, World, WorldEvent, WorldSnapshot
from app.repositories.sqlalchemy import PgAdvisoryOwnershipLock, SqlAlchemyUnitOfWork
from app.runner.manager import RunnerManager
from app.schemas.world import SimulationUpdate, TickAdvanceRequest, WorldCreate
from app.services.world_service import WorldService
from app.simulation.engine_adapter import SimulationEngineAdapter

pytestmark = pytest.mark.integration

RUNNING = SimulationUpdate(status="RUNNING", speed=16)


# ---------- helpers ----------
def service(pg_engine, runner_status=None, keep_latest=3):
    return WorldService(
        SqlAlchemyUnitOfWork(Session(pg_engine, expire_on_commit=False), snapshot_keep_latest=keep_latest),
        SimulationEngineAdapter(),
        settings.ENGINE_VERSION,
        runner_status=runner_status,
    )


def new_world(pg_engine, *, running=True, speed=16, seed=7):
    svc = service(pg_engine)
    w = svc.create_world(WorldCreate(name="r", seed=seed))
    if running:
        svc.change_simulation(w.id, SimulationUpdate(status="RUNNING", speed=speed))
    return w.id


def set_status(pg_engine, wid, status):
    service(pg_engine).change_simulation(wid, SimulationUpdate(status=status))


def tick(pg_engine, wid):
    with Session(pg_engine) as s:
        return s.get(World, wid).current_tick


def status(pg_engine, wid):
    with Session(pg_engine) as s:
        return s.get(World, wid).status


def scalar(pg_engine, stmt):
    with Session(pg_engine) as s:
        return s.scalar(stmt)


def snapshot_ticks(pg_engine, wid):
    with Session(pg_engine) as s:
        return sorted(s.scalars(select(WorldSnapshot.tick).where(WorldSnapshot.world_id == wid)))


def assert_invariants(pg_engine, wid):
    with Session(pg_engine) as s:
        n, mx = s.execute(
            select(func.count(), func.max(WorldEvent.sequence)).where(WorldEvent.world_id == wid)
        ).one()
        ledger = s.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.world_id == wid))
    assert n == (mx or 0), f"event sequences not contiguous: count={n} max={mx}"
    assert ledger == 0


@asynccontextmanager
async def manager_ctx(pg_engine, *, keep_latest=3, interval_ms=20, discovery_ms=20, backoff_max_ms=200):
    url = pg_engine.url.render_as_string(hide_password=False)
    own = create_engine(url, poolclass=NullPool)
    holder: dict = {}

    @contextmanager
    def scope():
        with Session(pg_engine, expire_on_commit=False) as db:
            yield WorldService(
                SqlAlchemyUnitOfWork(db, snapshot_keep_latest=keep_latest),
                SimulationEngineAdapter(),
                settings.ENGINE_VERSION,
                runner_status=holder.get("m"),
            )

    m = RunnerManager(scope, PgAdvisoryOwnershipLock(own), interval_ms, discovery_ms, backoff_max_ms, 5000)
    holder["m"] = m
    m.start()
    try:
        yield m
    finally:
        await m.stop()
        own.dispose()


async def wait_until(cond, timeout=10.0, step=0.01):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        await asyncio.sleep(step)
    return False


def owner_state(m, wid):
    s = m.get(wid)
    return s.state if s else None


# ---------- AC2 lifecycle ----------
def test_running_world_starts_advancing_and_follows_pause_resume_archive(pg_engine):
    wid = new_world(pg_engine, running=False)

    async def body():
        async with manager_ctx(pg_engine) as m:
            await asyncio.sleep(0.3)
            assert tick(pg_engine, wid) == 0  # INITIALIZED never advances
            set_status(pg_engine, wid, "RUNNING")
            assert await wait_until(lambda: tick(pg_engine, wid) > 0)

            set_status(pg_engine, wid, "PAUSED")
            await asyncio.sleep(0.2)
            t1 = tick(pg_engine, wid)
            await asyncio.sleep(0.3)
            assert tick(pg_engine, wid) == t1

            set_status(pg_engine, wid, "RUNNING")
            assert await wait_until(lambda: tick(pg_engine, wid) > t1)

            set_status(pg_engine, wid, "ARCHIVED")
            await asyncio.sleep(0.2)
            t2 = tick(pg_engine, wid)
            await asyncio.sleep(0.4)
            assert tick(pg_engine, wid) == t2
            assert m.get(wid).state == "stopped"

    asyncio.run(body())


def test_failed_world_is_never_advanced(pg_engine):
    wid = new_world(pg_engine)
    with Session(pg_engine) as s:
        s.execute(text("UPDATE worlds SET status='FAILED' WHERE id=:i"), {"i": wid})
        s.commit()

    async def body():
        async with manager_ctx(pg_engine) as m:
            await asyncio.sleep(0.4)
            assert m.get(wid) is None

    asyncio.run(body())
    assert tick(pg_engine, wid) == 0


# ---------- AC3 cadence ----------
def test_ticks_advance_in_speed_multiples_with_one_snapshot_per_commit(pg_engine):
    wid = new_world(pg_engine, speed=16)

    async def body():
        async with manager_ctx(pg_engine, keep_latest=10_000):
            assert await wait_until(lambda: tick(pg_engine, wid) >= 16 * 8)

    asyncio.run(body())
    t = tick(pg_engine, wid)
    assert t % 16 == 0
    assert snapshot_ticks(pg_engine, wid) == list(range(0, t + 1, 16))


# ---------- AC4 ownership ----------
def test_two_managers_run_a_world_at_single_manager_rate_and_takeover_works(pg_engine):
    base_wid = new_world(pg_engine, seed=1)
    wid = new_world(pg_engine, seed=2)
    window = 1.5

    async def body():
        async with manager_ctx(pg_engine) as solo:
            await wait_until(lambda: owner_state(solo, base_wid) == "running")
            t0 = tick(pg_engine, base_wid)
            await asyncio.sleep(window)
            baseline = tick(pg_engine, base_wid) - t0
        set_status(pg_engine, base_wid, "PAUSED")
        # keep only `wid` running for the duo phase
        async with manager_ctx(pg_engine) as a, manager_ctx(pg_engine) as b:
            assert await wait_until(lambda: owner_state(a, wid) or owner_state(b, wid))
            await asyncio.sleep(0.1)
            owners = [m for m in (a, b) if m.get(wid) is not None]
            assert len(owners) == 1
            t0 = tick(pg_engine, wid)
            await asyncio.sleep(window)
            duo = tick(pg_engine, wid) - t0
            assert duo <= baseline * 1.5 + 16, (duo, baseline)

            owner, other = (a, b) if owners[0] is a else (b, a)
            await owner.stop()
            t1 = tick(pg_engine, wid)
            assert await wait_until(lambda: tick(pg_engine, wid) > t1 + 16)
            assert owner_state(other, wid) == "running"

    asyncio.run(body())
    assert_invariants(pg_engine, wid)


# ---------- AC5 failure classification ----------
def test_transient_db_lock_keeps_world_running_then_recovers(pg_engine):
    wid = new_world(pg_engine)

    async def body():
        async with manager_ctx(pg_engine) as m:
            assert await wait_until(lambda: tick(pg_engine, wid) >= 32)
            holder = Session(pg_engine)
            holder.execute(select(World).where(World.id == wid).with_for_update())
            seen_retrying = False
            end = time.monotonic() + 0.4
            while time.monotonic() < end:
                st = m.get(wid)
                if st.state == "retrying" and st.consecutive_failures > 0:
                    seen_retrying = True
                await asyncio.sleep(0.01)
            holder.rollback()
            holder.close()
            assert seen_retrying
            t = tick(pg_engine, wid)
            assert await wait_until(lambda: tick(pg_engine, wid) > t and m.get(wid).state == "running")
            assert status(pg_engine, wid) == "RUNNING"

    asyncio.run(body())
    assert_invariants(pg_engine, wid)


def test_engine_failure_marks_world_failed_and_stops_runner(pg_engine):
    wid = new_world(pg_engine)
    with Session(pg_engine) as s:
        snap = s.scalars(select(WorldSnapshot).where(WorldSnapshot.world_id == wid)).one()
        snap.state_data = {**snap.state_data, "format_version": 999}
        s.commit()

    async def body():
        async with manager_ctx(pg_engine) as m:
            assert await wait_until(lambda: status(pg_engine, wid) == "FAILED")
            assert await wait_until(lambda: owner_state(m, wid) == "stopped")
            assert m.get(wid).last_error == "SIMULATION_FAILED"

    asyncio.run(body())


# ---------- AC6 restart ----------
def test_new_manager_continues_from_last_commit_without_duplicates_or_catch_up(pg_engine):
    wid = new_world(pg_engine)

    async def body():
        async with manager_ctx(pg_engine) as a:
            assert await wait_until(lambda: tick(pg_engine, wid) >= 64)
        t_stop = tick(pg_engine, wid)
        await asyncio.sleep(0.5)  # downtime: must not be caught up
        assert tick(pg_engine, wid) == t_stop
        async with manager_ctx(pg_engine) as b:
            start = time.monotonic()
            assert await wait_until(lambda: tick(pg_engine, wid) > t_stop + 32)
            await asyncio.sleep(0.2)
            elapsed = time.monotonic() - start
        return t_stop, elapsed

    t_stop, elapsed = asyncio.run(body())
    grown = tick(pg_engine, wid) - t_stop
    assert grown % 16 == 0
    assert grown <= 16 * (elapsed / 0.02 + 2)
    assert_invariants(pg_engine, wid)


# ---------- AC7 retention ----------
def test_retention_keeps_month_ends_and_newest_three_and_latest_restores(pg_engine):
    wid = new_world(pg_engine)

    async def body():
        async with manager_ctx(pg_engine):
            assert await wait_until(lambda: tick(pg_engine, wid) > 720 + 64, timeout=60)

    asyncio.run(body())
    ticks = snapshot_ticks(pg_engine, wid)
    assert set(ticks) == {0, 720} | set(ticks[-3:])
    with Session(pg_engine) as s:
        snap = s.scalars(
            select(WorldSnapshot).where(WorldSnapshot.world_id == wid).order_by(WorldSnapshot.tick.desc())
        ).first()
        state = WorldState.from_snapshot(
            EngineSnapshot(
                id=uuid.UUID(int=0), tick=snap.tick, last_event_sequence=snap.last_event_sequence,
                engine_version=snap.engine_version, state_data=snap.state_data,
            )
        )
        assert state.to_snapshot().state_data == snap.state_data


# ---------- AC8 runner field ----------
def test_state_shows_runner_only_for_the_owning_manager(pg_engine):
    wid = new_world(pg_engine)

    async def body():
        async with manager_ctx(pg_engine) as a, manager_ctx(pg_engine) as b:
            assert await wait_until(lambda: a.get(wid) or b.get(wid))
            await asyncio.sleep(0.1)
            owner, other = (a, b) if a.get(wid) else (b, a)
            owned = service(pg_engine, owner).get_world_state(wid)
            assert owned.runner is not None and owned.runner.state in ("running", "retrying")
            assert service(pg_engine, other).get_world_state(wid).runner is None

    asyncio.run(body())


# ---------- AC9 measurement ----------
def test_advance_720_ticks_reports_compute_and_persist_ms(pg_engine):
    wid = new_world(pg_engine, running=False)
    set_status(pg_engine, wid, "RUNNING")
    set_status(pg_engine, wid, "PAUSED")
    r = service(pg_engine).advance_ticks(wid, TickAdvanceRequest(count=720, expected_tick=0))
    print(f"\nAC9 720 ticks: compute_ms={r.compute_ms:.1f} persist_ms={r.persist_ms:.1f}")
    assert r.compute_ms > 0 and r.persist_ms > 0


# ---------- AC11 soak ----------
@pytest.mark.soak
def test_soak_one_year_of_ticks_keeps_invariants(pg_engine):
    wid = new_world(pg_engine)
    started = time.monotonic()

    async def body():
        async with manager_ctx(pg_engine, interval_ms=0, discovery_ms=20):
            assert await wait_until(lambda: tick(pg_engine, wid) >= 8640, timeout=900, step=0.1)

    asyncio.run(body())
    elapsed = time.monotonic() - started
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1 if sys.platform == "darwin" else 1024) / 1e6
    snaps = snapshot_ticks(pg_engine, wid)
    print(f"\nSOAK ticks={tick(pg_engine, wid)} elapsed={elapsed:.1f}s snapshots={len(snaps)} peak_rss={rss:.0f}MB")
    assert status(pg_engine, wid) == "RUNNING"
    assert len(snaps) <= 3 + 13
    assert_invariants(pg_engine, wid)
