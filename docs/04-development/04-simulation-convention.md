# Simulation Engine 컨벤션

> 근거: README §3.8, §6.3, §7.1, §7.3. simulation_engine/은 엔티티 dataclass(backend 모델 미러링)까지 있고 System 실행 로직은 아직 구현하지 않았다.

- Pure Python으로 구현하고 FastAPI, SQLAlchemy, PostgreSQL 등과 직접 결합하지 않는다. (README §7.1)
- 입력은 WorldState, SimulationConfig, Policy, RandomSeed, 현재 Tick이다. 출력은 변경된 WorldState, DomainEvents, EconomyTransactions, Metrics다. (README §7.1)
- 난수 시드와 실행 규칙 버전(engineVersion)을 관리한다. 가능하면 난수 스트림을 시민, 이벤트 종류, Tick 기준으로 분리한다. (README §7.3, §3.1)
- 화폐는 정수형 최소 화폐 단위이며 부동소수점을 쓰지 않는다. (README §3.8)
- 자금은 계정 간 이전으로만 움직이고, Tick 처리 중 경제 불변식을 검증한다. (README §6.3, §7.2 8단계)
- 정책 변경은 Tick 시작 시 반영한다. (README §7.2 2단계, §9.4)

## 패키지 구조 / 모듈 네이밍

- 경로: `simulation_engine/src/simulation_engine/` (src 레이아웃). 테스트는 `simulation_engine/tests/`.
- 모듈은 snake_case 파일 하나가 책임 하나를 갖는다. 각 모듈에는 책임을 설명하는 docstring을 둔다.
- 별도 `domain/` 패키지는 두지 않는다. 엔진 패키지가 도메인 모델(entities)을 소유한다.
- 하위 패키지:

| 패키지 | 책임 |
|--------|------|
| `entities/` | 세계·시민·가구·기업·고용·건물·정부·정책 엔티티 |
| `economy/` | 경제 원장: 계정·거래·원장 항목 |
| `metrics/` | 도시 지표 모델 |
| `world/` | WorldState, 시뮬레이션 설정, 초기 세계 생성, 스냅샷, 맵 Chunk |
| `systems/` | 행동·고용·급여·소비·기업·정부·이동 규칙에 따른 상태 전이 |
| `events/` | 도메인 이벤트 모델과 생성 |
| `policies/` | 세금·고용 등 정책 규칙 |
| `utils/` | 확률·난수 보조 |

- 최상위 모듈: `engine.py`(Tick 진행, System 실행 순서), `clock.py`(시뮬레이션 시간, System 실행 주기), `context.py`(Tick 실행 컨텍스트).

## 코딩 규칙

- 엔진 코드와 테스트 모두 표준 라이브러리만 쓴다. FastAPI, SQLAlchemy, Pydantic, psycopg를 import하지 않는다. 서드파티 의존성은 0이다. (Python >= 3.12)
- 타입 힌트를 사용한다.
- 엔티티는 `dataclass(slots=True, kw_only=True)`로 정의한다. 필드는 backend 모델과 같은 이름을 쓰고, DB 전용 필드(created_at, updated_at, world_id)는 두지 않는다.
- System 인터페이스는 `typing.Protocol`(`run(state, rng) -> list[DomainEvent]`)로 정의할 예정이다.
- 화폐는 정수(원)다. 비율은 정수 basis point(bps)로 표현한다. 예: 1500 = 15%.
- 상태·유형 값은 `StrEnum`으로 정의한다 (코드 기준: `WorldStatus`, `CompanyStatus`, `BuildingType`, `AccountOwnerType`, `AccountType`, `TransactionType`, `MetricCode`). 단 `World.status`, `Company.status`, `Citizen.employment_status`, `Employment.status`, `Building.status`, `Building.type` 필드는 enum이 아니라 `str`이다 (enum 값을 문자열로 저장) (코드 기준).
- 상태 변경은 System을 통해서만 한다.
- 난수는 주입된 RNG만 쓴다. 전역 `random`을 쓰지 않는다.

## 테스트

- `unittest`를 쓴다. pytest는 쓰지 않는다.
- 실행: `cd simulation_engine && PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest` (코드 기준. 시스템 python3가 3.12 미만이면 실패)

## .omc 위치

- `.omc`는 `simulation_engine/` 최상단에만 둔다. `src/`, `tests/` 아래에는 만들지 않는다.

## 미정

- 린터 / 포매터: TBD
