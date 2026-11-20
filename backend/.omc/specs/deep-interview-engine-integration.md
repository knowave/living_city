# Deep Interview 스펙: Backend Phase 1 — 시뮬레이션 엔진 연동

## 메타데이터
- 인터뷰 ID: di-engine-integration-20261120
- 라운드: 4 (+ Round 0 범위 확인)
- 최종 모호도: 18%
- 유형: brownfield
- 작성일: 2026-11-20
- 기준값: 0.2
- 기준값 출처: default
- 초기 맥락 요약 여부: 아니오
- 상태: 통과 — 승인됨 (가정 1–9 승인, team sonnet/haiku 실행)
- 참고: 이번 세션은 OMC state MCP 연결에 실패해 state_write로 인터뷰 상태를 저장하지 못했다.

## 명확도 분석
| 차원 | 점수 | 가중치 | 반영값 |
|---|---|---|---|
| 목표(Goal) | 0.88 | 0.35 | 0.308 |
| 제약(Constraints) | 0.80 | 0.25 | 0.200 |
| 완료 기준(Criteria) | 0.72 | 0.25 | 0.180 |
| 맥락(Context) | 0.88 | 0.15 | 0.132 |
| **명확도 합계** | | | **0.82** |
| **모호도** | | | **0.18** |

## 범위(Topology)
| 구성요소 | 상태 | 설명 | 대응 완료 기준 |
|---|---|---|---|
| 엔진 Adapter | 진행 | port 뒤에서 generate_world, Snapshot 복원, step/run(n) 호출 | AC3–AC6 |
| Mapper와 영속화 경계 | 진행 | 엔진 dataclass → ORM 변환(id 재매핑), 한 트랜잭션에 일괄 저장 | AC4, AC7, AC8 |
| 진입점 | 진행 | POST /worlds 실제 생성, POST /worlds/{id}/ticks, PATCH /policies를 대기 명령으로 | AC3, AC5, AC6 |
| 중복 적용 방지와 결정성 | 진행 | world.version, idempotency_key, (world_id, sequence), Snapshot 계약 | AC8–AC11 |
| docs 먼저 갱신 | 진행 | 충돌 분석과 연동 설계를 docs에 반영 | AC1 |
| 테스트 | 진행 | 단위(fake), 통합(실제 Postgres), 기존 76개 회귀 | AC12 |
| 주기 Runner, 배속·일시정지 REST, SSE, frontend, MapChunk, 새 규칙 | 보류 | 사용자가 지정한 이번 Phase 제외 항목. 다음 Phase 순서: Runner → REST → SSE | — |

## 목표
동결된 simulation_engine v1을 엔진 port와 adapter로 backend에 연결한다. `POST /worlds`는 실제 세계를 생성하고, `POST /worlds/{id}/ticks`는 세계를 N Tick 진행한다. 엔진 출력(엔티티 상태, 거래, 원장, 이벤트, 지표, World의 tick, Snapshot)은 요청 1회당 트랜잭션 1개로 원자적으로 저장한다. 엔진 id는 세계별 DB id로 재매핑하고, 정책 변경은 엔진 명령으로 전달하며, 엔진의 Snapshot·결정성 계약을 지킨다.

## 제약
### 사용자 지정
- simulation_engine v1은 동결: 엔진 코드 수정 금지, 새 경제·시민 규칙 추가 금지.
- 14개 DB 엔티티·테이블은 수정하지 않는다(컬럼·테이블·제약 추가 금지).
- 코드보다 docs를 먼저 갱신한다(CLAUDE.md 규칙).
- 기존 계층 유지: controller → use case ABC ← service → repository/port ABC ← 구현. `app/api/deps.py`만 조립 지점이다. service는 sqlalchemy, fastapi, simulation_engine을 import하지 않는다.
- 문서와 응답은 한국어로 작성한다(프로젝트 메모리 지시). 코드 식별자, 명령어, 경로, 에러 원문은 그대로 둔다.

