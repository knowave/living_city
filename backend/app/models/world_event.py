import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class WorldEvent(BaseEntity):
    __tablename__ = "world_events"
    __table_args__ = (UniqueConstraint("world_id", "sequence"), UniqueConstraint("world_id", "id", name="uq_world_events_world_id_id"))

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    sequence: Mapped[int] = mapped_column(BigInteger)
    tick: Mapped[int] = mapped_column(BigInteger)
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
