# World

> 원본: README §3.1, §3.6, §3.9, §3.10

### 3.1 World — 도시 세계

시뮬레이션의 최상위 Aggregate Root.

주요 속성:

- id: 세계 식별자
- name: 도시 이름
- seed: 최초 생성 난수 시드
- currentTick: 현재 시뮬레이션 시간
- speed: 시간 진행 배율
- status: INITIALIZED, RUNNING, PAUSED, FAILED, ARCHIVED
- engineVersion: 시뮬레이션 규칙 버전
- version: 동시성 제어 버전

> 코드 기준 갱신: 엔진 World(`simulation_engine/src/simulation_engine/entities/world.py:17-24`)의 필드는 id, name, seed, current_tick, speed(기본 1), status(기본 INITIALIZED), engine_version이다. worldId와 낙관적 락 version은 DB 전용이라 엔진에 두지 않는다 (코드 기준).

World는 시민, 기업, 정책, 지도, 경제 상태 및 사건의 소유 범위를 정의한다.

서로 다른 World는 독립적인 시뮬레이션 상태를 유지한다.

### 3.6 Building — 건물

지도 위에 존재하는 공간 객체.

주요 속성:

- id, worldId
- type: RESIDENTIAL, COMMERCIAL, OFFICE, PUBLIC
- tileX, tileY
- width, height
- capacity
- occupiedCapacity
- status

건물은 화면 표현에만 사용되는 장식이 아니라 시민의 주거와 기업의 활동 장소를 나타낸다.

건물의 위치와 도로 연결성은 시민의 이동 시간에 영향을 준다.

### 3.9 WorldEvent — 세계 이벤트

도시에서 발생한 중요한 상태 변경을 기록한다.

주요 속성:

- id, worldId
- sequence
- tick
- type
- payload
- schemaVersion
- createdAt

이벤트는 사용자에게 보여줄 타임라인과 SSE 동기화에 활용한다.

> 코드 기준 갱신: 엔진 WorldEvent(`simulation_engine/src/simulation_engine/events/models.py:9-17`)는 id, sequence, tick, type, payload, schema_version을 가진다. worldId와 createdAt은 DB 전용이라 엔진에 없다 (코드 기준).

일반적인 데이터 변경과 이벤트 저장은 같은 트랜잭션에서 처리한다.

### 3.10 WorldSnapshot — 세계 스냅샷

특정 Tick의 세계 상태를 저장한다.

주요 속성:

- worldId
- tick
- lastEventSequence
- engineVersion
- stateData
- createdAt

스냅샷은 서버 복구, 상태 조회 및 시뮬레이션 재현에 활용한다.

> 코드 기준 갱신: 엔진 WorldSnapshot(`simulation_engine/src/simulation_engine/world/snapshot.py:9-16`)은 id, tick, last_event_sequence, engine_version, state_data를 가진다. worldId와 createdAt은 DB 전용이다 (코드 기준).

### 3.11 MapChunk — 맵 청크 (코드 기준 추가)

맵을 32 x 32 타일 단위로 나눈 청크 레코드다 (`simulation_engine/src/simulation_engine/world/map_chunk.py:6-20`).

- id, chunkX, chunkY, chunkSize (기본 32)
- terrainTiles, roadTiles: 길이 chunkSize²의 정수 배열. 타일 인덱스는 `localY * 32 + localX`
- schemaVersion, revision

