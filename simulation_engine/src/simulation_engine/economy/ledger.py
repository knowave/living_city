"""원장 항목(LedgerEntry) 엔티티."""

import uuid
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class LedgerEntry:
    id: uuid.UUID
    transaction_id: uuid.UUID
    account_id: uuid.UUID
    entry_no: int
    amount: int

    def __post_init__(self) -> None:
        if self.amount == 0:
            raise ValueError("amount는 0일 수 없음")
        if self.entry_no < 1:
            raise ValueError("entry_no는 1 이상이어야 함")
