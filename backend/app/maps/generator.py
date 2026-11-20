"""Deterministic 512x512 map generator. Pure Python; only the seeded Random below is used."""
import random
from collections import deque
from dataclasses import dataclass

from app.maps.tiles import (
    ARTERIAL, CHUNK_SIZE, CHUNKS_PER_SIDE, DIRS, ENGINE_AREA, GRASS, ISOLATED, LOCAL, MAP_SIZE,
    SAND, WATER, encode_road,
)
from app.simulation.interfaces import BuildingFootprint

M = MAP_SIZE
ARTERIAL_STEP = 64
LOCAL_STEP = 8
WATER_MARGIN = 2


@dataclass(frozen=True)
class ChunkData:
    chunk_x: int
    chunk_y: int
    terrain_tiles: list[int]
    road_tiles: list[int]


@dataclass
class GeneratedMap:
    terrain: bytearray  # index y * MAP_SIZE + x
    roads: bytearray  # encoded road value, 0 = none

    def chunks(self) -> list[ChunkData]:
        out = []
        for cy in range(CHUNKS_PER_SIDE):
            for cx in range(CHUNKS_PER_SIDE):
                t, r = [], []
                for ly in range(CHUNK_SIZE):
                    s = (cy * CHUNK_SIZE + ly) * M + cx * CHUNK_SIZE
                    t.extend(self.terrain[s : s + CHUNK_SIZE])
                    r.extend(self.roads[s : s + CHUNK_SIZE])
                out.append(ChunkData(cx, cy, t, r))
        return out


def perimeter(b: BuildingFootprint) -> list[tuple[int, int]]:
    """Edge-adjacent tiles in frontend entrance scan order: top, right, bottom, left."""
    x, y, w, h = b.tile_x, b.tile_y, b.width, b.height
    return (
        [(x + k, y - 1) for k in range(w)]
        + [(x + w, y + k) for k in range(h)]
        + [(x + k, y + h) for k in range(w)]
        + [(x - 1, y + k) for k in range(h)]
    )


def inside(x: int, y: int) -> bool:
    return 0 <= x < M and 0 <= y < M


def road_components(kind: bytearray) -> list[list[int]]:
    """4-adjacency components of non-zero tiles, in scan order."""
    seen = bytearray(M * M)
    comps = []
    for s in range(M * M):
        if not kind[s] or seen[s]:
            continue
        seen[s] = 1
        comp, stack = [], [s]
        while stack:
            t = stack.pop()
            comp.append(t)
            x, y = t % M, t // M
            for _, dx, dy in DIRS:
                nx, ny = x + dx, y + dy
                if inside(nx, ny) and kind[ny * M + nx] and not seen[ny * M + nx]:
                    seen[ny * M + nx] = 1
                    stack.append(ny * M + nx)
        comps.append(comp)
    return comps


def generate_map(seed: int, buildings: list[BuildingFootprint]) -> GeneratedMap:
    rng = random.Random(seed)
    solid = bytearray(M * M)  # building tiles
    margin = bytearray(M * M)  # tiles where water/sand are forbidden
    ex, ey, ew, eh = ENGINE_AREA
    for y in range(ey, ey + eh):
        for x in range(ex, ex + ew):
            margin[y * M + x] = 1
    for b in buildings:
        for y in range(b.tile_y, b.tile_y + b.height):
            for x in range(b.tile_x, b.tile_x + b.width):
                if inside(x, y):
                    solid[y * M + x] = 1
        for y in range(b.tile_y - WATER_MARGIN, b.tile_y + b.height + WATER_MARGIN):
            for x in range(b.tile_x - WATER_MARGIN, b.tile_x + b.width + WATER_MARGIN):
                if inside(x, y):
                    margin[y * M + x] = 1

    terrain = bytearray(M * M)  # GRASS == 0
    for _ in range(rng.randint(6, 10)):
        cx, cy = rng.randrange(M), rng.randrange(M)
        rx, ry = rng.randint(6, 20), rng.randint(6, 20)
        for y in range(max(0, cy - ry), min(M, cy + ry + 1)):
            for x in range(max(0, cx - rx), min(M, cx + rx + 1)):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1 and not margin[y * M + x]:
                    terrain[y * M + x] = WATER
    for i in range(M * M):  # sand = grass next to water
        if terrain[i] == GRASS and not margin[i]:
            x, y = i % M, i // M
            if any(inside(x + dx, y + dy) and terrain[(y + dy) * M + x + dx] == WATER for _, dx, dy in DIRS):
                terrain[i] = SAND

    kind = bytearray(M * M)  # 0 none, 1 local, 2 arterial

    def lay(x: int, y: int, k: int) -> None:
        i = y * M + x
        if not solid[i] and terrain[i] != WATER and kind[i] < k:
            kind[i] = k

    ox, oy = rng.randrange(LOCAL_STEP), rng.randrange(LOCAL_STEP)
    for y in range(ey, ey + eh):
        for x in range(ex, ex + ew):
            if (x - ox) % LOCAL_STEP == 0 or (y - oy) % LOCAL_STEP == 0:
                lay(x, y, 1)
    for y in range(M):
        for x in range(M):
            if x % ARTERIAL_STEP == 0 or y % ARTERIAL_STEP == 0:
                lay(x, y, 2)

    # keep only the largest road component so every road belongs to one network
    comps = road_components(kind)
    main = bytearray(M * M)
    if comps:
        for t in max(comps, key=len):
            main[t] = 1
    for i in range(M * M):
        if kind[i] and not main[i]:
            kind[i] = 0

    for b in buildings:
        ring = [(x, y) for x, y in perimeter(b) if inside(x, y)]
        if any(main[y * M + x] for x, y in ring):
            continue
        prev = {(x, y): None for x, y in ring if not solid[y * M + x] and terrain[y * M + x] != WATER}
        queue = deque(prev)
        goal = None
        while queue and goal is None:
            x, y = queue.popleft()
            if main[y * M + x]:
                goal = (x, y)
                break
            for _, dx, dy in DIRS:
                n = (x + dx, y + dy)
                if inside(*n) and n not in prev and not solid[n[1] * M + n[0]] and terrain[n[1] * M + n[0]] != WATER:
                    prev[n] = (x, y)
                    queue.append(n)
        while goal is not None:  # carve from the road back to the building
            i = goal[1] * M + goal[0]
            main[i] = 1
            kind[i] = kind[i] or 1
            goal = prev[goal]

    roads = bytearray(M * M)
    for i in range(M * M):
        if kind[i]:
            x, y = i % M, i // M
            conn = sum(
                bit for bit, dx, dy in DIRS if inside(x + dx, y + dy) and kind[(y + dy) * M + x + dx]
            )
            roads[i] = encode_road(ARTERIAL if kind[i] == 2 else LOCAL, conn or ISOLATED)
    return GeneratedMap(terrain, roads)