### 인터뷰 결정
- **R1 id 재매핑:** 엔진이 만든 모든 행(정책, 건물, 시민, 가구, 기업, 고용, 계좌, 거래, 원장, 이벤트, 지표, Snapshot)의 DB id = `uuid5(worlds.id, str(engine_id))`. `worlds.id`는 지금처럼 backend uuid4다. 변환은 엔진→DB 한 방향이다. 복원은 Snapshot `state_data`로 하고, 여기에는 엔진 id를 그대로 둔다. 이벤트 `payload`에서 키가 `_id`로 끝나는 값은 DB id로 바꿔 저장한다. `idempotency_key`는 이미 세계별 유일하므로 엔진 값을 그대로 저장한다.
- **R2 정책 변경:** `PATCH /policies`는 지금처럼 `world_policies` 행을 넣는다(effective_tick = current_tick + 1). 이 행은 적용 대기 명령 역할을 한다. 다음 Tick 진행 때 adapter가 Snapshot에 없는 DB 정책 행을 version 순서로 `PolicyChangeCommand`로 바꿔 `step()`에 넘긴다. 같은 트랜잭션에서 대기 행을 엔진이 만든 정책 행으로 교체한다. 같은 Tick 안에서 두 번째 PATCH가 오면 06-database §10.4에 따라 `(world_id, effective_tick)` 기준 UPSERT로 대기 행을 덮어쓰고 version을 1 올린다.
- **R3 진입점:** `WorldUseCase.advance_ticks(world_id, count)`와 `POST /api/v1/worlds/{id}/ticks`, 본문 `{count: 1..720}`. 응답: `from_tick`, `to_tick`, `event_count`, `last_event_sequence`, `transaction_count`. FAILED·ARCHIVED 세계는 409 `WORLD_NOT_RUNNABLE`.
- **R4 원자성:** 요청 1회 = DB 트랜잭션 1개. N Tick을 메모리에서 진행한 뒤 결과 전체와 마지막 Tick의 Snapshot 1개를 저장한다. 실패하면 배치 전체를 롤백한다. 시작 시 읽은 `world.version`을 저장 시 비교하고, 다르면 409 `CONCURRENT_UPDATE`.

## 승인 시 확인할 가정
1. **Event Sourcing 범위(06-database TBD):** "마지막 Snapshot에서 재개"로 정한다. 마지막 Snapshot과 그 이후 행이 기준이다. R4에서 따라 나온 결정이지만 TBD를 닫는 것이므로 명시적으로 확인받는다.
2. **세계 생성:** `POST /worlds {name, seed?}` → `generate_world(seed, name=name)`. 초기 정책은 엔진 값(복지 1,000,000, 세율 1500)을 쓰며, backend 기본값 복지 0을 대체한다. 정책, 건물 21동, 가구, 시민 100명, 기업 10개, 고용, 계좌, OPENING_BALANCE 거래 111건과 원장, tick 0 Snapshot을 저장한다. 상태는 INITIALIZED.
3. **World 필드:** `status`, `speed`, `version`, `name`은 backend가 소유한다. mapper는 엔진 World에서 `current_tick`만 반영하고, 엔진 World의 status·speed는 무시한다.
4. **엔진 실패:** `InvariantViolation` 등 엔진 예외가 나면 배치를 롤백하고, 별도 트랜잭션으로 세계를 `FAILED`로 바꾼 뒤 409 `SIMULATION_FAILED`를 돌려준다.
5. **엔티티 저장:** 배치마다 엔진 엔티티 7종 전체를 재매핑한 id 기준으로 FK 순서에 맞춰 upsert한다(PG `INSERT … ON CONFLICT (id) DO UPDATE`). v1 규모에서 배치당 약 250행이다.
6. **타입 변환:** `risk_tolerance`, `consumption_preference` = bps ÷ 10000 Float(03-simulation-engine §7.8). 지표 `Decimal`은 `Numeric(24,6)`에 맞춰 반올림한다.
7. **복원 정합성:** 최신 Snapshot의 tick은 `worlds.current_tick`과 같아야 한다. 다르면 409 `SNAPSHOT_MISMATCH`를 돌려주고 자동 복구하지 않는다.
8. **port 위치:** 엔진 port ABC와 결과 DTO는 `app/simulation/interfaces.py`, adapter는 `app/simulation/engine_adapter.py`, mapper는 `app/repositories/sqlalchemy/engine_mapper.py`. `simulation_engine`을 import하는 모듈은 이 두 구현 모듈뿐이다. backend는 `simulation-engine`을 editable path 의존성으로 추가한다.
9. **통합 테스트:** pytest marker `integration`. 테스트 세션마다 임시 Postgres DB를 fixture가 만들고 지운다(이전 `lc_*_tmp` 점검 방식과 같다). Postgres에 연결할 수 없으면 건너뛴다.

