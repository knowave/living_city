from abc import ABC, abstractmethod
from uuid import UUID

from app.schemas.city import (
    ChunkRangeQuery,
    ChunkRead,
    CitizenRead,
    CompanyRead,
    MetricQuery,
    MetricRead,
)


class CityQueryUseCase(ABC):
    @abstractmethod
    def get_chunks(self, world_id: UUID, query: ChunkRangeQuery) -> list[ChunkRead]:
        """Raises NotFoundError WORLD_NOT_FOUND, DomainValidationError INVALID_CHUNK_RANGE
        (min > max or negative)."""

    @abstractmethod
    def get_citizen(self, world_id: UUID, citizen_id: UUID) -> CitizenRead:
        """With cash_balance. Raises NotFoundError CITIZEN_NOT_FOUND (also if in other world)."""

    @abstractmethod
    def get_company(self, world_id: UUID, company_id: UUID) -> CompanyRead:
        """With cash_balance. Raises NotFoundError COMPANY_NOT_FOUND."""

    @abstractmethod
    def get_metrics(self, world_id: UUID, query: MetricQuery) -> list[MetricRead]:
        """Raises NotFoundError WORLD_NOT_FOUND, DomainValidationError INVALID_TICK_RANGE
        (from_tick > to_tick)."""
