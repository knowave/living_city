# Deep Interview 스펙: Backend Phase 2 — Runner와 실행 제어

## 메타데이터
- 인터뷰 ID: di-runner-20261120
- 라운드: 5 (+ Round 0 범위 확인)
- 최종 모호도: 19%
- 유형: brownfield
- 작성일: 2026-11-20
- 기준값: 0.2
- 기준값 출처: default
- 초기 맥락 요약 여부: 아니오
- 상태: 통과 — 승인됨 (가정 1–10 승인, team sonnet/haiku 실행)
- 참고: OMC state MCP 연결 실패로 state_write 없이 진행했다.

## 명확도 분석
| 차원 | 점수 | 가중치 | 반영값 |
|---|---|---|---|
| 목표(Goal) | 0.85 | 0.35 | 0.298 |
| 제약(Constraints) | 0.82 | 0.25 | 0.205 |
| 완료 기준(Criteria) | 0.72 | 0.25 | 0.180 |
| 맥락(Context) | 0.87 | 0.15 | 0.131 |
| **명확도 합계** | | | **0.81** |
| **모호도** | | | **0.19** |

## 범위(Topology)
| 구성요소 | 상태 | 설명 | 대응 완료 기준 |
|---|---|---|---|
| Runner 생명주기 | 진행 | 앱 시작 시 RUNNING World 발견, 시작·정지·재개·정상 종료 | AC2, AC6 |
| Tick 스케줄러 | 진행 | 간격 기본 1초(설정), 주기마다 speed만큼 진행, Catch-up 없음 | AC3 |
| 실행 소유권과 동시성 | 진행 | PG advisory lock 소유권 + 기존 행 잠금·expected_tick | AC4 |
| 장애 분류와 복구 | 진행 | 엔진 오류만 FAILED, 일시 오류는 무기한 백오프, 재시작 복원, Snapshot 보관 정책 | AC5, AC6, AC7 |
| 실행 API | 진행 | 기존 PATCH /simulation과 Runner 연결, 배속 {1,4,16} 유지, GET /state에 runner 필드 | AC2, AC8 |
| 측정 | 진행 | 배치별 엔진 계산 시간과 저장 시간을 분리 기록 | AC9 |
| 테스트와 docs | 진행 | 동시·재시도·재시작·상태 전이·장시간(soak 분리), count 경계 | AC1, AC10, AC11 |
| SSE, frontend 실제 데이터 연동, Catch-up, 요청 ID 멱등성 | 보류 | 다음 Phase / 사용자 제안의 v1 제외 | — |

## 목표
브라우저가 닫혀 있어도 서버가 RUNNING 상태인 World의 시간을 스스로 진행한다. World마다 실행자는 정확히 하나이고, 프로세스가 여러 개여도 PostgreSQL advisory lock으로 이를 보장한다. Runner는 엔진이나 ORM을 직접 만지지 않고 Phase 1의 Engine Integration use case만 호출한다. 엔진 불변식 오류만 World를 FAILED로 만들고, 일시적인 인프라 장애는 상태를 바꾸지 않은 채 백오프로 재시도한다. 서버를 재시작하면 마지막 커밋에서 이어 간다.

## 제약
- 엔진 수정 금지, 14개 테이블 스키마 변경 금지, 새 테이블 없음.
- docs를 코드보다 먼저 갱신한다. 문서와 보고는 한국어로 쓴다.
- 계층 규칙 유지:
  - Runner(`app/runner/`)는 use case ABC만 호출하고 sqlalchemy·simulation_engine·ORM을 import하지 않는다.
  - advisory lock SQL은 repository/infra 구현에 두고, Runner는 그 ABC를 통해서만 쓴다.
  - 구현체 조립은 composition root(`app/api/deps.py` 또는 그 옆 조립 함수)에서만 한다.
- 프로세스 내부 잠금에 정확성을 기대지 않는다. 내부 잠금은 최적화 용도로만 쓴다.
- Phase 1의 보호 장치(행 잠금 NOWAIT, expected_tick, version)는 그대로 둔다.

