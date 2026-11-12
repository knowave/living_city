# Economy

> 원본: README §3.8, §6

### 3.8 Economy — 경제 원장

경제 시스템은 시민, 기업, 정부 사이의 자금 이동을 관리한다.

주요 개념:

- Account: 시민, 가계, 기업, 정부 또는 시스템이 소유한 경제 계정 (코드 기준)
- Transaction: 경제적 사건
- LedgerEntry: 거래에 따른 계정 잔액 변화

시민·기업의 잔액은 별도 컬럼이 아니라 `accounts.balance`(CASH 계정)가 유일한 기준이다. 스키마는 [데이터 저장 설계 §10.4](../03-architecture/06-database.md)를 따른다.

**Account**

| 항목 | 값 |
|---|---|
| owner_type | CITIZEN / HOUSEHOLD / COMPANY / GOVERNMENT / SYSTEM |
| account_type | CASH / SAVINGS / TREASURY / ISSUANCE |
| currency | KRW |

GOVERNMENT와 SYSTEM 계정은 `world_id`로 식별하며 별도 governments 테이블은 없다. SYSTEM/ISSUANCE 계정만 음수 잔액을 허용한다.

> 코드 기준 갱신: 엔진 Account(`simulation_engine/src/simulation_engine/economy/account.py:24-47`)는 is_active 필드(기본 True)를 추가로 가진다. CITIZEN/HOUSEHOLD/COMPANY 계정은 해당 소유자 id를 정확히 하나 가지고, GOVERNMENT/SYSTEM 계정은 소유자 id를 갖지 않는다. 음수 잔액 제한은 `__post_init__`에서 검증한다. `world_id` 식별은 DB 쪽 규칙이다 (코드 기준).

**Transaction 유형**

| 유형 | 설명 |
|---|---|
| OPENING_BALANCE | 세계 생성 시 초기 자본 배분 |
| SALARY | 기업 → 시민 급여 지급 (소득세 분리) |
| PURCHASE | 시민 → 기업 소비 |
| INCOME_TAX | 소득세 정부 납부 |
| RENT | 임대료 지급 |
| WELFARE | 정부 → 시민 복지 지급 |
| ACCOUNT_TRANSFER | 계정 간 일반 이전 |
| CAPITAL_INVESTMENT | 기업 자본 투자 |
| ADJUSTMENT | 관리·보정 조정 |
| REVERSAL | 기존 거래의 취소 (원 거래를 참조) |

**LedgerEntry**: `amount`의 부호가 해당 계정의 잔액 증감이다 (양수 = 증가, 음수 = 감소). 한 거래의 amount 합계는 항상 0이다.

> 코드 기준 갱신: 엔진 LedgerEntry(`simulation_engine/src/simulation_engine/economy/ledger.py:15-18`)는 amount가 0이면 거부하고 entry_no는 1 이상이어야 한다. 거래 단위의 amount 합계 0 검증은 엔진 코드에 아직 없다 (코드 기준).

> 코드 기준 갱신: 엔진 Transaction(`simulation_engine/src/simulation_engine/economy/transaction.py:23-30`)은 transaction_type, tick, idempotency_key(필수), description, reverses_transaction_id, metadata를 가진다. REVERSAL은 reverses_transaction_id로 원 거래를 참조한다 (코드 기준).

급여 거래 예시 (월 급여 300만원, 소득세 15%):

| 계정 | amount |
|---|---:|
| 기업 CASH | -3,000,000 |
| 시민 CASH | +2,550,000 |
| 정부 CASH | +450,000 |
| 합계 | 0 |

MVP에서는 정수형 최소 화폐 단위를 사용하며, 부동소수점 실수로 화폐를 저장하지 않는다.

모든 실제 자금 이동은 계정 간 이전으로 처리하고, 최초 세계 생성 시에만 초기 자본을 배분한다.

초기 자본은 SYSTEM/ISSUANCE 계정에서 OPENING_BALANCE 거래로 각 계정에 배분한다. ISSUANCE 계정은 발행한 만큼 음수 잔액을 가지므로 전체 계정 잔액 합계는 0으로 유지되고 자금 보존 원칙(6.3)이 성립한다.

## 6. 경제 시뮬레이션

### 6.1 기본 경제 순환

기업은 시민에게 급여를 지급한다.

시민의 급여 일부는 소득세로 정부에 이전되고 나머지는 시민에게 지급된다.

시민은 세후 소득 중 일부를 소비하며, 소비 금액은 기업의 매출이 된다.

정부는 세수를 바탕으로 실업자 지원 등의 복지 지출을 실행한다.

### 6.2 소득세 15% 예시

월 급여가 300만원인 시민을 가정한다.

| 항목 | 금액 |
|---|---:|
| 기업 급여 지급 총액 | 3,000,000원 |
| 소득세 15% | 450,000원 |
| 시민 실수령액 | 2,550,000원 |
| 세후 소득의 70% 소비 | 1,785,000원 |
| 소비 후 잔액 증가분 | 765,000원 |

예시는 다른 생활비가 없다는 가정의 단순 모델이다.

실제로는 주거비와 필수 소비를 먼저 반영하고, 현금 잔액을 초과하는 소비는 허용하지 않는다.

### 6.3 자금 보존 원칙

초기 세계 생성 이후에는 원칙적으로 시민, 기업, 정부의 자금 합계가 임의로 증가하거나 감소하지 않아야 한다.

급여 지급, 세금, 소비, 복지 지급 등은 모두 자금 이전 거래로 처리한다.

화폐 발행, 은행 대출, 외부 무역 등의 시스템을 추가하기 전까지는 자금 보존을 주요 불변식으로 둔다.

### 6.4 경제 지표

- 취업률 및 실업률
- 시민 평균 소득
- 시민 평균 및 중위 자산
- 기업별 매출과 이익
- 기업 파산율
- 정부 세수와 지출
- 가계 총소비
- 소득 분포와 불평등 지표

월별 집계 결과를 스냅샷으로 관리한다.

지표는 `world_metrics`에 저장한다 ([스키마](../03-architecture/06-database.md)). 지표 코드는 12종이다.

> 코드 기준 갱신: 엔진 WorldMetric(`simulation_engine/src/simulation_engine/metrics/models.py:9-48`)의 metric_value는 `Decimal`이다. period는 HOURLY, DAILY, MONTHLY 중 하나이며, unit enum에는 위 표에 없는 RATIO가 추가로 있다 (코드 기준).

| code | 단위 | 설명 |
|---|---|---|
| POPULATION | COUNT | 전체 인구 |
| EMPLOYED_POPULATION | COUNT | 취업자 수 |
| UNEMPLOYMENT_RATE | PERCENT | 실업률 |
| AVERAGE_SALARY | KRW | 평균 월급 |
| AVERAGE_WEALTH | KRW | 평균 보유 자산 |
| TOTAL_CONSUMPTION | KRW | 기간별 총 소비 |
| TOTAL_COMPANY_REVENUE | KRW | 기간별 기업 매출 |
| ACTIVE_COMPANIES | COUNT | 운영 중인 기업 수 |
| BANKRUPT_COMPANIES | COUNT | 해당 기간 파산 기업 수 |
| GOVERNMENT_REVENUE | KRW | 기간별 정부 세입 |
| GOVERNMENT_EXPENDITURE | KRW | 기간별 정부 지출 |
| AVERAGE_HAPPINESS | INDEX | 평균 행복도 |

위 6.4 목록 중 중위 자산, 기업 이익, 불평등 지표는 아직 지표 코드가 없다 (TBD).

계산식과 집계 대상: TBD.

