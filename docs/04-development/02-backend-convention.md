# Backend 컨벤션

> 근거: backend/pyproject.toml, backend/app/ 구조, backend/app/main.py, backend/app/core/config.py. 없는 항목은 `TBD`.

## 디렉터리 책임 (`backend/app/`)

| 경로 | 구성 (현재 존재) |
|---|---|
| `api/v1/` | `api.py`(라우터 집계), `endpoints/`(예: `health.py`) |
| `api/deps.py` | `get_db` (요청 단위 DB 세션 의존성) |
| `core/` | `config.py`(pydantic-settings), `security.py` |
| `db/base.py` | `Base`, `BaseEntity` (id, created_at, updated_at 공통) |
| `db/session.py` | `engine`, `SessionLocal` |
| `models/` | 엔티티당 모듈 하나. `models/__init__.py`에서 모두 import (`create_all`이 인식하도록) |
| `crud`, `schemas`, `services`, `utils` | 패키지 골격만 존재 (내용 TBD) |

- ORM 규칙(타입, 명명, 제약)은 [데이터 저장 설계 §10.3](../03-architecture/06-database.md)을 따른다.

- 라우터는 `app/main.py`에서 `settings.API_V1_STR` 접두사로 등록한다. (app/main.py)
- 설정은 `Settings`(pydantic-settings)로 읽고 `.env`를 사용한다. 키: `PROJECT_NAME`, `API_V1_STR`, `DATABASE_URL`(기본 `postgresql+psycopg://<사용자>@localhost:5432/living_city`, 실제 값은 `.env`에서 설정), `DB_AUTO_SYNC`(기본 `true`). (app/core/config.py)
- 패키지 관리와 실행은 uv를 쓴다: `uv sync`, `uv run uvicorn app.main:app --reload`. (pyproject.toml, uv.lock)
- Docker 이미지는 uv가 아니라 `requirements.txt`를 pip으로 설치한다 (코드 기준: backend/Dockerfile). `requirements.txt`는 버전을 고정하지 않으므로 `pyproject.toml`과 별도로 관리해야 한다.
- 시뮬레이션 규칙은 backend 프레임워크 코드에 두지 않는다. (README §7.1)
- 엔드포인트 정의는 [REST API 및 SSE](../03-architecture/07-rest-sse.md)를 따른다. (README §9)

## 미정

- 계층 간 호출 규칙(api → services → crud): TBD
- 마이그레이션 운영 규칙(alembic): TBD
- 린터 / 포매터 / 타입 검사: TBD
