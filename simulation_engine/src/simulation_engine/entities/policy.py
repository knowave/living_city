"""월드 정책(WorldPolicy) 엔티티 정의를 담는다."""

import uuid
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class WorldPolicy:
    id: uuid.UUID
    income_tax_rate: int = 1500  # basis points: 1500 = 15%
    welfare_amount: int = 0
    effective_tick: int = 0
    version: int = 1
