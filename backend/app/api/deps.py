from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.interfaces import UnitOfWork
from app.repositories.sqlalchemy import SqlAlchemyUnitOfWork
from app.services.city_query_service import CityQueryService
from app.services.world_service import WorldService
from app.usecases.city import CityQueryUseCase
from app.usecases.world import WorldUseCase


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


def get_uow(db: Session = Depends(get_db)) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(db)


def get_world_use_case(uow: UnitOfWork = Depends(get_uow)) -> WorldUseCase:
    return WorldService(uow, settings.ENGINE_VERSION)


def get_city_query_use_case(uow: UnitOfWork = Depends(get_uow)) -> CityQueryUseCase:
    return CityQueryService(uow)
