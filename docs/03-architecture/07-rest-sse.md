# REST API 및 SSE

> 원본: README §9.1, §9.2

> 구현 상태: REST 18개 엔드포인트가 구현되었다(`GET /api/v1/health` 별도). `POST /worlds`는 엔진으로 실제 세계를 생성하고 맵(MapChunk 256개)을 같은 트랜잭션에서 저장한다. 맵·건물·시민·기업·요약·`/view` 조회 API는 Backend Phase 3(REST API 완성)에서 구현되었다. 수동 `POST /worlds/{world_id}/ticks`는 PAUSED에서만 진행한다. Simulation Runner는 구현되었다(자동 Tick 진행, [시뮬레이션 엔진 §7.4](03-simulation-engine.md)). SSE는 미구현이다. 다음 순서는 SSE → frontend 실제 데이터 연동이다.
> 경로 접두사 (코드 기준): 모든 경로는 `API_V1_STR`(`/api/v1`) 아래에 등록된다 (backend/app/main.py:28). 아래 표의 경로는 접두사를 뺀 상대 경로다.

## 9.1 REST API

REST API는 조회와 사용자 명령을 담당한다.

| Method | Endpoint | 기능 |
|---|---|---|
| POST | /worlds | 도시 생성 (맵 포함) |
| GET | /worlds/{id} | 도시 메타데이터 |
| GET | /worlds/{id}/state | 도시 상태 및 이벤트 커서 |
| GET | /worlds/{id}/map | 맵 메타데이터 (크기, 청크 수, 엔진 영역) |
| GET | /worlds/{id}/chunks | 맵 Chunk 조회 |
| GET | /worlds/{id}/buildings | 건물 목록 (타일 범위 필터) |
| GET | /worlds/{id}/buildings/{buildingId} | 건물 상세 |
| GET | /worlds/{id}/citizens | 시민 목록 (페이지네이션, 필터) |
| GET | /worlds/{id}/citizens/{citizenId} | 시민 상세 |
| GET | /worlds/{id}/companies | 기업 목록 (페이지네이션, 필터) |
| GET | /worlds/{id}/companies/{companyId} | 기업 상세 |
| GET | /worlds/{id}/companies/{companyId}/employees | 기업 직원 목록 (페이지네이션) |
| GET | /worlds/{id}/metrics | 경제 통계 |
| GET | /worlds/{id}/summary | 도시 요약 (대시보드 통계) |
| GET | /worlds/{id}/view | 화면 복원용 단일 시점 조회 |
| PATCH | /worlds/{id}/simulation | 실행, 정지, 배속 변경 |
| PATCH | /worlds/{id}/policies | 정책 변경 |
| POST | /worlds/{id}/ticks | 수동 Tick 진행 (PAUSED 전용) |

### 공통 규칙

- **응답 형식**: JSON 필드는 snake_case다. 맵·건물·시민·기업 응답 필드는 frontend DTO(`frontend/src/render/map/types.ts`, `citizens/types.ts`)의 키와 같다.
- **목록 envelope**: 페이지네이션 목록은 `{items, total, limit, offset, as_of_tick, event_cursor}`(`Page[T]`)를 돌려준다. 정렬은 id 순이다.
  - `limit`: 기본 100, 최대 500. `offset`: 0 이상. 범위를 벗어나면 422 `VALIDATION_ERROR`.
  - `total`은 필터를 적용한 전체 개수다.
- **단순 목록**: `GET /chunks`, `GET /buildings`는 envelope 없이 배열을 바로 돌려준다.
- **`as_of_tick`, `event_cursor`**: 시간이 흐르는 데이터를 돌려주는 응답(목록, 상세, `/summary`, `/view`)에 있다.
  - `as_of_tick`: 응답을 만든 트랜잭션에서 읽은 `worlds.current_tick`이다.
  - `event_cursor`: 같은 트랜잭션에서 읽은 `world_events.sequence` 최댓값이다. 이벤트가 없으면 0이다.
  - 두 값과 데이터는 같은 커밋 상태에서 읽은 것이므로 한 응답 안에서 서로 모순되지 않는다. 같은 `event_cursor`를 받은 두 응답의 데이터는 같다.
  - 이 조회들은 [데이터 저장 설계 §10.6](06-database.md)의 REPEATABLE READ 트랜잭션에서 실행한다. 조회는 행 잠금을 잡지 않으므로 Runner의 쓰기를 막지 않는다.
  - SSE 재접속 계약(다음 Phase에서 구현): 클라이언트는 응답의 `event_cursor`를 저장해 두었다가 SSE 재연결 때 그 커서 이후 이벤트부터 받는다.
