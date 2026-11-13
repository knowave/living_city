"""Repository ABCs used by services. No ORM models cross this boundary."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import TracebackType
from uuid import UUID

from app.schemas.city import (
    ChunkRangeQuery,
    ChunkRead,
    CitizenRead,
    CompanyRead,
    MetricQuery,
    MetricRead,
)
from app.schemas.enums import AccountOwnerType, WorldStatus
from app.schemas.world import PolicyRead, WorldRead


@dataclass(frozen=True)
class NewWorld:
    name: str
    seed: int
    engine_version: str


@dataclass(frozen=True)
class NewPolicy:
    world_id: UUID
    income_tax_rate: int
    welfare_amount: int
    effective_tick: int
    version: int


class WorldRepository(ABC):
    @abstractmethod
    def add(self, data: NewWorld) -> WorldRead: ...

    @abstractmethod
    def get(self, world_id: UUID) -> WorldRead | None: ...

    @abstractmethod
    def update_simulation(
        self, world_id: UUID, status: WorldStatus, speed: int, expected_version: int
    ) -> WorldRead:
        """Raises ConflictError("CONCURRENT_UPDATE") if worlds.version != expected_version."""


class WorldPolicyRepository(ABC):
    @abstractmethod
    def add(self, data: NewPolicy) -> PolicyRead:
        """Raises ConflictError("CONCURRENT_UPDATE") on (world_id, version) clash."""

    @abstractmethod
    def latest(self, world_id: UUID) -> PolicyRead | None:
        """Highest version."""

    @abstractmethod
    def current(self, world_id: UUID, tick: int) -> PolicyRead | None:
        """Policy with greatest effective_tick <= tick."""


class WorldEventRepository(ABC):
    @abstractmethod
    def max_sequence(self, world_id: UUID) -> int:
        """0 if no events."""


class MapChunkRepository(ABC):
    @abstractmethod
    def list(self, world_id: UUID, query: ChunkRangeQuery) -> list[ChunkRead]: ...


class CitizenRepository(ABC):
    @abstractmethod
    def get(self, world_id: UUID, citizen_id: UUID) -> CitizenRead | None: ...


class CompanyRepository(ABC):
    @abstractmethod
    def get(self, world_id: UUID, company_id: UUID) -> CompanyRead | None: ...


class AccountRepository(ABC):
    @abstractmethod
    def cash_balance(
        self, world_id: UUID, owner_type: AccountOwnerType, owner_id: UUID
    ) -> int | None:
        """Balance of the CASH/KRW account, None if absent."""


class WorldMetricRepository(ABC):
    @abstractmethod
    def list(self, world_id: UUID, query: MetricQuery) -> list[MetricRead]: ...


class UnitOfWork(ABC):
    worlds: WorldRepository
    policies: WorldPolicyRepository
    events: WorldEventRepository
    chunks: MapChunkRepository
    citizens: CitizenRepository
    companies: CompanyRepository
    accounts: AccountRepository
    metrics: WorldMetricRepository

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()
