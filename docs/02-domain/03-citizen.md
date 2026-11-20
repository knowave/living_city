# Citizen

> 원본: README §3.2, §3.3, §4

### 3.2 Citizen — 시민

도시의 자율적 경제 및 사회 활동 주체.

주요 속성:

- id, worldId, householdId
- name, age
- homeBuildingId, currentBuildingId
- employmentStatus
- employerId
- 현금 잔액: 별도 컬럼 없음. 시민 소유 CASH 계좌(accounts.balance)에서 조회한다 ([경제](06-economy.md)) (코드 기준)
- happiness, health
- skills, riskTolerance, consumptionPreference
- currentActivity
- currentDestination, arrivalTick

> 코드 기준 갱신: 엔진 Citizen(`simulation_engine/src/simulation_engine/entities/citizen.py:9-24`)은 skills를 `dict[str, int]`로, riskTolerance와 consumptionPreference를 정수 bps(10000 = 1.0)로 가진다. 필드명은 snake_case이며 worldId는 없다 (코드 기준).

각 시민은 개인별 특성에 따라 소비, 구직, 이동 등의 행동을 결정한다.

시민의 돈과 행동 상태는 별도로 관리한다. 예를 들어 행복도가 높더라도 현금이 부족하면 원하는 소비를 실행하지 못할 수 있다.

### 3.3 Household — 가구

주거 및 공동 생활비를 관리하는 단위.

주요 속성:

- id, worldId
- residenceBuildingId
- memberIds (코드 기준: 엔진·백엔드 모델에 필드 없음. 소속은 Citizen.householdId로 표현한다)
- monthlyHousingCost

MVP에서는 시민 1명당 가구 1개로 시작한다.

향후 가족과 공동 소비, 이사, 가구별 저축 및 부채를 확장할 수 있도록 별도 도메인으로 유지한다.

## 4. 시민 행동 시스템

### 4.1 행동 원칙

시민은 사용자가 직접 행동을 지시하지 않아도 자신의 상태를 기준으로 행동한다.

MVP에서는 규칙 기반 의사결정과 가중치 확률을 사용한다.

입력 조건:

- 현재 시간
- 고용 상태
- 보유 현금
- 월 소득
- 소비 성향
- 위험 선호도
- 개인의 기본 생활비
- 이전 행동과 현재 목적지

출력 결과:

- 출근
- 귀가
- 소비
- 구직
- 휴식
- 기타 일상 행동

### 4.2 구직 행동

실직 상태인 시민은 자신의 기술 수준, 위험 선호도, 기업의 채용 조건을 평가한다.

구직 활동의 성공 여부는 기업의 채용 수요와 시민의 능력, 확률적 요인으로 결정한다.

기업에 채용 가능한 자리가 없으면 구직 활동은 실패한다.

### 4.3 소비 행동

시민은 세후 소득과 현금 잔액, 필수 생활비, 소비 성향에 따라 소비 예산을 설정한다.

소비는 가상의 상점이나 서비스 기업을 대상으로 발생한다.

소비 실행 시 시민 계정에서 기업 계정으로 실제 자금이 이동한다.

### 4.4 이동 행동

시민은 논리적 출발지, 목적지, 이동 시작 Tick 및 예상 도착 Tick을 가진다.

시뮬레이션 엔진은 이동의 시작과 완료를 결정한다.

프론트엔드는 도로망을 사용해 시각적 경로를 계산하고 이동 애니메이션을 표현한다.

사용자가 브라우저를 닫더라도 시민의 논리적 이동은 정상적으로 진행된다.

#### 이동 시간 규칙

- `TILES_PER_TICK = 40`: 시뮬레이션 1 Tick당 시민이 이동할 수 있는 타일 수(도메인 규칙).
- `arrivalTick = departureTick + max(1, ceil((|x2 - x1| + |y2 - y1|) / TILES_PER_TICK))`
- (x1, y1), (x2, y2)는 출발·도착 건물 입구 도로 타일 좌표다. 실제 경로 길이가 아니라 맨해튼 거리를 쓴다. 경로가 길면 화면상 속도가 빨라 보일 수 있으며 초기에는 허용한다.
- 이 계산은 Python 시뮬레이션 엔진이 소유한다. 프론트엔드는 출발·도착 Tick을 받아 표현만 한다.
- Python 참고 시그니처(이번 phase에서 엔진 코드는 수정하지 않는다): `calculate_arrival_tick(departure_tick, origin, destination, speed=40)`
- Phase 3 프론트엔드의 동일 공식 구현은 Mock 엔진 안의 임시 코드이며 영구 도메인 로직이 아니다. Phase 4~5에서 엔진 값으로 대체한다.

#### 이동 이벤트(프론트엔드 가정)

SSE `citizen.movement.started`의 제안 payload다. 백엔드는 아직 정의하지 않았다.

```json
{ "citizen_id": "...", "from_building_id": "...", "to_building_id": "...", "start_tick": 0, "arrival_tick": 0 }
```

