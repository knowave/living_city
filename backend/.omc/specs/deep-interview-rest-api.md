# Deep Interview 스펙: Backend Phase 3 — REST API 완성 (맵·건물 공간 데이터 일치)

## 메타데이터
- 인터뷰 ID: di-rest-api-20261120
- 라운드: 5 (+ Round 0 범위 확인)
- 최종 모호도: 19%
- 유형: brownfield
- 작성일: 2026-11-20
- 기준값: 0.2
- 기준값 출처: default
- 초기 맥락 요약 여부: 아니오
- 상태: 통과 — 승인됨 (가정 1–11 승인, team sonnet/haiku 실행)
- 참고: OMC state MCP 연결 실패로 state_write 없이 진행했다.

## 명확도 분석
| 차원 | 점수 | 가중치 | 반영값 |
|---|---|---|---|
| 목표(Goal) | 0.86 | 0.35 | 0.301 |
| 제약(Constraints) | 0.80 | 0.25 | 0.200 |
| 완료 기준(Criteria) | 0.74 | 0.25 | 0.185 |
| 맥락(Context) | 0.86 | 0.15 | 0.129 |
| **명확도 합계** | | | **0.81** |
| **모호도** | | | **0.19** |

## 범위(Topology)
| 구성요소 | 상태 | 설명 | 대응 완료 기준 |
|---|---|---|---|
| 맵 생성·저장과 건물 API (핵심) | 진행 | backend 맵 생성기가 엔진 건물 좌표를 고정하고 512×512 지형·도로를 만들어 map_chunks에 저장, 연결성 검증, 청크·건물·맵 메타 API | AC2–AC5 |
| World·Simulation 조회 계약 | 진행 | 단일 트랜잭션 `/view`, 응답 기준 커서, 수동 `/ticks`는 PAUSED에서만 | AC6, AC7 |
| 시민·기업 조회 | 진행 | 목록(페이지네이션)·상세, 시민 이동 정보는 최신 이동 이벤트에서 | AC8, AC9 |
| 도시 통계 | 진행 | 대시보드 요약 API | AC10 |
| 통합·회귀 검증 | 진행 | 실행 중 조회 일관성, PAUSED, 동시 접근, 페이지 경계, p95 측정 | AC11, AC12 |
| docs 먼저 갱신 | 진행 | 맵 책임 소재와 API 계약 확정 | AC1 |
| SSE, frontend 수정 | 보류 | 다음 Phase | — |

## 목표
자동으로 진행되는 World를 frontend가 REST만으로 정확히 복원·조회할 수 있게 한다. 핵심은 엔진 건물 좌표와 화면 맵의 일치다. backend 맵 생성기가 엔진이 정한 건물 위치를 바꾸지 않고, 그 주위로 지형과 도로를 시드 기반으로 결정적으로 만들어 저장한다. 이때 모든 건물 입구가 하나의 도로망에 연결되도록 보장한다. 시간이 흐르는 데이터는 한 트랜잭션에서 읽은 기준 Tick·이벤트 커서와 함께 내려 주어, 다음 Phase의 SSE가 끊김 없이 이어지게 한다.

## 제약
- 엔진 수정 금지(경제·이동 규칙 포함), 14개 테이블 스키마 변경 금지, 새 테이블 없음.
- docs를 코드보다 먼저 갱신한다. 문서와 보고는 한국어로 쓴다.
- 기존 계층 규칙을 유지한다. 맵 생성기는 backend의 순수 Python 모듈로 두고 sqlalchemy·fastapi를 import하지 않는다. service는 port·repository ABC로만 쓴다.
- frontend 코드는 바꾸지 않는다. 다만 응답 형식은 frontend DTO(`frontend/src/render/map/types.ts`, `citizens/types.ts`)의 snake_case 필드와 맞춘다.
- 타일 스키마는 docs 04-map-rendering의 v1을 따른다(terrain GRASS 0, WATER 1, SAND 2; road = `(class<<5)|conn`, class LOCAL 0·ARTERIAL 1, conn N1·E2·S4·W8, 고립 16, 0 = 도로 없음; 타일 인덱스 `local_y*32+local_x`).