- **시민 이동 정보(`movement`)**: `current_activity`가 `MOVING`인 시민에게만 값이 있다. 값은 그 시민의 가장 최근 `citizen.movement.started` 이벤트 payload(이미 DB id로 바뀐 값)에서 가져온다. 이동 중이 아니거나 도착했으면 `null`이다. 목록, 상세, `/view`가 같은 규칙을 쓴다. `as_of_tick`(= `worlds.current_tick`, 완료한 Tick 수)을 기준으로 이동 중인 시민은 항상 `start_tick < as_of_tick <= arrival_tick`이다. 엔진은 `tick == arrival_tick`인 Tick을 처리할 때 도착시키므로, `as_of_tick == arrival_tick`이면 아직 MOVING이다.
- **호환성**: 시민·기업 상세는 필드를 더한 응답이다(기존 필드는 그대로). frontend는 아직 이 API를 쓰지 않는다.
- **성능 목표**: 로컬 PostgreSQL, 시민 100명, Runner x16 실행 중에 각 API를 50회 호출해 p95를 잰다. 목표는 `/view` ≤ 200ms, 맵 전체 청크 256개 ≤ 500ms, 목록·상세 ≤ 100ms다. 목표를 넘으면 결과만 보고하고 테스트를 실패시키지 않는다. 정확성 테스트는 반드시 통과해야 한다.

### 요청/응답 상세 (구현 기준)

- `POST /worlds`: body `name`(1~100자, 필수), `seed`(선택 int, 생략 시 63비트 난수를 만들어 저장), `engine_version`(선택, 기본 `ENGINE_VERSION` 설정값). 엔진 `generate_world`로 세계를 생성한다. 같은 seed와 엔진 건물 좌표로 맵을 생성해 검증한 뒤, 세계와 맵(map_chunks 256개)을 한 트랜잭션에서 저장한다. 201로 응답한다(status `INITIALIZED`, current_tick 0, speed 1). 초기 정책은 엔진 값(income_tax_rate 1500bp, welfare_amount 1,000,000, effective_tick 0, version 1)이다.
  - 맵 생성 규칙과 검증은 [맵 및 렌더링 설계 §8.5](04-map-rendering.md)를 따른다.
  - 엔진 세계 생성이나 맵 생성·검증이 실패하면 아무것도 저장하지 않고(World 행도 남기지 않는다) 409 `WORLD_GENERATION_FAILED`로 응답한다.
  - 오류: 409 `WORLD_GENERATION_FAILED`, 422 `VALIDATION_ERROR`.
