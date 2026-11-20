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

### 7.2.1 엔진 내부 Tick 순서 (v1)

7.2의 1–8단계는 엔진이 처리한다. 9–11단계는 backend 영역이다. 엔진 `step()`의 내부 순서는 다음과 같다.

1. 명령을 적용한다. 정책 변경은 Tick 시작에 반영한다.
2. 직전 Tick부터 상점에 있던(SHOPPING) 시민이 귀가를 출발한다.
3. 이동을 처리한다. arrival_tick이 현재 Tick인 시민을 도착시킨다.
4. 소비를 처리한다. 이번 Tick에 상점에 도착한 시민이 구매하고 SHOPPING으로 Tick을 마친다.
5. 행동을 결정한다. 08시 출근, 18시 귀가, 소비 출발을 처리한다 ([03-citizen §4.5](../02-domain/03-citizen.md)).
6. 월말 Tick이면 월말 정산을 한다. 급여 → 운영비 → 복지 → 공공 조달 → 수출 → 기업 상태 평가 → 채용·해고 → 월 소비 예산 계산 → `economy.month.closed` 순서다 ([06-economy §6.8](../02-domain/06-economy.md)).
7. 지표를 계산한다. 월말이면 월간 지표를 내고 `metrics.updated`를 낸다.
8. 불변식을 검사한다. 통과하면 `simulation.tick`을 내고 current_tick을 1 올린다.

`step()`은 TickResult(tick, events, transactions, ledger_entries, metrics)를 반환한다.

시간 계산: 1 Tick = 1시간, 하루 = 24 Tick, 월 = 30일이다. Tick t의 시각은 `t % 24`, 일은 `t // 24`다. 월말 Tick은 각 월의 마지막 Tick(`t % 720 == 719`)이다.

## 7.3 결정적 실행

시뮬레이션 엔진은 난수 시드와 실행 규칙 버전을 관리한다.

동일한 초기 상태, 동일한 정책 입력 순서, 동일한 엔진 버전, 동일한 난수 흐름에서 동일한 결과가 나오도록 설계한다.

가능하면 난수 스트림을 시민, 이벤트 종류, Tick 기준으로 분리하여 처리 순서 변경이 결과 전체를 불필요하게 흔들지 않도록 한다.

#### RNG 파생 스트림 (v1)

- 엔진은 RNG 상태를 저장하지 않는다. 필요할 때마다 시드와 키로 새 스트림을 만든다.
- `rng(seed, *keys)` = `random.Random(int.from_bytes(sha256(repr((seed,) + keys)).digest()[:8]))`.
- 키 예: `("shop", tick, citizen_id)`, `("hire", tick, company_id)`.
- 전역 `random`과 `hash()`를 쓰지 않는다. `hash()`는 프로세스마다 값이 달라진다.
- Snapshot에 저장하는 RNG 상태는 시드 값이다.

#### 이벤트 sequence (v1)

- 엔진이 세계별로 1부터 단조 증가하는 sequence를 붙인다.
- 다음 번호는 `next_event_sequence`로 저장한다.
- Snapshot의 `last_event_sequence`는 `next_event_sequence − 1`이다. backend는 이 값을 그대로 저장한다.

#### 이벤트 payload (v1)

| 이벤트 | payload |
|---|---|
| `citizen.movement.started` | `citizen_id`, `from_building_id`, `to_building_id`, `start_tick`, `arrival_tick` |
| `citizen.employment.changed` | `citizen_id`, `company_id`, `employment_status`(시민의 EMPLOYED·UNEMPLOYED), `reason`(`hired`·`fired`·`bankruptcy`) |
| `company.status.changed` | `company_id`, `from_status`, `to_status` |

- 고용 종료 사유는 `reason`으로만 구분한다. employments.status는 TERMINATED 하나다 ([04-business §5.7](../02-domain/04-business.md)).

#### 식별자와 멱등 키 (v1)