### 인터뷰 결정
- **R1 맵 책임:** backend 맵 생성기가 세계를 만들 때 지형과 도로를 생성해 `map_chunks`에 저장한다. 세계 생성과 같은 트랜잭션이다. 서버가 맵의 최종 권한을 가진다. 연결성 검증에 실패하면 세계 생성을 409 `WORLD_GENERATION_FAILED`로 거절하고 아무것도 저장하지 않는다. phase-06의 "도로·MapChunk 생성은 frontend 담당"은 docs에서 이 결정으로 바꾼다.
- **R2 맵 크기:** 512×512(청크 16×16 = 256개)다. 엔진 건물은 좌표를 그대로 둔다(0~127 영역). 나머지 영역은 건물 없는 지형과 도로로 채운다. 좌표 변환은 없다.
- **R3 이동 정보:** MOVING인 시민마다 가장 최근의 `citizen.movement.started` 이벤트(이미 DB id로 바뀐 payload)로 `movement { from_building_id, to_building_id, start_tick, arrival_tick }`을 채운다. 이동 중이 아니면 `null`이다. 다음 Phase의 SSE 이벤트와 형식이 같다.
- **R4 일관성:** `GET /worlds/{id}/view`는 한 트랜잭션(REPEATABLE READ)에서 World 상태, 현재 정책, runner, 시민 전체(이동 정보 포함), 건물 전체, 기업 요약을 읽고 `as_of_tick`, `event_cursor`를 함께 돌려준다. 목록·상세 API 응답에도 같은 트랜잭션에서 읽은 `as_of_tick`, `event_cursor`를 넣는다.
- **R5 성능 기준:** 로컬 PG, 시민 100명, Runner x16 실행 중에 각 API를 50회 호출해 p95를 잰다. 기준은 `/view` ≤ 200ms, 맵 전체 청크 256개 ≤ 500ms, 목록·상세 ≤ 100ms다. 기준을 넘으면 보고만 하고 테스트를 실패시키지 않는다. 정확성 테스트는 반드시 통과해야 한다.

## 승인 시 확인할 가정
1. **맵 생성 알고리즘:** `app/maps/generator.py`가 담당하고, 같은 (world seed, 건물 목록)이면 항상 같은 맵이 나온다.
   - 엔진 영역(0~127)과 건물 주변 여유 2칸에는 물·모래를 두지 않는다. 그 밖에는 호수와 모래를 시드 기반으로 둘 수 있다.
   - 도로:
     - 간선 격자를 64칸 간격으로 깐다(물 위 제외, 건물 칸 회피).
     - 엔진 영역 안에는 로컬 도로를 깐다.
     - 각 건물 둘레의 빈칸에서 가장 가까운 도로까지 BFS로 연결 도로를 낸다. 건물 칸과 물은 피한다.
     - conn 비트는 전역으로 계산한다.
   - 검증:
     - 모든 건물이 둘레에 도로 타일을 하나 이상 가진다(frontend 입구 규칙: 위→오른쪽→아래→왼쪽 순으로 처음 나오는 도로 타일).
     - 모든 입구가 하나의 연결 요소에 있다.
     - 도로·물이 건물 칸과 겹치지 않는다.
   - 빈칸이 없어 둘레가 막힌 건물이 있으면 검증에 실패하고 409를 돌려준다.