- `GET /worlds/{id}`: 세계 메타데이터. 없으면 404 `WORLD_NOT_FOUND`.
- `GET /worlds/{id}/state`: status, current_tick, speed, 현재 정책, `event_cursor`(world_events.sequence 최댓값, 없으면 0). 현재 정책은 effective_tick ≤ current_tick인 최신 version이다. 실행 여부의 공식 기준은 `status`다(RUNNING이면 서버가 진행 중으로 본다). `runner` 필드는 실행 중인 프로세스의 런타임 정보(소유 프로세스 기준 상태, 마지막 오류, 측정값)이며, 이 프로세스가 소유한 World에만 값이 있다. `null`은 "이 프로세스는 모른다"는 뜻이지 "실행 중이 아니다"라는 뜻이 아니다. 클라이언트는 `runner`가 `null`이라는 이유로 실행 여부를 판단하지 않는다. 멀티 프로세스 배포에서 다른 프로세스의 runner 정보를 조회하는 방법은 배포 전 과제다(단일 프로세스 배포라면 현재 동작으로 충분하다). 값은 `state`(`running`·`retrying`·`stopped`), `consecutive_failures`, `last_error`, `last_compute_ms`, `last_persist_ms`, `last_tick`이다.
- `GET /worlds/{id}/map`: 맵 메타데이터. 응답은 `{width: 512, height: 512, chunk_size: 32, chunks_x: 16, chunks_y: 16, tile_schema_version: 1, engine_area: {x: 0, y: 0, width: 128, height: 128}}`다. `engine_area`는 엔진 건물이 놓이는 영역이다. 없는 세계는 404 `WORLD_NOT_FOUND`.
- `GET /worlds/{id}/chunks`: 세계의 Chunk 배열. 선택 쿼리 `x_min`, `x_max`, `y_min`, `y_max`(경계 포함 chunk 좌표). 범위를 생략하면 전체(256개)를 돌려준다. 각 항목은 frontend ChunkDTO와 같다: `chunk_x`, `chunk_y`, `chunk_size`, `terrain_tiles`(1024개), `road_tiles`(1024개), `schema_version`, `revision`. 타일 값은 [맵 및 렌더링 설계 §8.2](04-map-rendering.md)의 타일 스키마 v1을 따른다.
- `GET /worlds/{id}/buildings`: 건물 배열. 선택 쿼리 `x_min`, `x_max`, `y_min`, `y_max`(타일 좌표 범위)를 주면 그 범위와 겹치는 건물을 돌려준다. 건물이 청크 경계에 걸쳐 있어도 포함된다. 각 항목은 `BuildingRead`(frontend BuildingDTO와 같다)다: `id`, `world_id`, `type`, `tile_x`, `tile_y`, `width`, `height`, `capacity`, `occupied_capacity`, `status`. `created_at`, `updated_at`은 포함하지 않는다.
- `GET /worlds/{id}/buildings/{buildingId}`: 건물 상세. `BuildingRead` + `company_ids`(그 건물에 있는 기업 id 목록) + `household_count`(거주 가구 수)다. 없거나 다른 세계 소속이면 404 `BUILDING_NOT_FOUND`.
- `GET /worlds/{id}/citizens`: 시민 목록(`Page[CitizenRead]`). 선택 쿼리 `limit`, `offset`, `employment_status`(EMPLOYED·UNEMPLOYED), `current_activity`(AT_HOME·MOVING·WORKING·SHOPPING), `building_id`. `building_id`는 그 건물에 현재 있는 시민(`current_building_id`가 같은 시민)만 고른다.
- `GET /worlds/{id}/citizens/{citizenId}`: 시민 상세. `CitizenRead` + `as_of_tick` + `event_cursor`다.
  - `CitizenRead` 필드: 기존 시민 필드 + `movement` + `employment` + `cash_balance`.
  - `movement`: `{from_building_id, to_building_id, start_tick, arrival_tick}` 또는 `null`(공통 규칙 참조).
  - `employment`: 활성 고용이 있으면 `{company_id, salary, hired_tick}`, 없으면 `null`.
  - `cash_balance`: 해당 시민의 CASH/KRW 계정 잔액. 계정이 없으면 null.
  - 없거나 다른 세계 소속이면 404 `CITIZEN_NOT_FOUND`.
