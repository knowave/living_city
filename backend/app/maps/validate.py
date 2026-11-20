from app.maps.generator import GeneratedMap, M, inside, perimeter
from app.maps.tiles import ARTERIAL, DIRS, ISOLATED, SAND, WATER
from app.simulation.interfaces import BuildingFootprint


class MapValidationError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_map(m: GeneratedMap, buildings: list[BuildingFootprint]) -> None:
    if len(m.terrain) != M * M or len(m.roads) != M * M:
        raise MapValidationError("bad map size")
    if max(m.terrain) > SAND:
        raise MapValidationError("terrain value out of range")
    for i, v in enumerate(m.roads):
        if v and ((v >> 5) > ARTERIAL or not 1 <= (v & 31) <= ISOLATED):
            raise MapValidationError(f"road value out of range at {i % M},{i // M}")

    for b in buildings:
        if not (inside(b.tile_x, b.tile_y) and inside(b.tile_x + b.width - 1, b.tile_y + b.height - 1)):
            raise MapValidationError(f"building {b.engine_id} outside the map")
        for y in range(b.tile_y, b.tile_y + b.height):
            for x in range(b.tile_x, b.tile_x + b.width):
                if m.roads[y * M + x] or m.terrain[y * M + x] == WATER:
                    raise MapValidationError(f"road or water on building {b.engine_id}")

    for i, v in enumerate(m.roads):  # conn bits must match actual neighbours
        if v:
            x, y = i % M, i // M
            want = sum(bit for bit, dx, dy in DIRS if inside(x + dx, y + dy) and m.roads[(y + dy) * M + x + dx])
            if (v & 31) != (want or ISOLATED):
                raise MapValidationError(f"conn mismatch at {x},{y}")

    entrances = []
    for b in buildings:
        e = next(((x, y) for x, y in perimeter(b) if inside(x, y) and m.roads[y * M + x]), None)
        if e is None:
            raise MapValidationError(f"building {b.engine_id} has no entrance")
        entrances.append(e)
    if not entrances:
        return
    start = entrances[0]
    seen, stack = {start}, [start]
    while stack:
        x, y = stack.pop()
        for _, dx, dy in DIRS:
            n = (x + dx, y + dy)
            if n not in seen and inside(*n) and m.roads[n[1] * M + n[0]]:
                seen.add(n)
                stack.append(n)
    if any(e not in seen for e in entrances):
        raise MapValidationError("entrances are not in one road component")