### 인터뷰 결정
- **R1 Snapshot 보관:** 세계마다 최신 `SNAPSHOT_KEEP_LATEST`개(기본 3)와 월말 Tick(`tick % 720 == 0`)의 Snapshot만 남긴다. 나머지는 Tick 저장과 같은 트랜잭션에서 지운다. 수동 `/ticks`에도 똑같이 적용한다. 06-database의 Snapshot 보관 정책 TBD를 이것으로 닫는다.
- **R2 소유권:** Runner가 World를 맡을 때 전용 DB 연결에서 `pg_try_advisory_lock(<World 키>)`를 잡고, 실행하는 동안 계속 유지한다. 잡지 못하면 다른 프로세스가 소유한 것이므로 실행하지 않는다. 프로세스가 죽거나 연결이 끊기면 잠금이 자동으로 풀리고, 다른 프로세스가 발견 주기에 다시 시도해 이어받는다.
- **R3 배속:** 기존 {1, 4, 16}을 유지한다(x8 없음). docs와 코드 모두 바꾸지 않는다.
- **R4 장애 처리:**
  - `SIMULATION_FAILED`(엔진 불변식 오류): 지금처럼 World를 FAILED로 바꾸고 Runner를 끝낸다.
  - 일시적 오류(DB 연결 `OperationalError` 계열, `WORLD_BUSY`, `CONCURRENT_UPDATE`): 1초부터 2배씩 늘려 최대 `RUNNER_BACKOFF_MAX_MS`(30초)까지 무기한 재시도하고, World 상태는 바꾸지 않는다.
  - `TICK_MISMATCH`: `details.current_tick`으로 다시 맞추고 바로 이어 간다.
  - `SNAPSHOT_MISMATCH`: 데이터 정합성 문제이므로 그 World의 Runner만 멈추고(상태 유지), 오류를 기록한다.
  - Runner 상태(실행 중, 재시도 중, 중지, 마지막 오류, 연속 실패 수, 마지막 측정값)는 로그와 `GET /worlds/{id}/state`의 `runner` 필드로 보여 준다.
- **R5 검증:**
  - 기본 테스트는 x16, 간격 20ms로 720 Tick 이상을 돌린다.
  - 재시작은 Runner 관리자를 종료한 뒤 새로 띄워서 확인한다. 관리자 두 개를 동시에 띄워 한쪽만 실행하는지도 확인한다.
  - 8640 Tick(1년) 이상은 pytest marker `soak`으로 분리하고 기본 실행에서 뺀다.

## 승인 시 확인할 가정
1. **Runner 전용 use case:** `WorldUseCase.advance_running(world_id, expected_tick) -> TickAdvanceRead`를 추가한다.
   - 행 잠금(NOWAIT)을 잡은 뒤 status가 RUNNING인지 확인하고, 아니면 409 `WORLD_NOT_RUNNING`을 돌려준다. Runner는 이 응답을 받으면 정상적으로 멈춘다.
   - count는 잠금 안에서 읽은 `world.speed`다.
   - 나머지는 `advance_ticks`와 같은 흐름이다(공통 내부 함수 재사용).
   - 수동 `/ticks`는 지금 동작 그대로 둔다(INITIALIZED·PAUSED에서도 실행 가능).
2. **스케줄러:**
   - World마다 asyncio Task 하나를 두고, 동기 DB·엔진 작업은 `asyncio.to_thread`로 실행한다.
   - 주기마다 `advance_running`을 한 번 호출한다(커밋 1회, Snapshot 1개). x16이면 한 번에 16 Tick을 진행한다.
   - 단조 시계를 기준으로 다음 시작 시각을 맞춘다. 처리가 간격보다 길어지면 다음 주기를 바로 시작하되, 밀린 Tick을 보충하지는 않는다(Catch-up 없음).
3. **발견(Discovery):** `RunnerManager`가 `RUNNER_DISCOVERY_INTERVAL_MS`(기본 1000)마다 RUNNING World 목록을 조회하고, 아직 소유하지 않은 World에 대해 소유권을 시도한다. `PATCH /simulation`으로 RUNNING이 되면 다음 발견 주기(최대 약 1초 뒤)에 시작한다. PAUSED·ARCHIVED가 되면 다음 Tick 주기에 `WORLD_NOT_RUNNING`을 받고 멈추며, 이때 advisory lock을 푼다.
4. **연결 수:** 소유한 World 하나마다 advisory lock을 잡는 전용 연결 하나를 쓴다. Tick 실행용 세션은 주기마다 새로 만든다. MVP 규모(World 수 적음)에서는 허용하고, docs에 한계로 적는다.
5. **정상 종료:** 앱 lifespan이 끝나면 새 주기를 막고, 진행 중인 주기가 끝나기를 최대 10초 기다린 뒤 잠금을 풀고 연결을 닫는다.
6. **설정값:** `RUNNER_ENABLED`(기본 true, 테스트는 false), `RUNNER_TICK_INTERVAL_MS=1000`, `RUNNER_DISCOVERY_INTERVAL_MS=1000`, `RUNNER_BACKOFF_MAX_MS=30000`, `SNAPSHOT_KEEP_LATEST=3`.
7. **측정:** 서비스가 엔진 실행(`compute_ms`)과 저장·커밋(`persist_ms`) 시간을 따로 재서 `TickAdvanceRead`에 선택 필드로 담는다. Runner는 이를 INFO 로그(world_id, ticks, compute_ms, persist_ms)와 runner 상태에 남긴다.
8. **runner 필드:** `GET /state`의 `runner`는 이 프로세스가 아는 정보다. 다른 프로세스가 소유한 World는 `null`이고, 이 한계를 docs에 적는다.
9. **Phase 1 보강:**
   - `count=0`·`721`은 422임을 테스트한다.
   - 세계 생성 중 엔진 실패는 409 `WORLD_GENERATION_FAILED`를 유지한다. 그 밖의 내부 오류는 500으로 남겨 두고 바꾸지 않는다.
