# Deep Interview 스펙: World 동시 실행 제어와 Tick 실행 계약

## 메타데이터
- 인터뷰 ID: di-tick-concurrency-20261120
- 라운드: 4 (+ Round 0 범위 확인, Round 3 재질문 1회)
- 최종 모호도: 19%
- 유형: brownfield
- 작성일: 2026-11-20
- 기준값: 0.2
- 기준값 출처: default
- 초기 맥락 요약 여부: 아니오
- 상태: 통과 — 승인됨 (가정 1–7 승인, team sonnet/haiku 실행)
- 참고: OMC state MCP 연결 실패로 state_write 없이 진행했다.

## 명확도 분석
| 차원 | 점수 | 가중치 | 반영값 |
|---|---|---|---|
| 목표(Goal) | 0.88 | 0.35 | 0.308 |
| 제약(Constraints) | 0.82 | 0.25 | 0.205 |
| 완료 기준(Criteria) | 0.66 | 0.25 | 0.165 |
| 맥락(Context) | 0.88 | 0.15 | 0.132 |
| **명확도 합계** | | | **0.81** |
| **모호도** | | | **0.19** |

## 범위(Topology)
| 구성요소 | 상태 | 설명 | 대응 완료 기준 |
|---|---|---|---|
| DB 수준 동시성 제어 | 진행 | `/ticks`는 worlds 행 `FOR UPDATE NOWAIT` + 기존 version 검증 이중 보호 | AC2, AC3, AC6 |
| Tick 실행 계약 | 진행 | `expected_tick` 필수. 불일치(이미 반영 포함)는 409 `TICK_MISMATCH` | AC4 |
| 다른 쓰기 경로 직렬화 | 진행 | PATCH /policies, PATCH /simulation은 `FOR UPDATE`로 최대 5초 대기 | AC5 |
| 검증과 docs | 진행 | 실제 Postgres 병렬 테스트, docs 먼저 갱신 | AC1, AC7 |
| 요청 ID(Idempotency-Key) 멱등성 | 보류 | 사용자 결정(Round 3 재질문): expected_tick으로 중복 실행은 막히므로 이번엔 보류, 새 테이블 없음. docs에 후속 과제로만 기록 | — |
| 자동 Runner | 보류 | 다음 Phase | — |

## 목표
같은 World에 대한 쓰기 요청이 동시에 들어와도 DB에는 정확히 하나의 결과만 반영되게 하고, Tick 진행 요청에 실행 계약(`expected_tick`)을 두어 재시도해도 중복 실행되지 않게 한다. 제어는 프로세스 내부 잠금이 아니라 PostgreSQL 수준에서 하여 서버 프로세스가 여러 개여도 성립해야 한다.

## 제약
- 엔진(simulation_engine v1) 수정 금지, 기존 14개 테이블의 스키마 변경 금지, 새 테이블 추가 없음.
- docs를 코드보다 먼저 갱신한다. 문서와 보고는 한국어로 쓴다.
- 기존 계층 규칙을 유지한다. 잠금 SQL은 repository 구현(`app/repositories/sqlalchemy/`)에만 두고, service는 repository ABC 메서드로만 잠금을 요청한다.
- 기존 `world.version` 검증(`advance_tick`, `update_simulation`)은 그대로 둔다(이중 보호).
- 프로세스 내부 `asyncio.Lock`/`threading.Lock`에 의존하지 않는다.

### 인터뷰 결정
- **R1 Tick 잠금:** `advance_ticks`는 시작할 때 `SELECT … FROM worlds WHERE id = :id FOR UPDATE NOWAIT`로 행을 잠근다. 잠금은 엔진 실행과 저장, 커밋이 끝날 때까지 유지한다. 이미 잠겨 있으면(PG `lock_not_available`, 55P03) 바로 409 `WORLD_BUSY`를 돌려준다. 저장 시 version 검증은 그대로 둔다.
- **R2 실행 계약:** `TickAdvanceRequest`에 `expected_tick: int`(필수, ≥ 0)를 둔다. 잠금을 얻은 뒤 `current_tick != expected_tick`이면 409 `TICK_MISMATCH`이고, `details`에 `{"current_tick": n}`을 담는다. 이미 반영된 재시도도 똑같이 409이며, 이미 반영됐는지는 클라이언트(Runner)가 current_tick으로 판단한다.
- **R3 요청 ID:** 보류. 다만 docs에 후속 과제로 적는다.
- **R4 PATCH 직렬화:** `change_policy`와 `change_simulation`은 `SELECT … FOR UPDATE`(대기)로 행을 잠그고 `lock_timeout` 5초를 둔다. 시간을 넘기면 409 `WORLD_BUSY`. 잠금을 얻은 뒤 World를 다시 읽고, 정책 `effective_tick = current_tick + 1`을 커밋된 tick 기준으로 계산한다.

