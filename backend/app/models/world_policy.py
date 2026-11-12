import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class WorldPolicy(BaseEntity):
    __tablename__ = "world_policies"
    __table_args__ = (
        UniqueConstraint("world_id", "id", name="uq_world_policies_world_id_id"),
        UniqueConstraint("world_id", "effective_tick", name="uq_world_policies_world_id_effective_tick"),
        UniqueConstraint("world_id", "version", name="uq_world_policies_world_id_version"),
        CheckConstraint("income_tax_rate BETWEEN 0 AND 10000", name="ck_world_policies_income_tax_rate_range"),
        CheckConstraint("welfare_amount >= 0", name="ck_world_policies_welfare_amount_non_negative"),
    )

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    # basis points: 1500 = 15%
    income_tax_rate: Mapped[int] = mapped_column(Integer, default=1500)
    welfare_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    effective_tick: Mapped[int] = mapped_column(BigInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
