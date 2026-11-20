import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


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


class Transaction(BaseEntity):
    __tablename__ = "transactions"

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"))
    transaction_type: Mapped[str] = mapped_column(String(32))
    tick: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    reverses_transaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["world_id", "reverses_transaction_id"],
            ["transactions.world_id", "transactions.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("world_id", "id", name="uq_transactions_world_id_id"),
        UniqueConstraint("world_id", "idempotency_key", name="uq_transactions_idempotency"),
        Index("idx_transactions_world_tick", "world_id", text("tick DESC")),
        Index(
            "idx_transactions_type_tick", "world_id", "transaction_type", text("tick DESC")
        ),
        Index(
            "uq_transactions_reversal",
            "world_id",
            "reverses_transaction_id",
            unique=True,
            postgresql_where=text("reverses_transaction_id IS NOT NULL"),
        ),
    )