2. **기존 세계:** 이번 Phase 전에 만든 세계는 맵이 없다. backfill 명령(`uv run python -m app.maps.backfill`)으로 채운다. 세계 생성 경로에만 자동 생성을 붙인다.
3. **맵 메타:** `GET /worlds/{id}/map` → `{width:512, height:512, chunk_size:32, chunks_x:16, chunks_y:16, tile_schema_version:1, engine_area:{x:0, y:0, width:128, height:128}}`.
4. **청크 API:** 기존 `GET /worlds/{id}/chunks`(청크 범위 질의)를 유지하고 응답 형식은 frontend ChunkDTO와 같다. 범위를 생략하면 전체를 돌려준다.
5. **건물 API:** `GET /worlds/{id}/buildings`(선택: 타일 범위 `x_min,x_max,y_min,y_max`로 겹치는 건물)와 `GET /worlds/{id}/buildings/{building_id}`. 필드는 frontend BuildingDTO와 같다(`id, world_id, type, tile_x, tile_y, width, height, capacity, occupied_capacity, status`). 상세에는 그 건물에 있는 기업 id와 거주 가구 수를 더한다.
6. **시민 API:**
   - `GET /worlds/{id}/citizens?limit&offset&employment_status&current_activity&building_id`: 기본 limit 100, 최대 500, id 순 정렬. 응답은 `{items, total, limit, offset, as_of_tick, event_cursor}`.
   - 상세 `GET /citizens/{cid}`는 기존 필드에 다음을 더한다.
     - `movement`
     - `employment {company_id, salary, hired_tick}` 또는 null
     - `cash_balance`
     - `as_of_tick`, `event_cursor`
7. **기업 API:**
   - 목록 `GET /worlds/{id}/companies?limit&offset&status&industry`
   - 상세에 `cash_balance`와 고용 요약을 더한다.
   - `GET /companies/{cid}/employees`(페이지네이션)
   - 매출 구분 4항목은 저장된 테이블이 없어 이번에는 제외한다.
8. **통계 API:** `GET /worlds/{id}/summary` → 다음 항목을 한 트랜잭션에서 계산한다.
   - 인구, 취업자 수, 실업률, 운영 중·DISTRESSED·파산 기업 수
   - 정부 국고 잔액, 도시 내부 자금(시민 + 기업 + 정부 잔액)
   - 최신 월간 지표 12종(`tick`, 값)
   - 지표 이력은 기존 `GET /metrics`를 쓴다.
9. **수동 `/ticks`:** PAUSED에서만 허용하고, 그 밖의 상태는 409 `WORLD_NOT_PAUSED`다(앞서 결정한 정책을 구현). 상태 전이표상 INITIALIZED → PAUSED가 없으므로, 수동 진행은 RUNNING을 거쳐 PAUSED에서 한다. 기존 테스트도 이 흐름으로 고친다. `expected_tick` 계약은 유지한다.
10. **응답 형식 변경:** 시민·기업 상세가 필드를 더하는 호환성 변경이다(frontend는 아직 API를 쓰지 않는다).
11. **REPEATABLE READ:** repository 구현에서 `/view`·목록·통계용 읽기 세션을 REPEATABLE READ로 연다(서비스는 ABC만 씀). 실행 중 조회는 Runner 쓰기를 막지 않는다(MVCC).

## 제외 범위
- SSE, frontend 수정(맵 크기 상수, API 연동), 엔진 수정, 스키마 변경, 매출 구분 저장, 경로·이동 시간을 도로 기준으로 바꾸는 일, 인증, 커서 기반 페이지네이션.

## 완료 기준
- [ ] AC1: 코드보다 docs를 먼저 갱신한다.
  - `04-map-rendering.md`: 맵 책임 = backend 생성기, 512 맵과 엔진 영역, 생성 규칙과 검증
  - `phase-06` Non-Goal 문구 정정
  - `07-rest-sse.md`: 새 엔드포인트와 응답 형식, `as_of_tick`·`event_cursor`, `/ticks` PAUSED 정책
  - `06-database.md`: map_chunks 생성 시점, REPEATABLE READ 조회
  - `02-backend-convention.md`: `app/maps` 계층 규칙
