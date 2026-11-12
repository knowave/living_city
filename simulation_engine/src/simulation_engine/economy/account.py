"""계정(Account) 엔티티와 소유자·계정 유형 열거형."""

import uuid
from dataclasses import dataclass
from enum import StrEnum


class AccountOwnerType(StrEnum):
    CITIZEN = "CITIZEN"
    HOUSEHOLD = "HOUSEHOLD"
    COMPANY = "COMPANY"
    GOVERNMENT = "GOVERNMENT"
    SYSTEM = "SYSTEM"


class AccountType(StrEnum):
    CASH = "CASH"
    SAVINGS = "SAVINGS"
    TREASURY = "TREASURY"
    ISSUANCE = "ISSUANCE"


@dataclass(slots=True, kw_only=True)
class Account:
    id: uuid.UUID
    owner_type: AccountOwnerType
    citizen_id: uuid.UUID | None = None
    household_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    account_type: AccountType = AccountType.CASH
    currency: str = "KRW"
    balance: int = 0
    is_active: bool = True

    def __post_init__(self) -> None:
        owners = {
            AccountOwnerType.CITIZEN: "citizen_id",
            AccountOwnerType.HOUSEHOLD: "household_id",
            AccountOwnerType.COMPANY: "company_id",
        }
        expected = owners.get(self.owner_type)  # GOVERNMENT/SYSTEM: 소유자 id 없음
        for field in owners.values():
            if (getattr(self, field) is not None) != (field == expected):
                raise ValueError(f"{self.owner_type} 계정의 소유자 id 구성이 올바르지 않음: {field}")
        if self.balance < 0 and not (
            self.owner_type == AccountOwnerType.SYSTEM and self.account_type == AccountType.ISSUANCE
        ):
            raise ValueError("balance는 SYSTEM ISSUANCE 계정 외에는 음수일 수 없음")
