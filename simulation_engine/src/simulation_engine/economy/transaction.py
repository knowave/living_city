"""거래(Transaction) 엔티티와 거래 유형 열거형."""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TransactionType(StrEnum):
    OPENING_BALANCE = "OPENING_BALANCE"
    SALARY = "SALARY"
    PURCHASE = "PURCHASE"
    INCOME_TAX = "INCOME_TAX"
    RENT = "RENT"
    WELFARE = "WELFARE"
    ACCOUNT_TRANSFER = "ACCOUNT_TRANSFER"
    CAPITAL_INVESTMENT = "CAPITAL_INVESTMENT"
    ADJUSTMENT = "ADJUSTMENT"
    REVERSAL = "REVERSAL"
    OPERATING_EXPENSE = "OPERATING_EXPENSE"
    PUBLIC_PROCUREMENT = "PUBLIC_PROCUREMENT"
    EXPORT = "EXPORT"


@dataclass(slots=True, kw_only=True)
class Transaction:
    id: uuid.UUID
    transaction_type: TransactionType
    tick: int
    idempotency_key: str
    description: str | None = None
    reverses_transaction_id: uuid.UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
