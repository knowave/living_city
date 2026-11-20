from abc import ABC, abstractmethod
from uuid import UUID

from app.schemas.world import (
    PolicyRead,
    PolicyUpdate,
    SimulationUpdate,
    TickAdvanceRead,
    TickAdvanceRequest,
    WorldCreate,
    WorldRead,
    WorldStateRead,
)


class WorldUseCase(ABC):
    @abstractmethod
    def create_world(self, data: WorldCreate) -> WorldRead:
        """Create world (INITIALIZED, tick 0, speed 1) and generate its initial state with the
        engine (entities, accounts, policy, snapshot at tick 0) in one transaction. Generates
        seed if None; engine_version defaults to settings.
        Raises ConflictError WORLD_GENERATION_FAILED (engine error; nothing is persisted)."""

    @abstractmethod
    def get_world(self, world_id: UUID) -> WorldRead:
        """Raises NotFoundError WORLD_NOT_FOUND."""

    @abstractmethod
    def get_world_state(self, world_id: UUID) -> WorldStateRead:
        """Snapshot with event_cursor and current policy.
        Raises NotFoundError WORLD_NOT_FOUND."""

    @abstractmethod
    def change_simulation(self, world_id: UUID, data: SimulationUpdate) -> WorldRead:
        """Change status and/or speed. Validates the status transition table and speed bounds.
        Raises NotFoundError WORLD_NOT_FOUND, InvalidStateError INVALID_STATE_TRANSITION,
        DomainValidationError INVALID_SPEED, ConflictError CONCURRENT_UPDATE, WORLD_BUSY (row lock
        wait exceeded lock timeout)."""

    @abstractmethod
    def change_policy(self, world_id: UUID, data: PolicyUpdate) -> PolicyRead:
        """Register a pending policy version with effective_tick = current_tick + 1 (omitted
        fields inherit from latest; same effective_tick row is replaced). It is applied as an
        engine command at the next advance_ticks. Raises NotFoundError WORLD_NOT_FOUND,
        DomainValidationError INVALID_POLICY (rate 0..10000, welfare >= 0),
        ConflictError CONCURRENT_UPDATE, WORLD_BUSY (row lock wait exceeded lock timeout)."""

    @abstractmethod
    def advance_ticks(self, world_id: UUID, data: TickAdvanceRequest) -> TickAdvanceRead:
        """Run `count` ticks with the engine and persist the result in one transaction.
        Locks the world row with NOWAIT first. Raises NotFoundError WORLD_NOT_FOUND,
        ConflictError WORLD_BUSY (another write holds the lock), InvalidStateError
        WORLD_NOT_RUNNABLE (FAILED or ARCHIVED), ConflictError TICK_MISMATCH (expected_tick !=
        current_tick; details.current_tick), ConflictError SNAPSHOT_MISMATCH (no snapshot or snapshot.tick !=
        current_tick), CONCURRENT_UPDATE, SIMULATION_FAILED (engine error; world becomes FAILED)."""

    @abstractmethod
    def advance_running(self, world_id: UUID, expected_tick: int) -> TickAdvanceRead:
        """Runner path: advance a RUNNING world by its current `speed` ticks (speed read under the
        row lock). Same transaction/flow as advance_ticks. Raises NotFoundError WORLD_NOT_FOUND,
        ConflictError WORLD_BUSY, InvalidStateError WORLD_NOT_RUNNING (status != RUNNING),
        ConflictError TICK_MISMATCH, SNAPSHOT_MISMATCH, CONCURRENT_UPDATE, SIMULATION_FAILED."""

    @abstractmethod
    def list_running_world_ids(self) -> list[UUID]:
        """Ids of worlds whose status is RUNNING."""
