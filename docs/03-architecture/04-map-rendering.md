# 맵 및 렌더링 설계

> 원본: README §8

## 8.1 그래픽 방식

Three.js 3D 씬을 고정 각도 OrthographicCamera(yaw 45°, pitch ≈35.26°)로 보는 Isometric 시점을 사용한다.

논리적인 타일 좌표와 3D 월드 좌표를 분리한다.

- 타일 좌표: 건물 배치, 도로 연결성, 경로 계산
- 3D 월드 좌표: 렌더링, 마우스 선택(레이캐스트), 이동 애니메이션. 1 타일 = 1 월드 단위, XZ 평면이 지면, Y가 위쪽이다.

카메라 조작: 드래그 이동(pan), 휠 줌(커서 기준), 회전 없음, 이동 범위 제한 (drei MapControls).

## 8.2 Chunk 기반 맵

기본 Chunk 크기는 32 × 32 타일이다.

카메라에 보이는 Chunk와 주변 여유 영역만 로드하고 렌더링한다.

지도 데이터는 시뮬레이션 전체에서 유지되지만, 렌더링 리소스는 카메라 위치에 따라 생성 및 해제할 수 있다.

### Chunk 저장 (map_chunks)

- World별로 (chunk_x, chunk_y)가 고유하다. 기본 맵 512 × 512 타일 = 32 × 32 타일 Chunk 256개.
- terrain_tiles, road_tiles는 JSONB 1차원 배열이며 각각 정확히 1,024개(32 × 32) 타일 ID를 담는다.
- 타일 인덱스: `index = local_y * 32 + local_x` (Python과 TypeScript가 같은 규칙을 쓴다).
- schema_version은 타일 데이터 형식 버전, revision은 Chunk 변경 버전이다.
- 건물은 buildings에서 관리하며 map_chunks에 FK로 묶지 않는다. 건물 좌표와 점유 범위로 겹치는 Chunk를 조회한다. (범위 조회 API는 Chunk와 겹치는 건물을 모두 돌려주며, 렌더링 소유권은 아래 "건물 렌더링 소유권"을 따른다.)
- 상세 스키마: [데이터 저장 설계](06-database.md)

### 타일 스키마 v1 (schema_version = 1)

- terrain_tiles 값: 0 GRASS, 1 WATER, 2 SAND.
- road_tiles 값: `(class << 5) | connection`, 0은 도로 없음.
  - connection 1~15는 인접 도로 비트마스크: N(−y)=1, E(+x)=2, S(+y)=4, W(−x)=8. 16은 고립(연결 없음).
  - class 0 = LOCAL(값 1~16), class 1 = ARTERIAL(값 33~48).
  - connection은 도로 class와 무관하게, Chunk 경계를 넘어서도 계산한다.
- 알 수 없는 값은 지형은 GRASS, 도로는 없음으로 렌더링하고 경고를 한 번만 남긴다.

### 건물 렌더링 소유권

- 범위 조회는 Chunk와 겹치는 건물을 모두 반환하므로 같은 건물이 여러 Chunk 응답에 나올 수 있다.
- 렌더링 소유 Chunk는 건물 앵커 `(tile_x, tile_y)`가 속한 Chunk 하나뿐이다. 다른 Chunk 응답에 나온 같은 건물은 그리지 않는다.
- 건물 id로 중복을 제거한다.

## 8.3 렌더링 계층

- Terrain: 지형
- Road: 도로와 보도
- World Entities: 건물, 시민, 차량
- Overlay: 선택 표시, 이동 경로 및 효과
- React UI: 대시보드와 상세 패널

깊이는 3D 깊이 버퍼(depth buffer)가 처리하므로 수동 깊이 정렬은 쓰지 않는다.

### 프론트엔드 Chunk 렌더링 구성

