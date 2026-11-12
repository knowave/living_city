"""가구(Household) 엔티티 정의를 담는다."""

import uuid
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class Household:
    id: uuid.UUID
    residence_building_id: uuid.UUID | None = None
    monthly_housing_cost: int = 0
