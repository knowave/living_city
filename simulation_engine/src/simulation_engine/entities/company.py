"""사업체(Company) 엔티티와 상태 enum을 담는다."""

import uuid
from dataclasses import dataclass
from enum import StrEnum


class CompanyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISTRESSED = "DISTRESSED"
    BANKRUPT = "BANKRUPT"
    CLOSED = "CLOSED"


@dataclass(slots=True, kw_only=True)
class Company:
    id: uuid.UUID
    name: str
    industry: str
    building_id: uuid.UUID | None = None
    employee_capacity: int = 0
    employee_count: int = 0
    base_wage: int = 0
    operating_cost: int = 0
    status: str = CompanyStatus.ACTIVE.value
