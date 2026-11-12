# 기술 스택

> 근거: README §7.1, §8, §10, §14 및 backend/pyproject.toml, backend/app/ 구조. 확인되지 않은 항목은 `TBD`.

| 컴포넌트 | 항목 | 내용 | 근거 |
|---|---|---|---|
| backend | 언어 | Python >=3.12 | pyproject.toml `requires-python` |
| backend | 웹 프레임워크 | FastAPI (외부 명령 및 상태 조회 담당) | README §14, pyproject.toml |
| backend | 서버 | uvicorn[standard] | pyproject.toml |
| backend | 설정 | pydantic-settings (`.env`) | pyproject.toml, app/core/config.py |
| backend | 패키지 관리 | uv (`uv.lock`) | backend/uv.lock |
| backend | 테스트 | pytest, httpx | pyproject.toml dev 그룹 |
| backend | 통신 | REST (조회·명령), SSE (이벤트 전달) | README §9 |
| backend | ORM | SQLAlchemy >=2.1.8, psycopg[binary] (PostgreSQL 드라이버) | backend/pyproject.toml (코드 기준) |
| backend | 마이그레이션 | alembic 미설정 (`backend/alembic/`에 README만 있고 pyproject 의존성에도 없음) | backend/alembic/ (코드 기준) |
| simulation_engine | 언어 | Pure Python (프레임워크와 직접 결합하지 않음) | README §7.1 |
| simulation_engine | 버전 | Python >=3.12 | simulation_engine/pyproject.toml |
| simulation_engine | 의존성 | 런타임 의존성 없음 (표준 라이브러리만, 엔진 코드와 테스트 모두) | simulation_engine/pyproject.toml |
| simulation_engine | 패키지 관리 | setuptools 메타데이터만 (lock 파일 없음, 테스트는 `uv run --no-project`로 실행) | simulation_engine/pyproject.toml (코드 기준) |
| simulation_engine | 테스트 | unittest (Python 3.12 필요: `StrEnum` 사용) | simulation_engine/tests/ (코드 기준) |
| frontend | 렌더링 | PixiJS 8 (2.5D Isometric), @pixi/tilemap, pixi-viewport | README §8, §14, frontend/package.json (코드 기준) |
| frontend | UI | React 19, Tailwind CSS 4 (`@tailwindcss/vite`) | frontend/package.json (코드 기준) |
| frontend | 언어 | TypeScript ~7.0.2 (`tsc -b`로 빌드 검사) | frontend/package.json, tsconfig.app.json (코드 기준) |
| frontend | 빌드·개발 서버 | Vite ^8.3.6 (`/api` → localhost:8000 프록시) | frontend/vite.config.ts (코드 기준) |
| frontend | 상태·서버 데이터 | zustand ^5.1.0, @tanstack/react-query ^5.107.1 | frontend/package.json (코드 기준) |
| frontend | 패키지 관리 | yarn 4.18.1, nodeLinker: node-modules | frontend/package.json, .yarnrc.yml (코드 기준) |
| frontend | 린터·테스트 | oxlint ^1.90.0 (`yarn lint`), vitest ^5.1.0 (`yarn test`) | frontend/package.json, .oxlintrc.json (코드 기준) |
| frontend | 서버 통신 | REST, SSE | README §9 |
| database | RDBMS | PostgreSQL | README §10.1 |
| database | 버전 | TBD | - |