- `GET /worlds/{id}/companies`: 기업 목록(`Page[CompanyRead]`). 선택 쿼리 `limit`, `offset`, `status`(ACTIVE·DISTRESSED·BANKRUPT), `industry`.
- `GET /worlds/{id}/companies/{companyId}`: 기업 상세. `CompanyRead` + `cash_balance`(CASH/KRW 계정 잔액) + 고용 요약(`active_employees`: ACTIVE 고용 수) + `as_of_tick` + `event_cursor`다. 없으면 404 `COMPANY_NOT_FOUND`.
- `GET /worlds/{id}/companies/{companyId}/employees`: 직원 목록(`Page[CitizenRead]`). 선택 쿼리 `limit`, `offset`. 파산 기업은 직원이 없으므로 빈 목록(`total` 0)을 돌려준다. 기업이 없으면 404 `COMPANY_NOT_FOUND`.
- `GET /worlds/{id}/metrics`: world_metrics 행을 tick 순으로 반환. 선택 쿼리 `metric_code`, `period`, `from_tick`, `to_tick`.
- `GET /worlds/{id}/summary`: 도시 요약. 한 트랜잭션에서 계산한다. 응답은 `{as_of_tick, event_cursor, population, employed, unemployment_rate, companies: {active, distressed, bankrupt}, government_treasury, city_internal_money, latest_metrics}`다.
  - `population`: 인구. `employed`: 취업자 수. `unemployment_rate`: 실업률.
  - `companies`: 운영 중(ACTIVE), DISTRESSED, 파산(BANKRUPT) 기업 수.
  - `government_treasury`: 정부 국고 잔액.
  - `city_internal_money`: 도시 내부 자금 = 시민 + 기업 + 정부 잔액 합계.
  - `latest_metrics`: 최신 월간 지표 12종(`MetricRead`, tick과 값). 지표 이력은 `GET /metrics`를 쓴다.
  - 매출 구분 4항목은 저장된 테이블이 없어 이번 응답에서 제외한다.
  - 없는 세계는 404 `WORLD_NOT_FOUND`.
- `GET /worlds/{id}/view`: 화면 복원용 단일 시점 조회. 한 트랜잭션에서 World 상태, 현재 정책, runner, 시민 전체(이동 정보 포함), 건물 전체, 기업 목록을 읽는다.
  - 응답은 `{as_of_tick, event_cursor, world: WorldStateRead, citizens: [CitizenRead], buildings: [BuildingRead], companies: [CompanyRead]}`다.
  - `world`는 `/state`와 같은 구성이다. `citizens`, `buildings`, `companies`는 페이지네이션 없이 전부 돌려준다.
  - `companies`는 전체 `CompanyRead`(`cash_balance` 포함)다.
  - 없는 세계는 404 `WORLD_NOT_FOUND`.
