"""Repository ABCs used by services. No ORM models cross this boundary."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import TracebackType
from uuid import UUID

from app.maps.generator import ChunkData
from app.schemas.city import (
    BuildingRangeQuery,
    BuildingRead,
    ChunkRangeQuery,
    ChunkRead,
    CitizenFilter,
    CitizenRead,
    CompanyRead,
    EmploymentRead,
    MetricQuery,
    MetricRead,
    MovementRead,
)
from app.schemas.enums import AccountOwnerType, WorldStatus
from app.schemas.world import PolicyRead, WorldRead
from app.simulation.interfaces import EngineBatch


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


@dataclass(frozen=True)
class SnapshotRecord:
    tick: int
    last_event_sequence: int
    state_data: dict


class WorldRepository(ABC):
    @abstractmethod
    def add(self, data: NewWorld) -> WorldRead: ...

    @abstractmethod
    def get(self, world_id: UUID) -> WorldRead | None: ...

    @abstractmethod
    def lock_for_update(
        self, world_id: UUID, *, nowait: bool, timeout_ms: int | None = None
    ) -> WorldRead | None:
        """SELECT ... FOR UPDATE [NOWAIT] and return the latest row (None if missing). Wait mode
        applies `timeout_ms` as lock_timeout. Raises ConflictError("WORLD_BUSY") if the lock
        cannot be acquired (PG 55P03); the transaction is rolled back in that case."""

    @abstractmethod
    def update_simulation(
        self, world_id: UUID, status: WorldStatus, speed: int, expected_version: int
    ) -> WorldRead:
        """Raises ConflictError("CONCURRENT_UPDATE") if worlds.version != expected_version."""

    @abstractmethod
    def advance_tick(self, world_id: UUID, new_tick: int, expected_version: int) -> WorldRead:
        """Raises ConflictError("CONCURRENT_UPDATE") if worlds.version != expected_version."""

    @abstractmethod
    def mark_failed(self, world_id: UUID) -> None:
        """status=FAILED (version incremented)."""

    @abstractmethod
    def list_ids_by_status(self, status: WorldStatus) -> list[UUID]: ...


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

    @abstractmethod
    def all(self, world_id: UUID) -> list[PolicyRead]:
        """Ascending version."""

    @abstractmethod
    def upsert_pending(self, data: NewPolicy) -> PolicyRead:
        """Row with same (world_id, effective_tick): overwrite values and set version=data.version;
        otherwise insert."""


class WorldSnapshotRepository(ABC):
    @abstractmethod
    def latest(self, world_id: UUID) -> SnapshotRecord | None: ...


class SimulationPersistence(ABC):
    """Both methods flush only (no commit). Upsert 7 entity kinds, insert transactions, ledger,
    events, metrics and snapshot; save_advance also replaces the backend pending policy row of the
    same effective_tick with the engine's.
    save_advance also prunes world_snapshots in the same transaction: keeps tick % 720 == 0 and
    the newest `keep_latest` ticks."""

    @abstractmethod
    def save_generation(self, world_id: UUID, batch: EngineBatch) -> None: ...

    @abstractmethod
    def save_advance(self, world_id: UUID, batch: EngineBatch) -> None: ...


class WorldEventRepository(ABC):
    @abstractmethod
    def max_sequence(self, world_id: UUID) -> int:
        """0 if no events."""


class MapChunkRepository(ABC):
    @abstractmethod
    def save_all(self, world_id: UUID, chunks: list[ChunkData]) -> None: ...

    @abstractmethod
    def count(self, world_id: UUID) -> int: ...

    @abstractmethod
    def list(self, world_id: UUID, query: ChunkRangeQuery) -> list[ChunkRead]: ...


class BuildingRepository(ABC):
    @abstractmethod
    def list(self, world_id: UUID, query: BuildingRangeQuery) -> list[BuildingRead]:
        """Buildings whose tile rectangle overlaps the (inclusive) range; omitted bounds are open.
        Ordered by id."""

    @abstractmethod
    def get(self, world_id: UUID, building_id: UUID) -> BuildingRead | None: ...

    @abstractmethod
    def company_ids(self, world_id: UUID, building_id: UUID) -> list[UUID]: ...

    @abstractmethod
    def household_count(self, world_id: UUID, building_id: UUID) -> int:
        """Households whose residence is this building."""


class CitizenRepository(ABC):
    @abstractmethod
    def get(self, world_id: UUID, citizen_id: UUID) -> CitizenRead | None:
        """Base row only (no movement/employment/cash_balance)."""

    @abstractmethod
    def list(
        self, world_id: UUID, flt: CitizenFilter, limit: int | None, offset: int
    ) -> tuple[list[CitizenRead], int]:
        """(page ordered by id, total matching). limit None = all."""

    @abstractmethod
    def movements(self, world_id: UUID, citizen_ids: list[UUID]) -> dict[UUID, MovementRead]:
        """Latest `citizen.movement.started` event per citizen (one set-based query)."""

    @abstractmethod
    def employments(self, world_id: UUID, citizen_ids: list[UUID]) -> dict[UUID, EmploymentRead]:
        """ACTIVE employment per citizen."""

    @abstractmethod
    def count(self, world_id: UUID) -> int: ...

    @abstractmethod
    def count_employed(self, world_id: UUID) -> int:
        """Citizens with an ACTIVE employment."""


class CompanyRepository(ABC):
    @abstractmethod
    def get(self, world_id: UUID, company_id: UUID) -> CompanyRead | None: ...

    @abstractmethod
    def list(
        self,
        world_id: UUID,
        status: str | None,
        industry: str | None,
        limit: int | None,
        offset: int,
    ) -> tuple[list[CompanyRead], int]:
        """(page ordered by id, total matching). limit None = all."""

    @abstractmethod
    def active_employees(self, world_id: UUID, company_id: UUID) -> int:
        """Count of ACTIVE employments."""

    @abstractmethod
    def count_by_status(self, world_id: UUID) -> dict[str, int]: ...


class AccountRepository(ABC):
    @abstractmethod
    def cash_balance(
        self, world_id: UUID, owner_type: AccountOwnerType, owner_id: UUID
    ) -> int | None:
        """Balance of the CASH/KRW account, None if absent."""

    @abstractmethod
    def cash_balances(
        self, world_id: UUID, owner_type: AccountOwnerType, owner_ids: list[UUID]
    ) -> dict[UUID, int]:
        """Set-based cash_balance for CITIZEN/COMPANY owners (missing owners omitted)."""

    @abstractmethod
    def government_treasury(self, world_id: UUID) -> int:
        """GOVERNMENT/TREASURY/KRW balance (0 if absent)."""

    @abstractmethod
    def city_internal_money(self, world_id: UUID) -> int:
        """Sum of balances of CITIZEN, HOUSEHOLD, COMPANY and GOVERNMENT accounts."""


class WorldMetricRepository(ABC):
    @abstractmethod
    def list(self, world_id: UUID, query: MetricQuery) -> list[MetricRead]: ...

    @abstractmethod
    def latest_monthly(self, world_id: UUID) -> list[MetricRead]:
        """MONTHLY metrics at the greatest MONTHLY tick."""


class UnitOfWork(ABC):
    worlds: WorldRepository
    policies: WorldPolicyRepository
    events: WorldEventRepository
    chunks: MapChunkRepository
    buildings: BuildingRepository
    citizens: CitizenRepository
    companies: CompanyRepository
    accounts: AccountRepository
    metrics: WorldMetricRepository
    snapshots: WorldSnapshotRepository
    simulation: SimulationPersistence

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...

    @abstractmethod
    def begin_consistent_read(self) -> None:
        """Start a REPEATABLE READ transaction. Must be called before the first statement; every
        later read (world tick, event cursor, data) sees one committed state. Ends with the
        request's session (no commit needed)."""

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
