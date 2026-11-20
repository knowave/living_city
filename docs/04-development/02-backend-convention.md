# Backend 컨벤션

> 근거: backend/pyproject.toml, backend/app/ 구조, backend/app/main.py, backend/app/core/config.py. 없는 항목은 `TBD`.

## 디렉터리 책임 (`backend/app/`)

| 경로 | 구성 (현재 존재) |
|---|---|
| `api/v1/` | `api.py`(라우터 집계), `endpoints/`(controller, 예: `health.py`, `worlds.py`) |
| `api/deps.py` | Composition Root. `get_db` → UnitOfWork → service를 조립하고 use case 타입으로 제공 |
| `usecases/` | use case 인터페이스(`abc.ABC`), 도메인 단위: `WorldUseCase`, `CityQueryUseCase` |
| `services/` | use case 구현 |
| `repositories/interfaces.py` | repository ABC + `UnitOfWork` ABC |
| `repositories/sqlalchemy/` | repository / UnitOfWork의 SQLAlchemy 구현. `engine_mapper.py`는 엔진 dataclass → ORM 변환, `ownership.py`는 Runner advisory lock 구현 |
| `simulation/` | `interfaces.py`(엔진 port `SimulationEnginePort`, `EngineBatch`, `PolicyCommandInput`, `SimulationEngineError`), `engine_adapter.py`(adapter 구현) |
| `maps/` | 맵 생성기(순수 Python). `tiles.py`(맵 상수, 타일 인코딩), `generator.py`(`generate_map`), `validate.py`(`validate_map`), `backfill.py`(`python -m app.maps.backfill`) |
| `schemas/` | Pydantic 요청/응답 DTO |
| `core/` | `config.py`(pydantic-settings), `security.py`, `exceptions.py`(도메인 예외) |
| `db/base.py` | `Base`, `BaseEntity` (id, created_at, updated_at 공통) |
| `db/session.py` | `engine`, `SessionLocal` |
| `models/` | 엔티티당 모듈 하나. `models/__init__.py`에서 모두 import (`create_all`이 인식하도록) |
| `runner/` | Simulation Runner. `manager.py`(RunnerManager), `world_runner.py`(WorldRunner), `backoff.py`, `interfaces.py`(포트: `RunnerStatusProvider`, `OwnershipLock`, `OwnershipHandle`) |
| `utils` | 패키지 골격만 존재 (내용 TBD) |

- ORM 규칙(타입, 명명, 제약)은 [데이터 저장 설계 §10.3](../03-architecture/06-database.md)을 따른다.

- 라우터는 `app/main.py`에서 `settings.API_V1_STR` 접두사로 등록한다. (app/main.py)
- 설정은 `Settings`(pydantic-settings)로 읽고 `.env`를 사용한다. 키: `PROJECT_NAME`, `API_V1_STR`, `DATABASE_URL`(기본 `postgresql+psycopg://<사용자>@localhost:5432/living_city`, 실제 값은 `.env`에서 설정), `DB_AUTO_SYNC`(기본 `true`), `ENGINE_VERSION`(기본 `"0.1.0"`, 세계 생성 시 기본 engine_version), `WORLD_LOCK_TIMEOUT_MS`(기본 `5000`, PATCH가 세계 행 잠금을 기다리는 최대 ms), `RUNNER_ENABLED`(기본 `true`, 테스트는 `false`), `RUNNER_TICK_INTERVAL_MS`(기본 `1000`, Runner 주기), `RUNNER_DISCOVERY_INTERVAL_MS`(기본 `1000`, RUNNING World 발견 주기), `RUNNER_BACKOFF_MAX_MS`(기본 `30000`, 일시 오류 재시도 간격 상한), `RUNNER_SHUTDOWN_TIMEOUT_MS`(기본 `10000`, 종료 시 진행 중 주기 대기 상한), `SNAPSHOT_KEEP_LATEST`(기본 `3`, 세계별 최신 Snapshot 보관 수). (app/core/config.py)
- 패키지 관리와 실행은 uv를 쓴다: `uv sync`, `uv run uvicorn app.main:app --reload`. (pyproject.toml, uv.lock)
- Docker 이미지는 uv가 아니라 `requirements.txt`를 pip으로 설치한다 (코드 기준: backend/Dockerfile). `requirements.txt`는 버전을 고정하지 않으므로 `pyproject.toml`과 별도로 관리해야 한다.
- 시뮬레이션 규칙은 backend 프레임워크 코드에 두지 않는다. (README §7.1)
- 엔드포인트 정의는 [REST API 및 SSE](../03-architecture/07-rest-sse.md)를 따른다. (README §9)