## 제외 범위
- 주기 Tick Runner, 배속·일시정지 REST 변경, SSE 발행, frontend, MapChunk 생성·렌더링, 새 경제·시민 규칙, 엔진 수정, 스키마·테이블 변경, alembic, Snapshot 보관 정책, 페이지 나누기.

## 완료 기준
- [ ] AC1: 코드보다 docs를 먼저 갱신한다.
  - `07-rest-sse.md`: POST /worlds 생성, POST /ticks, PATCH /policies 대기 의미
  - `06-database.md`: id 재매핑 규칙, Snapshot 기준 재개, 정책 대기 행
  - `03-simulation-engine.md` §7.4, §7.10의 backend 쪽 메모
  - `02-backend-convention.md`: simulation port/adapter 계층 규칙
  - CLAUDE.md의 backend 상태 설명
- [ ] AC2: `simulation-engine`이 backend 의존성에 들어가고 `uv sync`가 된다. `simulation_engine`을 import하는 모듈은 `app/simulation/engine_adapter.py`, `app/repositories/sqlalchemy/engine_mapper.py`뿐이다(architecture 테스트로 검사).
- [ ] AC3: `POST /worlds`가 생성된 세계를 저장한다. 개수가 엔진 출력과 일치하고(건물 21, 시민 100, 기업 10, 활성 고용 88, OPENING_BALANCE 거래 111), 전체 계좌 잔액 합은 0이며, tick 0 Snapshot이 있다.
- [ ] AC4: 같은 시드로 만든 세계 두 개가 모두 저장되고(PK 충돌 없음), id 재매핑을 제외하면 상태가 같다.
- [ ] AC5: `POST /worlds/{id}/ticks {count}`는 다음을 지킨다.
  - `current_tick`이 count만큼 늘어난다.
  - 이벤트는 이전 최대값에서 끊김 없이 이어지는 sequence로 저장된다.
  - 거래, 원장, 지표, 엔티티 변경이 저장된다.
  - 새 tick의 Snapshot이 저장된다.
- [ ] AC6: `PATCH /policies`의 대기 정책이 다음 진행 때 `PolicyChangeCommand`로 적용되고 `policy.updated`를 낸다. effective_tick당 정책 행은 엔진 것 1건만 남는다.
- [ ] AC7: 원자성. 저장 도중 실패를 주입하면 다음이 모두 성립한다.
  - 배치의 행이 하나도 남지 않는다.
  - `current_tick`과 `version`이 그대로다.
  - 이전 Snapshot이 여전히 최신이다.
- [ ] AC8: 중복 방지. 오래된 `world.version`으로 배치를 다시 실행하면 409 `CONCURRENT_UPDATE`이고 아무것도 쓰이지 않는다. 강제로 다시 넣으면 DB 유니크 `(world_id, sequence)`, `(world_id, idempotency_key)`가 거부한다.
- [ ] AC9: 결정성. 다음 두 세계의 저장된 상태, 이벤트, 거래가 id를 되돌려 비교했을 때 같고, Snapshot `state_data`도 같다.
  - 한 세계는 N Tick을 한 번에 진행한다.
  - 같은 시드의 다른 세계는 k + (N−k)로 나눠 진행한다.
- [ ] AC10: Snapshot 계약. 저장된 `state_data`가 `WorldState.from_snapshot`으로 복원되고, `last_event_sequence`는 저장된 최대 sequence와 같다.
- [ ] AC11: 엔진 실패 시 세계는 FAILED가 되고 배치는 롤백되며 409 `SIMULATION_FAILED`를 돌려준다. FAILED·ARCHIVED 세계의 `/ticks` 호출은 409다.
- [ ] AC12: 다음 테스트를 추가하고 기존 테스트 76개가 모두 통과한다.
  - advance_ticks, create_world, change_policy 흐름의 service 단위 테스트(fake, DB 없음)
  - mapper 단위 테스트(DB 없음)
  - AC3–AC11의 실제 Postgres 통합 테스트

