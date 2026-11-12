# doc-sync-backend change log (relayed by lead from sync-backend report)

| doc file | before | after | code evidence |
|---|---|---|---|
| docs/03-architecture/06-database.md:48 | `SQLAlchemy 2.0 sync` | `SQLAlchemy 2.1.8 이상 sync` (코드 기준) | backend/pyproject.toml (`sqlalchemy>=2.1.8`) |
| docs/03-architecture/07-rest-sse.md:4-5 | no status | 구현 상태 note: only `GET /api/v1/health`; REST/SSE are design; paths relative to `API_V1_STR` | backend/app/api/v1/endpoints/health.py:6, app/main.py:28, app/api/v1/api.py:6 |
| docs/04-development/02-backend-convention.md:21 | only uv | Docker installs via pip from requirements.txt (unpinned) | backend/Dockerfile:3-4, requirements.txt |
| docs/04-development/05-api-convention.md:15 | naming/migration TBD | naming defined (plural snake_case tables, uq_/idx_/fk_/ck_), migration still TBD | backend/app/models/*.py, alembic/README.md |

## Claimed matching (no change)
14 table names; BaseEntity fields; BigInteger money; 13 uq_<table>_world_id_id; 15 composite FKs RESTRICT; MetricCode 12; TransactionType 10; settings keys; API_V1_STR.

## Not changed
alembic TBD, deferred triggers TBD, unimplemented endpoints kept as design, lint TBD, security.py placeholder, error/auth TBD, sequence assignment not coded.
Flag: 02-backend-convention DATABASE_URL default contains a personal username (from code default).
