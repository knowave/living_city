import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class LedgerEntry(BaseEntity):
    __tablename__ = "ledger_entries"

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"))
    transaction_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    entry_no: Mapped[int] = mapped_column(SmallInteger)
    amount: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (
        ForeignKeyConstraint(
            ["world_id", "transaction_id"],
            ["transactions.world_id", "transactions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["world_id", "account_id"], ["accounts.world_id", "accounts.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("amount <> 0", name="ck_ledger_entries_amount_non_zero"),
        CheckConstraint("entry_no >= 1", name="ck_ledger_entries_entry_no_positive"),
        UniqueConstraint("world_id", "id", name="uq_ledger_entries_world_id_id"),
        UniqueConstraint("transaction_id", "entry_no", name="uq_ledger_transaction_entry"),
        UniqueConstraint("transaction_id", "account_id", name="uq_ledger_transaction_account"),
        Index("idx_ledger_account_created", "account_id", text("created_at DESC")),
        Index("idx_ledger_world_transaction", "world_id", "transaction_id"),
    )