## 계층 규칙 (의존성 역전)

의존 방향: controller → use case(ABC) ← service → repository(ABC) ← SQLAlchemy 구현

- controller handler는 use case 메서드 하나만 호출한다. 검증도 그 메서드 안에 포함한다. (예: 로그인이라면 '토큰 발급' 메서드 하나가 자격 검증까지 수행)
- `services/`, `usecases/`는 `sqlalchemy`, `fastapi`, `app.db`, `app.api`, `app.models`를 import하지 않는다.
- `endpoints/`는 `sqlalchemy`, `app.models`, `app.repositories`, `app.services`를 import하지 않는다.
- 구현체 연결(service, SQLAlchemy 구현, 엔진 adapter, Runner 조립)은 `api/deps.py`에서만 한다.
- `app/runner/`는 use case ABC(`usecases/`)와 runner 포트(`runner/interfaces.py`)만 쓴다. `sqlalchemy`, `simulation_engine`, ORM(`app.models`)을 import하지 않는다.
- advisory lock SQL은 `app/repositories/sqlalchemy/ownership.py`에만 둔다. Runner는 이를 `OwnershipLock` 포트로만 쓴다.
- `simulation_engine`을 import하는 모듈은 `app/simulation/engine_adapter.py`와 `app/repositories/sqlalchemy/engine_mapper.py` 둘뿐이다. `services/`, `usecases/`, `simulation/interfaces.py`는 import하지 않는다.
- backend는 `simulation-engine`을 editable path 의존성(`../simulation_engine`)으로 둔다.
- `app/maps/`는 순수 Python 모듈이다. `sqlalchemy`, `fastapi`, `simulation_engine`을 import하지 않는다. 난수는 시드로 만든 `random.Random` 인스턴스만 쓴다. 전역 `random`과 `hash()`는 쓰지 않는다(같은 입력이면 같은 맵). service는 맵 생성기를 순수 함수로 직접 호출할 수 있고, 저장은 repository로 한다.
- 커맨드의 커밋은 service가 UnitOfWork로 한다. 조회는 커밋하지 않는다.
- 행 잠금 SQL(`FOR UPDATE`, `NOWAIT`, `lock_timeout`)은 repository 구현(`app/repositories/sqlalchemy/`)에만 둔다. service는 `WorldRepository.lock_for_update`로 잠금을 요청한다.
- service는 ORM 객체가 아니라 `schemas`를 반환한다.
- 이 규칙은 tests의 import 검사 테스트로 강제한다.
- 테스트: service 단위 테스트(가짜 repository/UoW)를 둔다. controller 테스트는 두지 않는다.

## 연결 수 한계 (Runner)

- 소유한 World마다 advisory lock용 전용 연결 1개를 유지한다. Tick 실행 세션은 주기마다 새로 만들고 끝나면 닫는다.
- 따라서 프로세스의 DB 연결 수는 소유 World 수에 비례해 늘어난다. MVP 규모(World 수 적음)에서는 허용하며, 이를 한계로 기록한다. World 수가 늘면 방식을 다시 정한다. 확장 단계 후보: World마다 연결을 붙잡는 대신 크기가 제한된 Worker Pool이 여러 World를 나눠 실행하고, 실행 소유권을 별도 방식으로 관리한다(예: 소유권 갱신형 리스). 이 변경은 Runner 내부 구조만 바꾸고 `advance_running` 실행 계약(`expected_tick`, 행 잠금, version)은 유지한다.

## 미정

- 마이그레이션 운영 규칙(alembic): TBD
- 린터 / 포매터 / 타입 검사: TBD
