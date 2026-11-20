## 핸드오프: team-plan → team-exec (rest-api)

- **결정**: 스펙 `backend/.omc/specs/deep-interview-rest-api.md`(가정 1–11 승인). 순서: W1 docs → [W2 맵 생성·저장 ∥ W3 조회 API·/ticks 정책] → W4 통합·성능 테스트.
- **거절**: 엔진 도로 생성, frontend 생성, 128 맵, 좌표 4배 확대, Snapshot에서 이동 정보, 엔드포인트별 무일관 조회.
- **위험**: 2×2 건물이 붙어 둘레가 막히는 시드, 512 맵 conn 비트 전역 계산, REPEATABLE READ 세션 설정, 기존 테스트의 /ticks 호출(PAUSED 필요).
- **남은 것**: SSE, frontend 연동(맵 크기·API).

# 공유 계약

## 엔진 port 확장 — W2
- `app/simulation/interfaces.py`에 `BuildingFootprint(engine_id: str, tile_x: int, tile_y: int, width: int, height: int)` 추가, `EngineBatch.buildings: list[BuildingFootprint] = []`(generate에서만 채움). adapter가 엔진 Building에서 채운다.

## 맵 생성기 — W2 (`app/maps/`, sqlalchemy·fastapi·simulation_engine import 금지)
- `app/maps/tiles.py`: 상수 `MAP_SIZE=512, CHUNK_SIZE=32, CHUNKS_PER_SIDE=16, TILE_SCHEMA_VERSION=1, ENGINE_AREA=(0,0,128,128)`, Terrain GRASS=0 WATER=1 SAND=2, road 인코딩 `(cls<<5)|conn`(LOCAL=0, ARTERIAL=1, N=1 E=2 S=4 W=8, 고립=16).
- `app/maps/generator.py`: `generate_map(seed: int, buildings: list[BuildingFootprint]) -> GeneratedMap`; `GeneratedMap.terrain`, `.roads` (len 512*512, index y*512+x), `.chunks() -> list[ChunkData(chunk_x, chunk_y, terrain_tiles[1024], road_tiles[1024])]`(타일 인덱스 local_y*32+local_x). 결정적(시드로 만든 `random.Random`, 전역 random·hash 금지).
- `app/maps/validate.py`: `validate_map(map, buildings) -> None`, 실패 시 `MapValidationError(reason)`. 규칙: 건물 칸에 도로·물 없음, 모든 건물이 frontend 입구 규칙(둘레 위→오른쪽→아래→왼쪽 첫 도로 타일)으로 입구를 가짐, 모든 입구가 하나의 도로 연결 요소, conn 비트가 이웃과 일치, 값 범위.
- 생성 규칙: 엔진 영역 및 건물 둘레 2칸 내 물·모래 금지; 간선 격자 64칸 간격(건물 칸 회피, 물 위 제외); 엔진 영역 로컬 도로; 각 건물 둘레 빈칸→최근접 도로 BFS 연결(건물·물 회피); 마지막에 conn 전역 계산.
- `app/maps/backfill.py`(`python -m app.maps.backfill`): 맵 없는 세계마다 최신 Snapshot의 엔진 건물 대신 **DB buildings 행**(tile_x, tile_y, width, height)으로 생성해 저장. 멱등(있으면 건너뜀). 맵 시드 = worlds.seed.

## 저장 — W2
- repository ABC `MapChunkRepository.save_all(world_id, chunks: list[ChunkData]) -> None`(+ SQL insert, + fake), `MapChunkRepository.count(world_id) -> int`.
- `WorldService.create_world`: engine.generate → `generate_map(seed, batch.buildings)` → validate → (실패 시 `ConflictError("WORLD_GENERATION_FAILED")`, 저장 전) → worlds.add → save_generation → chunks.save_all → commit. 맵 생성기는 `MapGeneratorPort`로 주입하지 않고 순수 함수 직접 호출 허용(app.maps는 순수 모듈).

## 조회 API — W3 (`app/api/v1/endpoints/worlds.py` 한 줄 핸들러, `CityQueryUseCase` 확장)
- 공통: 목록 응답 `Page[T] = {items, total, limit, offset, as_of_tick, event_cursor}`; limit 기본 100, 최대 500, offset ≥ 0; 정렬 id.
- `GET /worlds/{id}/map` → `MapMetaRead{width, height, chunk_size, chunks_x, chunks_y, tile_schema_version, engine_area{x,y,width,height}}` (W3가 app.maps.tiles 상수 import; W2가 먼저 tiles.py를 만든다 — 없으면 대기).
- `GET /worlds/{id}/chunks`(기존 유지, 범위 생략 시 전체).
- `GET /worlds/{id}/buildings?x_min&x_max&y_min&y_max`(타일 범위와 겹치는 건물) → `list[BuildingRead]`; `BuildingRead` 키 = frontend BuildingDTO: `id, world_id, type, tile_x, tile_y, width, height, capacity, occupied_capacity, status`. `GET /worlds/{id}/buildings/{bid}` → `BuildingDetailRead`(+ `company_ids: list`, `household_count: int`).
- `GET /worlds/{id}/citizens?limit&offset&employment_status&current_activity&building_id` → `Page[CitizenRead]`; `CitizenRead`에 `movement: MovementRead|None`(`from_building_id, to_building_id, start_tick, arrival_tick`), `employment: EmploymentRead|None`(`company_id, salary, hired_tick`), `cash_balance` 추가. 상세 `CitizenDetailRead` = CitizenRead + `as_of_tick, event_cursor`.
- `GET /worlds/{id}/companies?limit&offset&status&industry` → `Page[CompanyRead]`; 상세에 `as_of_tick, event_cursor`; `GET /worlds/{id}/companies/{cid}/employees?limit&offset` → `Page[CitizenRead]`.
- `GET /worlds/{id}/summary` → `CitySummaryRead{as_of_tick, event_cursor, population, employed, unemployment_rate, companies{active, distressed, bankrupt}, government_treasury, city_internal_money, latest_metrics: list[MetricRead]}`.
- `GET /worlds/{id}/view` → `WorldViewRead{as_of_tick, event_cursor, world: WorldStateRead, citizens: list[CitizenRead], buildings: list[BuildingRead], companies: list[CompanyRead]}`.
- 이동 정보: MOVING 시민만, 시민별 최신 `citizen.movement.started` 이벤트(payload의 citizen_id로 매칭). `current_activity == "MOVING"` 기준.
- REPEATABLE READ: SQL UoW/세션 생성 시 읽기 전용 경로는 `session.connection(execution_options={"isolation_level": "REPEATABLE READ"})`로 시작(트랜잭션 첫 문장 전에). service는 `uow.begin_consistent_read()` 같은 ABC 메서드만 호출.
- 수동 `/ticks`: `advance_ticks`는 status != PAUSED면 `InvalidStateError("WORLD_NOT_PAUSED")`(FAILED·ARCHIVED도 WORLD_NOT_PAUSED로 통일). `advance_running`은 변경 없음.

## lead 보충 결정 (docs 반영 완료)
- 건물 상세 404 코드 `BUILDING_NOT_FOUND`. 시민 `building_id` 필터 = `current_building_id == building_id`.
- 기업 상세 고용 요약 = `active_employees`(ACTIVE 고용 수). `/view.companies` = 전체 `CompanyRead`(cash_balance 포함).
- 건물 연결 도로 class = LOCAL. limit 범위 밖(0, 501 등)과 offset < 0은 422 `VALIDATION_ERROR`.
- `/chunks`, `/buildings`는 단순 배열(정적 데이터, 커서 없음).