- `PATCH /worlds/{id}/simulation`: body `{status?, speed?}`. 허용 전이: INITIALIZED→RUNNING, RUNNING→PAUSED, PAUSED→RUNNING, {INITIALIZED, RUNNING, PAUSED}→ARCHIVED. FAILED는 시스템 전용, ARCHIVED는 종료 상태. 그 외 전이는 409 `INVALID_STATE_TRANSITION`. `speed`는 {1, 4, 16}만 허용하고 아니면 422. World.version 낙관적 락 충돌은 409 `CONCURRENT_UPDATE`. 상태/배속만 저장하며 tick은 실행하지 않는다. `RUNNING`으로 바꾸면 Runner가 발견 주기(`RUNNER_DISCOVERY_INTERVAL_MS`, 기본 1초) 안에 그 World의 진행을 시작한다. `PAUSED`·`ARCHIVED`로 바꾸면 Runner는 다음 Tick 주기에 멈춘다. 배속은 {1, 4, 16}을 유지한다(x8 없음). Runner는 배속만큼 Tick을 진행한다. 세계 행 잠금을 최대 `WORLD_LOCK_TIMEOUT_MS`(기본 5000 ms)까지 기다리며, 얻지 못하면 409 `WORLD_BUSY`.
- `PATCH /worlds/{id}/policies`: body `{income_tax_rate?, welfare_amount?}`. income_tax_rate는 0~10000bp, welfare_amount ≥ 0, 최소 한 필드 필수(아니면 422). 새 정책 행을 만든다: version = 최신 version + 1, effective_tick = 잠금을 얻은 뒤 읽은 커밋된 current_tick + 1, 지정하지 않은 필드는 최신 정책 값을 복사한다. 이 행은 적용 대기 명령이다. 다음 Tick 진행 때 엔진 `PolicyChangeCommand`로 적용되고 엔진이 만든 정책 행으로 교체된다. 같은 Tick 안의 두 번째 PATCH는 대기 행을 덮어쓰고 version을 올린다. 세계 행 잠금을 최대 `WORLD_LOCK_TIMEOUT_MS`(기본 5000 ms)까지 기다리며, 얻지 못하면 409 `WORLD_BUSY`.
- `POST /worlds/{world_id}/ticks`: body `{count, expected_tick}`. `count`는 1~720, `expected_tick`은 0 이상 정수이며 둘 다 필수다. 요청 1회가 DB 트랜잭션 1개이며, count Tick을 진행한 결과를 한 번에 저장하고 마지막 Tick의 Snapshot 1개를 남긴다. 세계 행을 `FOR UPDATE NOWAIT`로 잠그고, 잠금을 얻은 뒤 `current_tick == expected_tick`일 때만 실행한다. 이미 반영된 요청을 다시 보내도 `TICK_MISMATCH`가 나며, 재시도 판단은 클라이언트가 `details.current_tick`으로 한다. 응답 필드: `from_tick`, `to_tick`, `event_count`, `last_event_sequence`, `transaction_count`, `compute_ms`, `persist_ms`(선택: 엔진 계산 시간과 저장·커밋 시간, ms). 오류: 404 `WORLD_NOT_FOUND`, 409 `WORLD_NOT_PAUSED`(PAUSED가 아닌 모든 상태), 409 `WORLD_BUSY`(같은 세계에 다른 쓰기가 진행 중, 기다리지 않고 즉시 응답), 409 `TICK_MISMATCH`(`details: {"current_tick": n}`), 409 `SNAPSHOT_MISMATCH`, 409 `CONCURRENT_UPDATE`, 409 `SIMULATION_FAILED`(엔진 예외, 세계는 FAILED), 422 `VALIDATION_ERROR`(`expected_tick` 누락 포함).
  - 정책(2026-11-20, 구현됨): 수동 `/ticks`는 PAUSED에서만 허용한다. RUNNING·INITIALIZED·FAILED·ARCHIVED에서는 모두 409 `WORLD_NOT_PAUSED`를 돌려준다. 이전 문서의 `WORLD_NOT_RUNNABLE`(FAILED·ARCHIVED)은 이 코드로 통일했다. Runner와 수동 요청이 겹쳐 의도보다 시간이 빨리 흐르는 것을 막기 위해서다.
  - 수동 진행 흐름: INITIALIZED에서 PAUSED로 가는 전이는 없으므로, `PATCH /simulation`으로 RUNNING을 거쳐 PAUSED로 바꾼 뒤 `/ticks`를 호출한다.
  - 요청 ID 멱등성은 보류하되, `expected_tick` 기반 재시도 방지는 Runner와 수동 경로 모두 계속 유지한다.
- 요청 ID(Idempotency-Key) 멱등성은 후속 과제이며 보류 상태다 (2026-11-20). `expected_tick`으로 중복 실행은 이미 막히므로 지금은 구현하지 않는다.
- 오류 응답 형식은 [API 컨벤션](../04-development/05-api-convention.md)을 따른다.

### Runner 전용 use case (REST 아님)

- `advance_running(world_id, expected_tick)`: Runner가 주기마다 호출한다. `POST /ticks`와 같은 흐름이지만, status가 RUNNING이 아니면 409 `WORLD_NOT_RUNNING`을 돌려준다. Runner는 이 응답을 받으면 정상적으로 멈춘다. count는 잠금 안에서 읽은 `world.speed`다.
- 외부에 노출하는 HTTP 경로는 없다. 수동 `POST /ticks`는 PAUSED 전용이다(위 정책 참조).

## 9.2 SSE

SSE는 서버에서 발생한 상태 변경을 전달한다.

Endpoint:

GET /worlds/{id}/events

주요 이벤트:

- simulation.tick
- simulation.status.changed
- citizen.employment.changed
- citizen.movement.started
- company.status.changed
- economy.month.closed
- metrics.updated
- policy.updated

시민의 매 프레임 위치는 전송하지 않는다.
