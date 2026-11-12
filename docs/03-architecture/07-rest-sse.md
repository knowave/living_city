# REST API 및 SSE

> 원본: README §9.1, §9.2

> 구현 상태 (코드 기준): 현재 구현된 엔드포인트는 `GET /api/v1/health` 하나뿐이다 (backend/app/api/v1/endpoints/health.py:6). 아래 REST 표와 SSE는 설계이며 미구현이다.
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
