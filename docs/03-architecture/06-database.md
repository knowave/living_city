# 데이터 저장 설계

> 원본: README §10

## 10.1 관계형 데이터

PostgreSQL을 사용한다.

주요 테이블:

- worlds (구현)
- citizens (구현)
- households (구현)
- companies (구현)
- employments (구현)
- buildings (구현)
- world_policies (구현)
- accounts (구현)
- transactions (구현)
- ledger_entries (구현)
- world_events (구현)
- world_snapshots (구현)
- world_metrics (구현)
- map_chunks (구현)

## 10.2 데이터 구분

**현재 상태**

시민과 기업의 현재 상태, 계정 잔액, 현재 정책 등을 저장한다.

**이력**

시민의 고용 변화, 기업의 파산, 정책 변경 등 주요 도메인 이벤트를 저장한다.

**경제 거래**

금전 이동의 정합성을 검증할 수 있도록 원장 데이터를 저장한다.

**스냅샷**

복구와 재현을 위한 주기적 세계 상태를 저장한다.

모든 상태 변경을 이벤트만으로 재생산하는 완전한 Event Sourcing은 MVP에서 도입하지 않는다.

## 10.3 ORM 구현 규칙 (backend)

**스택**: SQLAlchemy 2.1.8 이상 sync + psycopg v3 (`postgresql+psycopg://`). (코드 기준: backend/pyproject.toml)

**BaseEntity**: 추상 기반 클래스. 모든 엔티티가 상속한다.

- `id`: UUID PK, 기본값 uuid4
- `created_at`, `updated_at`: timestamptz, 서버 기본값 `now()`. `updated_at`은 갱신 시(onupdate) 자동 변경

**명명**: Python 속성과 컬럼은 snake_case, 클래스명은 PascalCase.

**타입 규칙**

- enum은 문자열(String)로 저장한다. 네이티브 PG enum은 쓰지 않는다. 값 목록이 정해지지 않은 status 필드는 `String(32)`.
- 금액은 `BigInteger` 최소 단위 정수.
- `income_tax_rate`는 `Integer` basis points (15% = 1500).
- `risk_tolerance`, `consumption_preference`는 `Float`, `happiness`, `health`는 `Integer`.
- `skills`, `payload`, `state_data`는 JSONB.

**관계 규칙**

- 모든 엔티티는 `world_id` FK를 갖고 인덱스를 건다.
- Household에는 `member_ids` 컬럼을 두지 않는다. 구성원은 `citizens.household_id` 역참조로 구한다.
- 유니크: `world_events(world_id, sequence)`, `world_snapshots(world_id, tick)`.
- `worlds`를 제외한 모든 world-scoped 테이블(13개)은 `UNIQUE(world_id, id)`를 가진다 (`uq_<table>_world_id_id`).
- 엔티티 간 FK는 모두 복합 FK `(world_id, x_id) → (world_id, id)`이며 `ON DELETE RESTRICT`다. 다른 World의 엔티티를 참조할 수 없다. nullable FK는 MATCH SIMPLE이라 NULL이면 검사하지 않는다. `world_id → worlds.id`는 단일 컬럼 FK이며 역시 RESTRICT.
- 잔액 기준은 `accounts.balance` 하나다. 시민·기업에 `cash_balance` 컬럼을 두지 않는다. 잔액은 accounts(CASH)에서 조회한다 ([경제 원장](../02-domain/06-economy.md)).
- `transactions`, `ledger_entries`, `world_metrics`도 BaseEntity를 상속한다(`updated_at` 존재). 수정 금지는 DB가 아니라 서비스 규칙이다.
- `transactions.metadata` 컬럼의 Python 속성명은 `metadata_`다 (`metadata`는 declarative 예약어).
- `World.version`을 낙관적 락(optimistic locking)에 사용한다.

**로컬 자동 동기화**: 앱 시작 시 `DB_AUTO_SYNC`가 켜져 있고 DB에 접속 가능하면 `Base.metadata.create_all`을 실행한다. 없는 테이블만 만들고 기존 테이블은 삭제하거나 변경하지 않는다. DB에 접속할 수 없으면 경고 로그만 남기고 앱은 정상 기동한다.

**마이그레이션(alembic)**: TBD.

## 10.4 경제·통계·맵 테이블 스키마

