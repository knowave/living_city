# doc-sync: simulation_engine 문서 변경 로그 (sync-engine)

규칙: 문서만 수정. 변경 줄 또는 `> 코드 기준 갱신` 블록에 ` (코드 기준)` 표기. 코드 근거는 `simulation_engine/src/simulation_engine/` 기준 경로.

## 변경

| 문서 | 변경 전 | 변경 후 | 코드 근거 |
|---|---|---|---|
| docs/02-domain/01-domain-overview.md (관계) | Household가 memberIds로 Citizen을 가리킴 | memberIds 없음. 소속은 Citizen.householdId | entities/household.py:8-11, entities/citizen.py:10 |
| docs/02-domain/02-world.md (World) | 속성 목록만 있음 | 엔진 필드(speed 기본 1, status 기본 INITIALIZED) 명시. worldId·version은 DB 전용 | entities/world.py:17-24 |
| docs/02-domain/02-world.md (WorldEvent) | createdAt, worldId 포함 | 엔진 필드 id, sequence, tick, type, payload, schema_version. createdAt·worldId는 DB 전용 | events/models.py:9-17 |
| docs/02-domain/02-world.md (WorldSnapshot) | worldId, createdAt 포함 | 엔진 필드 명시. 두 필드 DB 전용 | world/snapshot.py:9-16 |
| docs/02-domain/02-world.md (3.11 MapChunk 추가) | 없음 | MapChunk 추가 (32x32, 타일 인덱스 식, schemaVersion, revision) | world/map_chunk.py:6-20 |
| docs/02-domain/03-citizen.md (Citizen) | 속성 목록만 있음 | skills dict[str,int], riskTolerance·consumptionPreference 정수 bps, snake_case, worldId 없음 | entities/citizen.py:9-24 |
| docs/02-domain/03-citizen.md (Household) | memberIds | memberIds 줄에 코드 기준 표기(필드 없음, Citizen.householdId로 표현) | entities/household.py, 백엔드 models/household.py (member 필드 없음) |
| docs/02-domain/05-government.md | 초기 소득세율 15%만 있음 | WorldPolicy 클래스명, income_tax_rate 1500 bps, welfare 기본 0, Government 클래스 아직 없음 | entities/policy.py:8-12, entities/government.py(docstring만) |
| docs/02-domain/06-economy.md (Account) | owner·음수 규칙만 있음 | is_active 추가, 소유자 id 구성 규칙, world_id 식별은 DB 쪽 | economy/account.py:24-47 |
| docs/02-domain/06-economy.md (LedgerEntry) | amount 합 0 규칙만 있음 | amount≠0, entry_no≥1 검증. 거래 단위 합 0 검증은 아직 없음 | economy/ledger.py:15-18 |
| docs/02-domain/06-economy.md (Transaction) | 유형 표만 있음 | 필드(idempotency_key 필수, reverses_transaction_id 등). 유형 10종은 코드와 일치 | economy/transaction.py:23-30 |
| docs/02-domain/06-economy.md (6.4 지표) | 지표 12종 표 | metric_value Decimal, period HOURLY/DAILY/MONTHLY, unit에 RATIO 추가 | metrics/models.py:9-48 |
| docs/02-domain/07-simulation-rules.md (정책 적용) | 경계 적용 문장만 있음 | 적용 Tick은 WorldPolicy.effective_tick. 적용 로직은 미구현 | entities/policy.py:12 |
| docs/03-architecture/03-simulation-engine.md (7.8 tests 트리) | test_package.py 한 줄 | 실제 테스트 4개 파일 | tests/ 목록 |
| docs/03-architecture/03-simulation-engine.md (7.8 현재 상태) | "엔티티·원장·이벤트·스냅샷·지표" 구현, System 미구현 | 청크 추가. 빈 스텁 목록 명시(state, config, generator, engine, clock, context, systems, policies, events/generator, utils, government). Household에 memberIds 없음 | 각 파일 docstring만 있음 |
| docs/04-development/04-simulation-convention.md (코딩 규칙) | 화폐·bps 규칙만 있음 | 상태·유형 값은 StrEnum. Citizen.employment_status, Employment.status, Building.status/type은 아직 str | entities/*.py, economy/*.py, metrics/models.py |

## 확인했으나 변경하지 않음 (코드와 일치 또는 설계 문서)

- 04-business.md: Company, Employment 필드와 Company 상태 4종이 코드와 일치. 변경 없음.
- 06-economy.md 소득세 예시, 자금 보존 원칙, 지표 12종 단위: 코드와 일치. 자금 보존의 런타임 검증은 아직 없음(설계 규칙으로 유지).
- 04-simulation-convention.md: dataclass(slots=True, kw_only=True), int 화폐, bps(1500=15%), unittest, 표준 라이브러리 전용, 모듈 구성 표 모두 일치.
- 03-simulation-engine.md 7.2 실행 순서, 7.5 엔진 구성, 7.7 실행 주기: 설계 문서(검토안). 코드가 없으므로 유지.
- 04-simulation-convention.md System Protocol(`run(state, rng) -> list[DomainEvent]`): 예정 상태로 유지.

## 코드와 다르지만 문서를 바꾸지 않은 항목 (이유)

- world_id, worldId, createdAt, updated_at, World.version: 03-simulation-engine 7.8이 DB 전용 필드로 엔진에 두지 않는다고 정함. 도메인 문서의 "모든 엔티티는 worldId로 World에 속한다"는 DB·백엔드 기준이라 유지(백엔드 BaseEntity에 world_id 있음).
- Employment "한 시민은 활성 고용 1개": 엔진·백엔드 모두 검증 코드 없음. 규칙 문서로 유지.
- Government & Policy 엔티티, "정부" 엔티티(03-simulation-engine 7.5 표): 엔진에 클래스 없음. 설계 용어로 유지하고 05-government.md에 현 상태만 덧붙임.
- Account 설명의 "GOVERNMENT/SYSTEM은 world_id로 식별": 엔진 Account에는 world_id가 없다(DB 규칙). 유지.
- 03-simulation-engine 7.8 "Household"·"Citizen" 등 미러링 규칙은 그대로 둠.
- Simulation Rules 1배속 기준(2초=1일), 배율 0/1/4/16: clock.py는 docstring뿐. 설계 값으로 유지.
- 06-economy 6.4 "중위 자산, 기업 이익, 불평등 지표 TBD": 코드에도 해당 MetricCode 없음. 일치.

## 범위 밖 관찰 (내가 수정하지 않음)

- simulation_engine/README.md 디렉터리 설명: `entities/ (citizen, business, government, building)`에 business라고 되어 있으나 실제 파일은 company.py. README는 소유 범위 밖(코드 쪽 문서)이라 수정하지 않음.

## 추가: simulation_engine/README.md (lead 지시)

| 문서 | 변경 전 | 변경 후 | 코드 근거 |
|---|---|---|---|
| simulation_engine/README.md (목적) | "패키지 골격만 있습니다" | 엔티티, 경제 원장, 월드 레코드, 지표 레코드 구현 상태와 System·엔진 실행 미구현을 구분해 기술 | entities/*.py, economy/*.py, world/snapshot.py, world/map_chunk.py, metrics/models.py, engine.py(docstring만) |
| simulation_engine/README.md (디렉터리 구조) | entities/ 설명에 business, government 표기. economy, metrics 누락 | company 등 실제 파일명 반영, economy·metrics 추가, government·state·config·generator 스텁 표기 | 파일 목록 |
| simulation_engine/README.md (테스트 실행) | `PYTHONPATH=src python3 -m unittest` | `PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest` + 3.12 이상 필요 명시 | uv 실행 24 tests OK 확인 |

## simulation_engine/README.md

확인 방법: `wc -l`로 src/simulation_engine 전체 .py 파일을 확인하고, 1줄짜리 파일은 docstring만 있는 스텁으로 봤습니다. 테스트는 아래 명령으로 실행했습니다.

### 변경 전 → 변경 후

- **구현 상태 줄**
  - 전: "현재는 패키지 골격만 있습니다. 실행 로직은 아직 구현하지 않았습니다."
  - 후 (실제 상태와 맞춤): 엔티티·경제 원장·월드 레코드(WorldEvent, WorldSnapshot, MapChunk)·지표 레코드는 구현됨. 스텁은 engine, clock, context, systems/*, policies/*, events/generator, world/state·config·generator, entities/government, utils/*.
  - 참고: 제공된 README 사본에는 "패키지 골격만 있습니다" 문구가 이미 없었고, 구현 상태 줄은 "현재 구현 상태: …"로 되어 있었습니다. 그 줄에는 스텁 목록이 일부(engine, clock, context, systems, policies)만 있어서 누락된 스텁을 추가했습니다.
- **디렉터리 트리**: 변경 없음. economy/, metrics/, entities의 개별 파일명(company 등), world/(state·config·generator 스텁, snapshot·map_chunk 구현), policies/(taxation·employment 스텁)이 이미 실제 파일과 일치했습니다.
- **테스트 명령**: 변경 없음. 이미 `cd simulation_engine && PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest`이고, 시스템 python3(3.9.6)에서 `StrEnum` import가 실패하는 설명도 이미 있었습니다.

### 테스트 결과

- 명령: `cd simulation_engine && PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest`
- 결과: `Ran 24 tests` / `OK`
- 참고: `python3 -c "from enum import StrEnum"` → ImportError (시스템 python3 3.9.6)
