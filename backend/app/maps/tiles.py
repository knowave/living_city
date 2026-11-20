"""Tile schema v1 constants (must match frontend/src/render/map/tiles.ts)."""
MAP_SIZE = 512
CHUNK_SIZE = 32
CHUNKS_PER_SIDE = 16
TILE_SCHEMA_VERSION = 1
ENGINE_AREA = (0, 0, 128, 128)  # x, y, width, height

GRASS, WATER, SAND = 0, 1, 2
LOCAL, ARTERIAL = 0, 1
N, E, S, W = 1, 2, 4, 8
ISOLATED = 16

# direction bits in N E S W order with their (dx, dy)
DIRS = ((N, 0, -1), (E, 1, 0), (S, 0, 1), (W, -1, 0))


def encode_road(cls: int, conn: int) -> int:
    return (cls << 5) | conn
