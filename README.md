# Living City

Living City는 독립적인 시민, 기업, 정부가 상호작용하면서 도시의 경제와 사회가 지속적으로 변화하는 자율 도시 시뮬레이션 플랫폼입니다.

사용자는 도시를 생성하고 시민들이 스스로 생활하는 모습을 관찰할 수 있으며, 세금·복지·고용 같은 정책을 바꿔 도시 전체에 생기는 변화를 실험할 수 있습니다. 도시의 변화는 미리 짜인 스토리가 아니라 시민과 기업의 행동 규칙, 경제 상태, 확률적 사건으로 결정됩니다.

## 기술 스택

| 구성 요소 | 기술 | 비고 |
|---|---|---|
| backend | FastAPI, SQLAlchemy, PostgreSQL | Python >= 3.12, 패키지 관리는 uv |
| simulation_engine | Pure Python | FastAPI, SQLAlchemy, PostgreSQL에 직접 의존하지 않음 |
| frontend | PixiJS 8, React 19, TypeScript, Vite | 2.5D Isometric 렌더링, 패키지 관리는 yarn 4 |
| 통신 | REST, SSE | 조회와 명령은 REST, 서버 상태 변경 전달은 SSE |

## 디렉터리 구조

```
living_city/
├── CLAUDE.md
├── docs/
│
├── simulation_engine/       # Pure Python
│   └── citizens, companies, economy, time progression
│
├── backend/                 # FastAPI
│   └── REST API, SSE, DB integration
│
└── frontend/                # React + TypeScript
    ├── UI                   # 대시보드, 정보 패널
    └── 3D Rendering Engine  # Three.js
        ├── city-map
        ├── buildings
        ├── citizens
        ├── camera
        └── animation
```

## 실행 방법

### backend

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
```

`.env`는 `backend/` 디렉터리에서 실행할 때 읽힙니다. `backend/.env.example`을 복사한 뒤 값을 채워 주세요.

### simulation_engine

```bash
cd simulation_engine
PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest
```

Python 3.12 이상, 표준 라이브러리만 사용합니다. 시스템 `python3`가 3.12 미만이면 `StrEnum` import 오류로 실패하므로 위처럼 3.12를 지정해 실행합니다.

### frontend

```bash
cd frontend
yarn install
yarn dev      # 개발 서버, /api 요청은 http://localhost:8000 으로 프록시
yarn test
yarn build
```

Node.js와 yarn(4.18.1, `packageManager` 필드)이 필요합니다.

## 문서

상세 설계와 개발 규칙은 [docs/README.md](docs/README.md)를 참고하세요.
