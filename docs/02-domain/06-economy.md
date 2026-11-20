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

GOVERNMENT와 SYSTEM 계정은 `world_id`로 식별하며 별도 governments 테이블은 없다. SYSTEM/ISSUANCE 계정만 음수 잔액을 허용한다. SYSTEM/CASH는 외부 공급자 계정이다 ([6.6](#66-외부-계정과-도시-내부-자금)).

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
| OPERATING_EXPENSE | 기업 운영비 지급 (B2B·정부·외부, [6.5](#65-운영비-operating_expense)) |
| PUBLIC_PROCUREMENT | 정부 → 기업 공공 조달 ([05-government](05-government.md)) |
| EXPORT | 외부 자금의 운영 중 기업 재유입 (간소화 수출, [6.6](#66-외부-계정과-도시-내부-자금)) |

**LedgerEntry**: `amount`의 부호가 해당 계정의 잔액 증감이다 (양수 = 증가, 음수 = 감소). 한 거래의 amount 합계는 항상 0이다.

> 코드 기준 갱신: 엔진 LedgerEntry(`simulation_engine/src/simulation_engine/economy/ledger.py:15-18`)는 amount가 0이면 거부하고 entry_no는 1 이상이어야 한다. 거래 단위의 amount 합계 0 검증은 엔진 코드에 아직 없다 (코드 기준).

> 코드 기준 갱신: 엔진 Transaction(`simulation_engine/src/simulation_engine/economy/transaction.py:23-30`)은 transaction_type, tick, idempotency_key(필수), description, reverses_transaction_id, metadata를 가진다. REVERSAL은 reverses_transaction_id로 원 거래를 참조한다 (코드 기준).

급여 거래 예시 (월 급여 300만원, 소득세 15%):

| 계정 | amount |
|---|---:|
| 기업 CASH | -3,000,000 |
| 시민 CASH | +2,550,000 |
| 정부 TREASURY | +450,000 |
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

예시는 다른 생활비가 없다는 가정의 단순 모델이다. 엔진 v1의 소비액은 [03-citizen §4.5](03-citizen.md)의 공식을 따르며, 위 70%는 설명용 예시다.

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
| TOTAL_COMPANY_REVENUE | KRW | 기간별 기업 총매출 (§6.7, GDP 아님) |
| ACTIVE_COMPANIES | COUNT | 운영 중인 기업 수 |
| BANKRUPT_COMPANIES | COUNT | 해당 기간 파산 기업 수 |
| GOVERNMENT_REVENUE | KRW | 기간별 정부 세입 |
| GOVERNMENT_EXPENDITURE | KRW | 기간별 정부 지출 |
| AVERAGE_HAPPINESS | INDEX | 평균 행복도 (v1은 변하지 않는 초기 기준값) |

위 6.4 목록 중 중위 자산, 기업 이익, 불평등 지표는 아직 지표 코드가 없다 (TBD).

계산식과 집계 대상: TBD.

- AVERAGE_HAPPINESS: v1에는 행복도 변화 규칙이 없어 모든 시민이 초기값 50을 유지한다. 이 지표는 경제 상태와 연동되지 않는 초기 기준 지표다.

### 거래 유형 추가 근거 (테이블 변경 없음)

`OPERATING_EXPENSE`, `PUBLIC_PROCUREMENT`, `EXPORT`는 엔진과 backend enum에 추가한다. `transactions.transaction_type`은 VARCHAR(32)이고 CHECK 제약이 없으므로 DB 테이블은 바꾸지 않는다 ([06-database](../03-architecture/06-database.md)).

### 6.5 운영비 (OPERATING_EXPENSE)

기업은 월 기준 운영비(`operating_cost`)를 낸다. 급여는 포함하지 않는다. 운영비는 월 1회, 월말 정산에서만 지급한다.

운영비 분배 비율은 다음과 같다.

| 수취처 | 비율 | 계정 |
|---|---:|---|
| B2B 공급 기업 | 70% | 공급 업종의 기업 CASH |
| 정부 (공공요금) | 20% | GOVERNMENT TREASURY |
| 외부 | 10% | SYSTEM CASH |

B2B 공급 관계는 다음과 같다.

| 지출 업종 | 공급 업종 |
|---|---|
| RETAIL | WHOLESALE |
| RESTAURANT | WHOLESALE |
| WHOLESALE | BUSINESS_SERVICE |
| BUSINESS_SERVICE | WHOLESALE |

- 공급 업종에 운영 중인 기업(ACTIVE·DISTRESSED)이 여럿이면 B2B 몫을 균등 분할한다. 원단위 나머지는 id 순으로 한 단위씩 나눈다.
- 운영 중인 공급 기업이 없으면 B2B 몫은 외부(SYSTEM CASH)로 간다.
- 수취처별로 거래를 나눠 기록한다.
- 연쇄 없음: 정산 중 받은 B2B 매출로 같은 달 운영비를 다시 지급하지 않는다. B2B 매출은 다음 평가에 반영한다.
- 잔액이 부족하면 음수 잔액을 만들지 않는다. 지급하지 못한 금액은 미납으로 기록하고, 미납이 있으면 기업 재무 악화로 판정한다 ([04-business §5.4](04-business.md)). 부분 지급은 없다. 잔액이 운영비 전액보다 적으면 전액 미납으로 처리한다 (2026-11-19 확정).

운영비 거래의 metadata 키는 다음과 같다.

| 키 | 설명 |
|---|---|
| expense_category | 분배 구분 (B2B·정부·외부) |
| supplier_company_id | 수취 기업 id (B2B 거래에만 있음) |
| period_tick | 정산 월말 Tick |

### 6.6 외부 계정과 도시 내부 자금

- 외부 자금은 SYSTEM/CASH 계정 1개로 표현한다. 초기 잔액은 0이며 음수가 될 수 없다.
- 외부로 나가는 돈: 운영비의 외부 몫(10%).
- 외부에서 들어오는 돈: 월말 수출 단계에서 외부 잔액 × 수출 비율(5000bps = 외부 잔액의 50%/월, 보정으로 정한 설정값)을 운영 중 기업에 나눠 준다. 거래 유형은 EXPORT다 (간소화 수출).
- 수출 분배: 운영 중 기업(ACTIVE·DISTRESSED) 전체에 균등 분할하고, 원단위 나머지는 id 순으로 한 단위씩 나눈다. 운영 중 기업이 없으면 재유입하지 않는다.
- 수출은 월 1회다. 공공 조달 다음, 기업 상태 평가 전에 실행한다 ([6.8](#68-월말-정산-순서)).
- 외부 계정 잔액 = 외부 유출 누계 − 외부 유입 누계다. 유입은 잔액을 넘지 않으므로 음수가 되지 않는다.
- 계정 전체 합계는 항상 0이다. 재유입이 있어도 자금 보존 원칙(6.3)은 유지된다.
- 도시 내부 자금 = 시민 + 기업 + 정부 계정 잔액 합계. SYSTEM과 ISSUANCE는 제외한다.
- 내부 자금 변화 = 외부 유입 − 외부 유출. 전체 합계가 0이므로 도시 내부 자금 = 초기 자본 총액 − 외부 계정 잔액이다.
- 도시 내부 자금은 별도로 집계한다. v1은 12종 지표 구조를 유지하므로 지표 코드 없이 엔진 함수(`metrics/calculator.py`의 `city_internal_money`)로만 제공한다.

### 6.7 매출 구분

기업 매출은 수취 거래의 유형에 따라 네 가지로 구분한다.

| 구분 | 거래 유형 | 설명 |
|---|---|---|
| 최종 소비 | PURCHASE | 시민의 소비 |
| B2B | OPERATING_EXPENSE (B2B 몫) | 기업 간 운영비 |
| 공공 조달 | PUBLIC_PROCUREMENT | 정부의 공공 조달 |
| 수출 | EXPORT | 외부 자금의 재유입 (간소화 수출) |

- 채용 잉여의 매출에는 네 항목을 모두 포함한다 ([04-business §5.5](04-business.md)).
- TOTAL_COMPANY_REVENUE는 기업들이 수령한 전체 매출의 합계로 정의한다. 최종 소비, B2B, 공공 조달, 수출을 포함하며, 중간 거래가 중복 집계되므로 GDP로 해석하지 않는다. GDP 산정은 v1 범위에서 제외한다 (2026-11-19 확정).

### 6.8 월말 정산 순서

월말 Tick에 다음 순서로 정산한다. 같은 달 안에서 연쇄 지급은 만들지 않는다.

1. 급여(SALARY)와 소득세(INCOME_TAX, 기본 1500bps)를 지급한다. 소득세는 정부 TREASURY로 간다. 급여 전액을 지급하지 못한 기업은 파산 판정 대상이다.
2. 운영비(OPERATING_EXPENSE)를 분배한다. ([6.5](#65-운영비-operating_expense))
3. 복지(WELFARE)를 지급한다. ([05-government](05-government.md))
4. 공공 조달(PUBLIC_PROCUREMENT)을 집행한다. ([05-government](05-government.md))
5. 수출(EXPORT)로 외부 자금을 재유입한다. ([6.6](#66-외부-계정과-도시-내부-자금))
6. 기업 상태를 평가한다. ([04-business §5.4](04-business.md))
7. 채용과 해고를 처리한다. ([04-business §5.5](04-business.md))
8. 다음 달 소비 예산을 계산한다. 보유 현금은 급여·복지 직후 값과 같다. 이후 정산 단계는 시민 현금을 바꾸지 않으므로, 채용·해고 뒤 현금과 같다. ([03-citizen §4.5](03-citizen.md))

2–5단계는 상태 평가(6단계)보다 먼저 실행된다. 따라서 당월 운영비, 조달, 수출 대금은 당월 재무 상태 평가와 채용 판단에 반영된다.
