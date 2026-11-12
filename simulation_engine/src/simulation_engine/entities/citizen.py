"""시민(Citizen) 엔티티 정의를 담는다."""

import uuid
from dataclasses import dataclass, field


@dataclass(slots=True, kw_only=True)
class Citizen:
    id: uuid.UUID
    household_id: uuid.UUID | None = None
    name: str
    age: int
    home_building_id: uuid.UUID | None = None
    current_building_id: uuid.UUID | None = None
    employment_status: str
    employer_id: uuid.UUID | None = None
    happiness: int
    health: int
    skills: dict[str, int] = field(default_factory=dict)
    risk_tolerance: int  # basis points (10000 = 1.0)
    consumption_preference: int  # basis points (10000 = 1.0)
    current_activity: str
    current_destination: uuid.UUID | None = None
    arrival_tick: int | None = None
