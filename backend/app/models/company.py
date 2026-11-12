import uuid
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class CompanyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISTRESSED = "DISTRESSED"
    BANKRUPT = "BANKRUPT"
    CLOSED = "CLOSED"


class Company(BaseEntity):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("world_id", "id", name="uq_companies_world_id_id"),
        ForeignKeyConstraint(["world_id", "building_id"], ["buildings.world_id", "buildings.id"], ondelete="RESTRICT", name="fk_companies_building_id"),
    )

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    industry: Mapped[str] = mapped_column(String(64))
    building_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    employee_capacity: Mapped[int] = mapped_column(Integer, default=0)
    employee_count: Mapped[int] = mapped_column(Integer, default=0)
    base_wage: Mapped[int] = mapped_column(BigInteger, default=0)
    operating_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(32), default=CompanyStatus.ACTIVE.value)