- [ ] AC2: 맵 결정성. 같은 시드로 맵을 두 번 생성하면 타일 배열이 완전히 같고, 다른 시드면 다르다(단위 테스트, DB 없음).
- [ ] AC3: 맵 정합성. 시드 20개 이상으로 다음이 모두 성립한다.
  - 엔진 건물 21개 모두가 둘레 도로 타일(frontend 입구 규칙)을 가진다.
  - 모든 입구가 하나의 도로 연결 요소에 있다.
  - 건물 칸에는 도로·물이 없다.
  - 모든 도로 conn 비트가 이웃과 맞는다.
  - 모든 값이 타일 스키마 v1 범위 안에 있다.
- [ ] AC4: 저장. `POST /worlds`가 청크 256개를 저장한다(CHECK 통과, 길이 1024). 맵 검증이 실패하면 409이고 아무것도 저장되지 않는다(주입으로 검증). backfill이 맵 없는 세계를 채우고, 다시 실행해도 결과가 바뀌지 않는다.
- [ ] AC5: `GET /map`, `/chunks`(전체·범위), `/buildings`(전체·타일 범위, 건물이 청크 경계에 걸쳐도 포함), 건물 상세가 계약대로 응답한다. 응답 필드 집합이 frontend DTO 키 목록과 같다(테스트로 대조).
- [ ] AC6: `/view` 일관성. Runner가 실행 중일 때 `/view`를 반복 호출하면 다음이 성립한다.
  - 응답 안의 `as_of_tick`과 시민 `arrival_tick`·`movement.start_tick`이 서로 모순되지 않는다.
  - `event_cursor`는 그 시점 `max(sequence)`와 같다.
  - 같은 `event_cursor`를 받은 두 응답의 데이터가 같다.
  - 동시 50회 호출에서 500이 없다.
- [ ] AC7: 수동 `/ticks`는 RUNNING·INITIALIZED·FAILED·ARCHIVED에서 409 `WORLD_NOT_PAUSED`(FAILED·ARCHIVED는 기존 코드 유지 여부를 docs에 명시)이고, PAUSED에서는 기존처럼 동작한다. 응답 유실 후 재시도해도 Tick이 추가로 진행되지 않는 테스트가 계속 통과한다.
- [ ] AC8: 시민 목록·상세. 페이지 경계(limit, offset, 마지막 페이지, total)와 필터가 동작한다. MOVING 시민의 `movement`가 최신 이동 이벤트와 같고, 도착한 시민은 `null`이다. `employment`, `cash_balance`가 DB와 같다.
- [ ] AC9: 기업 목록·상세·직원 목록이 동작하고 페이지네이션이 맞다. 파산 기업의 고용은 비어 있다.
- [ ] AC10: `/summary` 값이 DB에서 직접 센 값과 같다. 지표는 최신 월간 값이다.
- [ ] AC11: PAUSED 상태 조회에서 tick이 변하지 않고, 두 번 호출한 응답이 같다. 동시 접근(Runner 실행 중 여러 스레드 조회)에서 500이 없다.
- [ ] AC12: 성능 p95(로컬, Runner x16 실행 중, 50회)를 보고한다. 기준은 `/view` ≤ 200ms, 청크 256개 ≤ 500ms, 목록·상세 ≤ 100ms이고, 넘어도 실패로 처리하지 않는다. 기존 169개 테스트와 soak 테스트가 모두 통과한다.

## 드러난 가정과 해소
| 가정 | 문제 제기 | 결정 |
|---|---|---|
| 엔진·frontend 생성기를 그대로 잇는다 | 엔진은 도로가 없고, frontend는 입구가 도로에 연결돼야 한다 | backend 생성기가 엔진 좌표 주위에 도로를 만든다 (R1) |
| 맵 크기는 엔진을 따른다 | frontend가 512를 하드코딩하고 있다 | 512 맵 안에 엔진 영역을 그대로 둔다 (R2) |
| 출발 정보는 SSE로만 받는다 | 새로고침하면 이동 중인 시민을 그릴 수 없다 | 최신 이동 이벤트에서 채운다 (R3) |
| 엔드포인트별 조회로 충분하다 | 커밋 사이에 읽으면 커서와 상태가 어긋난다 | 단일 트랜잭션 `/view` + 응답 기준 커서 (R4, 반대 관점) |
| 성능은 측정만 한다 | 합격 기준이 없다 | p95 기준, 넘으면 보고 (R5) |