10. **World 키:** advisory lock 키는 `world_id`의 앞 8바이트를 signed int64로 바꾼 값이다. 충돌 가능성은 무시할 만하고, docs에 기록한다.

## 제외 범위
- SSE, frontend 실제 데이터 연동, Catch-up, 요청 ID 멱등성, x8 배속, 분산 Worker 오케스트레이션(Redis 등), 엔진 수정, 스키마 변경, 지표·성능 대시보드.

## 완료 기준
- [ ] AC1: 코드보다 docs를 먼저 갱신한다.
  - `03-simulation-engine.md` §7.4·§7.10: Runner 구조, advisory lock 소유권, 재시작 복원
  - `07-rest-sse.md`: PATCH /simulation이 Runner와 연결되는 방식, `GET /state`의 `runner` 필드, 내부 use case
  - `06-database.md`: Snapshot 보관 정책 확정
  - `02-backend-convention.md`: `app/runner` 계층 규칙과 설정값
  - `03-citizen.md`의 "1 Tick이 몇 초인가" TBD: 기본 1초, 설정 가능, 측정 후 확정한다고 적되 TBD 표시는 유지
  - CLAUDE.md의 backend 상태 설명
- [ ] AC2: 생명주기.
  - RUNNING인 World는 관리자 시작 후 발견 주기 안에 진행을 시작한다.
  - PATCH로 PAUSED가 되면 다음 주기에 멈추고(tick 증가 멈춤), 다시 RUNNING이 되면 이어 간다.
  - ARCHIVED가 되면 멈추고 다시 시작하지 않는다.
  - INITIALIZED·FAILED는 실행하지 않는다.
- [ ] AC3: 스케줄러. 간격 20ms, speed 16에서 N개 주기 뒤 tick이 16의 배수로 늘고, 주기당 커밋은 1회다. 처리가 지연돼도 밀린 Tick을 보충하지 않는다(가짜 느린 use case로 검증).
- [ ] AC4: 소유권과 동시성.
  - 관리자 두 개(각자 엔진·세션)를 같은 DB에서 동시에 돌려도 한 World를 한쪽만 실행한다(advisory lock).
  - 일정 시간 뒤 tick 증가량이 단일 관리자 기준을 넘지 않는다.
  - 소유한 관리자를 종료하면 다른 관리자가 이어받는다.
  - Phase 1의 병렬 `/ticks` 테스트와 재시도 테스트는 계속 통과한다.
- [ ] AC5: 장애 분류.
  - 엔진 불변식 오류를 주입하면 FAILED가 되고 Runner가 끝난다.
  - DB `OperationalError`, `WORLD_BUSY`, `CONCURRENT_UPDATE`를 주입하면 World 상태는 RUNNING을 유지한다. 백오프 간격이 1→2→4…로 늘고 30초에서 멈추며(가짜 시계·sleep으로 검증), 오류가 사라지면 다시 진행한다.
  - `TICK_MISMATCH`는 다시 맞춘 뒤 이어 간다.
  - `SNAPSHOT_MISMATCH`는 해당 Runner만 멈춘다.