- 엔티티 id는 시드로 만드는 결정적 UUID다. `new_id(kind)` = `uuid.UUID(bytes=sha256(f"{seed}:{kind}:{n}")[:16], version=4)`. n은 kind별 카운터이며 Snapshot에 저장한다.
- 거래 idempotency_key = `{type}:{tick}:{주체 id}[:{보조}]`. 같은 입력이면 같은 키가 나온다.

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
├── scripts/       # calibrate, company_pnl, economy_report, perf (실측·보정 도구)
├── src/simulation_engine/
│   ├── __init__.py            # __version__ (engineVersion)
│   ├── engine.py              # Tick 진행·System 실행 순서 관리
│   ├── clock.py               # 시뮬레이션 시간·System 실행 주기
│   ├── context.py             # Tick 실행 컨텍스트
│   ├── entities/  {world, citizen, household, company, employment, building, government, policy}.py
│   ├── economy/   {account, transaction, ledger}.py   # 경제 원장
│   ├── world/     {state, config, generator, snapshot, map_chunk}.py
│   ├── systems/   {behavior, movement, consumption, payroll, business, employment, government, external}.py
│   ├── events/    {models, generator}.py
│   ├── metrics/   {models, calculator}.py
│   ├── policies/  {taxation, employment}.py
│   └── utils/     {probability, random}.py
└── tests/         # test_package, test_entities, test_records, test_economy, test_foundation,
                   # test_generator, test_citizen_systems, test_economy_systems, test_metrics,
                   # test_integration, helpers (코드 기준)
```

현재 상태 (코드 기준): v1이 구현되어 있다. 세계 생성(`world/generator.py`), Tick 엔진(`engine.py`, `clock.py`, `context.py`), 시민 System(`systems/movement`, `behavior`, `consumption`), 경제 System(`systems/payroll`, `business`, `government`, `employment`, `external`), 정책(`policies/`), 지표 계산(`metrics/calculator.py`), Snapshot 변환(`world/state.py`의 `to_snapshot`·`from_snapshot`), 결정적 RNG(`utils/random.py`)가 여기에 든다. `python -m unittest`로 테스트 95개를 실행하며 약 20~25초 걸린다. `world/map_chunk.py`, `world/snapshot.py`, `events/models.py`는 레코드 정의이고, `utils/probability.py`는 v1에서 비어 있다. `entities/government.py`는 빈 스텁이며 정부 정책은 `WorldPolicy`(`entities/policy.py`)로 표현한다. `Household`에는 `memberIds`가 없고 소속은 `Citizen.household_id`로 연결한다 (`entities/household.py`, `entities/citizen.py`).

미러링 규칙: DB 전용 필드(created_at, updated_at, world_id, World의 낙관적 락 version)는 두지 않는다. id는 `uuid.UUID`. backend에서 Float인 `risk_tolerance`, `consumption_preference`는 엔진에서 정수 bps(10000 = 1.0)이며, 변환은 backend 어댑터가 맡는다.

## 7.9 아키텍처 검증 기준

엔진은 FastAPI 없이 테스트와 Python에서 독립 실행할 수 있어야 한다.

## 7.10 Snapshot과 미정 사항

### Snapshot 형식 (v1)

`state_data`는 아래 키를 가진다. UUID는 문자열로 쓴다. 거래·원장·이벤트 이력은 넣지 않는다. 이력은 backend 테이블에 있다.

| 키 | 내용 |
|---|---|
| format_version | 형식 버전 (v1은 1) |
| engine_version | 엔진 버전 |
| seed | 시드. RNG 상태에 해당한다 |
| tick | 저장 시점의 Tick |
| world, policies, buildings, citizens, households, companies, employments, accounts | 엔티티를 dict로 바꾼 목록. id 순으로 정렬한다 |
| engine.next_event_sequence | 다음 이벤트 번호 |
| engine.id_counters | kind별 ID 카운터 |
| engine.distressed_months | 기업별 DISTRESSED 연속 개월 수 |
| engine.last_month_income | 시민별 지난달 세후 소득 (세후 급여 + 복지금) |
| engine.last_shop_day | 시민별 마지막 소비일 |
| engine.monthly_budget | 시민별 월 소비 예산 (월말 계산값, 다음 달 일 소비액 계산에 쓴다) |
| engine.movement_starts | 이동 출발 Tick과 arrival_tick |
| engine.trip_purpose | 시민별 진행 중 이동의 목적 (`commute`·`home`·`shop`). 도착 시 activity 판정에 쓰고 도착하면 지운다 |
| engine.month_accumulators | 월 중 누적 집계값 |
| engine.unpaid_opex | 기업별 미납 운영비 |

복구 후 진행 결과는 중단 없이 진행한 결과와 같아야 한다 ([phase-06 AC15](../05-phases/phase-06-simulation-engine-v1.md)).

### 미정 (TBD)

- 엔진 재시작 정책 세부: TBD (backend 영역).
- 동시 실행 제어 세부 (7.4 이상): TBD (backend 영역).
