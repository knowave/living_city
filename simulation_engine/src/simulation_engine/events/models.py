"""도메인 이벤트 모델을 담는다."""

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, kw_only=True)
class WorldEvent:
    """월드에서 발생한 도메인 이벤트 레코드. backend WorldEvent 대응."""

    id: uuid.UUID
    sequence: int
    tick: int
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
