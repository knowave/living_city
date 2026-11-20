"""Read API against real PostgreSQL: AC4/AC5 (HTTP), map-building consistency, AC6/AC11 consistency, pagination.

/view MOVING semantics (engine systems/movement.py): start_move emits start_tick=T (tick being processed),
arrival_tick=T+ceil(dist/speed) >= T+1; arrival is handled when ctx.tick == arrival_tick. World.current_tick
is the count of completed ticks (after a commit to N, the last processed ctx.tick is N-1), so a citizen is
still MOVING at as_of_tick N iff start_tick < N <= arrival_tick.
"""

import concurrent.futures as cf
import time
from collections import deque

import pytest
from sqlalchemy import text

from app.maps.generator import perimeter
from app.maps.tiles import CHUNK_SIZE, CHUNKS_PER_SIDE, MAP_SIZE, WATER
from app.simulation.interfaces import BuildingFootprint
from tests.integration.conftest import http_pause
from tests.integration.live import live_client, running_world  # noqa: F401  (fixtures)

pytestmark = pytest.mark.integration

BUILDING_DTO_KEYS = {"id", "world_id", "type", "tile_x", "tile_y", "width", "height",
                     "capacity", "occupied_capacity", "status"}
CHUNK_DTO_KEYS = {"id", "world_id", "chunk_x", "chunk_y", "chunk_size", "terrain_tiles", "road_tiles",
                  "schema_version", "revision"}


@pytest.fixture
def wid(client):
    return client.post("/api/v1/worlds", json={"name": "c", "seed": 21}).json()["id"]


def base(wid):
    return f"/api/v1/worlds/{wid}"


# ---------- AC4 / AC5 via HTTP ----------
def test_map_meta_matches_contract(client, wid):
    assert client.get(f"{base(wid)}/map").json() == {
        "width": 512, "height": 512, "chunk_size": 32, "chunks_x": 16, "chunks_y": 16,
        "tile_schema_version": 1, "engine_area": {"x": 0, "y": 0, "width": 128, "height": 128},
    }


def test_chunks_without_range_returns_all_256_with_1024_tiles(client, wid):
    chunks = client.get(f"{base(wid)}/chunks").json()
    assert len(chunks) == 256
    assert {(c["chunk_x"], c["chunk_y"]) for c in chunks} == {(x, y) for x in range(16) for y in range(16)}
    assert all(len(c["terrain_tiles"]) == 1024 and len(c["road_tiles"]) == 1024 for c in chunks)
    assert all(set(c) == CHUNK_DTO_KEYS for c in chunks)


def test_chunks_range_returns_only_requested_subset(client, wid):
    got = client.get(f"{base(wid)}/chunks?x_min=2&x_max=4&y_min=5&y_max=6").json()
    assert {(c["chunk_x"], c["chunk_y"]) for c in got} == {(x, y) for x in (2, 3, 4) for y in (5, 6)}


def test_buildings_are_21_with_keys_equal_to_frontend_dto(client, wid):
    blds = client.get(f"{base(wid)}/buildings").json()
    assert len(blds) == 21
    assert all(set(b) == BUILDING_DTO_KEYS for b in blds)


@pytest.mark.parametrize("qx", [(30, 31), (32, 32)])  # one side of the boundary each
def test_building_straddling_chunk_boundary_is_found_from_either_side(client, wid, session_factory, qx):
    b = client.get(f"{base(wid)}/buildings").json()[0]
    s = session_factory()
    s.execute(text("UPDATE buildings SET tile_x=31 WHERE id=:i"), {"i": b["id"]})  # covers x=31..32
    s.commit()
    y = b["tile_y"]
    got = client.get(f"{base(wid)}/buildings?x_min={qx[0]}&x_max={qx[1]}&y_min={y}&y_max={y}").json()
    assert b["id"] in {x["id"] for x in got}


