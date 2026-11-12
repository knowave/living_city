# simulation_engine

Living City의 시뮬레이션 엔진 패키지입니다.

## 목적

- Pure Python으로 작성합니다. 표준 라이브러리만 사용하며 FastAPI 등 외부 프레임워크에 의존하지 않습니다.
- System 중심(경량 ECS + 도메인 중심) 구조를 따릅니다.
- 현재 구현 상태: 엔티티(World, Citizen, Household, Company, Employment, Building, WorldPolicy), 경제 원장(Account, Transaction, LedgerEntry), 월드 레코드(WorldEvent, WorldSnapshot, MapChunk), 지표 레코드(WorldMetric)는 dataclass로 구현되어 있습니다.
- 아직 구현하지 않은 부분(docstring만 있는 스텁): Tick 진행과 시간(engine, clock, context), System 전체(systems/*), 정책(policies/*), 이벤트 생성(events/generator), 월드 상태·설정·생성(world/state, world/config, world/generator), 정부 엔티티(entities/government), 유틸리티(utils/*).

## 디렉터리 구조

```
simulation_engine/
├── pyproject.toml
├── README.md
├── src/simulation_engine/
│   ├── __init__.py      # __version__ (engineVersion)
│   ├── engine.py        # Tick 진행·System 실행 순서 관리
│   ├── clock.py         # 시뮬레이션 시간·System 실행 주기
│   ├── context.py       # Tick 실행 컨텍스트
│   ├── entities/        # 도메인 모델 (world, citizen, household, company, employment, building, policy; government는 스텁)
│   ├── economy/         # 경제 원장 (account, transaction, ledger)
│   ├── metrics/         # 도시 지표 모델 (models)
│   ├── world/           # 월드 상태·설정·생성 (state, config, generator는 스텁; snapshot, map_chunk 구현)
│   ├── systems/         # System (behavior, employment, payroll, consumption, business, government, movement)
│   ├── events/          # 도메인 이벤트 (models, generator)
│   ├── policies/        # 정책 (taxation, employment)
│   └── utils/           # 유틸리티 (probability, random)
└── tests/               # unittest 기반 테스트
```

## 테스트 실행

```bash
cd simulation_engine && PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest
```

시스템 `python3`(3.9 등 3.12 미만)에서는 `StrEnum`이 없어 실패합니다. Python 3.12 이상이 필요합니다.

## 규칙

- `.omc`는 이 디렉터리(`simulation_engine/`) 최상단에만 둡니다. `src/`, `tests/` 아래에는 만들지 않습니다.
