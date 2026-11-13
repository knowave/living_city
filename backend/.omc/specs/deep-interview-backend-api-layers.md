# Deep Interview Spec: Backend REST API with strict layered architecture (DIP)

## Metadata
- Interview ID: di-backend-api-layers-20261112
- Rounds: 4 (+ Round 0 topology)
- Final Ambiguity Score: 16%
- Type: brownfield
- Generated: 2026-11-12
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED — pending approval

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| Goal | 0.88 | 0.35 | 0.308 |
| Constraints | 0.82 | 0.25 | 0.205 |
| Success Criteria | 0.75 | 0.25 | 0.1875 |
| Context | 0.90 | 0.15 | 0.135 |
| **Ambiguity** | | | **0.1645** |

## Topology
| Component | Status | Coverage |
|---|---|---|
| Layer structure & rules (use case ABCs, repository ABCs, UoW, Composition Root, global error handling) | active | AC2–AC5 |
| REST endpoints (9 from docs/03-architecture/07-rest-sse.md, DB-only scope) | active | AC6–AC8 |
| Docs update (layer rules, error format, API status/shapes) | active | AC1 |
| Tests — service-level unit tests only (fake repositories) | active | AC9 |
| Controller tests | dropped (user, Round 0: "controller 테스트를 하지말고 service 기준") | — |
| SSE `/worlds/{id}/events` | deferred (Round 1) | — |
| Auth / login | out of scope (the login example only illustrates the rule) | — |

## Goal
Implement the 9 REST endpoints of docs 07-rest-sse.md (DB-only behaviour) on a strict controller → use case (ABC) ← service → repository (ABC) ← SQLAlchemy layering, where each controller handler calls exactly one use-case method that contains all validation and orchestration, with wiring only in the Composition Root.

## Constraints
### Architecture (Rounds 2, 4)
- Layout:
  - `app/usecases/` — use-case interfaces (`abc.ABC`), grouped by domain: `WorldUseCase` (create_world, get_world, get_world_state, change_simulation, change_policy) and `CityQueryUseCase` (get_chunks, get_citizen, get_company, get_metrics). One method = one complete use case (validation included).
  - `app/services/` — implementations (`WorldService(WorldUseCase)`, `CityQueryService(CityQueryUseCase)`), depending ONLY on repository/UoW ABCs + schemas + core exceptions. No `sqlalchemy`, `fastapi`, `app.db`, `app.api` imports in `app/services/` or `app/usecases/`.
  - `app/repositories/interfaces.py` — repository ABCs (per aggregate as needed: World, WorldPolicy, WorldEvent, MapChunk, Citizen, Company, Account, WorldMetric) + `UnitOfWork` ABC (exposes repositories, `commit()`, `rollback()`).
  - `app/repositories/sqlalchemy/` — SQLAlchemy implementations + `SqlAlchemyUnitOfWork(Session)`.
  - Delete empty `app/crud/` (replaced by `app/repositories/`).
  - `app/schemas/` — Pydantic request/response DTOs. Services return schemas, never ORM objects (`model_config = ConfigDict(from_attributes=True)` allowed for mapping inside services/repositories).
  - `app/api/deps.py` — the only Composition Root: `get_db` → `SqlAlchemyUnitOfWork` → `WorldService` / `CityQueryService`; providers are typed as the use-case ABC (`def get_world_use_case(...) -> WorldUseCase`).
  - `app/api/v1/endpoints/worlds.py` — controllers: each handler body is a single `return use_case.<method>(...)` (path/body params passed through). Endpoints must not import `Session`, repositories, models, or services.
- Transactions: services call `uow.commit()` for commands; reads don't commit.
- Errors (Round 3): `app/core/exceptions.py` — `DomainError` base with `code`; `NotFoundError` (404), `ConflictError` (409), `InvalidStateError` (409 — state transition) and `DomainValidationError` (422). Global handlers in `app/main.py` render `{"error": {"code": "...", "message": "...", "details": ...?}}`; FastAPI `RequestValidationError` is rendered in the same shape (code `VALIDATION_ERROR`, details = errors list). No try/except in controllers.
- Keep existing `GET /api/v1/health` and lifespan behaviour.
- Python naming per PEP 8; money BigInteger ints; JSON field names snake_case.

### Endpoint behaviour (Round 1, DB-only)
| Method | Path | Use case | Behaviour |
|---|---|---|---|
| POST | /worlds | create_world | Create World (status INITIALIZED, current_tick 0, speed 1) + initial WorldPolicy (income_tax_rate 1500 bp, welfare_amount 0, effective_tick 0, version 1). 201. No citizens/companies/map generation (engine generator is a stub). |
| GET | /worlds/{id} | get_world | World metadata. 404 WORLD_NOT_FOUND. |
| GET | /worlds/{id}/state | get_world_state | status, current_tick, speed, current policy, `event_cursor` = max world_events.sequence (0 if none). |
| GET | /worlds/{id}/chunks | get_chunks | Chunks of the world; optional query `x_min,x_max,y_min,y_max` (inclusive chunk coords). |
| GET | /worlds/{id}/citizens/{citizen_id} | get_citizen | Citizen detail + `cash_balance` from the citizen's CASH/KRW account (null if none). 404 CITIZEN_NOT_FOUND (also when citizen belongs to another world). |
| GET | /worlds/{id}/companies/{company_id} | get_company | Company detail + `cash_balance` from CASH/KRW account. 404 COMPANY_NOT_FOUND. |
| GET | /worlds/{id}/metrics | get_metrics | world_metrics rows; optional query `metric_code`, `period`, `from_tick`, `to_tick`; ordered by tick. |
| PATCH | /worlds/{id}/simulation | change_simulation | Body `{status?, speed?}`; validates transition & speed; persists. No tick execution. |
| PATCH | /worlds/{id}/policies | change_policy | Body `{income_tax_rate?, welfare_amount?}`; new WorldPolicy row version = latest+1, effective_tick = current_tick + 1, unspecified fields copied from latest. |