모든 테이블은 BaseEntity 컬럼(`id`, `created_at`, `updated_at`)과 `world_id`(FK → worlds.id, NOT NULL)를 가지며, 아래 표에서는 생략한다. enum 성격 문자열 컬럼에는 `CHECK IN`을 두지 않는다 (값은 Python StrEnum으로 관리). 기본값은 Python `default`와 `server_default` 둘 다 지정한다. 의미는 [경제 원장](../02-domain/06-economy.md) 참조.

### accounts

| 컬럼 | 타입 | nullable | 기본값 | 설명 |
|---|---|---|---|---|
| owner_type | String(16) | N | | CITIZEN / HOUSEHOLD / COMPANY / GOVERNMENT / SYSTEM |
| citizen_id | UUID | Y | | 복합 FK → citizens |
| household_id | UUID | Y | | 복합 FK → households |
| company_id | UUID | Y | | 복합 FK → companies |
| account_type | String(16) | N | CASH | CASH / SAVINGS / TREASURY / ISSUANCE |
| currency | CHAR(3) | N | 'KRW' | 통화 |
| balance | BigInteger | N | 0 | 잔액 (최소 단위 정수) |
| is_active | Boolean | N | true | 활성 여부 |

CHECK

- `ck_accounts_owner`: owner_type='CITIZEN'이면 citizen_id만 NOT NULL, 'HOUSEHOLD'이면 household_id만, 'COMPANY'이면 company_id만 NOT NULL. 'GOVERNMENT'/'SYSTEM'이면 세 컬럼 모두 NULL.
- `ck_accounts_balance_non_negative`: `balance >= 0 OR (owner_type = 'SYSTEM' AND account_type = 'ISSUANCE')`

유니크/인덱스

- `uq_accounts_world_id_id` (world_id, id)
- `idx_accounts_world` (world_id)
- `idx_accounts_citizen` / `idx_accounts_household` / `idx_accounts_company`: 각 x_id 인덱스, partial `WHERE x_id IS NOT NULL`
- `uq_accounts_citizen` / `uq_accounts_household` / `uq_accounts_company`: unique partial (world_id, x_id, account_type, currency) `WHERE x_id IS NOT NULL`
- `uq_accounts_government` / `uq_accounts_system`: unique partial (world_id, account_type, currency) `WHERE owner_type = 'GOVERNMENT'` / `'SYSTEM'`

### transactions

| 컬럼 | 타입 | nullable | 기본값 | 설명 |
|---|---|---|---|---|
| transaction_type | String(32) | N | | OPENING_BALANCE, SALARY, PURCHASE, INCOME_TAX, RENT, WELFARE, ACCOUNT_TRANSFER, CAPITAL_INVESTMENT, ADJUSTMENT, REVERSAL, OPERATING_EXPENSE, PUBLIC_PROCUREMENT, EXPORT |
| tick | BigInteger | N | | 거래 발생 Tick |
| idempotency_key | String(180) | N | | 멱등 키 |
| description | Text | Y | | 설명 |
| reverses_transaction_id | UUID | Y | | 복합 자기 FK (world_id, reverses_transaction_id) → transactions(world_id, id) |
| metadata | JSONB | N | `{}` (server_default `'{}'::jsonb`) | 부가 정보. Python 속성 `metadata_` |

유니크/인덱스

- `uq_transactions_world_id_id` (world_id, id)
- `uq_transactions_idempotency` unique (world_id, idempotency_key)
- `idx_transactions_world_tick` (world_id, tick DESC)
- `idx_transactions_type_tick` (world_id, transaction_type, tick DESC)
- `uq_transactions_reversal` unique partial (world_id, reverses_transaction_id) `WHERE reverses_transaction_id IS NOT NULL`

### ledger_entries

| 컬럼 | 타입 | nullable | 기본값 | 설명 |
|---|---|---|---|---|
| transaction_id | UUID | N | | 복합 FK → transactions(world_id, id) |
| account_id | UUID | N | | 복합 FK → accounts(world_id, id) |
| entry_no | SmallInteger | N | | 거래 내 순번 (1부터) |
| amount | BigInteger | N | | 부호 있는 금액. 양수 = 입금, 음수 = 출금 |

CHECK

- `ck_ledger_entries_amount_non_zero`: `amount <> 0`
- `entry_no >= 1`

유니크/인덱스

- `uq_ledger_entries_world_id_id` (world_id, id)
- `uq_ledger_transaction_entry` unique (transaction_id, entry_no)
- `uq_ledger_transaction_account` unique (transaction_id, account_id)
- `idx_ledger_account_created` (account_id, created_at DESC)
- `idx_ledger_world_transaction` (world_id, transaction_id)

