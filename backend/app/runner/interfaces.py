from abc import ABC, abstractmethod
from uuid import UUID

from app.schemas.world import RunnerStatusRead


class RunnerStatusProvider(ABC):
    @abstractmethod
    def get(self, world_id: UUID) -> RunnerStatusRead | None: ...


class OwnershipHandle(ABC):
    @abstractmethod
    def release(self) -> None: ...


class OwnershipLock(ABC):
    @abstractmethod
    def try_acquire(self, world_id: UUID) -> OwnershipHandle | None:
        """pg_try_advisory_lock on a dedicated connection; None if owned elsewhere."""
