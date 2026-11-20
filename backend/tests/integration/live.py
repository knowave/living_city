"""Helpers: Runner (x16, 20ms) in a background thread + a TestClient whose DB sessions are closed per request."""

import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from tests.integration.test_runner_integration import manager_ctx, new_world, tick, wait_until


@pytest.fixture
def live_client(pg_engine):
    from sqlalchemy.orm import sessionmaker

    maker = sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False)

    def _db():
        s = maker()
        try:
            yield s
        finally:
            s.rollback()
            s.close()

    app.dependency_overrides[get_db] = _db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def running_world(pg_engine):
    """World running at x16 under a RunnerManager living in a background thread."""
    wid = new_world(pg_engine, running=True, speed=16, seed=5)
    stop = threading.Event()
    ready = threading.Event()

    async def body():
        async with manager_ctx(pg_engine, interval_ms=20):
            assert await wait_until(lambda: tick(pg_engine, wid) >= 16)
            ready.set()
            while not stop.is_set():
                await asyncio.sleep(0.02)

    th = threading.Thread(target=lambda: asyncio.run(body()), daemon=True)
    th.start()
    assert ready.wait(20)
    yield wid
    stop.set()
    th.join(20)
