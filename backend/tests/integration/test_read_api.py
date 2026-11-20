import pytest
from sqlalchemy import select, text

from app.models import Citizen, WorldEvent
from app.repositories.sqlalchemy import SqlAlchemyUnitOfWork
from tests.integration.conftest import http_pause

pytestmark = pytest.mark.integration


@pytest.fixture
def wid(client):
    return client.post("/api/v1/worlds", json={"name": "r", "seed": 11}).json()["id"]


def test_read_endpoints_against_real_db(client, wid):
    base = f"/api/v1/worlds/{wid}"
    assert client.get(f"{base}/map").json()["width"] == 512

    p = client.get(f"{base}/citizens?limit=5").json()
    assert len(p["items"]) == 5 and p["total"] >= 5 and p["limit"] == 5
    assert (p["as_of_tick"], p["event_cursor"]) == (0, p["event_cursor"])
    assert p["items"][0]["cash_balance"] is not None
    one = client.get(f"{base}/citizens/{p['items'][0]['id']}").json()
    assert one["movement"] is None and "as_of_tick" in one

    cos = client.get(f"{base}/companies?limit=2").json()
    cid = cos["items"][0]["id"]
    d = client.get(f"{base}/companies/{cid}").json()
    emp = client.get(f"{base}/companies/{cid}/employees").json()
    assert d["active_employees"] == emp["total"]

    blds = client.get(f"{base}/buildings").json()
    assert blds and client.get(f"{base}/buildings/{blds[0]['id']}").json()["company_ids"] is not None
    b = blds[0]
    near = client.get(f"{base}/buildings?x_min={b['tile_x']}&x_max={b['tile_x']}&y_min={b['tile_y']}&y_max={b['tile_y']}").json()
    assert b["id"] in {x["id"] for x in near}

    s = client.get(f"{base}/summary").json()
    assert s["population"] == client.get(f"{base}/citizens").json()["total"]
    assert s["city_internal_money"] > 0 and s["government_treasury"] > 0

    v = client.get(f"{base}/view").json()
    assert len(v["citizens"]) == s["population"] and v["world"]["world_id"] == wid

    for bad in ("limit=0", "limit=501", "offset=-1"):
        assert client.get(f"{base}/citizens?{bad}").status_code == 422
    assert client.get(f"{base}/buildings/00000000-0000-0000-0000-000000000000").json()["error"]["code"] == "BUILDING_NOT_FOUND"


def test_movement_from_latest_started_event_only_for_moving(client, wid, session_factory):
    s = session_factory()
    cit = s.scalars(select(Citizen).where(Citizen.world_id == wid)).first()
    cit.current_activity = "MOVING"
    seq = s.scalar(text("select coalesce(max(sequence),0) from world_events where world_id=:w"), {"w": wid})
    for i, (a, b) in enumerate([("old", "x"), ("new", "y")], start=1):
        s.add(WorldEvent(world_id=wid, sequence=seq + i, tick=i, type="citizen.movement.started",
                         payload={"citizen_id": str(cit.id), "from_building_id": str(cit.home_building_id),
                                  "to_building_id": str(cit.home_building_id), "start_tick": i, "arrival_tick": i + 5}))
    s.commit()
    got = client.get(f"/api/v1/worlds/{wid}/citizens/{cit.id}").json()
    assert got["movement"]["start_tick"] == 2


def test_begin_consistent_read_sets_repeatable_read(session_factory, wid):
    s = session_factory()
    SqlAlchemyUnitOfWork(s).begin_consistent_read()
    assert s.scalar(text("show transaction_isolation")) == "repeatable read"