#### TBD

- 실제 시간으로 1 Tick이 몇 초인가: TBD. Phase 3 Mock은 10초, 배속 x1/x4/x16을 쓴다.

### 4.5 엔진 v1 행동 규칙

엔진 v1([phase-06](../05-phases/phase-06-simulation-engine-v1.md))의 상태 값과 하루 일과다. 수치는 설정값이다.

#### 상태 값

| 필드 | 값 | 설명 |
|---|---|---|
| employment_status | EMPLOYED, UNEMPLOYED | 활성 고용 관계 유무 |
| current_activity | AT_HOME, MOVING, WORKING, SHOPPING | 현재 활동 |
| happiness, health | 초기값 50, 100 | v1에서는 초기값만 보유하고 변하지 않는다. 행복도 변화 규칙은 v1에서 제외한다 |

엔진은 이 4개 값만 낸다. IDLE은 frontend Mock 전용이다.

- 목적지는 `current_activity`가 아니라 `current_destination`(건물 id)으로 구분한다.
- 시민은 `arrival_tick`에 목적지에 도착한다. 도착 전까지 MOVING이다.
- Phase 3 Mock의 IDLE 값은 이 목록과 다르다. 엔진 연동 시 맞춘다.

#### 하루 일과

| 시각 | 취업자 | 실직자 |
|---|---|---|
| 08시 | 집에서 출발 (MOVING). 도착 시 WORKING. 소비 이동 중이면 그날 출근을 건너뛴다 | AT_HOME 유지 |
| 18시 | 직장에서 귀가 출발 (MOVING). 도착 시 AT_HOME | AT_HOME 유지 |
| 19시 이후 | 소비 출발 조건을 만족하면 소비 출발 ([소비 규칙](#소비-규칙)) | 소비 출발 조건 적용 |

- 취업자 활동 흐름: AT_HOME → MOVING → WORKING → MOVING → AT_HOME.
- 소비 활동 흐름: AT_HOME → MOVING → SHOPPING → MOVING → AT_HOME.
- 이동 도착 Tick은 §4.4 공식을 따른다.
- 소비 이동은 출근보다 우선하지 않는다. 소비 이동 중에 08시가 되면 그날 출근만 건너뛴다. 급여에는 영향이 없다.

#### 소비 규칙

- 소비일: Tick의 시각이 19시 이상이면 그 날짜, 아니면 전날이다.
- 소비일 하루에 최대 1회 소비한다.
- 소비 출발 조건: 소비일에 아직 소비하지 않았고, 19시 이후에 집에 있거나 19시 이후에 집에 도착했다. 자정을 넘겨도 된다. 마감 시각은 없다.
- 소비 출발 시 시민별 `last_shop_day`를 소비일로 기록한다 ([03-simulation-engine §7.10](../03-architecture/03-simulation-engine.md)).
- 소비 대상은 운영 중(ACTIVE·DISTRESSED) RETAIL·RESTAURANT 중 시드 RNG로 고른 기업이다.
- 월 소비 예산은 월 1회 월말 정산 직후 계산한다. 월 예산 = ⌊지난달 세후 소득 × consumption_preference ÷ 10000⌋ + ⌊max(0, 보유 현금 − 생활 예비금) × 추가 소비율 ÷ 10000⌋.
- 보유 현금은 월말 급여·복지 직후 값이다. 이후 정산 단계는 시민 현금을 바꾸지 않으므로 채용·해고 뒤 현금과 같다. 계산한 예산은 엔진 내부 값 `monthly_budget`에 저장하고 다음 달 소비에 쓴다.
- 일 소비액 = min(잔액, ⌊월 예산 ÷ 30⌋). 소비액이 0원이면 외출하지 않는다.
- 생활 예비금은 1,000,000원, 추가 소비율은 3000bps(30%)다. 보정으로 정한 설정값이다.
- 이유: 소득 기준 소비만 있으면 시민 저축이 계속 쌓여 기업으로 돌아오지 않는다. 누적 현금에 비례한 추가 소비로 이 누수를 막는다.
- 지난달 세후 소득 = 세후 급여 + 복지금.
- 첫 달 예산은 세계 생성 시 같은 식으로 계산한다. 이때 지난달 소득은 취업자 월급의 85%(실직자는 0)이고, 보유 현금은 초기 현금이다.
- 소비 거래는 PURCHASE이며 시민 CASH에서 기업 CASH로 이동한다. 상점 도착 Tick에 거래하고 SHOPPING 상태로 그 Tick을 마친 뒤, 다음 Tick 시작에 귀가를 출발한다. 화면에서 쇼핑 중인 시민이 보이도록 상점에 1 Tick 머문다 (2026-11-19 결정).
- 변경 이유: 128×128 맵에서 19시까지 귀가하는 취업자가 약 16%뿐이라서, 19시 고정 시각 대신 소비일 기준으로 바꿨다.
