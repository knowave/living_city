"""월드(World) 엔티티와 상태 enum을 담는다."""

import uuid
from dataclasses import dataclass
from enum import StrEnum


class WorldStatus(StrEnum):
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


@dataclass(slots=True, kw_only=True)
class World:
    id: uuid.UUID
    name: str
    seed: int
    current_tick: int = 0
    speed: int = 1
    status: str = WorldStatus.INITIALIZED.value
    engine_version: str