- ChunkManager: Chunk 로드 상태와 활성화/해제를 관리한다. 활성화 큐는 프레임당 최대 8개이며 보이는 Chunk를 먼저 처리한다. 비활성화되면 그 Chunk가 만든 지면 geometry와 InstancedMesh를 dispose한다(공유 material·박스 geometry는 ChunkManager 해제 시 한 번만 dispose).
- VisibilityManager: 카메라 frustum과 1 Chunk 링으로 필요한 Chunk를 구한다. 보수적으로 판정한다(놓치는 Chunk가 없도록 넓게).
- ChunkRenderer: Chunk당 지형·도로·표시를 하나의 병합 BufferGeometry(vertex color)로 만든다.
- BuildingRenderer / InstanceManager: Chunk당 InstancedMesh로 건물을 그린다. 대안(fallback)은 레이어별 InstancedMesh다.
- 카메라 줌: 기본 20, MIN_ZOOM 12, MAX_ZOOM 60.
- 타입: 프론트엔드 도메인 타입은 camelCase이고, DTO 매퍼가 백엔드 snake_case 응답을 변환한다. 건물 DTO에는 created_at/updated_at을 포함하지 않는다. 건물 status 값은 TBD이다.

## 8.4 시민 이동 렌더링

Python 엔진은 이동 목적과 논리적 도착 시점을 결정한다.

프론트엔드는 이동 이벤트를 받아 경로를 찾고 애니메이션을 재생한다.

렌더링 프레임 속도와 시뮬레이션 Tick은 서로 독립적으로 동작한다.

### 논리 상태와 렌더 상태 분리

- 논리 상태(`Citizen`, `MovementEvent`)에는 좌표를 두지 않는다. 좌표는 (이동 이벤트, 현재 Tick, 경로)에서 프레임마다 계산한다.
- 프레임마다 바뀌는 위치와 방향은 React state가 아니라 typed array(렌더 상태)에 둔다.
- 렌더 계층은 지난 이동을 재생하지 않는다. 화면 복귀, 배속, 숨김 탭 이후에도 현재 Tick만 조회한다. 이미 끝난 이동은 도착(idle) 상태로 표시하고, 진행 중인 이동만 보간한다.

### 시민 InstancedMesh

- 시민은 공유 geometry 1개와 material 1개를 쓰는 InstancedMesh 1개로 그린다.
- instance 수(`count`)는 Chunk visible set 안에 있는 시민 수다. 화면 밖 시민은 instance 버퍼에 올리지 않는다.
- 렌더 비용은 보이는 시민 수에 비례하고, 시뮬레이션 비용은 엔진이 소유한다. 두 비용은 독립적으로 확장한다.

### 보도 표현

- 보도는 도로 타일 위에서 이동 방향 기준 오른쪽으로 옮긴 시각적 offset이다. 맵 스키마(v1)는 바꾸지 않는다.

### 경로 스케줄러(PathFinder)

경로 탐색은 렌더 전용이며 Chunk 로딩과 별개의 작업 예산으로 돈다.

- 화면에 보이는(visible Chunk 안의) 이동 중 시민만 경로를 요청한다.
- 같은 (출발 건물, 도착 건물) 경로는 캐시를 재사용한다.
- 카메라 이동으로 대상에서 빠지면 대기 중 요청을 취소한다.
- 프레임당 처리량을 시간 예산(1 ms) 또는 건수 상수로 제한한다.
- 경로가 준비되기 전에는 출발·도착 입구 사이 직선 보간으로 대략적인 위치를 표시한다(시간 진행은 동일). 경로가 준비되면 다음 프레임부터 경로 위치로 전환한다. 짧은 순간 건물 위를 지날 수 있다.
- 경로 탐색이 실측 병목이면 Web Worker로 옮기는 것을 후속 작업으로 둔다(Phase 3 범위 아님).

### 도로망 접근성

모든 건물 입구는 주 도로망 연결 요소에 연결되어야 한다. 맵 생성 단계에서 검증하고, 연결되지 않은 건물은 배치하지 않는다.

### 도착 Tick

도착 Tick은 엔진이 정한다([03-citizen §4.4](../02-domain/03-citizen.md)). 프론트엔드는 출발·도착 Tick만 받아 표현한다.