### world_metrics

| 컬럼 | 타입 | nullable | 기본값 | 설명 |
|---|---|---|---|---|
| tick | BigInteger | N | | 집계 Tick |
| metric_code | String(64) | N | | 지표 코드 12종 ([경제 지표](../02-domain/06-economy.md)) |
| metric_value | Numeric(24,6) | N | | 지표 값 (Python Decimal, 금액 아님) |
| unit | String(20) | N | | COUNT / KRW / PERCENT / RATIO / INDEX |
| period | String(10) | N | | HOURLY / DAILY / MONTHLY |
| definition_version | Integer | N | 1 | 지표 정의 버전 |

유니크/인덱스

- `uq_world_metrics_world_id_id` (world_id, id)
- `uq_world_metrics` unique (world_id, tick, metric_code, period)
- `idx_world_metrics_chart` (world_id, metric_code, period, tick DESC)

### map_chunks

| 컬럼 | 타입 | nullable | 기본값 | 설명 |
|---|---|---|---|---|
| chunk_x | Integer | N | | 청크 X 좌표 |
| chunk_y | Integer | N | | 청크 Y 좌표 |
| chunk_size | SmallInteger | N | 32 | 청크 한 변의 타일 수 |
| terrain_tiles | JSONB | N | | 지형 타일 배열 (1024개) |
| road_tiles | JSONB | N | | 도로 타일 배열 (1024개) |
| schema_version | Integer | N | 1 | 타일 포맷 버전 |
| revision | Integer | N | 1 | 청크 수정 번호 |

terrain_tiles, road_tiles 값의 의미(schema_version 1)는 [맵 및 렌더링 설계](04-map-rendering.md)의 "타일 스키마 v1"을 따른다.

CHECK: `chunk_x >= 0`, `chunk_y >= 0`, `chunk_size = 32`, `schema_version >= 1`, `revision >= 1`, `jsonb_typeof(terrain_tiles) = 'array'`, `jsonb_typeof(road_tiles) = 'array'`, `jsonb_array_length(terrain_tiles) = 1024`, `jsonb_array_length(road_tiles) = 1024`.

유니크/인덱스: `uq_map_chunks_world_id_id` (world_id, id), `uq_map_chunks_position` unique (world_id, chunk_x, chunk_y). buildings는 map_chunks를 FK로 참조하지 않는다. 타일 인덱스 = `local_y * 32 + local_x`.

### 서비스 규칙 (DB 트리거 미적용)

아래 규칙은 서비스 계층이 보장한다. DB 트리거로 강제하지 않는다.

- 거래별 ledger_entries의 `amount` 합계는 0이다.
- 거래당 ledger_entries는 2건 이상이다.
- 한 거래의 모든 계좌는 같은 World 소속이다.
- ledger_entries와 transactions는 수정·삭제하지 않는다. 취소는 REVERSAL 거래로 처리한다.
- ledger 생성과 `accounts.balance` 변경은 한 DB 트랜잭션에서 수행한다.
- 잔액이 부족하면 거래 전체가 실패한다.

지연 제약 트리거(합계 0, ledger 불변)는 alembic 도입 시 추가한다: TBD.

## 10.5 Implemented Baseline 및 우선 검토 항목

현재 `backend/app/models/*.py`가 만드는 스키마(10.3, 10.4의 모든 컬럼·제약)를 **Living City Database Schema — Implemented Baseline**으로 둔다. Baseline은 그대로 유지하고, 아래 세 항목만 우선 검토한다.

> 근거: 2026-11-12, 임시 DB에 `DB_AUTO_SYNC`로 스키마를 생성하고 psql로 직접 삽입해 확인했다. "제안 제약"은 같은 DB에서 생성·동작을 확인한 뒤 롤백했다. 2026-11-12에 아래 제약을 `backend/app/models`에 반영했다 (모델 반영, 코드 기준).

### 1. Employments 고유성

