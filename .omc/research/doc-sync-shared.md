# doc-sync-shared 변경 기록

범위: 공유 문서 (README.md, CLAUDE.md, docs/README.md, docs/03-architecture/01·02, docs/04-development/01·06). 코드 미수정, backend/.env 미열람, 의존성 설치 미실행.

## 변경 내역

| 파일 | 변경 전 | 변경 후 | 근거 |
|---|---|---|---|
| README.md 기술 스택 표 (frontend) | PixiJS, React | PixiJS 8, React 19, TypeScript, Vite; 패키지 관리 yarn 4 | frontend/package.json |
| README.md 디렉터리 | `frontend/ # ... (현재 비어 있음)` | `(Vite 기반 골격)` | frontend/src 에 App.tsx, main.tsx 존재 |
| README.md simulation_engine 실행 | `PYTHONPATH=src python3 -m unittest` | `PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest` + 3.12 필요 안내 | 아래 실행 결과 (시스템 python3 = 3.9.6 에서 실패) |
| README.md frontend 실행 | `TBD (디렉터리가 아직 비어 있습니다)` | `yarn install / yarn dev / yarn test / yarn build`, Node + yarn 4.18.1 안내 | frontend/package.json scripts, vite.config.ts 프록시 |
| CLAUDE.md 디렉터리 표 (simulation_engine) | 골격 있음, 로직 미구현 | 일부 구현 (entities, economy, world, policies 등, engine·systems 골격) (코드 기준) | simulation_engine/src: engine.py, systems/*.py 는 docstring 한 줄 |
| CLAUDE.md 디렉터리 표 (frontend) | 비어 있음 | 골격 있음 (Vite + React 기본 앱) (코드 기준) | frontend/src |
| CLAUDE.md 명령 (simulation_engine) | `PYTHONPATH=src python3 -m unittest` | uv 3.12 명령 (코드 기준) | 실행 결과 |
| CLAUDE.md 명령 (frontend) | 없음 | `yarn install/dev/test/lint/build` 줄 추가 (코드 기준) | frontend/package.json |
| docs/03-architecture/02-tech-stack.md backend ORM | SQLAlchemy (pyproject 에 아직 없음) | SQLAlchemy >=2.1.8, psycopg[binary] (코드 기준) | backend/pyproject.toml |
| 02-tech-stack backend 마이그레이션 | alembic (디렉터리만, 내용 TBD) | alembic 미설정 (README만 있고 의존성 없음) (코드 기준) | backend/alembic/README.md, pyproject.toml |
| 02-tech-stack simulation_engine 패키지 관리 | setuptools 메타데이터만 (uv 미사용) | lock 파일 없음, 테스트는 uv run --no-project 로 실행 (코드 기준) | simulation_engine/pyproject.toml |
| 02-tech-stack simulation_engine 테스트 | unittest | unittest (Python 3.12 필요: StrEnum) (코드 기준) | 실행 결과 |
| 02-tech-stack frontend 렌더링/UI | PixiJS / React | PixiJS 8 + @pixi/tilemap + pixi-viewport; React 19 + Tailwind CSS 4 (코드 기준) | frontend/package.json |
| 02-tech-stack frontend 언어·빌드·테스트 | TBD | TypeScript ~7.0.2, Vite ^8.3.6, zustand, react-query, yarn 4.18.1, oxlint, vitest ^5.1.0 (코드 기준) | frontend/package.json, .yarnrc.yml, .oxlintrc.json |
| 06-testing-guide 실행 방법 (frontend) | TBD (frontend/ 비어 있음) | `cd frontend && yarn test` (smoke.test.ts 1개) (코드 기준) | 실행 결과 |
| 06-testing-guide 실행 방법 (simulation_engine) | python3 -m unittest | uv 3.12 명령 (코드 기준) | 실행 결과 |

변경 없음 (검토 후 모순 없음): docs/README.md, docs/03-architecture/01-system-architecture.md, docs/04-development/01-common-convention.md.

## 실행한 명령과 결과

| 명령 | 위치 | 결과 |
|---|---|---|
| `uv run pytest -q` | backend | 12 passed, 1 warning (StarletteDeprecationWarning, httpx) |
| `PYTHONPATH=src python3 -m unittest` | simulation_engine | 실패. python3 = /Library/Developer/CommandLineTools/.../Python 3.9.6. `from enum import StrEnum` ImportError, 21 errors (`economy/account.py:5`) |
| `python3 -m pytest -q` | simulation_engine | 실패. system python3 에 pytest 없음 |
| `PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest` | simulation_engine | Ran 24 tests, OK |
| `yarn test` (vitest run) | frontend | 1 file, 1 test passed |
| `yarn lint` (oxlint) | frontend | exit 0 |
| `yarn typecheck` (tsc -b --noEmit) | frontend | exit 0 |
| `yarn build` (tsc -b && vite build) | frontend | exit 0, dist 생성 (gitignore 대상) |

미실행: `yarn install`, `yarn dev` (설치 금지 조건으로 생략. README 의 yarn install/dev 는 문서 명령이며 미검증). `uv sync` 및 backend 서버 기동 미실행.

## 확인된 사실 (코드 기준)

- backend 의존성: fastapi, uvicorn[standard], pydantic-settings, sqlalchemy>=2.1.8, psycopg[binary]>=3.3.8. dev: pytest, httpx. alembic 은 의존성에 없음.
- backend Dockerfile: python:3.12-slim, requirements.txt 로 설치, `uvicorn app.main:app`.
- backend 는 simulation_engine 을 import 하지 않음 (grep 결과 없음).
- frontend: packageManager yarn@4.18.1, nodeLinker node-modules. scripts: dev=vite, build=tsc -b && vite build, lint=oxlint, typecheck, test=vitest run, preview.
- simulation_engine: 패키지명 simulation-engine, src layout, 의존성 없음, requires-python >=3.12.

## 변경하지 않은 불일치 (사유)

1. docs/04-development/01-common-convention.md: "린터 / 포매터: TBD". frontend 는 oxlint 가 있으나 포매터는 없음. 모순이라기보다 미정 항목의 일부 채움이라 지시(모순만 수정)에 따라 보류. 채우려면 린터 항목만 "frontend: oxlint (`yarn lint`)"로 추가 가능.
2. docs/03-architecture/02-tech-stack.md database 버전 TBD: 코드/설정에 PostgreSQL 버전 근거 없음 (docker-compose 등 없음). 유지.
3. docs/03-architecture/02-tech-stack.md frontend "TypeScript ~7.0.2": package.json 값 그대로 기재. 실제 설치 버전은 yarn.lock 확인 안 함.
4. simulation_engine/README.md (소유: 다른 에이전트): "현재는 패키지 골격만 있습니다. 실행 로직은 아직 구현하지 않았습니다." 는 entities/economy/world 구현 존재와 모순. 또 실행 명령 `PYTHONPATH=src python3 -m unittest` 가 시스템 python3 에서 실패. sync-engine 에 전달 필요.
5. backend/app 구조 (CLAUDE.md "app/{api/v1,core,crud,db,models,schemas,services,utils}"): 실제 디렉터리 확인 일부만 (api, core, models, db 등 존재). 세부 검증은 sync-backend 범위로 보류.
6. docs/04-development/06-testing-guide.md 의 "엔진 단위 테스트/통합/프론트엔드 테스트" 항목 목록은 설계 체크리스트 성격이라 실제 테스트 케이스와 대응 여부는 미검증. 실행 명령만 갱신.

## fix round 1

| file:line | before → after |
|---|---|
| docs/04-development/04-simulation-convention.md:46 | `PYTHONPATH=src python3 -m unittest` → `PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest` (코드 기준, 시스템 python3 3.12 미만이면 실패 명시) |
| docs/04-development/02-backend-convention.md:20 | `postgresql+psycopg://ian@localhost:5432/living_city` → `postgresql+psycopg://<사용자>@localhost:5432/living_city`, 실제 값은 `.env`에서 설정 명시. `grep ian@` (docs, README.md, CLAUDE.md) 결과 0건 |
| docs/04-development/05-api-convention.md:13 | 네이밍 규칙 줄을 `## 미정`(15행) 위로 이동. 미정 아래는 `마이그레이션 파일 규칙: TBD`(17행), `에러 응답 형식, 인증: TBD`(18행)만 남김 |
| docs/02-domain/03-citizen.md:16 | `... ([경제](06-economy.md))` → `... ([경제](06-economy.md)) (코드 기준)` |
| docs/02-domain/04-business.md:14 | `... ([경제](06-economy.md))` → `... ([경제](06-economy.md)) (코드 기준)` |
| docs/02-domain/06-economy.md:11 | `... 경제 계정` → `... 경제 계정 (코드 기준)` |
| docs/04-development/04-simulation-convention.md:39 | `단 Citizen.employment_status, Employment.status, Building.status, Building.type(엔진 필드 기준)은 아직 str이다.` → `단 World.status, Company.status, Citizen.employment_status, Employment.status, Building.status, Building.type 필드는 enum이 아니라 str이다 (enum 값을 문자열로 저장) (코드 기준).` 6개 필드 모두 entities/*.py에서 `: str` 확인 |
| docs/04-development/01-common-convention.md:19 | `- 린터 / 포매터: TBD` → `- 린터 / 포매터: frontend는 oxlint(yarn lint, 코드 기준). 포매터와 backend 린터는 TBD` |
| CLAUDE.md:43 | `골격 있음` → `일부 구현 (14개 ORM 모델, DB 세션, GET /api/v1/health. crud·schemas·services·utils는 빈 패키지) (코드 기준)`. 검증: models 파일 14개, health 라우터 존재, 4개 패키지 빈 `__init__.py`만 있음 |
| docs/03-architecture/06-database.md (15 composite FK) | 변경 없음. backend/app/models/*.py의 composite ForeignKeyConstraint 2열 항목을 AST로 세면 15개. backend/tests/test_models.py:69 `assert seen == 15`와 일치 |

FK count: 15 (composite ForeignKeyConstraint, 2열 `(world_id, x_id)`). Doc claim correct, left unchanged.
Note: docs/04-development/06-testing-guide.md:36 already contains the same uv command (not edited by this round).
