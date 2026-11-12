import uuid
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


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


def _owner_uniques() -> list[Index]:
    return [
        Index(
            f"uq_accounts_{o}",
            "world_id",
            f"{o}_id",
            "account_type",
            "currency",
            unique=True,
            postgresql_where=text(f"{o}_id IS NOT NULL"),
        )
        for o in ("citizen", "household", "company")
    ]


def _owner_indexes() -> list[Index]:
    return [
        Index(f"idx_accounts_{o}", f"{o}_id", postgresql_where=text(f"{o}_id IS NOT NULL"))
        for o in ("citizen", "household", "company")
    ]


class Account(BaseEntity):
    __tablename__ = "accounts"

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"))
    owner_type: Mapped[str] = mapped_column(String(16))
    citizen_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    household_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    account_type: Mapped[str] = mapped_column(
        String(16), default=AccountType.CASH.value, server_default=text("'CASH'")
    )
    currency: Mapped[str] = mapped_column(CHAR(3), default="KRW", server_default=text("'KRW'"))
    balance: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    __table_args__ = (
        ForeignKeyConstraint(
            ["world_id", "citizen_id"], ["citizens.world_id", "citizens.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["world_id", "household_id"],
            ["households.world_id", "households.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["world_id", "company_id"], ["companies.world_id", "companies.id"], ondelete="RESTRICT"
        ),
        CheckConstraint(
            "(owner_type = 'CITIZEN' AND citizen_id IS NOT NULL AND household_id IS NULL AND company_id IS NULL)"
            " OR (owner_type = 'HOUSEHOLD' AND household_id IS NOT NULL AND citizen_id IS NULL AND company_id IS NULL)"
            " OR (owner_type = 'COMPANY' AND company_id IS NOT NULL AND citizen_id IS NULL AND household_id IS NULL)"
            " OR (owner_type IN ('GOVERNMENT', 'SYSTEM') AND citizen_id IS NULL AND household_id IS NULL AND company_id IS NULL)",
            name="ck_accounts_owner",
        ),
        CheckConstraint(
            "balance >= 0 OR (owner_type = 'SYSTEM' AND account_type = 'ISSUANCE')",
            name="ck_accounts_balance_non_negative",
        ),
        UniqueConstraint("world_id", "id", name="uq_accounts_world_id_id"),
        Index("idx_accounts_world", "world_id"),
        *_owner_indexes(),
        *_owner_uniques(),
        Index(
            "uq_accounts_government",
            "world_id",
            "account_type",
            "currency",
            unique=True,
            postgresql_where=text("owner_type = 'GOVERNMENT'"),
        ),
        Index(
            "uq_accounts_system",
            "world_id",
            "account_type",
            "currency",
            unique=True,
            postgresql_where=text("owner_type = 'SYSTEM'"),
        ),
    )
