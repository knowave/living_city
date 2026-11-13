from uuid import UUID

from app.core.exceptions import DomainValidationError, NotFoundError
from app.repositories.interfaces import UnitOfWork
from app.schemas.city import (
    ChunkRangeQuery,
    ChunkRead,
    CitizenRead,
    CompanyRead,
    MetricQuery,
    MetricRead,
)
from app.schemas.enums import AccountOwnerType
from app.usecases.city import CityQueryUseCase


class CityQueryService(CityQueryUseCase):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def _require_world(self, world_id: UUID) -> None:
        if self._uow.worlds.get(world_id) is None:
            raise NotFoundError("WORLD_NOT_FOUND", "World not found")

    def get_chunks(self, world_id: UUID, query: ChunkRangeQuery) -> list[ChunkRead]:
        self._require_world(world_id)

        for lo, hi in ((query.x_min, query.x_max), (query.y_min, query.y_max)):
            if lo is not None and hi is not None and lo > hi:
                raise DomainValidationError("INVALID_CHUNK_RANGE", "min must be <= max")

        return self._uow.chunks.list(world_id, query)

    def get_citizen(self, world_id: UUID, citizen_id: UUID) -> CitizenRead:
        self._require_world(world_id)

        citizen = self._uow.citizens.get(world_id, citizen_id)
        
        if citizen is None:
            raise NotFoundError("CITIZEN_NOT_FOUND", "Citizen not found")
        
        balance = self._uow.accounts.cash_balance(world_id, AccountOwnerType.CITIZEN, citizen_id)
        
        return citizen.model_copy(update={"cash_balance": balance})

    def get_company(self, world_id: UUID, company_id: UUID) -> CompanyRead:
        self._require_world(world_id)
        
        company = self._uow.companies.get(world_id, company_id)
        
        if company is None:
            raise NotFoundError("COMPANY_NOT_FOUND", "Company not found")
        
        balance = self._uow.accounts.cash_balance(world_id, AccountOwnerType.COMPANY, company_id)
        
        return company.model_copy(update={"cash_balance": balance})

    def get_metrics(self, world_id: UUID, query: MetricQuery) -> list[MetricRead]:
        self._require_world(world_id)
        
        if (
            query.from_tick is not None
            and query.to_tick is not None
            and query.from_tick > query.to_tick
        ):
            raise DomainValidationError("INVALID_TICK_RANGE", "from_tick must be <= to_tick")
        
        return self._uow.metrics.list(world_id, query)
