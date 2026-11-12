# Deep Interview Spec: accounts / transactions / ledger_entries / world_metrics / map_chunks

## Metadata
- Interview ID: di-economy-map-entities-20261111
- Rounds: 4 (+ Round 0 topology)
- Final Ambiguity Score: 13%
- Type: brownfield
- Generated: 2026-11-11
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: yes (user's full schema paste is the source; the binding parts are restated below)
- Status: PASSED — pending approval

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| Goal | 0.90 | 0.35 | 0.315 |
| Constraints | 0.85 | 0.25 | 0.2125 |
| Success Criteria | 0.82 | 0.25 | 0.205 |
| Context | 0.90 | 0.15 | 0.135 |
| **Ambiguity** | | | **0.1325** |

## Topology
| Component | Status | Coverage |
|---|---|---|
| Economy ledger entities (accounts, transactions, ledger_entries) | active | AC3–AC6 |
| Metrics & map entities (world_metrics, map_chunks) | active | AC7, AC8 |
| Existing-entity alignment (drop cash_balance, UNIQUE(world_id,id), composite FKs) | active | AC2, AC9 |
| Docs update (TBD/미구현 → defined) | active | AC1 |
| Alembic migrations | deferred (user: "마이그레이션 생성하지 말고") | — |
| DB triggers (ledger sum = 0, ledger immutability) | deferred (Round 4: add with alembic) | — |

## Goal
Add SQLAlchemy models for the 5 remaining tables exactly per the user's schema, align the 9 existing models (single balance source, cross-world-safe composite FKs), and update the docs that mark these tables as TBD/미구현. No migrations, no triggers.

## Constraints
### Global
- All 5 new models inherit `BaseEntity` (id UUID, created_at, updated_at) — including transactions / ledger_entries / world_metrics (Round 2; updated_at extra vs user schema, accepted).
- snake_case attrs/columns; money BIGINT minor units (KRW); enums stored as String with Python `StrEnum` for listed values (no CHECK IN — existing rule; see Open Assumptions).
- Every world-scoped table (all except `worlds`, 13 total) gets `UniqueConstraint("world_id", "id", name="uq_<table>_world_id_id")`.
- Every FK between world-scoped tables is a composite `ForeignKeyConstraint(["world_id", "<x>_id"], ["<target>.world_id", "<target>.id"], ondelete="RESTRICT")`. `world_id` FKs → `worlds.id` stay single-column, `ondelete="RESTRICT"`. Nullable composite FKs rely on MATCH SIMPLE (NULL → not checked).
  - Existing to convert: citizens→households, buildings(home, current, current_destination), companies(employer); households→buildings(residence); companies→buildings; employments→citizens, companies.
- Remove `cash_balance` from `Citizen` and `Company` models (Round 1). Balance source = `accounts.balance`.
- `transactions.metadata` column: Python attr `metadata_ = mapped_column("metadata", JSONB, ...)` (reserved name in declarative).
- Partial indexes via `Index(..., postgresql_where=text(...))`; DESC indexes via `column.desc()`.

### accounts
Columns: world_id (FK worlds), owner_type String(16) (CITIZEN|HOUSEHOLD|COMPANY|GOVERNMENT|SYSTEM), citizen_id / household_id / company_id nullable (composite FKs), account_type String(16) default CASH (CASH|SAVINGS|TREASURY|ISSUANCE), currency CHAR(3) default 'KRW', balance BigInteger default 0, is_active Boolean default true. Defaults set as both Python `default` and `server_default`.
CHECKs:
- `ck_accounts_owner`: owner_type='CITIZEN' ⇒ only citizen_id NOT NULL; 'HOUSEHOLD' ⇒ only household_id; 'COMPANY' ⇒ only company_id; 'GOVERNMENT'/'SYSTEM' ⇒ all three NULL.
- `ck_accounts_balance_non_negative`: `balance >= 0 OR (owner_type = 'SYSTEM' AND account_type = 'ISSUANCE')`.
Indexes: idx_accounts_world; idx_accounts_citizen/household/company (partial WHERE x IS NOT NULL); uq_accounts_citizen/household/company (unique partial on (world_id, x_id, account_type, currency)); uq_accounts_government / uq_accounts_system (unique partial on (world_id, account_type, currency) WHERE owner_type = ...). Plus uq_accounts_world_id_id.

### transactions
Columns: world_id, transaction_type String(32) (StrEnum: OPENING_BALANCE, SALARY, PURCHASE, INCOME_TAX, RENT, WELFARE, ACCOUNT_TRANSFER, CAPITAL_INVESTMENT, ADJUSTMENT, REVERSAL), tick BigInteger, idempotency_key String(180), description Text nullable, reverses_transaction_id nullable (composite self-FK (world_id, reverses_transaction_id) → transactions(world_id, id)), metadata JSONB NOT NULL default {} (server_default `'{}'::jsonb`).
Indexes: uq_transactions_idempotency (world_id, idempotency_key) unique; idx_transactions_world_tick (world_id, tick DESC); idx_transactions_type_tick (world_id, transaction_type, tick DESC); uq_transactions_reversal unique partial (world_id, reverses_transaction_id) WHERE NOT NULL; uq_transactions_world_id_id.

### ledger_entries
Columns: world_id, transaction_id (composite FK → transactions(world_id,id)), account_id (composite FK → accounts(world_id,id)), entry_no SmallInteger, amount BigInteger.
CHECK `ck_ledger_entries_amount_non_zero`: amount <> 0. CHECK entry_no >= 1 (assumption).
Indexes: uq_ledger_transaction_entry (transaction_id, entry_no); uq_ledger_transaction_account (transaction_id, account_id); idx_ledger_account_created (account_id, created_at DESC); idx_ledger_world_transaction (world_id, transaction_id); uq_ledger_entries_world_id_id.

### world_metrics
Columns: world_id, tick BigInteger, metric_code String(64) (StrEnum of the 12 codes: POPULATION, EMPLOYED_POPULATION, UNEMPLOYMENT_RATE, AVERAGE_SALARY, AVERAGE_WEALTH, TOTAL_CONSUMPTION, TOTAL_COMPANY_REVENUE, ACTIVE_COMPANIES, BANKRUPT_COMPANIES, GOVERNMENT_REVENUE, GOVERNMENT_EXPENDITURE, AVERAGE_HAPPINESS), metric_value Numeric(24,6) (Python Decimal — not money), unit String(20) (COUNT|KRW|PERCENT|RATIO|INDEX), period String(10) (HOURLY|DAILY|MONTHLY), definition_version Integer default 1.
Indexes: uq_world_metrics (world_id, tick, metric_code, period); idx_world_metrics_chart (world_id, metric_code, period, tick DESC); uq_world_metrics_world_id_id.

### map_chunks
Columns: world_id, chunk_x Integer, chunk_y Integer, chunk_size SmallInteger default 32, terrain_tiles JSONB, road_tiles JSONB, schema_version Integer default 1, revision Integer default 1.
CHECKs (all 9 from user): chunk_x>=0, chunk_y>=0, chunk_size=32, schema_version>=1, revision>=1, jsonb_typeof(terrain_tiles)='array', jsonb_typeof(road_tiles)='array', jsonb_array_length(terrain_tiles)=1024, jsonb_array_length(road_tiles)=1024. Tile index = local_y*32 + local_x (docs).
Index: uq_map_chunks_position (world_id, chunk_x, chunk_y); uq_map_chunks_world_id_id. No FK from buildings.

### Docs (update before code — CLAUDE.md)
- docs/03-architecture/06-database.md: remove "속성 TBD, 미구현" for the 5 tables; add their schemas (columns, constraints, indexes), composite FK rule, (world_id,id) uniques, RESTRICT delete policy, balance single source, deferred triggers + service rules (sum = 0 per transaction, ≥2 entries, immutable ledger/transactions, reversal by REVERSAL transaction, ledger insert + balance update in one DB transaction, insufficient balance fails whole transaction).
- docs/02-domain/06-economy.md: Account/Transaction/LedgerEntry definitions, SYSTEM/ISSUANCE + OPENING_BALANCE for initial capital, salary example ledger, metric code list (calculation formulas: TBD).
- docs/02-domain/03-citizen.md, 04-business.md: cashBalance → "잔액은 accounts(CASH)에서 조회" (no column).
- docs/03-architecture/04-map-rendering.md: map_chunks storage (32×32 JSONB arrays, 1024 elements, index formula, buildings not FK'd to chunks).

## Non-Goals
- Alembic setup / migration files.
- DB triggers (sum-zero, immutability) — documented as service rules only.
- Services, CRUD, schemas, endpoints; metric calculation formulas.
- Altering an existing local DB (create_all won't alter; user must drop tables if they exist).

## Acceptance Criteria
- [ ] AC1: docs above updated before code; no "속성 TBD, 미구현" remains for the 5 tables.
- [ ] AC2: `cash_balance` gone from Citizen/Company models, docs, tests.
- [ ] AC3: `Base.metadata.tables` has the 14 tables; all 5 new models subclass BaseEntity.
- [ ] AC4: accounts CHECKs (owner combo, balance) and all 9 named indexes/uniques present with correct partial WHERE.
- [ ] AC5: transactions indexes (incl. DESC, partial reversal unique), composite self-FK, `metadata` column name with `metadata_` attr.
- [ ] AC6: ledger_entries composite FKs to transactions & accounts, amount<>0 CHECK, 4 indexes.
- [ ] AC7: world_metrics Numeric(24,6), unique + chart index.
- [ ] AC8: map_chunks 9 CHECKs + position unique.
- [ ] AC9: all 13 world-scoped tables have UNIQUE(world_id,id); every inter-entity FK is composite with ondelete RESTRICT.
- [ ] AC10: every table's `CreateTable` and every `CreateIndex` compiles for the PostgreSQL dialect; `uv run pytest` passes (tests updated/added; no DB required).
- [ ] AC11: (manual, after user's `createdb living_city`) app start creates all 14 tables without error.

## Open Assumptions (surface at approval)
- Enum-valued String columns (owner_type, account_type, transaction_type, metric_code, unit, period) get NO `CHECK IN (...)` — consistent with existing rule; owner_type is still bounded by `ck_accounts_owner`.
- `entry_no >= 1` CHECK added (not in user schema).
- `period = HOURLY` kept although 1 Tick = 1 day (per user schema).
- `currency` CHAR(3) default 'KRW'; no currency table.

## Assumptions Exposed & Resolved
| Assumption | Resolution |
|---|---|
| Existing cash_balance kept | Dropped; accounts.balance only (R1) |
| Immutable tables need own base | Inherit BaseEntity anyway (R2) |
| Composite FK only for new tables | All inter-entity FKs composite (R3) |
| DB-level ledger enforcement now | Triggers deferred to alembic; single-row CHECKs only (R4) |
| Alembic migration in scope | Excluded by user |

## Ontology (Key Entities)
| Entity | Type | Key fields | Relationships |
|---|---|---|---|
| Account | core | owner_type, citizen/household/company_id, account_type, currency, balance, is_active | owned by Citizen/Household/Company or world (GOVERNMENT/SYSTEM) |
| Transaction | core | transaction_type, tick, idempotency_key, reverses_transaction_id, metadata | has ≥2 LedgerEntries; may reverse a Transaction |
| LedgerEntry | core | transaction_id, account_id, entry_no, amount | Transaction × Account |
| WorldMetric | supporting | tick, metric_code, metric_value, unit, period, definition_version | World |
| MapChunk | supporting | chunk_x, chunk_y, chunk_size, terrain_tiles, road_tiles, schema_version, revision | World |
| BaseEntity | supporting | id, created_at, updated_at | parent of all |

## Ontology Convergence
| Round | Count | New | Stable | Ratio |
|---|---|---|---|---|
| 1 | 6 | 6 | - | - |
| 2–4 | 6 | 0 | 6 | 100% |

## Interview Transcript
<details><summary>4 rounds</summary>

- R0 topology (ledger, metrics/map, existing alignment, docs; no alembic) → 맞음
- R1 drop citizens/companies.cash_balance → yes (32%)
- R2 immutable tables still inherit BaseEntity → yes (26%)
- R3 composite FKs everywhere incl. existing → yes (22%)
- R4 no triggers now, single-row CHECKs only → yes (13%)
</details>
