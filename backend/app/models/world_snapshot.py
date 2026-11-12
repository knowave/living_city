import uuid

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class WorldSnapshot(BaseEntity):
    __tablename__ = "world_snapshots"
    __table_args__ = (UniqueConstraint("world_id", "tick"), UniqueConstraint("world_id", "id", name="uq_world_snapshots_world_id_id"))

    world_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    tick: Mapped[int] = mapped_column(BigInteger)
    last_event_sequence: Mapped[int] = mapped_column(BigInteger)
    engine_version: Mapped[str] = mapped_column(String(32))
    state_data: Mapped[dict] = mapped_column(JSONB, default=dict)
