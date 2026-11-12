"""맵 청크(MapChunk) 레코드와 청크 크기 상수를 담는다."""

import uuid
from dataclasses import dataclass

CHUNK_SIZE = 32  # tile index = local_y * CHUNK_SIZE + local_x


@dataclass(slots=True, kw_only=True)
class MapChunk:
    """맵을 CHUNK_SIZE x CHUNK_SIZE 타일 단위로 나눈 청크 레코드. backend MapChunk 대응."""

    id: uuid.UUID
    chunk_x: int
    chunk_y: int
    chunk_size: int = CHUNK_SIZE
    terrain_tiles: list[int]
    road_tiles: list[int]
    schema_version: int = 1
    revision: int = 1
