import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class BuildingType(StrEnum):
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    OFFICE = "OFFICE"
    PUBLIC = "PUBLIC"


class Building(BaseEntity):
    __tablename__ = "buildings"
    __table_args__ = (UniqueConstraint("world_id", "id", name="uq_buildings_world_id_id"),)

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    tile_x: Mapped[int] = mapped_column(Integer)
    tile_y: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    occupied_capacity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32))