## 승인 시 확인할 가정
1. **검사 순서:** 잠금(NOWAIT) → 존재 확인(404) → 상태(`WORLD_NOT_RUNNABLE`) → `expected_tick`(`TICK_MISMATCH`) → snapshot(`SNAPSHOT_MISMATCH`) → 엔진 → 저장 → `advance_tick`(version) → 커밋.
2. **엔진 실패 경로:** 지금은 rollback 후 `mark_failed`인데, rollback이 잠금도 풀어 버린다. 그래서 `mark_failed`도 같은 잠금 규칙(`FOR UPDATE` 대기)으로 다시 잠근 뒤 FAILED로 바꾼다.
3. **세 번째 방어선:** 혹시 저장 중 `IntegrityError`(이벤트 sequence나 idempotency_key 유니크)가 나면 500이 아니라 409 `CONCURRENT_UPDATE`로 바꾼다. version 검증의 `StaleDataError`도 지금처럼 409 `CONCURRENT_UPDATE`다.
4. **잠금 구현:** repository ABC에 `WorldRepository.lock_for_update(world_id, *, nowait: bool, timeout_ms: int | None) -> WorldRead | None`을 추가한다. SQLAlchemy 구현은 `with_for_update(nowait=...)`를 쓰고, 대기형은 `SET LOCAL lock_timeout`을 건다. PG 오류 `55P03`을 `ConflictError("WORLD_BUSY")`로 바꾼다. 테스트 fake는 "잠김" 플래그로 흉내 낸다.
5. **호환성:** `/ticks` 본문에 `expected_tick`이 필수가 되므로 기존 테스트와 호출부를 고친다. frontend는 아직 이 API를 쓰지 않는다.
6. **create_world:** 새 World라 경합 대상이 아니다. 바꾸지 않는다.
7. **lock_timeout 5초:** 설정값(`WORLD_LOCK_TIMEOUT_MS=5000`)으로 둔다.

## 제외 범위
- 요청 ID(Idempotency-Key) 멱등성과 새 테이블, 자동 Runner, SSE, 배속·일시정지 REST 변경, 엔진 수정, 분산 잠금(Redis 등), 읽기 API 잠금.

## 완료 기준
- [ ] AC1: 코드보다 docs를 먼저 갱신한다.
  - `07-rest-sse.md`: `/ticks`의 `expected_tick`, 409 `WORLD_BUSY`·`TICK_MISMATCH`, PATCH의 대기 잠금
  - `06-database.md`: 동시성 제어 규칙(행 잠금 + version 이중 보호)
  - `03-simulation-engine.md` §7.4: 동일 World 동시 실행 금지를 DB 행 잠금으로 보장
  - `02-backend-convention.md`: 잠금은 repository 구현에만 둔다
  - 요청 ID 멱등성을 후속 과제로 기록
- [ ] AC2: 실제 Postgres에서 같은 World에 `/ticks`(같은 expected_tick, count 10) 두 요청을 스레드와 barrier로 동시에 보낸다.
  - 정확히 하나만 200, 나머지는 409(`WORLD_BUSY` 또는 `TICK_MISMATCH`)이며 500은 없다.
  - `current_tick`은 시작값 + 10이다.
  - 이벤트·거래 행 수와 Snapshot 수는 배치 하나만큼만 늘었다.
- [ ] AC3: 세션 1이 worlds 행을 `FOR UPDATE`로 잡은 동안 `/ticks`를 호출하면 바로(1초 이내) 409 `WORLD_BUSY`가 나고 아무것도 쓰이지 않는다.
- [ ] AC4: expected_tick 계약.
  - 일치하면 실행한다.
  - 같은 요청을 다시 보내면 409 `TICK_MISMATCH`이고 `details.current_tick`이 실제 값과 같으며, 두 번째 실행은 일어나지 않는다(행 수 불변).
  - expected_tick 누락은 422다.
