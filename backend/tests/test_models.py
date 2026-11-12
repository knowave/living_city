from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, CheckConstraint, Numeric, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

import app.models  # noqa: F401
from app.models import Transaction
from app.db.base import Base, BaseEntity
from app.main import app

TABLES = {
    "worlds", "buildings", "citizens", "households", "companies", "employments",
    "world_policies", "world_events", "world_snapshots",
    "accounts", "transactions", "ledger_entries", "world_metrics", "map_chunks",
}
MONEY = {"base_wage", "operating_cost", "salary", "monthly_housing_cost", "welfare_amount", "balance", "amount"}
JSON_COLS = {"skills", "payload", "state_data", "terrain_tiles", "road_tiles"}
PG = postgresql.dialect()


def _t(n):
    return Base.metadata.tables[n]


def _uniques(t):
    return {u.name: tuple(c.name for c in u.columns) for u in t.constraints if isinstance(u, UniqueConstraint)}


def test_tables():
    assert set(Base.metadata.tables) == TABLES
    assert not hasattr(BaseEntity, "__table__")
    assert not any("cash_balance" in t.c for t in Base.metadata.tables.values())


def test_base_columns_and_types():
    for t in Base.metadata.tables.values():
        assert t.c.id.primary_key
        assert "created_at" in t.c and "updated_at" in t.c
        for c in t.c:
            if c.name in MONEY:
                assert isinstance(c.type, BigInteger)
            if c.name in JSON_COLS:
                assert isinstance(c.type, postgresql.JSONB)


def test_world_fk_and_unique_world_id_id():
    for name, t in Base.metadata.tables.items():
        if name == "worlds":
            continue
        assert ("world_id", "id") in _uniques(t).values(), name
        fks = [fk for fk in t.c.world_id.foreign_keys if fk.constraint.columns.keys() == ["world_id"]]
        assert [fk.target_fullname for fk in fks] == ["worlds.id"], name
        assert fks[0].ondelete == "RESTRICT", name


def test_inter_entity_fks_are_composite():
    seen = 0
    for name, t in Base.metadata.tables.items():
        for fk in t.foreign_key_constraints:
            cols = [c.name for c in fk.columns]
            if cols == ["world_id"]:
                continue
            seen += 1
            assert len(cols) == 2 and cols[0] == "world_id", (name, cols)
            tgt = {e.target_fullname.split(".", 1)[1] for e in fk.elements}
            assert tgt == {"world_id", "id"}, (name, cols)
            assert len({e.column.table.name for e in fk.elements}) == 1
            assert fk.ondelete == "RESTRICT", (name, cols)
    assert seen == 15


def test_unique_constraints():
    assert ("world_id", "sequence") in _uniques(_t("world_events")).values()
    assert ("world_id", "tick") in _uniques(_t("world_snapshots")).values()


def test_accounts():
    t = _t("accounts")
    names = {c.name for c in t.constraints if isinstance(c, CheckConstraint)}
    assert {"ck_accounts_owner", "ck_accounts_balance_non_negative"} <= names
    idx = {i.name: i for i in t.indexes}
    u = _uniques(t)
    named = set(idx) | set(u)
    assert {
        "uq_accounts_world_id_id", "idx_accounts_world", "idx_accounts_citizen", "idx_accounts_household",
        "idx_accounts_company", "uq_accounts_citizen", "uq_accounts_household", "uq_accounts_company",
        "uq_accounts_government", "uq_accounts_system",
    } <= named
    for x in ("citizen", "household", "company"):
        for p in ("idx", "uq"):
            i = idx[f"{p}_accounts_{x}"]
            assert f"{x}_id IS NOT NULL" in str(i.dialect_options["postgresql"]["where"])
    assert idx["uq_accounts_citizen"].unique
    for x in ("government", "system"):
        i = idx[f"uq_accounts_{x}"]
        assert i.unique and f"'{x.upper()}'" in str(i.dialect_options["postgresql"]["where"])


def test_transactions():
    t = _t("transactions")
    assert "metadata" in t.c
    assert Transaction.metadata_.property.columns[0].name == "metadata"
    i = {i.name: i for i in t.indexes}["uq_transactions_reversal"]
    assert i.unique and "reverses_transaction_id IS NOT NULL" in str(i.dialect_options["postgresql"]["where"])


def test_ledger_entries():
    t = _t("ledger_entries")
    assert any(isinstance(c, CheckConstraint) and "amount <> 0" in str(c.sqltext) for c in t.constraints)


def test_world_metrics_and_map_chunks():
    c = _t("world_metrics").c.metric_value.type
    assert isinstance(c, Numeric) and (c.precision, c.scale) == (24, 6)
    m = _t("map_chunks")
    assert sum(isinstance(c, CheckConstraint) for c in m.constraints) == 9
    assert _uniques(m)["uq_map_chunks_position"] == ("world_id", "chunk_x", "chunk_y")


def test_ddl_compiles():
    for t in Base.metadata.tables.values():
        CreateTable(t).compile(dialect=PG)
        for i in t.indexes:
            CreateIndex(i).compile(dialect=PG)


def test_health_with_unreachable_db(monkeypatch):
    from sqlalchemy import create_engine

    monkeypatch.setattr("app.db.session.engine", create_engine("postgresql+psycopg://x@127.0.0.1:1/x"))
    with TestClient(app) as c:
        r = c.get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def _checks(t):
    return {c.name: str(c.sqltext) for c in t.constraints if isinstance(c, CheckConstraint)}


def test_proposed_constraints():
    e = _t("employments")
    idx = {i.name: i for i in e.indexes}["uq_employments_world_citizen_active"]
    assert idx.unique and [c.name for c in idx.columns] == ["world_id", "citizen_id"]
    assert "WHERE terminated_tick IS NULL" in str(CreateIndex(idx).compile(dialect=PG))
    assert _checks(e)["ck_employments_status_terminated"] == "(status = 'ACTIVE') = (terminated_tick IS NULL)"
    p = _t("world_policies")
    u = _uniques(p)
    assert u["uq_world_policies_world_id_effective_tick"] == ("world_id", "effective_tick")
    assert u["uq_world_policies_world_id_version"] == ("world_id", "version")
    ck = _checks(p)
    assert ck["ck_world_policies_income_tax_rate_range"] == "income_tax_rate BETWEEN 0 AND 10000"
    assert ck["ck_world_policies_welfare_amount_non_negative"] == "welfare_amount >= 0"
    assert _checks(_t("companies"))["ck_companies_employee_count_range"] == "employee_count BETWEEN 0 AND employee_capacity"
