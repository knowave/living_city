import pytest
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.generator import generate_world

from app.maps.generator import M, generate_map
from app.maps.tiles import DIRS, ISOLATED
from app.maps.validate import MapValidationError, validate_map
from app.simulation.interfaces import BuildingFootprint
from tests.maps.helpers import BLOCKED

SEEDS = range(1, 26)


def footprints(seed):
    st = generate_world(seed, SimulationConfig(), name="t").state
    return [BuildingFootprint(str(b.id), b.tile_x, b.tile_y, b.width, b.height) for b in st.buildings.values()]


@pytest.fixture(scope="module")
def cases():
    return {s: footprints(s) for s in SEEDS}


def test_deterministic_and_seed_dependent(cases):
    a, b = generate_map(1, cases[1]), generate_map(1, cases[1])
    assert a.terrain == b.terrain and a.roads == b.roads
    c = generate_map(2, cases[1])
    assert (a.terrain, a.roads) != (c.terrain, c.roads)


def test_valid_for_many_seeds(cases):
    for s, bs in cases.items():
        validate_map(generate_map(s, bs), bs)


def test_properties_and_chunks(cases):
    bs = cases[3]
    m = generate_map(3, bs)
    assert max(m.terrain) <= 2
    for b in bs:
        tiles = [(x, y) for y in range(b.tile_y, b.tile_y + b.height) for x in range(b.tile_x, b.tile_x + b.width)]
        assert all(m.roads[y * M + x] == 0 and m.terrain[y * M + x] != 1 for x, y in tiles)
    for i, v in enumerate(m.roads):
        if v:
            x, y = i % M, i // M
            want = sum(bit for bit, dx, dy in DIRS if 0 <= x + dx < M and 0 <= y + dy < M and m.roads[(y + dy) * M + x + dx])
            assert v & 31 == (want or ISOLATED)
    chunks = m.chunks()
    assert len(chunks) == 256 and len({(c.chunk_x, c.chunk_y) for c in chunks}) == 256
    assert all(len(c.terrain_tiles) == 1024 and len(c.road_tiles) == 1024 for c in chunks)
    c = chunks[1 * 16 + 2]  # chunk (2, 1)
    assert c.road_tiles[5 * 32 + 7] == m.roads[(32 + 5) * M + 64 + 7]


def test_blocked_building_fails_validation():
    with pytest.raises(MapValidationError, match="no entrance"):
        validate_map(generate_map(1, BLOCKED), BLOCKED)


def test_corrupted_conn_fails_validation(cases):
    m = generate_map(1, cases[1])
    i = next(i for i, v in enumerate(m.roads) if v)
    m.roads[i] ^= 1
    with pytest.raises(MapValidationError):
        validate_map(m, cases[1])
