# Deep Interview Spec: SQLAlchemy entities + BaseEntity + local DB auto-sync

## Metadata
- Interview ID: di-sqlalchemy-entities-20261111
- Rounds: 5 (+ Round 0 topology)
- Final Ambiguity Score: 14%
- Type: brownfield
- Generated: 2026-11-11
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED — pending approval

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.90 | 0.35 | 0.315 |
| Constraint Clarity | 0.85 | 0.25 | 0.2125 |
| Success Criteria | 0.80 | 0.25 | 0.20 |
| Context Clarity | 0.90 | 0.15 | 0.135 |
| **Total Clarity** | | | **0.8625** |
| **Ambiguity** | | | **0.1375** |

## Topology
| Component | Status | Description | Coverage |
|-----------|--------|-------------|----------|
| DB connection & session | active | `DATABASE_URL` setting, sync engine + `SessionLocal` + `get_db` | AC3, AC4 |
| BaseEntity | active | Abstract base: UUID `id`, `created_at`, `updated_at` | AC5 |
| Domain entities | active | 9 documented entities in `app/models/` | AC6, AC7 |
| Local DB auto-sync | active | On startup, `create_all` if enabled & reachable; warn otherwise | AC8, AC9 |
| accounts, transactions, ledger_entries, world_metrics, map_chunks | deferred | No attributes in docs (TBD) — wait for docs (user, Round 1) | — |
| alembic migrations | deferred | User: "마이그레이션 파일은 나중에" | — |

## Goal
Add SQLAlchemy 2.0 ORM models for the 9 entities whose attributes are defined in `docs/02-domain/`, all inheriting a shared `BaseEntity` (UUID id, created_at, updated_at), plus a sync PostgreSQL engine/session and an opt-in startup schema sync (`Base.metadata.create_all`) that never drops data and never blocks app startup.

## Constraints
- Paths: project root `/Users/ian/private/living_city`; backend at `backend/`. `.omc` only at `backend/.omc` (project directive).
- **Docs first** (CLAUDE.md): before code, update `docs/03-architecture/06-database.md` (BaseEntity, naming/type rules, the 9 implemented tables, 5 deferred tables, auto-sync behaviour) and `docs/04-development/02-backend-convention.md` (db/models layout, `DATABASE_URL`, `DB_AUTO_SYNC`, alembic still TBD).
- SQLAlchemy 2.0 typed (`Mapped`/`mapped_column`), **sync**, driver **psycopg v3** (`psycopg[binary]`). Add `sqlalchemy`, `psycopg[binary]` to `pyproject.toml` (via `uv add`) and `requirements.txt`.
- Settings: `DATABASE_URL` default `postgresql+psycopg://ian@localhost:5432/living_city`; `DB_AUTO_SYNC: bool` default `True`. Add both to `.env`.
- `app/db/base.py`: `Base(DeclarativeBase)` + abstract `BaseEntity(Base)` with `id: UUID` PK (`default=uuid.uuid4`, PG `UUID(as_uuid=True)`), `created_at`/`updated_at` `DateTime(timezone=True)`, `server_default=func.now()`, `updated_at` `onupdate=func.now()`.
- `app/db/session.py`: `engine` (`pool_pre_ping=True`), `SessionLocal`. `app/api/deps.py`: `get_db()` generator.
- Naming (user-confirmed at approval): Python attributes and DB columns snake_case — `id`, `created_at`, `updated_at` (NOT createdAt/updatedAt); class names PascalCase per PEP 8 (`BaseEntity`, `WorldPolicy`); table names as in 06-database.md (`worlds`, `buildings`, `citizens`, `households`, `companies`, `employments`, `world_policies`, `world_events`, `world_snapshots`).
- Enums stored as `String` (no native PG enum); allowed values from docs kept as Python `StrEnum` where docs list them (World.status, Building.type, Company.status).
- Money (`cash_balance`, `base_wage`, `operating_cost`, `salary`, `monthly_housing_cost`, `welfare_amount`) = `BigInteger` minor units. No floats for money.
- Every non-World entity has `world_id` FK → `worlds.id`, indexed. FKs per docs/02-domain/01-domain-overview.md relations. `Household.member_ids` is NOT a column; `citizens.household_id` back-reference.
- JSON-like attributes (`Citizen.skills`, `WorldEvent.payload`, `WorldSnapshot.state_data`) = `JSONB`.
- Uniques: `world_events (world_id, sequence)`, `world_snapshots (world_id, tick)`.
- `World.version` = SQLAlchemy `version_id_col` (optimistic concurrency per docs).
- `app/models/__init__.py` imports all models so `Base.metadata` is complete.
- Auto-sync in FastAPI `lifespan`: if `DB_AUTO_SYNC` → try `Base.metadata.create_all(engine)`; on `OperationalError` log a warning and continue. Never `drop_all`.
- `simulation_engine/` must not import SQLAlchemy (untouched).

## Non-Goals
- alembic setup / migration files.
- The 5 attribute-less tables.
- CRUD, schemas, services, endpoints for entities.
- Creating the `living_city` database (user will do it).
- Altering existing tables on model change (create_all creates missing tables only).

