import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, SmallInteger, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity

CHUNK_SIZE = 32  # tile index = local_y * CHUNK_SIZE + local_x


class MapChunk(BaseEntity):
    __tablename__ = "map_chunks"
    __table_args__ = (
        UniqueConstraint("world_id", "id", name="uq_map_chunks_world_id_id"),
        UniqueConstraint("world_id", "chunk_x", "chunk_y", name="uq_map_chunks_position"),
        CheckConstraint("chunk_x >= 0", name="ck_map_chunks_chunk_x_non_negative"),
        CheckConstraint("chunk_y >= 0", name="ck_map_chunks_chunk_y_non_negative"),
        CheckConstraint("chunk_size = 32", name="ck_map_chunks_chunk_size"),
        CheckConstraint("schema_version >= 1", name="ck_map_chunks_schema_version"),
        CheckConstraint("revision >= 1", name="ck_map_chunks_revision"),
        CheckConstraint("jsonb_typeof(terrain_tiles) = 'array'", name="ck_map_chunks_terrain_is_array"),
        CheckConstraint("jsonb_typeof(road_tiles) = 'array'", name="ck_map_chunks_road_is_array"),
        CheckConstraint("jsonb_array_length(terrain_tiles) = 1024", name="ck_map_chunks_terrain_len"),
        CheckConstraint("jsonb_array_length(road_tiles) = 1024", name="ck_map_chunks_road_len"),
    )

    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), nullable=False
    )
    chunk_x: Mapped[int] = mapped_column(Integer)
    chunk_y: Mapped[int] = mapped_column(Integer)
    chunk_size: Mapped[int] = mapped_column(SmallInteger, default=CHUNK_SIZE, server_default=str(CHUNK_SIZE))
    terrain_tiles: Mapped[list[int]] = mapped_column(JSONB)
    road_tiles: Mapped[list[int]] = mapped_column(JSONB)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
