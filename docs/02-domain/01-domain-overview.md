# 도메인 개요

> 원본: README §3 (개요, 새로 작성)

README §3의 엔티티 목록과 관계를 요약한 연결 문서이다.

## 엔티티

| 엔티티 | 역할 |
|---|---|
| World | 시뮬레이션의 최상위 Aggregate Root. 시민, 기업, 정책, 지도, 경제 상태 및 사건의 소유 범위를 정의한다. |
| Citizen | 도시의 자율적 경제 및 사회 활동 주체. |
| Household | 주거 및 공동 생활비를 관리하는 단위. |
| Company | 시민을 고용하고 상품 및 서비스를 판매하는 경제 주체. |
| Employment | 시민과 기업 사이의 고용 이력. |
| Building | 지도 위에 존재하는 공간 객체. 시민의 주거와 기업의 활동 장소를 나타낸다. |
| Government & Policy | 세금을 징수하고 공공 지출을 실행하는 정부와 그 정책. |
| Economy (Account, Transaction, LedgerEntry) | 시민, 기업, 정부 사이의 자금 이동을 관리하는 경제 원장. |
| WorldEvent | 도시에서 발생한 중요한 상태 변경 기록. |
| WorldSnapshot | 특정 Tick의 세계 상태 저장본. |

## 관계

- 모든 엔티티는 worldId로 World에 속한다.
- Citizen은 householdId, homeBuildingId, currentBuildingId, employerId로 Household, Building, Company와 연결된다.
- Household는 residenceBuildingId로 Building을 가리킨다. 시민의 소속 가구는 Citizen.householdId로 표현하며 Household에는 memberIds 필드가 없다 (코드 기준: `simulation_engine/src/simulation_engine/entities/household.py:8-11`, `citizen.py:10`)
- Company는 buildingId로 Building을 가리킨다.
- Employment는 citizenId와 companyId로 Citizen과 Company를 잇는다.
- Account는 시민, 기업 또는 정부가 소유한다.
- WorldSnapshot은 lastEventSequence로 WorldEvent와 연결된다.

## 문서 목록

| 문서 | 내용 |
|---|---|
| [02-world.md](02-world.md) | World, Building, WorldEvent, WorldSnapshot |
| [03-citizen.md](03-citizen.md) | Citizen, Household, 시민 행동 시스템 |
| [04-business.md](04-business.md) | Company, Employment, 기업 행동 시스템 |
| [05-government.md](05-government.md) | Government & Policy |
| [06-economy.md](06-economy.md) | Economy, 경제 시뮬레이션 |
| [07-simulation-rules.md](07-simulation-rules.md) | 시간, 자금 보존, 결정적 실행, 정책 적용 시점 |
