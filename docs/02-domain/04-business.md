# Business

> 원본: README §3.4, §3.5, §5

### 3.4 Company — 기업

시민을 고용하고 상품 및 서비스를 판매하는 경제 주체.

주요 속성:

- id, worldId
- name, industry
- buildingId
- 현금 잔액: 별도 컬럼 없음. 기업 소유 CASH 계좌(accounts.balance)에서 조회한다 ([경제](06-economy.md)) (코드 기준)
- employeeCapacity
- employeeCount
- baseWage
- operatingCost
- status: ACTIVE, DISTRESSED, BANKRUPT, CLOSED

기업은 급여와 운영 비용을 지급하고, 시민의 소비를 통해 매출을 얻는다.

현금 사정과 고용 수요에 따라 신규 채용, 임금 조정, 해고 등의 의사결정을 수행한다.

### 3.5 Employment — 고용 관계

시민과 기업 사이의 고용 이력을 관리한다.

주요 속성:

- id, worldId
- citizenId, companyId
- salary
- hiredTick, terminatedTick
- status

한 시민은 동시에 하나의 활성 고용 관계만 가진다.

고용 관계를 별도로 관리하면 이직과 실직 이력 및 기업별 고용 통계를 추적할 수 있다.

### 3.6 업종 (엔진 v1)

엔진 v1은 업종 4개를 쓴다. 아래 수치는 모두 설정값이다. 제품 규칙이 아니며 보정 결과(AC18)에 따라 바뀔 수 있다.

| 업종 | 입지 건물 | 기업 수 | base_wage (월) | operating_cost (월) | employee_capacity |
|---|---|---:|---:|---:|---:|
| RETAIL | 상업 | 3 | 240만 원 | 500만 원 | 12 |
| RESTAURANT | 상업 | 3 | 240만 원 | 500만 원 | 12 |
| WHOLESALE | 사무 | 2 | 300만 원 | 500만 원 | 6 |
| BUSINESS_SERVICE | 사무 | 2 | 360만 원 | 500만 원 | 2 |

- employee_capacity는 기업당 정원이다. 보정안 C1로 확정한 설정값이다.
- 초기 고용은 88명이며 정원 합과 같다 (3×12 + 3×12 + 2×6 + 2×2).
- 업종 간 공급 관계는 [06-economy §6.5](06-economy.md)를 따른다.

## 5. 기업 행동 시스템

기업은 각 월의 매출, 비용, 현금 잔액, 인력 수요에 따라 의사결정을 수행한다.

### 5.1 채용

- 매출 또는 예상 수요가 증가한다.
- 현재 인력이 부족하다고 판단한다.
- 추가 급여를 지급할 충분한 자금이 있다.
- 조건을 만족하는 구직자가 존재한다.

위 조건을 충족하면 채용을 시도한다.

### 5.2 해고

- 매출 감소가 일정 기간 지속된다.
- 급여 지급 후 운영 자금이 부족할 것으로 예상된다.
- 현재 인력이 필요한 수준을 초과한다.

이 조건에 따라 확률적으로 또는 규칙에 따라 해고를 실행한다.

### 5.3 재무 악화 및 파산

기업의 현금이 부족하면 DISTRESSED 상태로 전환한다.

정해진 기간 내 현금 사정이 회복되지 않으면 BANKRUPT 상태로 전환할 수 있다.

파산 시 활성 고용 관계를 종료하고 기업의 경제활동을 중단한다.

### 5.4 상태 전이 (엔진 v1)

월말 정산의 상태 평가 단계에서 판정한다 ([06-economy §6.8](06-economy.md)). 월 고정비 = 급여 총액 + operating_cost이며, 급여 총액은 활성 고용의 salary 합계다.

| 현재 상태 | 조건 | 다음 상태 |
|---|---|---|
| ACTIVE | 현금 < 월 고정비 × 1, 또는 운영비 미납 | DISTRESSED |
| DISTRESSED | 현금 ≥ 월 고정비 × 2 | ACTIVE |
| ACTIVE, DISTRESSED | 급여 전액 미지급, 또는 DISTRESSED 3개월 연속 | BANKRUPT |

평가 순서 (2026-11-19 확정): 월말에 모든 조건을 평가한 뒤 최종 상태를 하나로 정한다.

1. 급여를 전액 지급하지 못했으면 다른 조건과 관계없이 BANKRUPT.
2. 재무 악화 조건(현금 < 월 고정비 × 1, 또는 운영비 미납)을 충족하면 ACTIVE는 DISTRESSED(연속 1개월)가 되고, DISTRESSED는 연속 개월 수에 1을 더한다. 이 달에는 회복하지 않는다.
3. 재무 악화 조건을 충족하지 않은 DISTRESSED는 현금 ≥ 월 고정비 × 2이면 ACTIVE(연속 0개월)로 돌아가고, 아니면 DISTRESSED를 유지하며 연속 개월 수에 1을 더한다.
4. 연속 개월 수가 3 이상이면 BANKRUPT.

- 운영비 미납은 재무 악화 조건일 뿐 DISTRESSED를 바로 확정하지 않는다. 같은 달 급여 미지급이면 BANKRUPT, 연속 3개월째면 BANKRUPT가 최종 상태다.
- DISTRESSED 연속 개월 수는 평가마다 센다. DISTRESSED가 아닌 달에는 0으로 되돌린다.
- BANKRUPT에서 다른 상태로 돌아가지 않는다.
- CLOSED는 v1에서 쓰지 않는다.
- 위 수치(고정비 배수 1·2, 3개월)는 설정값이다.
- 운영 중은 ACTIVE 또는 DISTRESSED를 뜻한다. 소비, 운영비, 공공 조달 대상 정의에 공통으로 쓴다.

### 5.5 채용·해고 (엔진 v1)

채용과 해고는 상태 평가 직후에 처리한다. 같은 달 평가 결과를 따른다. 기업은 id 순으로 처리한다.

채용:

- 대상: ACTIVE 기업.
- 조건: 방금 마감한 회계월의 잉여가 0보다 크고, 정원에 여유가 있다.
  - 잉여 = (시민 소비 + B2B + 공공 조달 + 수출 매출) − 급여 − 실제 지급 운영비.
  - 공공 조달과 수출은 상태 평가보다 먼저 실행된다. 따라서 당월 조달·수출 대금은 당월 재무 상태와 채용 판단에 모두 반영된다 ([06-economy §6.8](06-economy.md)).
- 한도: 월 1명.
- 후보: 실직자 중 시드 RNG로 고른다.
- 급여: 기업의 base_wage.

해고:

- 대상: DISTRESSED 기업.
- 한도: 월 1명.
- 대상 시민: 가장 최근에 채용된 고용부터 해고한다 (hired_tick이 가장 늦은 고용).
- 해고된 시민은 UNEMPLOYED가 된다.

### 5.6 파산 (엔진 v1)

- 파산 시 활성 고용을 모두 종료한다. terminated_tick은 파산 Tick이다.
- 파산 기업은 급여, 운영비, 매출 거래를 중단한다. 소비 대상, B2B 공급자, 공공 조달 대상에서 빠진다.
- 잔액은 계좌에 그대로 남는다.

### 5.7 고용 종료 상태 (엔진 v1)

- 고용 종료 시 employments.status는 해고·파산 구분 없이 TERMINATED 하나로 둔다. terminated_tick을 함께 기록한다.
- 종료 사유는 고용 상태가 아니라 이벤트 `citizen.employment.changed`의 `reason`으로 구분한다 ([03-simulation-engine §7.3](../03-architecture/03-simulation-engine.md)).
