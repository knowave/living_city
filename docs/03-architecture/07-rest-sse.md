# REST API 및 SSE

> 원본: README §9.1, §9.2

> 구현 상태: REST 9개 엔드포인트는 DB만 다루는 동작으로 구현되었다(`GET /api/v1/health` 별도). 엔진 의존 부분(세계 생성: 시민/기업/맵 생성, tick 실행)은 미구현이다. SSE는 미구현이다.
> 경로 접두사 (코드 기준): 모든 경로는 `API_V1_STR`(`/api/v1`) 아래에 등록된다 (backend/app/main.py:28). 아래 표의 경로는 접두사를 뺀 상대 경로다.

## 9.1 REST API

REST API는 조회와 사용자 명령을 담당한다.

| Method | Endpoint | 기능 |
|---|---|---|
| POST | /worlds | 도시 생성 |
| GET | /worlds/{id} | 도시 메타데이터 |
| GET | /worlds/{id}/state | 도시 상태 및 이벤트 커서 |
| GET | /worlds/{id}/chunks | 맵 Chunk 조회 |
| GET | /worlds/{id}/citizens/{citizenId} | 시민 상세 |
| GET | /worlds/{id}/companies/{companyId} | 기업 상세 |
| GET | /worlds/{id}/metrics | 경제 통계 |
| PATCH | /worlds/{id}/simulation | 실행, 정지, 배속 변경 |
| PATCH | /worlds/{id}/policies | 정책 변경 |

### 요청/응답 상세 (구현 기준)

- `POST /worlds`: body `name`(1~100자, 필수), `seed`(선택 int, 생략 시 63비트 난수를 만들어 저장), `engine_version`(선택, 기본 `ENGINE_VERSION` 설정값). World(status `INITIALIZED`, current_tick 0, speed 1)와 초기 정책(income_tax_rate 1500bp, welfare_amount 0, effective_tick 0, version 1)을 만들어 201로 응답한다. 시민/기업/맵은 생성하지 않는다(세계 생성은 엔진 연동 후).
- `GET /worlds/{id}`: 세계 메타데이터. 없으면 404 `WORLD_NOT_FOUND`.
- `GET /worlds/{id}/state`: status, current_tick, speed, 현재 정책, `event_cursor`(world_events.sequence 최댓값, 없으면 0). 현재 정책은 effective_tick ≤ current_tick인 최신 version이다.
- `GET /worlds/{id}/chunks`: 세계의 Chunk 목록. 선택 쿼리 `x_min`, `x_max`, `y_min`, `y_max`(경계 포함 chunk 좌표).
- `GET /worlds/{id}/citizens/{citizen_id}`: 시민 상세 + `cash_balance`(해당 시민의 CASH/KRW 계정 잔액, 계정이 없으면 null). 없거나 다른 세계 소속이면 404 `CITIZEN_NOT_FOUND`.
- `GET /worlds/{id}/companies/{company_id}`: 기업 상세 + `cash_balance`(CASH/KRW 계정 잔액). 없으면 404 `COMPANY_NOT_FOUND`.
- `GET /worlds/{id}/metrics`: world_metrics 행을 tick 순으로 반환. 선택 쿼리 `metric_code`, `period`, `from_tick`, `to_tick`.
- `PATCH /worlds/{id}/simulation`: body `{status?, speed?}`. 허용 전이: INITIALIZED→RUNNING, RUNNING→PAUSED, PAUSED→RUNNING, {INITIALIZED, RUNNING, PAUSED}→ARCHIVED. FAILED는 시스템 전용, ARCHIVED는 종료 상태. 그 외 전이는 409 `INVALID_STATE_TRANSITION`. `speed`는 {1, 4, 16}만 허용하고 아니면 422. World.version 낙관적 락 충돌은 409 `CONCURRENT_UPDATE`. 상태/배속만 저장하며 tick은 실행하지 않는다.
- `PATCH /worlds/{id}/policies`: body `{income_tax_rate?, welfare_amount?}`. income_tax_rate는 0~10000bp, welfare_amount ≥ 0, 최소 한 필드 필수(아니면 422). 새 정책 행을 만든다: version = 최신 version + 1, effective_tick = current_tick + 1, 지정하지 않은 필드는 최신 정책 값을 복사한다.
- 오류 응답 형식은 [API 컨벤션](../04-development/05-api-convention.md)을 따른다.

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
