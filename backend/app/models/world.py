from enum import StrEnum

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class WorldStatus(StrEnum):
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class World(BaseEntity):
    __tablename__ = "worlds"

    name: Mapped[str] = mapped_column(String(100))
    seed: Mapped[int] = mapped_column(BigInteger)
    current_tick: Mapped[int] = mapped_column(BigInteger, default=0)
    speed: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default=WorldStatus.INITIALIZED.value)
    engine_version: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}
