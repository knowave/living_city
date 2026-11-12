import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class Employment(BaseEntity):
    __tablename__ = "employments"
    __table_args__ = (
        UniqueConstraint("world_id", "id", name="uq_employments_world_id_id"),
        ForeignKeyConstraint(["world_id", "citizen_id"], ["citizens.world_id", "citizens.id"], ondelete="RESTRICT", name="fk_employments_citizen_id"),
        ForeignKeyConstraint(["world_id", "company_id"], ["companies.world_id", "companies.id"], ondelete="RESTRICT", name="fk_employments_company_id"),
        Index("uq_employments_world_citizen_active", "world_id", "citizen_id", unique=True, postgresql_where=text("terminated_tick IS NULL")),
        CheckConstraint("(status = 'ACTIVE') = (terminated_tick IS NULL)", name="ck_employments_status_terminated"),
    )

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    citizen_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    salary: Mapped[int] = mapped_column(BigInteger)
    hired_tick: Mapped[int] = mapped_column(BigInteger)
    terminated_tick: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(32))