- [ ] AC5: PATCH 직렬화.
  - 잠금을 5초 안에 풀면 PATCH가 성공하고, `effective_tick`이 풀린 뒤의 `current_tick + 1`이다.
  - 5초 넘게 잡고 있으면 409 `WORLD_BUSY`다.
  - 정책 변경과 Tick 진행이 섞여도 세계가 FAILED가 되지 않는다.
- [ ] AC6: version 이중 보호. 잠금 없이 오래된 version으로 `advance_tick`을 호출하면 기존처럼 `CONCURRENT_UPDATE`다. 저장 중 IntegrityError를 주입하면 409 `CONCURRENT_UPDATE`이고 500이 아니다.
- [ ] AC7: service 단위 테스트(fake 잠금)와 기존 116개 테스트가 모두 통과하고, `lc_it_*` 임시 DB가 남지 않는다.

## 드러난 가정과 해소
| 가정 | 문제 제기 | 결정 |
|---|---|---|
| version 검증만으로 충분하다 | 실제로는 B가 이벤트 유니크에서 막혀 500이 나고, 엔진 작업도 버려진다 | 행 잠금 NOWAIT + version 이중 보호 (R1) |
| 이미 반영된 재시도는 200으로 돌려줘야 한다 | 판정이 복잡하다 | 409 `TICK_MISMATCH` + current_tick, 판단은 클라이언트 (R2) |
| 요청 ID 멱등성이 필요하다 | expected_tick으로 중복 실행이 이미 막히고, 새 테이블이 필요하다 | 보류 (R3 재질문) |
| PATCH도 즉시 실패해야 한다 | Runner가 연속 실행하면 사용자 PATCH가 계속 굶는다 | FOR UPDATE 대기 + 5초 timeout (R4, 반대 관점) |

## 기술 맥락
- `WorldService.advance_ticks`(`app/services/world_service.py`): 지금은 잠금 없이 읽고, 엔진을 실행하고, `save_advance` 뒤에 `advance_tick(expected_version)`을 호출한다. 저장이 version 검사보다 먼저라서 경합한 요청은 `world_events (world_id, sequence)` 유니크에서 IntegrityError(500)로 끝난다.
- `SqlWorldRepository.advance_tick`, `update_simulation`: `row.version != expected_version` 비교 + `version_id_col`의 StaleDataError → `ConflictError("CONCURRENT_UPDATE")`.
- 정책 경합: 대기 행의 `effective_tick`이 그 사이 진행된 tick보다 과거가 되면, 엔진 `_validate_commands`가 거부해 세계가 FAILED가 된다.
- 세션은 sync SQLAlchemy + psycopg3이며, PG 기본 격리 수준은 READ COMMITTED다.

## 핵심 개념(Ontology)
| 개념 | 유형 | 필드 | 관계 |
|---|---|---|---|
| World | 핵심 | id, current_tick, version, status | 잠금 대상 행 |
| WorldLock | 보조 | nowait, timeout_ms | worlds 행 FOR UPDATE |
| TickContract | 보조 | expected_tick, count | `/ticks` 요청 |
| WORLD_BUSY | 오류 | 409 | 잠금 실패 |
| TICK_MISMATCH | 오류 | 409, details.current_tick | 계약 불일치 |
| Version | 보조 | worlds.version | 저장 시 2차 방어 |

## 개념 수렴
| 라운드 | 개념 수 | 신규 | 변경 | 유지 | 안정도 |
|---|---|---|---|---|---|
| 1 | 5 | 5 | - | - | - |
| 2 | 6 | 1 (TICK_MISMATCH) | 0 | 5 | 83% |
| 3 | 6 | 0 | 0 | 6 | 100% |
| 4 | 6 | 0 | 0 | 6 | 100% |

## 인터뷰 기록
<details><summary>4라운드</summary>

- R0 범위(DB 잠금, 실행 계약, 요청 ID, PATCH 직렬화, 검증·docs) → 맞음
- R1 동시 /ticks에서 진 요청 → 즉시 409 WORLD_BUSY (42%)
- R2 expected_tick 계약 → 필수 + 이미 반영 시 409 (33%)
- R3 요청 ID 멱등성 → (처음 답 "새 테이블로 구현" 후 사용자 요청으로 재질문) 이번엔 보류 (26%)
- R4 (반대 관점) PATCH 잠금 → 짧게 기다린 뒤 처리, lock_timeout 5초 (19%)
</details>
