from collections.abc import Generator
from contextlib import contextmanager

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.interfaces import UnitOfWork
from app.repositories.sqlalchemy import PgAdvisoryOwnershipLock, SqlAlchemyUnitOfWork
from app.runner.manager import RunnerManager
from app.services.city_query_service import CityQueryService
from app.services.world_service import WorldService
from app.simulation.engine_adapter import SimulationEngineAdapter
from app.simulation.interfaces import SimulationEnginePort
from app.usecases.city import CityQueryUseCase
from app.usecases.world import WorldUseCase


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


def get_uow(db: Session = Depends(get_db)) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(db, snapshot_keep_latest=settings.SNAPSHOT_KEEP_LATEST)


_engine: SimulationEnginePort | None = None


def get_simulation_engine() -> SimulationEnginePort:
    global _engine
    if _engine is None:
        _engine = SimulationEngineAdapter()
    return _engine


def get_world_use_case(
    uow: UnitOfWork = Depends(get_uow),
    engine: SimulationEnginePort = Depends(get_simulation_engine),
) -> WorldUseCase:
    return WorldService(
        uow,
        engine,
        settings.ENGINE_VERSION,
        settings.WORLD_LOCK_TIMEOUT_MS,
        runner_status=_runner_manager,
    )


@contextmanager
def world_use_case_scope() -> Generator[WorldUseCase, None, None]:
    """Fresh session + use case per runner cycle (no request context)."""
    with SessionLocal() as db:
        yield WorldService(
            SqlAlchemyUnitOfWork(db, snapshot_keep_latest=settings.SNAPSHOT_KEEP_LATEST),
            get_simulation_engine(),
            settings.ENGINE_VERSION,
            settings.WORLD_LOCK_TIMEOUT_MS,
        )


_runner_manager: RunnerManager | None = None


def build_runner_manager() -> RunnerManager:
    global _runner_manager
    if _runner_manager is None:
        _runner_manager = RunnerManager(
            world_use_case_scope,
            PgAdvisoryOwnershipLock(
                # dedicated unpooled engine: each owned world holds one connection for good
                create_engine(settings.DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)
            ),
            settings.RUNNER_TICK_INTERVAL_MS,
            settings.RUNNER_DISCOVERY_INTERVAL_MS,
            settings.RUNNER_BACKOFF_MAX_MS,
            settings.RUNNER_SHUTDOWN_TIMEOUT_MS,
        )
    return _runner_manager


def get_city_query_use_case(uow: UnitOfWork = Depends(get_uow)) -> CityQueryUseCase:
    return CityQueryService(uow)
