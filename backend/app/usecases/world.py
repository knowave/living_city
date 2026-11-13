from abc import ABC, abstractmethod
from uuid import UUID

from app.schemas.world import (
    PolicyRead,
    PolicyUpdate,
    SimulationUpdate,
    WorldCreate,
    WorldRead,
    WorldStateRead,
)


class WorldUseCase(ABC):
    @abstractmethod
    def create_world(self, data: WorldCreate) -> WorldRead:
        """Create world (INITIALIZED, tick 0, speed 1) plus its initial policy (version 1,
        effective_tick 0). Generates seed if None; engine_version defaults to settings."""

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
        DomainValidationError INVALID_SPEED, ConflictError CONCURRENT_UPDATE."""

    @abstractmethod
    def change_policy(self, world_id: UUID, data: PolicyUpdate) -> PolicyRead:
        """Append a new policy version effective at the world's current tick (omitted fields
        inherit from latest). Raises NotFoundError WORLD_NOT_FOUND,
        DomainValidationError INVALID_POLICY (rate 0..10000, welfare >= 0),
        ConflictError CONCURRENT_UPDATE."""
