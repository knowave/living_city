from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.repositories.sqlalchemy.engine_mapper import db_id, entity_rows
from app.simulation.engine_adapter import EngineRaw, SimulationEngineAdapter


@pytest.fixture(scope="module")
def batch():
    return SimulationEngineAdapter().generate(42, "t")


def rows(batch, world_id):
    return entity_rows(world_id, batch.raw, list(batch.raw.state.policies.values()))


def test_db_id_deterministic_and_world_scoped():
    w1, w2, e = uuid4(), uuid4(), uuid4()
    assert db_id(w1, e) == db_id(w1, e)
    assert db_id(w1, e) != db_id(w2, e)


def test_row_counts(batch):
    r = rows(batch, uuid4())
    assert len(r["buildings"]) == 21
    assert len(r["citizens"]) == 100
    assert len(r["companies"]) == 10
    assert len(r["world_snapshots"]) == 1
    assert len(r["transactions"]) == 111
    assert {t["transaction_type"] for t in r["transactions"]} == {"OPENING_BALANCE"}


def test_ids_differ_across_worlds_and_fks_consistent(batch):
    w1, w2 = uuid4(), uuid4()
    r1, r2 = rows(batch, w1), rows(batch, w2)
    assert not {x["id"] for x in r1["citizens"]} & {x["id"] for x in r2["citizens"]}
    ids = {t: {x["id"] for x in r1[t]} for t in ("buildings", "households", "companies", "citizens", "accounts", "transactions")}
    assert all(x["world_id"] == w1 for x in r1["citizens"])
    for c in r1["citizens"]:
        assert c["household_id"] in ids["households"]
        assert c["home_building_id"] in ids["buildings"]
        assert c["employer_id"] is None or c["employer_id"] in ids["companies"]
    for co in r1["companies"]:
        assert co["building_id"] in ids["buildings"]
    for le in r1["ledger_entries"]:
        assert le["transaction_id"] in ids["transactions"]
        assert le["account_id"] in ids["accounts"]
    for e in r1["employments"]:
        assert e["citizen_id"] in ids["citizens"] and e["company_id"] in ids["companies"]


def test_float_enum_and_snapshot(batch):
    r = rows(batch, uuid4())
    raw: EngineRaw = batch.raw
    first = raw.state.ordered("citizens")[0]
    c = next(x for x in r["citizens"] if x["id"] == db_id(r["citizens"][0]["world_id"], first.id))
    assert c["risk_tolerance"] == first.risk_tolerance / 10000 and isinstance(c["risk_tolerance"], float)
    assert all(isinstance(a["owner_type"], str) for a in r["accounts"])
    assert r["world_snapshots"][0]["state_data"] is batch.snapshot_state_data  # untouched
    assert {t["idempotency_key"] for t in r["transactions"]} == {t.idempotency_key for t in raw.transactions}


def test_payload_remap_and_metric_quantize():
    w = uuid4()
    b = SimulationEngineAdapter().advance(
        SimulationEngineAdapter().generate(42, "t").snapshot_state_data, [], 720
    )
    r = entity_rows(w, b.raw, [])
    citizen_ids = {x.id for x in b.raw.state.ordered("citizens")}
    remapped = [e for e in r["world_events"] if "citizen_id" in e["payload"]]
    assert remapped
    for e in remapped:
        assert UUID(e["payload"]["citizen_id"]) in {db_id(w, i) for i in citizen_ids}
    assert r["world_metrics"]
    assert all(m["metric_value"] == m["metric_value"].quantize(Decimal("0.000001")) for m in r["world_metrics"])
