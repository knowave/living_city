import uuid

from sqlalchemy import BigInteger, ForeignKey, ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class Household(BaseEntity):
    __tablename__ = "households"
    __table_args__ = (
        UniqueConstraint("world_id", "id", name="uq_households_world_id_id"),
        ForeignKeyConstraint(["world_id", "residence_building_id"], ["buildings.world_id", "buildings.id"], ondelete="RESTRICT", name="fk_households_residence_building_id"),
    )

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    residence_building_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    monthly_housing_cost: Mapped[int] = mapped_column(BigInteger, default=0)
