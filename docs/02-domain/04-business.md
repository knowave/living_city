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