## Open Assumptions (surface at approval)
1. Simulation transitions allowed: INITIALIZED→RUNNING, RUNNING→PAUSED, PAUSED→RUNNING, {INITIALIZED,RUNNING,PAUSED}→ARCHIVED; FAILED is system-only; ARCHIVED is terminal. Others → 409 INVALID_STATE_TRANSITION.
2. `speed` ∈ {1, 4, 16} (docs: 정지/1/4/16배속 — "정지" is status PAUSED). Else 422.
3. POST /worlds body: `name` (1–100 chars, required), `seed` (optional int; random 63-bit if omitted, stored), `engine_version` (optional; default from new setting `ENGINE_VERSION="0.1.0"`). Backend does not import simulation_engine.
4. Policy bounds: income_tax_rate 0–10000 bp, welfare_amount ≥ 0; at least one field required (else 422).
5. Policy "current" = latest version with effective_tick ≤ current_tick (for /state).
6. Using World.version optimistic lock on simulation change (StaleDataError → 409 CONCURRENT_UPDATE).

## Non-Goals
- SSE, tick execution/Simulation Runner, world generation (citizens/companies/map), auth/login/users, alembic, controller/integration tests, pagination.

## Acceptance Criteria
- [ ] AC1: Docs updated before code: `docs/04-development/02-backend-convention.md` (layer layout + dependency rules + Composition Root; "계층 간 호출 규칙" no longer TBD), `docs/04-development/05-api-convention.md` (error format; 인증 stays TBD), `docs/03-architecture/07-rest-sse.md` (implementation status per endpoint, request/response fields, SSE still unimplemented).
- [ ] AC2: `app/usecases/` has exactly the 2 ABCs with abstract methods listed; `app/services/` implements them.
- [ ] AC3: Import rules hold — checked by a test that parses imports (ast): `app/usecases`, `app/services` import nothing from `sqlalchemy`, `fastapi`, `app.db`, `app.api`, `app.models`, `app.repositories.sqlalchemy`; `app/api/v1/endpoints` imports nothing from `sqlalchemy`, `app.models`, `app.repositories`, `app.services`.
- [ ] AC4: Every controller handler body is a single use-case method call (checked by ast test: one `Return` of one `Call` on the injected use case).
- [ ] AC5: `app/crud/` removed; `app/repositories/{interfaces.py,sqlalchemy/}` exist; deps.py is the only module importing both services and sqlalchemy repositories.
- [ ] AC6: All 9 routes registered under `/api/v1` (checked against `app.routes`).
- [ ] AC7: Error responses use `{"error": {"code","message"}}` for domain errors and request validation.
- [ ] AC8: (manual, after `createdb living_city`) POST /worlds → GET /worlds/{id}/state round-trips via real DB.
- [ ] AC9: Service unit tests with in-memory fake repositories/UoW (no DB, no TestClient) cover: create_world (defaults, policy created, commit called), get_* not-found, citizen of another world → 404, state event_cursor, chunks range filter, metrics filters, change_simulation allowed/denied transitions + speed validation, change_policy versioning/effective_tick/copying/validation. `uv run pytest` passes (existing tests kept).

## Assumptions Exposed & Resolved
| Assumption | Resolution |
|---|---|
| Login must be built | Example only; out of scope (R0) |
| Controller tests needed | Service-level unit tests only (R0) |
| Engine-dependent APIs fully working | DB-only scope; SSE deferred (R1) |
| Protocol vs ABC, crud folder | ABC; crud → repositories; Composition Root in deps.py (R2) |
| Error format | `{"error":{code,message,details}}` via global handlers (R3) |
| One class per use case | Grouped by domain; one method = one use case (R4) |

## Ontology (Key Entities)
| Entity | Type | Notes |
|---|---|---|
| Controller | layer | FastAPI endpoint; calls one use-case method |
| WorldUseCase / CityQueryUseCase | layer (port) | ABCs in app/usecases |
| WorldService / CityQueryService | layer | implement use cases; depend on repository ABCs |
| Repository ABCs + UnitOfWork | layer (port) | app/repositories/interfaces.py |
| SqlAlchemy repositories | adapter | app/repositories/sqlalchemy |
| Composition Root | wiring | app/api/deps.py |
| World, WorldPolicy, WorldEvent, MapChunk, Citizen, Company, Account, WorldMetric | domain data | existing models |

## Ontology Convergence
| Round | Count | New | Stable | Ratio |
|---|---|---|---|---|
| 1 | 10 | 10 | - | - |
| 2 | 12 | 2 (UnitOfWork, Composition Root) | 10 | 83% |
| 3–4 | 12 | 0 | 12 | 100% |

## Interview Transcript
<details><summary>4 rounds</summary>

- R0 topology → 맞음, but no controller tests; service-level unit tests only
- R1 9 endpoints, DB-only, SSE deferred → yes (33%)
- R2 layout: ABC, crud→repositories, deps.py composition root, service commits, returns schemas → yes (26%)
- R3 error format `{"error":{code,message,details}}` → yes (21%)
- R4 use cases grouped by domain → yes (16%)
</details>
