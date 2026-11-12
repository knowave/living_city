"""월드 스냅샷(WorldSnapshot) 레코드를 담는다."""

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, kw_only=True)
class WorldSnapshot:
    """특정 tick의 월드 상태 스냅샷 레코드. backend WorldSnapshot 대응."""

    id: uuid.UUID
    tick: int
    last_event_sequence: int
    engine_version: str
    state_data: dict[str, Any] = field(default_factory=dict)
