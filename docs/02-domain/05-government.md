# Government

> 원본: README §3.7

### 3.7 Government & Policy — 정부와 정책

정부는 세금을 징수하고 공공 지출을 실행한다.

정책 속성:

- worldId
- incomeTaxRate
- welfareAmount
- effectiveTick
- version

초기 소득세율은 15%로 설정한다.

> 코드 기준 갱신: 엔진 클래스명은 WorldPolicy(`simulation_engine/src/simulation_engine/entities/policy.py:8-12`)다. income_tax_rate는 정수 bps로 기본값 1500(= 15%), welfare_amount 기본값 0, effective_tick은 정책이 적용되는 Tick이다. 엔진에는 아직 Government 엔티티 클래스가 없다 (`entities/government.py`는 docstring만 있음). 정부 계정은 Account(owner_type=GOVERNMENT)로 표현한다 (코드 기준).

정책 변경은 명령으로 접수하며, 다음 시뮬레이션 Tick의 명확한 경계에서 적용한다.

### 3.7.1 세입과 세출 계정 (엔진 v1)

정부의 자금은 GOVERNMENT/TREASURY 계정에 둔다. 소득세와 운영비 공공요금 몫이 들어오고, 복지와 공공 조달이 나간다.

### 3.7.2 복지 지급 (엔진 v1)

- 대상: 실직 상태(UNEMPLOYED)인 시민.
- 금액: WorldPolicy.welfare_amount. 기본값 100만 원이다. 설정값이다.
- 시점: 월 1회, 월말 정산의 복지 단계 ([06-economy §6.8](06-economy.md)).
- 거래: WELFARE. 정부 TREASURY에서 시민 CASH로 이동한다.
- 정부 잔액이 모자라면 시민 id 순으로 한 명분 전액을 줄 수 있는 시민까지만 지급한다. 부분 지급은 없고, 나머지 시민은 받지 못한다 (2026-11-19 확정).
- 복지금은 다음 달 소득에 포함된다 ([03-citizen §4.5](03-citizen.md)).

### 3.7.3 공공 조달 (엔진 v1)

- 시점: 월 1회, 월말 정산의 공공 조달 단계. 복지 지급 뒤에 실행한다.
- 예산 = (정부 TREASURY 잔액 − 다음 달 예상 복지액) × 50%.
- 계산식 (2026-11-19 확정): R = 복지금 × 현재 실직자 수, B = max(0, 국고 잔액 − R), P = ⌊B × 0.5⌋. P가 조달 예산이다. 0.5는 설정값(procurement_budget_bps 5000)이다.
- 현재 실직자 수와 국고 잔액은 그 달 복지 지급 직후, 채용·해고 이전 값이다. 월말 정산 순서(복지 → 조달 → … → 채용·해고)와 일치한다.
- P가 0이면 집행하지 않는다.
- 대상: 운영 중(ACTIVE·DISTRESSED)인 WHOLESALE·BUSINESS_SERVICE 기업. 대상이 없으면 집행하지 않는다.
- 분배: 대상 기업에 균등 분할한다. 원단위 나머지는 id 순으로 한 단위씩 나눈다.
- 거래: PUBLIC_PROCUREMENT. 정부 TREASURY에서 기업 CASH로 이동한다.
- 조달 대금은 기업 매출의 '공공 조달' 구분이다 ([06-economy §6.7](06-economy.md)).