## Acceptance Criteria
- [ ] AC1: docs 06-database.md and 02-backend-convention.md updated before code with the rules above.
- [ ] AC2: `uv sync` succeeds with sqlalchemy + psycopg; `requirements.txt` mirrors runtime deps.
- [ ] AC3: `Settings` exposes `DATABASE_URL` and `DB_AUTO_SYNC` with the defaults above; `.env` contains both.
- [ ] AC4: `app/db/session.py` exposes `engine`, `SessionLocal`; `app/api/deps.py` exposes `get_db`.
- [ ] AC5: `BaseEntity` is abstract (no table) and every one of the 9 models subclasses it; each table has `id uuid PK`, `created_at`, `updated_at`.
- [ ] AC6: `Base.metadata.tables` contains exactly the 9 table names (test, no DB needed).
- [ ] AC7: Columns/FKs/uniques match the docs + constraints (test via metadata inspection: money columns BigInteger, JSONB columns, world_id FKs, the two unique constraints). DDL compiles for PostgreSQL dialect (`CreateTable(...).compile(dialect=postgresql.dialect())`).
- [ ] AC8: With DB unreachable, app starts, warning logged, `GET /api/v1/health` still 200 `{"status":"ok"}` (existing test passes).
- [ ] AC9: (manual, after user runs `createdb living_city`) app start creates the 9 tables; restart does not drop/alter data.
- [ ] AC10: `uv run pytest` passes.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|---|---|---|
| All 14 tables in docs | 5 have no attributes; CLAUDE.md forbids guessing TBD | Only 9; 5 deferred |
| "동기화" | create vs drop/recreate | create_all only, warn if unreachable |
| Async needed for FastAPI | sync vs async | Sync SQLAlchemy + psycopg |
| Default `postgres` role | Local PG 18 has role `ian`, no `postgres`, no `living_city` DB | URL uses `ian`; user creates DB |
| camelCase from docs | DB quoting cost | snake_case everywhere |

## Open Assumptions (types docs don't specify — surface at approval)
- `happiness`, `health`: Integer. `risk_tolerance`, `consumption_preference`: Float (not money). `age`, `speed`, `capacity`, tile/size fields: Integer. Ticks: BigInteger.
- Free-text status fields without listed values (`Building.status`, `Employment.status`, `Citizen.employment_status`, `current_activity`): `String(32)` without check constraint.
- `current_destination`: nullable FK → `buildings.id`. `employer_id`: nullable FK → `companies.id`. `WorldSnapshot.last_event_sequence`: BigInteger (no FK).
- Circular FKs (citizens↔households↔buildings, companies↔buildings) use `use_alter` where needed for create_all ordering.

## Technical Context
backend: FastAPI skeleton; `app/db/{base,session}.py`, `app/api/deps.py` are 1-line placeholders; `app/models/` empty; `app/core/config.py` has `Settings(PROJECT_NAME, API_V1_STR)`; tests/test_health.py exists. Local PostgreSQL 18 on localhost:5432, role `ian`.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|---|---|---|---|
| BaseEntity | supporting | id, created_at, updated_at | parent of all |
| World | core | name, seed, current_tick, speed, status, engine_version, version | owns all |
| Building | core | world_id, type, tile_x, tile_y, width, height, capacity, occupied_capacity, status | in World |
| Citizen | core | world_id, household_id, name, age, home/current_building_id, employment_status, employer_id, cash_balance, happiness, health, skills, risk_tolerance, consumption_preference, current_activity, current_destination, arrival_tick | Household, Building, Company |
| Household | core | world_id, residence_building_id, monthly_housing_cost | has many Citizens |
| Company | core | world_id, name, industry, building_id, cash_balance, employee_capacity, employee_count, base_wage, operating_cost, status | Building |
| Employment | core | world_id, citizen_id, company_id, salary, hired_tick, terminated_tick, status | Citizen–Company |
| WorldPolicy | core | world_id, income_tax_rate, welfare_amount, effective_tick, version | World |
| WorldEvent | supporting | world_id, sequence, tick, type, payload, schema_version | World |
| WorldSnapshot | supporting | world_id, tick, last_event_sequence, engine_version, state_data | World |

Note: `income_tax_rate` (15%) — stored as Integer basis points (1500) to avoid float; listed in Open Assumptions at approval.

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|---|---|---|---|---|---|
| 1 | 10 | 10 | - | - | - |
| 2–5 | 10 | 0 | 0 | 10 | 100% |

## Interview Transcript
<details><summary>Full Q&A (5 rounds)</summary>

- R0 Topology (DB/session, BaseEntity, entities, auto-sync; alembic deferred) → 맞음
- R1 Only 9 documented entities, defer 5 → 예 (40%)
- R2 Sync = create_all only, warn if unreachable → 예 (31%)
- R3 Sync SQLAlchemy + psycopg, DATABASE_URL → 예 (25%)
- R4 URL ian@localhost/living_city + createdb → "DB는 내가 만들게" (22%)
- R5 Modeling rules (snake_case, string enums, FK, BigInteger, JSONB) + docs first → 예 (14%)
</details>