# ---------- map-building consistency on stored data ----------
def test_stored_map_has_entrances_in_one_road_component_and_no_road_or_water_under_buildings(client, wid):
    roads = bytearray(MAP_SIZE * MAP_SIZE)
    terrain = bytearray(MAP_SIZE * MAP_SIZE)
    for c in client.get(f"{base(wid)}/chunks").json():
        for i in range(CHUNK_SIZE * CHUNK_SIZE):
            x = c["chunk_x"] * CHUNK_SIZE + i % CHUNK_SIZE
            y = c["chunk_y"] * CHUNK_SIZE + i // CHUNK_SIZE
            roads[y * MAP_SIZE + x] = c["road_tiles"][i]
            terrain[y * MAP_SIZE + x] = c["terrain_tiles"][i]

    def inside(x, y):
        return 0 <= x < MAP_SIZE and 0 <= y < MAP_SIZE

    entrances = []
    for b in client.get(f"{base(wid)}/buildings").json():
        for y in range(b["tile_y"], b["tile_y"] + b["height"]):
            for x in range(b["tile_x"], b["tile_x"] + b["width"]):
                assert roads[y * MAP_SIZE + x] == 0 and terrain[y * MAP_SIZE + x] != WATER
        fp = BuildingFootprint(b["id"], b["tile_x"], b["tile_y"], b["width"], b["height"])
        e = next(((x, y) for x, y in perimeter(fp) if inside(x, y) and roads[y * MAP_SIZE + x]), None)
        assert e is not None, f"no entrance for {b['id']}"
        entrances.append(e)

    seen, q = {entrances[0]}, deque([entrances[0]])
    while q:
        x, y = q.popleft()
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            n = (x + dx, y + dy)
            if n not in seen and inside(*n) and roads[n[1] * MAP_SIZE + n[0]]:
                seen.add(n)
                q.append(n)
    assert all(e in seen for e in entrances)


# ---------- pagination boundaries ----------
@pytest.mark.parametrize("limit", [1, 7, 99, 100, 101, 500])
def test_citizens_limit_returns_min_of_limit_and_total(client, wid, limit):
    p = client.get(f"{base(wid)}/citizens?limit={limit}").json()
    assert (len(p["items"]), p["limit"]) == (min(limit, p["total"]), limit)


def test_citizens_offset_beyond_total_returns_empty_items_with_total(client, wid):
    total = client.get(f"{base(wid)}/citizens").json()["total"]
    p = client.get(f"{base(wid)}/citizens?offset={total + 50}").json()
    assert p["items"] == [] and p["total"] == total and p["offset"] == total + 50


def test_citizens_last_page_is_partial(client, wid):
    total = client.get(f"{base(wid)}/citizens").json()["total"]
    p = client.get(f"{base(wid)}/citizens?limit=30&offset={total - 5}").json()
    assert len(p["items"]) == 5


@pytest.mark.parametrize("path", ["citizens", "companies"])
@pytest.mark.parametrize("bad", ["limit=0", "limit=501", "offset=-1"])
def test_invalid_pagination_params_return_422(client, wid, path, bad):
    assert client.get(f"{base(wid)}/{path}?{bad}").status_code == 422


# ---------- AC11 PAUSED ----------
def test_paused_world_view_is_identical_across_calls(client, wid):
    http_pause(client, wid)
    a = client.get(f"{base(wid)}/view").json()
    time.sleep(0.2)
    b = client.get(f"{base(wid)}/view").json()
    assert a == b and a["as_of_tick"] == b["as_of_tick"]


# ---------- AC6 / AC11 with a running Runner ----------
def assert_view_consistent(v):
    t = v["as_of_tick"]
    assert len(v["citizens"]) == 100
    assert v["world"]["current_tick"] == t and v["world"]["event_cursor"] == v["event_cursor"]
    for c in v["citizens"]:
        if c["current_activity"] == "MOVING":
            m = c["movement"]
            assert m is not None
            assert m["start_tick"] < t <= m["arrival_tick"], (t, m)
            assert c["arrival_tick"] == m["arrival_tick"]
        else:
            assert c["movement"] is None


def test_view_is_internally_consistent_while_runner_advances(live_client, running_world):
    by_cursor, ticks, saw_moving = {}, [], False
    for _ in range(60):
        r = live_client.get(f"{base(running_world)}/view")
        assert r.status_code == 200
        v = r.json()
        assert_view_consistent(v)
        saw_moving |= any(c["movement"] for c in v["citizens"])
        ticks.append(v["as_of_tick"])
        prev = by_cursor.setdefault(v["event_cursor"], v)
        assert prev == v, "same event_cursor must give identical payload"
    assert ticks == sorted(ticks) and ticks[-1] > ticks[0], "runner should have advanced"


def test_concurrent_reads_while_runner_advances_never_fail(live_client, running_world):
    b = base(running_world)

    def call(i):
        path = ("/view", "/citizens?limit=50", "/companies", "/summary")[i % 4]
        return live_client.get(b + path).status_code

    with cf.ThreadPoolExecutor(50) as ex:
        codes = list(ex.map(call, range(100)))
    assert set(codes) == {200}
