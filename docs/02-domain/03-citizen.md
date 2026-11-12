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

