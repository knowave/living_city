import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (register tables)
from app.api.deps import get_db
from app.core.config import settings
from app.db.base import Base
from app.main import app
from app.repositories.sqlalchemy import SqlAlchemyUnitOfWork
from app.services.world_service import WorldService
from app.simulation.engine_adapter import SimulationEngineAdapter


@pytest.fixture(scope="session")
def pg_engine():
    url = make_url(settings.DATABASE_URL)
    name = f"lc_it_{os.getpid()}"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError as e:
        admin.dispose()
        pytest.skip(f"PostgreSQL unreachable: {e.__cause__ or e}")
    eng = create_engine(url.set(database=name))
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()
        with admin.connect() as c:
            c.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :n"),
                {"n": name},
            )
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()


@pytest.fixture
def session_factory(pg_engine):
    sessions = []
    maker = sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False)

    def make():
        s = maker()
        sessions.append(s)
        return s

    yield make
    for s in sessions:
        s.rollback()
        s.close()


@pytest.fixture
def make_service(session_factory):
    """Returns a factory: each call -> WorldService on a fresh session."""

    def make():
        return WorldService(
            SqlAlchemyUnitOfWork(session_factory()),
            SimulationEngineAdapter(),
            settings.ENGINE_VERSION,
        )

    return make


@pytest.fixture
def client(session_factory):
    def _db():
        s = session_factory()
        yield s

    app.dependency_overrides[get_db] = _db
    yield TestClient(app)  # no `with`: skip lifespan (it would create_all on the real DB)
    app.dependency_overrides.clear()


def pause_world(svc_or_make, world_id):
    """INITIALIZED -> RUNNING -> PAUSED: manual /ticks needs PAUSED (runner is off in tests)."""
    from app.schemas.world import SimulationUpdate

    for st in ("RUNNING", "PAUSED"):
        (svc_or_make() if callable(svc_or_make) else svc_or_make).change_simulation(
            world_id, SimulationUpdate(status=st)
        )


def http_pause(client, wid):
    for st in ("RUNNING", "PAUSED"):
        r = client.patch(f"/api/v1/worlds/{wid}/simulation", json={"status": st})
        assert r.status_code == 200, r.text
    return wid
