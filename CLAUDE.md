# CLAUDE.md

AI 에이전트용 개발 지침. 사람용 소개는 [README.md](README.md), 설계 전체 목차는 [docs/README.md](docs/README.md).

## 프로젝트 요약

Living City는 시민·기업·정부가 상호작용하며 도시 경제가 스스로 변화하는 자율 도시 시뮬레이션 웹 서비스다. backend는 FastAPI, 시뮬레이션 엔진은 Pure Python, frontend는 Three.js(React Three Fiber) + React, 통신은 REST + SSE다. `docs/`가 설계의 단일 출처(source of truth)다.

## 핵심 원칙

- 계층 책임 분리: 엔진은 도메인 규칙, FastAPI는 외부 명령과 상태 조회, Three.js는 시각적 표현을 맡는다 ([설계 원칙](docs/01-product/01-overview.md)).
- 엔진은 프레임워크 독립: `simulation_engine`은 FastAPI, SQLAlchemy, PostgreSQL을 import하지 않는다 ([시뮬레이션 엔진](docs/03-architecture/03-simulation-engine.md)).
- 화폐는 정수형 최소 단위만 쓴다. 부동소수점으로 저장하지 않는다 ([경제](docs/02-domain/06-economy.md)).
- 자금 보존: 초기 세계 생성 이후 모든 자금 이동은 계정 간 이전 거래이며, 합계가 임의로 변하면 안 된다 ([경제](docs/02-domain/06-economy.md), [시뮬레이션 규칙](docs/02-domain/07-simulation-rules.md)).
- 결정성: 같은 시드, 정책 입력 순서, 엔진 버전이면 같은 결과가 나와야 한다 ([시뮬레이션 규칙](docs/02-domain/07-simulation-rules.md)).
- 서버가 세계 상태의 최종 권한을 가진다. 이벤트는 저장 커밋 이후에만 발행한다 ([데이터 흐름](docs/03-architecture/05-data-flow.md)).
- 초기 단계에서 불필요한 분산 아키텍처와 AI 의존성을 도입하지 않는다 ([시스템 아키텍처](docs/03-architecture/01-system-architecture.md)).
- MVP 제외 기능은 구현하지 않는다. 단, 데이터 모델 확장성은 유지한다 ([기능 범위](docs/01-product/03-features.md)).

## 문서 참조 규칙

코드를 쓰기 전에 아래 표에서 작업 종류에 맞는 문서를 먼저 읽는다.

| 작업 종류 | 먼저 읽을 문서 |
|---|---|
| 제품 범위, MVP 포함/제외 판단 | [01-overview](docs/01-product/01-overview.md), [02-requirements](docs/01-product/02-requirements.md), [03-features](docs/01-product/03-features.md) |
| 도메인 모델링 (엔티티, 속성) | [01-domain-overview](docs/02-domain/01-domain-overview.md), [02-world](docs/02-domain/02-world.md), [03-citizen](docs/02-domain/03-citizen.md), [04-business](docs/02-domain/04-business.md), [05-government](docs/02-domain/05-government.md) |
| 시뮬레이션 엔진, Tick, 난수 | [03-simulation-engine](docs/03-architecture/03-simulation-engine.md), [07-simulation-rules](docs/02-domain/07-simulation-rules.md), [04-simulation-convention](docs/04-development/04-simulation-convention.md) |
| 경제, 원장, 세금, 급여, 소비 | [06-economy](docs/02-domain/06-economy.md), [07-simulation-rules](docs/02-domain/07-simulation-rules.md) |
| 맵, 렌더링, 시민 이동 시각화 | [04-map-rendering](docs/03-architecture/04-map-rendering.md), [05-data-flow](docs/03-architecture/05-data-flow.md), [03-frontend-convention](docs/04-development/03-frontend-convention.md) |
| REST API, SSE | [07-rest-sse](docs/03-architecture/07-rest-sse.md), [05-data-flow](docs/03-architecture/05-data-flow.md), [05-api-convention](docs/04-development/05-api-convention.md) |
| DB, 마이그레이션, 테이블 | [06-database](docs/03-architecture/06-database.md), [02-backend-convention](docs/04-development/02-backend-convention.md) |
| 전체 구조, 기술 스택 | [01-system-architecture](docs/03-architecture/01-system-architecture.md), [02-tech-stack](docs/03-architecture/02-tech-stack.md) |
| 테스트 작성 | [06-testing-guide](docs/04-development/06-testing-guide.md) |
| phase 단위 작업 | [05-phases](docs/05-phases/) 의 해당 phase 문서, 전체 흐름은 [04-roadmap](docs/01-product/04-roadmap.md) |

Phase 문서: [phase-01-map-prototype](docs/05-phases/phase-01-map-prototype.md), [phase-02-chunk-rendering](docs/05-phases/phase-02-chunk-rendering.md), [phase-03-citizen-movement](docs/05-phases/phase-03-citizen-movement.md), [phase-04-simulation-engine](docs/05-phases/phase-04-simulation-engine.md), [phase-05-economic-system](docs/05-phases/phase-05-economic-system.md), [phase-06-simulation-engine-v1](docs/05-phases/phase-06-simulation-engine-v1.md)

## 디렉터리별 책임

| 디렉터리 | 책임 | 상태 |
|---|---|---|
| `backend/` | FastAPI 서버. REST/SSE, DB 저장, Simulation Runner. 구조는 `app/{api/v1,core,crud,db,models,schemas,services,utils}` | 일부 구현 (14개 ORM 모델, DB 세션, `GET /api/v1/health`. crud·schemas·services·utils는 빈 패키지) (코드 기준) |
| `simulation_engine/` | 도메인 규칙만 담은 Pure Python 엔진 | v1 구현 (세계 생성, Tick 엔진, 시민·경제 System, 지표, Snapshot. [phase-06](docs/05-phases/phase-06-simulation-engine-v1.md) 참조) (코드 기준) |
| `frontend/` | 3D 렌더링 모듈(src/render: city-map, buildings, camera) 프로토타입과 React UI | 골격 있음 (Vite + React 기본 앱, stores·api는 빈 디렉터리). 시민 모듈 `src/render/citizens/`(Mock)은 Phase 3 진행 중 (코드 기준) |

컨벤션은 [01-common-convention](docs/04-development/01-common-convention.md), [02-backend-convention](docs/04-development/02-backend-convention.md), [03-frontend-convention](docs/04-development/03-frontend-convention.md), [04-simulation-convention](docs/04-development/04-simulation-convention.md), [05-api-convention](docs/04-development/05-api-convention.md)을 따른다.

backend 명령(`backend/`에서 실행): `uv sync`, `uv run uvicorn app.main:app --reload`, `uv run pytest`.

simulation_engine 명령(`simulation_engine/`에서 실행): `PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest` (시스템 python3가 3.12 미만이면 실패) (코드 기준).

frontend 명령(`frontend/`에서 실행): `yarn install`, `yarn dev`, `yarn test`, `yarn lint`, `yarn build` (코드 기준).

## 문서 유지 규칙

- 설계가 바뀌면 코드보다 먼저 해당 docs 파일을 갱신한다.
- 문서와 코드가 충돌하면 임의로 판단하지 말고 사용자에게 확인한다.
- `TBD`로 표시된 항목은 추측으로 채우지 않는다. 사용자에게 묻는다.
- 새 문서는 맞는 docs 하위 폴더에 두고 [docs/README.md](docs/README.md) 목차에 추가한다.
- 원본 설계 명세 백업은 `.omc/backup/README.original.md`이며 수정하지 않는다.
