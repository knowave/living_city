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
| `repositories/sqlalchemy/` | repository / UnitOfWork의 SQLAlchemy 구현 |
| `schemas/` | Pydantic 요청/응답 DTO |
| `core/` | `config.py`(pydantic-settings), `security.py`, `exceptions.py`(도메인 예외) |
| `db/base.py` | `Base`, `BaseEntity` (id, created_at, updated_at 공통) |
| `db/session.py` | `engine`, `SessionLocal` |
| `models/` | 엔티티당 모듈 하나. `models/__init__.py`에서 모두 import (`create_all`이 인식하도록) |
| `utils` | 패키지 골격만 존재 (내용 TBD) |

- ORM 규칙(타입, 명명, 제약)은 [데이터 저장 설계 §10.3](../03-architecture/06-database.md)을 따른다.

- 라우터는 `app/main.py`에서 `settings.API_V1_STR` 접두사로 등록한다. (app/main.py)
- 설정은 `Settings`(pydantic-settings)로 읽고 `.env`를 사용한다. 키: `PROJECT_NAME`, `API_V1_STR`, `DATABASE_URL`(기본 `postgresql+psycopg://<사용자>@localhost:5432/living_city`, 실제 값은 `.env`에서 설정), `DB_AUTO_SYNC`(기본 `true`), `ENGINE_VERSION`(기본 `"0.1.0"`, 세계 생성 시 기본 engine_version). (app/core/config.py)
- 패키지 관리와 실행은 uv를 쓴다: `uv sync`, `uv run uvicorn app.main:app --reload`. (pyproject.toml, uv.lock)
- Docker 이미지는 uv가 아니라 `requirements.txt`를 pip으로 설치한다 (코드 기준: backend/Dockerfile). `requirements.txt`는 버전을 고정하지 않으므로 `pyproject.toml`과 별도로 관리해야 한다.
- 시뮬레이션 규칙은 backend 프레임워크 코드에 두지 않는다. (README §7.1)
- 엔드포인트 정의는 [REST API 및 SSE](../03-architecture/07-rest-sse.md)를 따른다. (README §9)

## 계층 규칙 (의존성 역전)

의존 방향: controller → use case(ABC) ← service → repository(ABC) ← SQLAlchemy 구현

- controller handler는 use case 메서드 하나만 호출한다. 검증도 그 메서드 안에 포함한다. (예: 로그인이라면 '토큰 발급' 메서드 하나가 자격 검증까지 수행)
- `services/`, `usecases/`는 `sqlalchemy`, `fastapi`, `app.db`, `app.api`, `app.models`를 import하지 않는다.
- `endpoints/`는 `sqlalchemy`, `app.models`, `app.repositories`, `app.services`를 import하지 않는다.
- 구현체 연결(service, SQLAlchemy 구현)은 `api/deps.py`에서만 한다.
- 커맨드의 커밋은 service가 UnitOfWork로 한다. 조회는 커밋하지 않는다.
- service는 ORM 객체가 아니라 `schemas`를 반환한다.
- 이 규칙은 tests의 import 검사 테스트로 강제한다.
- 테스트: service 단위 테스트(가짜 repository/UoW)를 둔다. controller 테스트는 두지 않는다.

## 미정

- 마이그레이션 운영 규칙(alembic): TBD
- 린터 / 포매터 / 타입 검사: TBD