## 기술 맥락
- 엔진: `map_size=128`, 건물 21개, 모두 2×2(`generator.py:28`), 겹침만 피하는 배치. 도로·지형·입구는 고려하지 않는다. 이동 시간은 앵커 간 맨해튼 거리 ÷ 40이다(도로 무관, 표시는 progress 비율이라 영향 없음).
- frontend Mock(`frontend/src/render/map/generator.ts`):
  - 512, CHUNK 32, mulberry32 시드
  - 간선 64칸·로컬 16칸 도로
  - 입구는 둘레를 위→오른쪽→아래→왼쪽 순으로 훑어 처음 나오는 도로 타일
  - 최대 도로 연결 요소에 있는 건물만 남긴다
- frontend DTO:
  - Chunk: `chunk_x, chunk_y, chunk_size, terrain_tiles, road_tiles, schema_version, revision`
  - Building: `id, world_id, type, tile_x, tile_y, width, height, capacity, occupied_capacity, status`
  - Citizen = backend CitizenRead
  - 이동 이벤트: `citizen_id, from_building_id, to_building_id, start_tick, arrival_tick`
- backend:
  - REST 10개(시민·기업은 단건 조회만, 건물 API 없음)
  - `GET /chunks`는 있지만 데이터가 없다
  - `map_chunks` CHECK: chunk_size 32, 배열 길이 1024, UNIQUE(world_id, chunk_x, chunk_y)

## 핵심 개념(Ontology)
| 개념 | 유형 | 필드 | 관계 |
|---|---|---|---|
| MapGenerator | 핵심 | seed, buildings, size 512 | MapChunk 256개 생성 |
| MapChunk | 핵심 | chunk_x, chunk_y, terrain_tiles, road_tiles | World 소속 |
| Building | 핵심 | tile_x, tile_y, width, height, type | 엔진 좌표 고정 |
| Entrance | 보조 | 둘레 첫 도로 타일 | 도로 연결 요소 |
| WorldView | 핵심 | as_of_tick, event_cursor, citizens, buildings | 단일 트랜잭션 |
| CitizenMovement | 보조 | from/to_building_id, start/arrival_tick | 최신 이동 이벤트 |
| CitySummary | 보조 | 인구, 고용, 기업 수, 국고, 지표 | 대시보드 |

## 개념 수렴
| 라운드 | 개념 수 | 신규 | 변경 | 유지 | 안정도 |
|---|---|---|---|---|---|
| 1 | 4 | 4 | - | - | - |
| 2 | 5 | 1 (Entrance) | 0 | 4 | 80% |
| 3 | 6 | 1 (CitizenMovement) | 0 | 5 | 83% |
| 4 | 7 | 1 (WorldView) | 0 | 6 | 86% |
| 5 | 7 | 0 | 0 | 7 | 100% |

## 인터뷰 기록
<details><summary>5라운드</summary>

- R0 범위(맵·건물, World 조회 계약, 시민·기업, 통계, 검증, docs) → 맞음
- R1 도로·MapChunk 책임 → backend 맵 생성기 + DB 저장 (50%)
- R2 맵 크기 → 512 맵 안에 엔진 영역 배치 (42%)
- R3 이동 정보 출처 → 최신 이동 이벤트 (35%)
- R4 (반대 관점) 조회 일관성 → 단일 트랜잭션 `/view` + 응답 기준 커서 (27%)
- R5 성능 기준 → p95 기준 + 표본 측정, 넘으면 보고 (19%)
</details>