- [ ] AC6: 재시작 복원. 관리자를 종료한 시점의 마지막 커밋 tick을 T라고 하면, 새 관리자는 T부터 이어 간다. 중복 이벤트 sequence나 거래가 없고 Catch-up도 없다.
- [ ] AC7: Snapshot 보관. 720 Tick 이상 실행한 뒤 남은 Snapshot은 최신 3개와 `tick % 720 == 0`인 것뿐이다. 최신 Snapshot으로 복원하는 데 문제가 없다.
- [ ] AC8: `GET /state`의 `runner` 필드가 실행 중·재시도 중·중지와 마지막 오류를 보여 준다. 소유하지 않은 World는 `null`이다.
- [ ] AC9: 측정. `TickAdvanceRead`에 `compute_ms`, `persist_ms`가 있고 Runner 로그에 남는다. 720 Tick 실행의 두 값을 보고서에 적는다.
- [ ] AC10: `count=0`·`721` → 422 테스트. 기존 138개 테스트와 Phase 1의 필수 검증 두 가지(병렬 중복 없음, 응답 유실 후 재시도 무중복)가 모두 통과한다.
- [ ] AC11: soak 테스트(8640 Tick 이상)는 `-m soak`으로만 돈다. 한 번 실행해 결과(소요 시간, Snapshot 수, 메모리)를 보고한다.

## 드러난 가정과 해소
| 가정 | 문제 제기 | 결정 |
|---|---|---|
| 커밋마다 Snapshot을 남겨도 된다 | 133KB × 초당 1회면 하루 11.5GB다 | 최신 N개 + 월말만 보존 (R1) |
| NOWAIT + expected_tick이면 실행자 하나가 보장된다 | 여러 프로세스가 번갈아 성공하면 2배속이 된다 | PG advisory lock 소유권 (R2) |
| 배속 x8 추가 | docs·코드는 {1,4,16}이다 | 기존 유지 (R3) |
| 일시 장애는 그냥 무한 재시도하면 된다 | 사용자에게 보이지 않는 정지 상태가 된다 | 무기한 백오프 + runner 상태 노출 (R4, 반대 관점) |
| 장시간 실행을 기본 테스트에 넣는다 | CI 시간이 늘어난다 | 기본 720+ Tick, 1년은 soak marker로 분리 (R5) |

## 기술 맥락
- 실측(시민 100명): `run(16)` 1.8ms, Snapshot `state_data` 약 133KB(직렬화 1.2ms). Phase 1에서 720 Tick 저장은 약 1초였다.
- `WorldService.advance_ticks`: NOWAIT 행 잠금 → 상태 → expected_tick → Snapshot → 엔진 → 저장 → version → 커밋. 엔진 오류는 재잠금 후 FAILED. 저장 중 IntegrityError는 409 `CONCURRENT_UPDATE`.
- `ALLOWED_SPEEDS = {1, 4, 16}`, 상태 전이표(`world_service.py:33`). FAILED는 시스템 전용이다.
- `app/main.py`의 lifespan은 지금 DB 자동 동기화만 한다. Runner 시작·종료는 여기에 붙인다.
- 세션은 sync SQLAlchemy + psycopg3다. advisory lock은 세션 범위라서 연결을 계속 붙잡고 있어야 한다.

## 핵심 개념(Ontology)
| 개념 | 유형 | 필드 | 관계 |
|---|---|---|---|
| RunnerManager | 핵심 | 소유 World 목록, 발견 주기 | WorldRunner를 만들고 정리 |
| WorldRunner | 핵심 | world_id, expected_tick, 상태, 백오프 | advance_running 호출 |
| OwnershipLock | 보조 | advisory key, 전용 연결 | World당 하나 |
| TickScheduler | 보조 | interval, speed | WorldRunner 안 |
| BackoffPolicy | 보조 | 1s→30s | 일시 오류 |
| SnapshotRetention | 보조 | keep_latest=3, 월말 | 저장 트랜잭션 |
| RunnerStatus | 보조 | state, last_error, failures, compute_ms, persist_ms | GET /state.runner |

## 개념 수렴
| 라운드 | 개념 수 | 신규 | 변경 | 유지 | 안정도 |
|---|---|---|---|---|---|
| 1 | 5 | 5 | - | - | - |
| 2 | 6 | 1 (OwnershipLock) | 0 | 5 | 83% |
| 3 | 6 | 0 | 0 | 6 | 100% |
| 4 | 7 | 1 (RunnerStatus) | 0 | 6 | 86% |
| 5 | 7 | 0 | 0 | 7 | 100% |

## 인터뷰 기록
<details><summary>5라운드</summary>

- R0 범위(생명주기, 스케줄러, 소유권, 장애·복구, 실행 API, 측정, 테스트·docs) → 맞음
- R1 Snapshot 보관 → 최신 N개 + 월말 보존 (52%)
- R2 실행자 하나 보장 → PG advisory lock 소유권 (43%)
- R3 배속 x8 충돌 → 기존 {1, 4, 16} 유지 (36%)
- R4 (반대 관점) 장애 처리 → 무기한 백오프 + 상태 노출 (29%)
- R5 장시간·재시작 검증 → 기본 + soak 분리 (19%)
</details>