## 드러난 가정과 해소
| 가정 | 문제 제기 | 결정 |
|---|---|---|
| 엔진 id를 그대로 저장해도 된다 | 시드로만 만든 id라 세계 간 전역 PK가 충돌한다 | mapper가 uuid5(world.id, 엔진 id)로 재매핑 (R1) |
| 정책 행은 backend가 만든다 | 엔진도 정책과 이벤트를 만들고, 복원은 Snapshot에서만 가능하다 | DB 행은 대기 명령, 엔진 행으로 교체 (R2) |
| 엔진 호출에는 Runner가 필요하다 | Runner는 이번 범위 밖이다 | 수동 use case + REST `/ticks` (R3) |
| Tick마다 커밋한다 | 커밋 단위가 곧 Snapshot 단위라 한 달에 Snapshot 720개가 생긴다 | 요청당 트랜잭션 1개 + Snapshot 1개 (R4, 반대 관점) |
| Float와 bps 타입 충돌(이전 D3) | docs §7.8이 이미 adapter에 변환을 맡겼다 | mapper에서 bps ÷ 10000 Float |

## 기술 맥락
- 엔진 API:
  - `generate_world(seed, config, name) -> GenerationResult(state, transactions, ledger_entries, events=[])`
  - `SimulationEngine(state, config).step(commands) -> TickResult(tick, events, transactions, ledger_entries, metrics)`, `run(n, commands_by_tick)`
  - `WorldState.to_snapshot()/from_snapshot()` (format_version 1)
  - 엔진 내부 상태(next_event_sequence, id_counters, distressed_months 등)는 Snapshot `state_data["engine"]`에만 있다.
- 엔진 id는 모두 시드에서 만든다(`generator.py:79`, `state.py:87-91`, Snapshot id `state.py:141`).
- 멱등 키 예: `SALARY:{tick}:{employment_id}`, `opening:{account_id}`. 최대 약 115자이고, DB 유니크는 (world_id, idempotency_key)다.
- `step()`이 World에서 바꾸는 것은 `current_tick += 1`뿐이다. generator는 이벤트를 내지 않고, 가구 계좌도 만들지 않는다.
- backend repository에는 엔진 출력용 쓰기·일괄 메서드가 없다. `World.version`은 `version_id_col`이고, `update_simulation`이 StaleDataError를 ConflictError로 바꾼다. 실제 Postgres를 쓰는 테스트는 아직 없다.
- 확인된 충돌:
  - 복지 기본값이 엔진 1,000,000, backend 0으로 다르다.
  - `change_policy`의 docstring과 코드의 effective_tick이 서로 다르다.
  - `UNIQUE(world_id, effective_tick)`인데 엔진은 이미 있는 effective_tick 명령을 거부한다.

## 핵심 개념(Ontology)
| 개념 | 유형 | 필드 | 관계 |
|---|---|---|---|
| World | 핵심 | id, current_tick, status, speed, version | 모든 행의 소유자 |
| WorldState | 외부(엔진) | 엔티티, 엔진 내부 상태 | Snapshot에서 복원 |
| WorldSnapshot | 핵심 | tick, last_event_sequence, state_data | 커밋된 배치마다 1개 |
| TickBatch | 보조 | from_tick, to_tick, results | EngineGateway가 생성 |
| PolicyCommand | 보조 | income_tax_rate, welfare_amount, effective_tick | 대기 중인 world_policies 행에서 생성 |
| IdMap | 보조 | world_id, engine_id → db_id | Mapper가 사용 |
| EngineMapper | 보조 | to_orm(...) | 엔진 dataclass → ORM |
| EngineGateway | port | generate, advance | simulation_engine 위의 adapter |
| UnitOfWork | port | repositories, commit | 요청당 트랜잭션 1개 |
| DomainEvent | 핵심 | sequence, type, payload | world_events |

## 개념 수렴
| 라운드 | 개념 수 | 신규 | 변경 | 유지 | 안정도 |
|---|---|---|---|---|---|
| 1 | 9 | 9 | - | - | - |
| 2 | 10 | 1 (PolicyCommand) | 0 | 9 | 90% |
| 3 | 10 | 0 | 0 | 10 | 100% |
| 4 | 10 | 0 | 0 | 10 | 100% |

## 인터뷰 기록
<details><summary>4라운드</summary>

- R0 범위(adapter, mapper·영속화, 진입점, 중복 방지·결정성, docs, 테스트) → 맞음
- R1 시드 기반 id 충돌 → Mapper에서 id 재매핑 (39%)
- R2 정책 변경 경로 → 대기 행 → 다음 Tick에서 명령 (31%)
- R3 Tick 진입점 → use case + REST (25%)
- R4 (반대 관점) 커밋 단위 → 요청 1회 = 트랜잭션 1개 (18%)
- 사용자 메시지: "Backend Phase 1에서 엔진과 영속화를 연결하고, 그다음 Runner, REST, SSE를 구현하면 돼."
</details>
