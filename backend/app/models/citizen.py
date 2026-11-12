import uuid

from sqlalchemy import BigInteger, Float, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class Citizen(BaseEntity):
    __tablename__ = "citizens"
    __table_args__ = (
        UniqueConstraint("world_id", "id", name="uq_citizens_world_id_id"),
        ForeignKeyConstraint(["world_id", "household_id"], ["households.world_id", "households.id"], ondelete="RESTRICT", name="fk_citizens_household_id"),
        ForeignKeyConstraint(["world_id", "home_building_id"], ["buildings.world_id", "buildings.id"], ondelete="RESTRICT", name="fk_citizens_home_building_id"),
        ForeignKeyConstraint(["world_id", "current_building_id"], ["buildings.world_id", "buildings.id"], ondelete="RESTRICT", name="fk_citizens_current_building_id"),
        ForeignKeyConstraint(["world_id", "employer_id"], ["companies.world_id", "companies.id"], ondelete="RESTRICT", name="fk_citizens_employer_id"),
        ForeignKeyConstraint(["world_id", "current_destination"], ["buildings.world_id", "buildings.id"], ondelete="RESTRICT", name="fk_citizens_current_destination"),
    )

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    household_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(Integer)
    home_building_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    current_building_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    employment_status: Mapped[str] = mapped_column(String(32))
    employer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    happiness: Mapped[int] = mapped_column(Integer)
    health: Mapped[int] = mapped_column(Integer)
    skills: Mapped[dict] = mapped_column(JSONB, default=dict)
    risk_tolerance: Mapped[float] = mapped_column(Float)
    consumption_preference: Mapped[float] = mapped_column(Float)
    current_activity: Mapped[str] = mapped_column(String(32))
    current_destination: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    arrival_tick: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
