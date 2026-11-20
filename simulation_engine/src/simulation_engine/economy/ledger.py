"""원장 항목(LedgerEntry) 엔티티와 거래 기록 함수."""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from simulation_engine.economy.account import AccountOwnerType, AccountType
from simulation_engine.economy.transaction import Transaction, TransactionType

if TYPE_CHECKING:
    from simulation_engine.context import TickContext


class InsufficientFunds(Exception):
    """거래 결과 잔액이 음수가 되는 계정이 있음. 아무것도 반영되지 않는다."""


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


def post_transaction(
    ctx: "TickContext",
    type: TransactionType | str,
    entries: list[tuple[uuid.UUID, int]],
    key: str,
    metadata: dict[str, Any] | None = None,
) -> Transaction:
    """entries=[(account_id, amount)]를 원자적으로 반영한다. 검증 실패 시 상태는 그대로다."""
    accounts = ctx.state.accounts
    ids = [a for a, _ in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("한 거래에서 같은 계정이 두 번 나올 수 없음")
    if any(amount == 0 for _, amount in entries):
        raise ValueError("amount는 0일 수 없음")
    if sum(amount for _, amount in entries) != 0:
        raise ValueError("거래의 원장 합계는 0이어야 함")
    for account_id, amount in entries:
        acc = accounts[account_id]
        is_issuance = acc.owner_type == AccountOwnerType.SYSTEM and acc.account_type == AccountType.ISSUANCE
        if acc.balance + amount < 0 and not is_issuance:
            raise InsufficientFunds(f"{account_id}: 잔액 {acc.balance}, 변동 {amount}")

    tx = Transaction(
        id=ctx.state.new_id("transaction"),
        transaction_type=TransactionType(type),
        tick=ctx.tick,
        idempotency_key=key,
        metadata=dict(metadata or {}),
    )
    ctx.transactions.append(tx)
    for no, (account_id, amount) in enumerate(entries, start=1):
        accounts[account_id].balance += amount
        ctx.ledger_entries.append(
            LedgerEntry(
                id=ctx.state.new_id("ledger_entry"),
                transaction_id=tx.id,
                account_id=account_id,
                entry_no=no,
                amount=amount,
            )
        )
    return tx