- 반영 전: 고유 제약은 `(world_id, id)`뿐이었다. 한 시민에게 두 기업의 활성 고용을 동시에 넣어도 DB가 받아들였다. 도메인 규칙 "한 시민은 동시에 하나의 활성 고용 관계만 가진다"([04-business.md](../02-domain/04-business.md))를 DB가 강제하지 못했다.
- 반영된 제약 (코드 기준):
  - `uq_employments_world_citizen_active`: unique partial index `(world_id, citizen_id) WHERE terminated_tick IS NULL`
  - `ck_employments_status_terminated`: `CHECK ((status = 'ACTIVE') = (terminated_tick IS NULL))`. 이 CHECK가 없으면 `status='TERMINATED'`이면서 `terminated_tick`이 NULL인 행이 활성 행으로 취급되어 재고용을 막는다.
- 중복 데이터가 이미 있으면 인덱스 생성이 실패한다. 기존 DB에 적용하기 전에 중복을 정리해야 한다.

### 2. WorldPolicies 적용 규칙

- 반영 전: `(world_id, effective_tick)`과 `(world_id, version)` 모두 고유 제약이 없었다. 같은 Tick·같은 version 정책이 여러 건 저장됐다. `income_tax_rate`(-5, 99999)와 `welfare_amount`(-100)에도 범위 제약이 없었다.
- 반영된 제약 (코드 기준):
  - `uq_world_policies_world_id_effective_tick`: `UNIQUE (world_id, effective_tick)`
  - `uq_world_policies_world_id_version`: `UNIQUE (world_id, version)`
  - `ck_world_policies_income_tax_rate_range`: `CHECK (income_tax_rate BETWEEN 0 AND 10000)`
  - `ck_world_policies_welfare_amount_non_negative`: `CHECK (welfare_amount >= 0)`
- 규칙 (서비스 코드 미구현, 규칙만 정의):
  - 한 World의 한 Tick에는 최종 정책 1건만 둔다. 같은 Tick의 후속 요청은 기존 행을 UPSERT로 덮어쓰고 `version`을 올린다. 이 UPSERT 규칙은 아직 구현된 서비스 코드가 없다(`app/services`는 빈 패키지).
  - `version`은 World 안에서 단조 증가하며, 정책 적용 순서는 `(effective_tick, version)`이다.

### 3. 경제 거래·고용 상태 정합성

- 반영 전: 아래 상태들이 서로 맞지 않아도 DB가 받아들였다. 이를 맞출 서비스·엔진 코드도 아직 없다(`app/services`, `app/crud`는 빈 패키지이고, 엔진 `systems/*`는 스텁이다).
  - 합계가 0이 아닌 거래와 원장 줄이 없는 거래를 저장할 수 있다.
  - 원장 줄을 넣어도 `accounts.balance`가 바뀌지 않는다.
  - `citizens.employer_id`, `employments`, `companies.employee_count`가 서로 어긋날 수 있다. 반영 전에는 `employee_count`가 정원을 넘는 값이나 음수도 허용됐다.
- 규칙:
  - 거래 1건은 `transactions` 기록, `ledger_entries` 생성, `accounts.balance` 갱신을 한 DB 트랜잭션에서 처리한다(10.4 서비스 규칙).
  - 고용·해고 1건은 `employments` 행, `citizens.employment_status`/`employer_id`, `companies.employee_count`를 한 DB 트랜잭션에서 갱신한다. `employments`는 이력이고, `citizens`의 두 컬럼은 빠른 조회를 위한 현재 상태 캐시다.
- 반영된 제약 (코드 기준): `ck_companies_employee_count_range`: `CHECK (employee_count BETWEEN 0 AND employee_capacity)`
- DB 보강 후보: 합계 0을 검사하는 지연 제약 트리거(TBD). 아직 반영하지 않았다.

### 적용 방법

`DB_AUTO_SYNC`의 `create_all`은 없는 테이블만 만들고, 이미 존재하는 테이블에는 제약을 추가하지 않는다. 따라서 새 DB나 빈 DB에는 위 제약이 모두 적용되지만, 기존 DB에는 적용되지 않는다. 기존 DB에 반영하려면 alembic 마이그레이션이 먼저 필요하다(alembic: TBD, 10.2 참조).

### Event Sourcing 범위

`world_events`와 `world_snapshots`가 있다고 해서 완전한 Event Sourcing이 되지는 않는다(10.2). 이 범위는 아래 둘 중 하나를 정해야 확정된다.
- Snapshot 기준 재개: 마지막 Snapshot과 그 이후 `world_events`만 있으면 된다.
- 이벤트만으로 재구성: 모든 상태 변경에 결정적 재실행이 가능한 입력(정책 명령, 시드, 엔진 버전)이 이벤트로 남아야 한다.

어느 쪽으로 할지는 TBD이다.
