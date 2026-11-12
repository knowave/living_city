"""고용(Employment) 엔티티 정의를 담는다."""

import uuid
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class Employment:
    id: uuid.UUID
    citizen_id: uuid.UUID
    company_id: uuid.UUID
    salary: int
    hired_tick: int
    terminated_tick: int | None = None
    status: str
