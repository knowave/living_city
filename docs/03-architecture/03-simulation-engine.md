# 시뮬레이션 엔진

> 원본: README §7

## 7.1 엔진 설계 원칙

Pure Python 기반으로 구현한다.

FastAPI, SQLAlchemy, PostgreSQL 등의 프레임워크와 직접 결합하지 않는다.

입력:

- WorldState
- SimulationConfig
- Policy
- RandomSeed
- 현재 Tick

출력:

- 변경된 WorldState
- DomainEvents
- EconomyTransactions
- Metrics

## 7.2 실행 순서

1. 현재 세계 상태 조회
2. 적용 예정인 정책 변경 반영
3. 날짜 및 월말 여부 확인
4. 시민 행동 결정
5. 논리적 이동과 활동 상태 갱신
6. 월말인 경우 기업, 급여, 세금, 소비 및 복지 정산
7. 기업의 채용과 해고 결정
8. 세계 상태 및 경제 불변식 검증
9. 변경 사항과 이벤트 원자적 저장
10. 커밋 이후 SSE 이벤트 발행
11. 다음 Tick 대기

## 7.3 결정적 실행

시뮬레이션 엔진은 난수 시드와 실행 규칙 버전을 관리한다.

동일한 초기 상태, 동일한 정책 입력 순서, 동일한 엔진 버전, 동일한 난수 흐름에서 동일한 결과가 나오도록 설계한다.

가능하면 난수 스트림을 시민, 이벤트 종류, Tick 기준으로 분리하여 처리 순서 변경이 결과 전체를 불필요하게 흔들지 않도록 한다.

## 7.4 실행 주체

서버의 독립적인 Simulation Runner가 Tick을 진행한다.

HTTP 요청이나 SSE 구독자의 존재 여부는 엔진 실행 여부에 영향을 주지 않는다.

MVP에서는 하나의 서버 프로세스가 세계별 실행 소유권을 관리할 수 있지만, 동일 세계를 여러 Runner가 동시에 실행하지 못하도록 보장해야 한다.

향후 멀티 인스턴스 환경에서는 별도 Worker와 분산 실행 소유권 제어를 도입한다.

## 7.5 엔진 구성

System 중심 구조를 채택한다. 경량 ECS 아이디어와 도메인 중심 설계를 함께 쓰며, 완전한 ECS는 아니다.

| 구성 요소 | 책임 |
|-----------|------|
| Simulation Engine | 시간(Tick) 진행과 System 실행 순서 관리 |
| SimulationClock | 날짜·시간 계산, System 실행 주기 결정 |
| World State | 특정 Tick의 도시 전체 논리 상태 |
| Entities | 시민·기업·정부·건물. dataclass로 정의 |
| Systems | 행동·고용·급여/세금·소비·기업·정부·이동 규칙으로 상태 전이 |
| Domain Events | 발생한 변화 기록 |
| Policies | 세금·고용 등 정책 규칙. System이 읽어서 적용 |

### 원칙

- System은 시간/Tick을 변경하지 않는다. Tick 진행은 엔진만 한다.
- System 실행 순서는 명시적으로 정의한다.
- 시민 순회 순서는 결정적이어야 한다. 예: id 정렬.
- 전역 random을 쓰지 않는다. 주입된 RNG만 쓴다.
- 스냅샷에서 재개할 때 RNG 상태도 함께 복원한다.
- 외부 명령(REST)은 상태를 직접 수정하지 않는다. Tick 경계에서 적용한다.
- 경제 거래는 불변식(자금 보존)을 검증한다.
- 엔진에 별도 `domain/` 패키지는 없다. 엔진 패키지가 도메인 모델을 소유한다.

## 7.6 System과 Agent

System 중심을 택한 이유는 다음과 같다.

- 대량의 시민을 일괄 처리하기 쉽다.
- System 실행 순서를 관리하기 쉽다.
- 개별 성향은 System이 시민 속성을 참고해 표현한다.

Agent 프레임워크와 행동 트리는 초기에 도입하지 않는다.

## 7.7 System 실행 주기 (검토안)

1 Tick = 시뮬레이션 1시간이다. 시간 규칙은 [07-simulation-rules](../02-domain/07-simulation-rules.md)를 따른다.

| System | 실행 주기 |
|--------|-----------|
| 시민 행동 결정 | 매 Tick |
| 출퇴근·이동 | 매 Tick |
| 소비 | 매 Tick 또는 일 단위 |
| 급여 | 월 1회 |
| 소득세 | 급여 지급 시 |
| 기업 재무 평가 | 월 1회 |
| 채용·해고 | 월 1회 |
| 연령 증가 | 연 1회 |

## 7.8 패키지 구조

```
simulation_engine/
├── pyproject.toml
├── README.md
├── src/simulation_engine/
│   ├── __init__.py            # __version__ (engineVersion)
│   ├── engine.py              # Tick 진행·System 실행 순서 관리
│   ├── clock.py               # 시뮬레이션 시간·System 실행 주기
│   ├── context.py             # Tick 실행 컨텍스트
│   ├── entities/  {world, citizen, household, company, employment, building, government, policy}.py
│   ├── economy/   {account, transaction, ledger}.py   # 경제 원장
│   ├── world/     {state, config, generator, snapshot, map_chunk}.py
│   ├── systems/   {behavior, employment, payroll, consumption, business, government, movement}.py
│   ├── events/    {models, generator}.py
│   ├── metrics/   {models}.py
│   ├── policies/  {taxation, employment}.py
│   └── utils/     {probability, random}.py
└── tests/         # test_package, test_entities, test_records, test_economy (코드 기준)
```

현재 상태: 엔티티·원장·이벤트·스냅샷·청크·지표 레코드는 backend 모델(backend/app/models)을 미러링한 dataclass로 정의했다. System·엔진 실행 로직은 구현하지 않았다. (코드 기준) `world/state.py`, `world/config.py`, `world/generator.py`, `engine.py`, `clock.py`, `context.py`, `systems/*`, `policies/*`, `events/generator.py`, `utils/*`는 모듈 docstring만 있는 빈 스텁이다. `entities/government.py`도 빈 스텁이며 정부 정책은 `WorldPolicy`(`entities/policy.py`)로 표현한다. `Household`에는 `memberIds`가 없고 소속은 `Citizen.household_id`로 연결한다 (`entities/household.py`, `entities/citizen.py`).

미러링 규칙: DB 전용 필드(created_at, updated_at, world_id, World의 낙관적 락 version)는 두지 않는다. id는 `uuid.UUID`. backend에서 Float인 `risk_tolerance`, `consumption_preference`는 엔진에서 정수 bps(10000 = 1.0)이며, 변환은 backend 어댑터가 맡는다.

## 7.9 아키텍처 검증 기준

엔진은 FastAPI 없이 테스트와 Python에서 독립 실행할 수 있어야 한다.

## 7.10 미정 (TBD)

- Snapshot 및 엔진 재시작 정책 세부
- 동시 실행 제어 세부 (7.4 이상)
