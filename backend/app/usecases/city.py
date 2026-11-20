from abc import ABC, abstractmethod
from uuid import UUID

from app.schemas.city import (
    BuildingDetailRead,
    BuildingRangeQuery,
    BuildingRead,
    ChunkRangeQuery,
    ChunkRead,
    CitizenDetailRead,
    CitizenQuery,
    CitizenRead,
    CitySummaryRead,
    CompanyDetailRead,
    CompanyRead,
    MapMetaRead,
    MetricQuery,
    MetricRead,
    Page,
    WorldViewRead,
)


class CityQueryUseCase(ABC):
    """List/detail/summary/view reads run in one REPEATABLE READ transaction, so as_of_tick,
    event_cursor and data come from the same committed state. All raise NotFoundError
    WORLD_NOT_FOUND for a missing world."""

    @abstractmethod
    def get_map(self, world_id: UUID) -> MapMetaRead: ...

    @abstractmethod
    def get_chunks(self, world_id: UUID, query: ChunkRangeQuery) -> list[ChunkRead]:
        """Raises DomainValidationError INVALID_CHUNK_RANGE (min > max or negative)."""

    @abstractmethod
    def get_buildings(self, world_id: UUID, query: BuildingRangeQuery) -> list[BuildingRead]:
        """Buildings overlapping the tile range. Raises DomainValidationError INVALID_TILE_RANGE."""

    @abstractmethod
    def get_building(self, world_id: UUID, building_id: UUID) -> BuildingDetailRead:
        """Raises NotFoundError BUILDING_NOT_FOUND."""

    @abstractmethod
    def list_citizens(
        self, world_id: UUID, query: CitizenQuery, limit: int, offset: int
    ) -> Page[CitizenRead]: ...

    @abstractmethod
    def get_citizen(self, world_id: UUID, citizen_id: UUID) -> CitizenDetailRead:
        """Raises NotFoundError CITIZEN_NOT_FOUND (also if in other world)."""

    @abstractmethod
    def list_companies(
        self, world_id: UUID, status: str | None, industry: str | None, limit: int, offset: int
    ) -> Page[CompanyRead]: ...

    @abstractmethod
    def get_company(self, world_id: UUID, company_id: UUID) -> CompanyDetailRead:
        """Raises NotFoundError COMPANY_NOT_FOUND."""

    @abstractmethod
    def list_company_employees(
        self, world_id: UUID, company_id: UUID, limit: int, offset: int
    ) -> Page[CitizenRead]:
        """Raises NotFoundError COMPANY_NOT_FOUND."""

    @abstractmethod
    def get_summary(self, world_id: UUID) -> CitySummaryRead: ...

    @abstractmethod
    def get_view(self, world_id: UUID) -> WorldViewRead: ...

    @abstractmethod
    def get_metrics(self, world_id: UUID, query: MetricQuery) -> list[MetricRead]:
        """Raises DomainValidationError INVALID_TICK_RANGE (from_tick > to_tick)."""
