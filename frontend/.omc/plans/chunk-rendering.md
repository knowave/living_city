# 계획: Chunk 기반 512×512 도시 렌더링 (Mock 데이터, REST 호환 모델)

- 입력 스펙: `frontend/.omc/specs/deep-interview-chunk-rendering.md` (AC 1-12가 수용 기준의 원본)
- 모드: RALPLAN SHORT, 개정 2판(Architect APPROVE_WITH_CHANGES, Critic REVISE 반영)
- 상태: **approved (2026-11-18, 사용자 승인: Q1·Q2·Q3·Q4 모두 권장 답)** (§8의 사용자 게이트 Q1-Q4 답변을 T0 전에 받는다)

---

## 1. 요구사항 요약

- 64×64 하드코딩 프로토타입을 512×512 타일 맵(32×32 청크 × 256개)으로 교체한다.
- 데이터는 시드 고정 Mock `MapGenerator`가 만든다. 출력은 백엔드 `ChunkRead`(`backend/app/schemas/city.py:9-20`)와 `Building` 모델(`backend/app/models/building.py:17-29`, `id`는 `backend/app/db/base.py:15`) 필드와 1:1(snake_case DTO)이다. 앱은 항상 DTO → mapper → camelCase 도메인을 거친다. 나중에 `GET /worlds/{id}/chunks` 응답으로 generator만 교체한다.
- 타일 스키마 v1: terrain 0=GRASS, 1=WATER, 2=SAND. road `value = (class << 5) | connection`, 0=도로 없음, connection N=1 E=2 S=4 W=8, 16=고립, class 0=LOCAL, 1=ARTERIAL. 연결 비트는 등급 무관, 청크 경계 포함 이웃 기준. 모르는 값은 GRASS/도로 없음 + 경고 1회.
- 카메라 뷰 + 1칸 링 청크만 활성화하고, 비활성화 시 GPU 자원을 해제한다. 공유 material/geometry는 재사용한다.
- 클릭 선택 유지(인스턴스 → 건물 id, 하이라이트, 빈 곳 클릭 해제, 드래그는 클릭 아님).
- 디버그 HUD: FPS/Avg, 활성 청크/256(+대기), draw calls, geometries, textures.
- 문서 먼저. 백엔드 코드 변경 없음. 새 의존성 없음. fetch/REST/SSE 없음.

---

## 2. RALPLAN-DR 요약

### 원칙
1. **REST 교체 가능성**: DTO 모양은 백엔드와 같고, 렌더 코드는 도메인 타입만 본다.
2. **생명주기 단일 소유**: 청크 자원을 만드는 곳과 해제하는 곳이 같은 모듈이다.
3. **순수 함수 우선**: 생성기, mapper, 타일 인덱스, 지면 버퍼, 가시성 판정은 WebGL 없이 Vitest(env node)로 테스트한다.
4. **최소 범위**: 스펙의 비목표(LOD, 텍스처, 경로, 곡선 도로)는 손대지 않는다. 기존 `tileRectToWorld`, `createFpsTracker`, MapControls clamp를 재사용한다.

### 결정 동인 (상위 3)
1. draw call이 건물 수와 무관하고 활성 청크 수에 비례하며 작아야 한다(AC 10).
2. 빈번한 카메라 이동에서 누수가 없고 프레임이 끊기지 않아야 한다(AC 7-8).
3. 인스턴스 클릭 역매핑(AC 11)과 경계 걸친 건물 1회 렌더(AC 9).

### 옵션 A — 렌더링 자원 구성

| 옵션 | 내용 | 장점 | 단점 |
|---|---|---|---|
| **A1 (채택)** 청크별 병합 지면 + 청크별 건물 InstancedMesh | 청크마다 terrain·road·방향표시를 vertex color 병합 `BufferGeometry` 1개로, 건물은 공유 unit box·공유 material의 `InstancedMesh` 1개로 그린다(건물 0개 청크는 생략) | 청크당 draw call ≤ 2. 지면 레이어 3개를 한 번에 배치한다. 지면은 클릭 대상이 아니라 병합해도 손해가 없다. | 지면 버퍼 생성 비용(청크당 최대 약 4.1만 정점, Uint16 범위 안) |
| A2 전역 InstancedMesh 풀 | 레이어마다 고정 용량 InstancedMesh 1개를 두고 슬롯을 빌리고 반납 | draw call 상수(~4), 할당/해제 없음 | 슬롯 할당기·단편화 처리 필요. 전체 bounding sphere라 프러스텀 컬링 무력화. 스펙의 "activate 때 만들고 deactivate 때 해제"와 어긋남 |
| A3 청크별 레이어별 InstancedMesh (**문서화된 대체안**) | terrain 1024 인스턴스, road, 표시, 건물 각각 InstancedMesh | 스펙 문구("반복 terrain에 InstancedMesh")와 일치 | 청크당 draw call 4개(A1의 2배) |
| A4 청크별 전체 병합(건물 포함) | 청크당 메시 1개 | draw call 최소 | 건물 클릭 역매핑과 하이라이트(정점 색 재작성)가 복잡 |

선택 근거: A1은 동인 1에서 가장 낫다(청크당 2 vs A3의 4, 지면 일괄 처리). A2는 복잡도가 크고 컬링을 잃는다(draw call이 실제 병목으로 측정되면 후속 검토). A4는 동인 3을 깬다. A3은 Q3에서 사용자가 스펙 문구를 고수할 때의 대체안이다. 바뀌는 곳은 `ChunkManager` 내부 지면 생성뿐이고 공개 인터페이스는 같다.

### 옵션 B — 생명주기 소유

| 옵션 | 장점 | 단점 |
|---|---|---|
| **B1 (채택)** 순수 TS `ChunkManager`가 THREE 객체를 만들고 `dispose()`한다. React는 `<ChunkLayer>` 하나가 group ref, 매 프레임 `update()`, 클릭만 맡는다 | 생성·해제·대기열이 한 파일에 있다. node 테스트에서 dispose 호출을 spy로 증명할 수 있다 | R3F 이벤트를 부모 `<group onClick>`에서 받아야 한다 |
| B2 활성 청크마다 React 컴포넌트(key=chunk id) + `useEffect` cleanup | 코드가 조금 짧다 | 해제가 R3F 자동 dispose와 수동 cleanup으로 나뉜다. 프레임당 생성 상한을 걸기 어렵다. node 테스트가 어렵다 |

### 옵션 C — 가시성 계산

| 옵션 | 장점 | 단점 |
|---|---|---|
| **C1 (채택)** `Frustum.setFromProjectionMatrix(proj × matrixWorldInverse)` 후 청크 256개 AABB(`Box3`, y 0..8)와 교차 검사, 그 뒤 8-이웃 링 추가 | 보수적이다(평면-박스 검사라 모서리 근처 청크를 약간 과대 선택할 수 있지만 누락은 없다). 256회 검사라 비용이 무시할 수준. node에서 테스트 가능 | 없음(256개 고정 맵에서는) |
| C2 화면 4 모서리를 y=0에 unproject한 AABB | 단순 | 45° 회전 footprint의 AABB라 최대 약 2배 과대 선택 |

---

## 3. 모듈 설계

### 파일 배치 (`frontend/src/render/`)

```
map/      types.ts, tiles.ts, mapper.ts, prng.ts, generator.ts (+ 각 .test.ts)
chunks/   visibility.ts, groundGeometry.ts, ChunkManager.ts, ChunkLayer.tsx (+ .test.ts)
buildings/ buildingStyle.ts(+test), SelectionPanel.tsx(수정)
perf/     fps.ts(유지), DebugMeter.tsx(FpsMeter 대체), DebugHud.tsx(FpsPanel 대체)
camera/IsometricCamera.tsx(수정), city-map/coords.ts(수정), CityScene.tsx(수정)
```

삭제: `city-map/Terrain.tsx`, `city-map/Roads.tsx`, `buildings/buildingData.ts`(+test), `buildings/Buildings.tsx`, `perf/FpsMeter.tsx`, `perf/FpsPanel.tsx`.

### 공개 인터페이스

```ts
// map/types.ts
export const CHUNK_SIZE = 32, CHUNKS_PER_SIDE = 16, TILES_PER_CHUNK = 1024, TILE_SCHEMA_VERSION = 1
export type BuildingType = 'RESIDENTIAL' | 'COMMERCIAL' | 'OFFICE' | 'PUBLIC'
export interface ChunkDTO { id: string; world_id: string; chunk_x: number; chunk_y: number; chunk_size: number;
  terrain_tiles: number[]; road_tiles: number[]; schema_version: number; revision: number }
export interface BuildingDTO { id: string; world_id: string; type: string /* 신뢰 경계: mapper가 검증 */;
  tile_x: number; tile_y: number; width: number; height: number; capacity: number; occupied_capacity: number; status: string }
export interface Chunk { id; worldId; chunkX; chunkY; chunkSize; terrainTiles: number[]; roadTiles: number[]; schemaVersion; revision }
export interface Building { id; worldId; type: BuildingType | null /* null = 모르는 타입, 기본 스타일 */; tileX; tileY; width; height; capacity; occupiedCapacity; status }
export type ChunkKey = `${number},${number}`

// map/tiles.ts
export const Terrain = { GRASS: 0, WATER: 1, SAND: 2 } as const
export const RoadClass = { LOCAL: 0, ARTERIAL: 1 } as const
export const Dir = { N: 1, E: 2, S: 4, W: 8 } as const; export const ROAD_ISOLATED = 16
export function tileIndex(localX: number, localY: number): number            // localY*32+localX
export function worldToChunk(tileX: number, tileY: number): { chunkX; chunkY; localX; localY }
export function chunkLocalToWorld(chunkX, chunkY, localX, localY): { tileX; tileY }
export function chunkKey(chunkX: number, chunkY: number): ChunkKey
export function encodeRoad(cls: number, connection: number): number          // (cls<<5)|connection
export function decodeRoad(v: number): { cls: number; connection: number } | null  // 0 → null
export function isKnownRoad(v: number): boolean   // 0, 또는 cls 0..1 & connection 1..16

// map/mapper.ts (신뢰 경계)
export function toChunk(dto: ChunkDTO, onUnknown: (count: number) => void): Chunk
  // 배열 길이 ≠ 1024 또는 chunk_size ≠ 32 → throw. 모르는 terrain/road 값 → 0, 개수 보고
export function toBuilding(dto: BuildingDTO, onUnknown: () => void): Building
  // 모르는 type → type null(기본 스타일), 크래시 없음
export interface CityMap { worldId: string; chunks: Map<ChunkKey, Chunk>; buildingById: Map<string, Building>;
  buildingsByChunk: Map<ChunkKey, Building[]> }  // 렌더 소유권 = 앵커 청크만
export function toCityMap(input: { chunks: ChunkDTO[]; buildings: BuildingDTO[] }, warn = console.warn): CityMap
  // 건물 id 중복 제거(첫 항목 유지, 미래 REST 범위 조회 결과 병합 대비). 모르는 값이 있으면 warn은 '타일 값(terrain·road 합쳐) 1회 + 건물 타입 1회'

// map/prng.ts
export function mulberry32(seed: number): () => number     // [0,1)
export function uuidV4(rng: () => number): string           // version 4, variant 10 비트 고정

// map/generator.ts
export const DEFAULT_SEED = 20261118
export const MOCK_BUILDING_STATUS = 'ACTIVE'                 // Q1 답에 따라 교체하는 단일 상수
export function generateWorld(seed: number): { chunks: ChunkDTO[]; buildings: BuildingDTO[] }

// chunks/visibility.ts
export interface ChunkSets { visible: Set<ChunkKey>; active: Set<ChunkKey> /* visible ∪ 링, 맵 범위 clip */; center: [x: number, z: number] }
export function computeChunkSets(camera: THREE.Camera, maxHeight = 8): ChunkSets
  // center = 카메라 시선과 y=0 평면의 교점(대기열 정렬 기준)

// chunks/groundGeometry.ts
export function buildGroundBuffers(chunk: Chunk): { position: Float32Array; normal: Float32Array; color: Float32Array; index: Uint16Array }

// chunks/ChunkManager.ts
export const MAX_ACTIVATIONS_PER_FRAME = 8
export class ChunkManager {
  constructor(root: THREE.Group, city: CityMap)
  sync(sets: ChunkSets): void        // 목표 밖 활성 청크는 즉시 해제, 목표 밖 대기 키는 대기열에서 제거,
                                     // 새 키는 대기열에 넣고 정렬(visible 먼저, 그 안에서 center 거리순, 링은 뒤)
  update(): void                     // 대기열에서 최대 8개 activate. 매 프레임 무조건 호출
  setSelected(buildingId: string | null): void
  buildingIdAt(object: THREE.Object3D, instanceId: number): string | null
  get activeCount(): number
  get pendingCount(): number
  dispose(): void                    // 전체 청크 + 공유 자원 해제, 대기열 비움
}

// buildings/buildingStyle.ts
export const STYLE: Record<BuildingType, { color: string; boxHeight: number }>   // Buildings.tsx:4-9에서 이동
export const DEFAULT_STYLE = { color: '#9e9e9e', boxHeight: 2 }
export function buildingTransform(b: Building): { position: Vec3; scale: Vec3 }  // x=tileX+w/2, y=0, z=tileY+h/2; scale=(w, boxHeight, h)

// perf/DebugMeter.tsx
export interface DebugStats extends FpsStats { activeChunks: number; pendingChunks: number; totalChunks: 256; calls: number; triangles: number; geometries: number; textures: number }
export function DebugMeter(props: { manager: () => ChunkManager | null; selectedId: () => string | null; onUpdate: (s: DebugStats) => void }): null
```

### 데이터 흐름

```
generateWorld(DEFAULT_SEED) ─DTO─▶ toCityMap() ─▶ CityMap (CityScene에서 useMemo 1회)
ChunkLayer.useFrame (매 프레임):
  key = camera.projectionMatrix.elements + camera.matrixWorld.elements  (리사이즈·줌·패닝 모두 반영)
  key가 바뀌면 computeChunkSets(camera) → active 키 문자열이 바뀌었을 때만 manager.sync(sets)
  manager.update()   ← 조건 없이 매 프레임 (대기열 소진)
activate(key): buildGroundBuffers → BufferGeometry + Mesh(공유 groundMaterial)
               건물이 있으면 InstancedMesh: setMatrixAt → setColorAt(스타일/선택색) → computeBoundingSphere → root.add
```

- **React 컴포넌트**: `CityScene`, `IsometricCamera`, `ChunkLayer`, `DebugMeter`, `DebugHud`, `SelectionPanel`. **순수 TS**: `map/*`, `visibility.ts`, `groundGeometry.ts`, `ChunkManager.ts`, `buildingStyle.ts`, `fps.ts`.
- `ChunkLayer` props 고정: `{ city: CityMap; selectedId: string | null; onSelect: (id: string) => void; managerRef: { current: ChunkManager | null } }`. `DebugMeter`는 같은 `managerRef`와 `city`를 받는다(`__lcDebug.screenPointOf`가 `city.buildingById` 사용).
- `ChunkLayer`: `<group ref onClick>`. `useEffect`에서 `new ChunkManager(group, city)`를 만들고 cleanup에서 `dispose()`. `selectedId` prop이 바뀌면 `setSelected`.

### 지면 지오메트리 사양

- 재질: **`MeshLambertMaterial({ vertexColors: true })` + normal 속성 전부 (0,1,0)**. 기존 메시의 조명 톤(`meshStandardMaterial`, `Terrain.tsx:8`)과 맞추려고 Basic 대신 Lambert를 쓴다.
- 색: `new THREE.Color(hex)`의 `r,g,b`(ColorManagement가 sRGB hex를 선형으로 변환한 값)를 그대로 color 속성에 넣는다.
- 층 높이(y): terrain 0, road 0.02, mark 0.04.
- terrain: 타일마다 1×1 quad, 색 GRASS/WATER/SAND.
- road(등급 색, LOCAL `#55585e`, ARTERIAL `#33363b`): 타일 중심의 0.5×0.5 quad와, 연결된 방향마다 중심 quad 가장자리에서 타일 가장자리까지 가는 팔(폭 0.5, 길이 0.25)을 둔다. 연결 없는 모서리 쪽은 잔디가 보여 방향을 형태로 읽을 수 있다.
- mark(LOCAL `#d0d0d0`, ARTERIAL `#f2d14b`): 연결 방향마다 중심에서 가장자리까지 폭 0.08, 길이 0.5인 선. 고립(16)은 중심 0.16×0.16 점.
- 정점 상한: 4096 + 1024×(4+16+16) = 40,960 < 65,536 → `Uint16Array` 인덱스.

### dispose 전략

| 자원 | 생성 | 해제 |
|---|---|---|
| 공유 `groundMaterial`, `buildingMaterial`(Lambert), `boxGeometry`(`BoxGeometry(1,1,1).translate(0,0.5,0)`) | ChunkManager 생성자 | `ChunkManager.dispose()` (= ChunkLayer 언마운트) |
| 청크 지면 `BufferGeometry` | activate | deactivate: `root.remove` 후 `geometry.dispose()` |
| 청크 건물 `InstancedMesh`(instanceMatrix/instanceColor) | activate(건물 ≥ 1일 때만) | deactivate: `root.remove` 후 `instancedMesh.dispose()`. 공유 geometry/material은 해제하지 않음 |

**측정 한계**: `gl.info.memory.geometries`는 한 번이라도 렌더된 geometry만 센다(공유 box +1). 즉 활성됐지만 프러스텀 컬링으로 그려지지 않은 링 청크는 빠지고, InstancedMesh의 instance 버퍼는 아예 집계되지 않는다. 그래서 CDP 검사는 절대값이 아니라 **기준선 대비 비교**로 판정한다. instance 버퍼와 렌더되지 않은 청크의 누수 증거는 `ChunkManager.test.ts`의 dispose spy가 맡는다. 텍스처는 쓰지 않으므로 textures 기대값은 기준선과 같다.

### 경계 걸친 건물 1회 규칙

- **렌더 소유권 = 앵커 타일 `(tile_x, tile_y)`의 청크만**(`buildingsByChunk`). 이것은 문서 `04-map-rendering.md:30`의 "건물 좌표와 점유 범위로 겹치는 Chunk를 조회한다"(조회 규칙)와 별개다. 미래 REST 범위 조회는 겹치는 건물을 여러 범위에서 중복 반환할 수 있으므로 `toCityMap`이 id로 중복을 제거한다.
- 앵커 청크가 비활성이면 그 건물은 그리지 않는다. 1칸 링 + 건물 최대 변 6 < 32 제약으로 보이는 영역에서 잘리지 않는다.

### 클릭 → 건물 id

- 지면 Mesh는 `mesh.raycast = () => {}`로 레이캐스트에서 제외한다. R3F는 핸들러가 붙은 `<group>`을 재귀 레이캐스트하므로 교차 대상은 건물 InstancedMesh뿐이다.
- `group onClick(e)`: `e.delta > 4`면 무시(드래그). 아니면 `e.stopPropagation()` 후 `manager.buildingIdAt(e.object, e.instanceId)` → `onSelect`. 역매핑은 `InstancedMesh.userData.buildingIds: string[]`(instance 순서)로 한다.
- 빈 곳 클릭: 기존 `Canvas onPointerMissed`(`CityScene.tsx:18`)를 유지한다(R3F가 delta ≤ 2 클릭만 missed 처리). 기존 terrain `<group onClick>`(`CityScene.tsx:24-26`)은 삭제한다.
- 하이라이트: `setColorAt(i, SELECTED_COLOR)` + `instanceColor.needsUpdate`. 이전 선택은 원래 색으로 되돌린다. 선택된 건물의 청크가 나중에 활성화되면 activate에서 반영한다.
- `SelectionPanel`은 `city.buildingById.get(selectedId)`를 받아 `Selected: <id> (<TYPE>)`를 표시한다(`SelectionPanel.tsx:7` 문구 유지). type이 null이면 `(UNKNOWN)`으로 표시한다.

### 디버그 HUD / 훅

- `DebugMeter`(Canvas 내부 `useFrame`): `createFpsTracker`(`perf/fps.ts:9`)가 0.5초마다 값을 줄 때 `gl.info.render.calls/triangles`, `gl.info.memory.geometries/textures`, `activeCount/pendingCount`를 함께 읽는다. useFrame은 `gl.render` 전에 돌아서 읽는 값은 직전 프레임 값이다.
- `DebugHud`(DOM, `FpsPanel.tsx` 위치·스타일): `FPS / Avg / Chunks a/256 (+p) / Calls / Tris / Geo / Tex`.
- dev 전용(`import.meta.env.DEV`): `window.__lcDebug = { stats(), activeKeys(), panTo(x, z), screenPointOf(buildingId), screenPointOfTile(x, y), selectedId() }`. `screenPointOf*`는 `Vector3.project(camera)`를 CSS px로 변환하고, 화면 밖이면 `null`. `panTo`는 `useThree(s => s.controls)`의 target과 camera.position을 같은 delta로 옮긴 뒤 `controls.update()`. 이를 위해 **T4가 `<MapControls>`에 `makeDefault`를 추가한다**(현재 `IsometricCamera.tsx:40-47`에 없음). 언마운트 시 `delete window.__lcDebug`. 타입은 `declare global`.

---

## 4. MapGenerator 알고리즘 개요

1. `rng = mulberry32(seed)`. 소비 순서 고정: world_id → 물 → 도로 → 청크 id(chunk_y, chunk_x 순) → 건물. 512×512 전역 `Uint8Array`로 작업한 뒤 청크로 자른다.
2. **UUID**: rng 4회 × 32bit → 16바이트, `b[6]=(b[6]&0x0f)|0x40`, `b[8]=(b[8]&0x3f)|0x80`, `8-4-4-4-12` 형식.
3. **물/모래**: 원형 호수 3–5개(반지름 8–28). 물과 체비셰프 거리 ≤ 2인 비물 타일은 SAND.
4. **대로(ARTERIAL)**: x·y 축마다 64 간격 + 축별 오프셋(rng 16–48)으로 전체 길이 직선. 물 위는 건너뛴다.
5. **골목(LOCAL)**: 대로 블록 안에서 16 간격 후보선을 확률 0.6으로 채택하고 블록 경계까지 그린다. 물과 대로는 덮지 않는다.
6. **연결 비트**: 전역 그리드에서 N(y−1)/E(x+1)/S(y+1)/W(x−1) 이웃 도로(등급 무관, 맵 밖 제외)마다 비트를 켜고, 0이면 16으로 둔다. 전역에서 계산하므로 청크 경계도 일관된다.
7. **청크 슬라이스**: chunk_y, chunk_x 0..15 순으로 `tileIndex`에 채운다. `chunk_size 32, schema_version 1, revision 1`.
8. **건물**: 점유 그리드를 두고 스트라이드 2로 훑으며 확률 0.35로 시도한다. 타입 가중치 RES 0.5 / COM 0.25 / OFF 0.15 / PUB 0.1. 크기 RES 2–3, COM 2–4, OFF 3–4, PUB 3–6. 조건: 맵 안, footprint에 도로·물·점유 없음, 바깥 4변 중 한 곳 이상이 도로에 인접. `capacity = 면적 × (RES 4, COM 6, OFF 10, PUB 8)`, `occupied_capacity 0`, `status = MOCK_BUILDING_STATUS`.
9. **목표**: 건물 약 6,000–12,000개(청크당 25–45). 테스트는 하한 ≥ 3,000만 고정하고, 실제 수와 생성 시간은 보고한다.

---

## 5. 카메라 변경 (Q4 사용자 확인 대상)

- `coords.ts:1` `MAP_SIZE = 512` → `MAP_CENTER = [256,0,256]`. `clampToMap`(`IsometricCamera.tsx:27-34`)은 MAP_SIZE를 참조하므로 0..512로 따라간다.
- `DISTANCE = 200` 유지(`IsometricCamera.tsx:6`). 최소 줌 1920×1080에서 카메라-지면 거리는 약 136–264로 near 0.1 / far 1000 안이다.
- 줌(ortho, CSS px / zoom = 월드 단위). 화면 W×H의 지면 footprint ≈ (W/z) × (1.73·H/z), 45° 회전.
  - `MIN_ZOOM` 6 → **12** (`IsometricCamera.tsx:18`): 1920×1080에서 약 160×156 타일 → 보이는 청크 약 50, +링 약 80.
  - 기본 줌 14 → **20** (`IsometricCamera.tsx:39`): 1280×720에서 보이는 청크 약 12–16, +링 ≤ 40.
  - `MAX_ZOOM = 60` 유지.
- 수치는 추정이고 확정은 테스트로 한다. `visibility.test.ts`가 drei와 같은 frustum(left=−W/2 … zoom)의 `OrthographicCamera`로 `active.size`를 검사한다: (1280×720, 기본 줌) ≤ 64, (1920×1080, MIN_ZOOM) ≤ 128, (2560×1440, MIN_ZOOM) ≤ 160. 넘으면 MIN_ZOOM을 올리고 문서에 반영한다.

---

## 6. 작업 분해 (team 병렬, 파일 소유권 비중첩)

선행 게이트: §8의 Q1–Q4 답변을 받은 뒤 T0을 시작한다.

| # | 작업자 | 소유 파일 | 선행 | 모델 |
|---|---|---|---|---|
| T0 | docs | `docs/03-architecture/04-map-rendering.md`(§8.2 타일 스키마 v1, road 인코딩, **조회 규칙 vs 렌더 소유권(앵커) 구분, id 중복 제거 규칙** / §8.3 ChunkManager·Visibility·렌더러, 링 1칸, 프레임당 활성화 상한), `docs/03-architecture/06-database.md`(map_chunks 표 terrain/road 값 의미), `docs/05-phases/phase-02-chunk-rendering.md`(작업 + 완료 기준 = §7 요약) | 사용자 게이트 | sonnet |
| T1 | model | `src/render/map/{types,tiles,mapper,prng}.ts` + `.test.ts` | T0 | sonnet |
| T2 | generator | `src/render/map/generator.ts`, `generator.test.ts` | T1 | sonnet |
| T3 | chunks | `src/render/chunks/*`, `src/render/buildings/buildingStyle.ts`(+test) | T1 | sonnet |
| T4 | scene | `CityScene.tsx`, `camera/IsometricCamera.tsx`(**`makeDefault` 추가**, 줌 값), `city-map/coords.ts`(+test), `buildings/SelectionPanel.tsx`, `perf/{DebugMeter,DebugHud}.tsx`, 구 파일 삭제 | T2, T3 | sonnet |
| T5 | verify | `frontend/scripts/cdp-pan-check.mjs` | 작성은 T1 이후 병렬, 실행은 T4 이후 | sonnet |

- T2와 T3는 T1 이후 병렬로 진행한다(T3 테스트는 수제 `CityMap` fixture를 쓴다).
- 컴파일이 깨지는 기간을 줄이려고 구 파일 삭제는 T4 한 곳에서만 한다.

---

## 7. 수용 기준 (테스트 가능한 형태, 명령은 `frontend/`에서)

| AC | 검증 |
|---|---|
| 1 | T0의 3개 문서에 `(class << 5) \| connection`, terrain 0/1/2, N1 E2 S4 W8 16, 링 1칸, 조회 규칙 vs 앵커 소유권, id 중복 제거, phase-02 완료 기준이 있다. 코드 커밋보다 먼저 커밋된다. |
| 2 | DTO 필드 집합 = `ChunkRead` 9필드, `Building` 10필드(Q2에 따라 created_at/updated_at 추가 여부 결정). `mapper.test.ts`: snake→camel 전 필드. 길이 ≠ 1024 또는 chunk_size ≠ 32면 throw. terrain 7·road 99 → 0, warn 정확히 1회. 모르는 건물 type → `type null`, 크래시 없음, warn 1회. 같은 id 건물 2개 입력 → 1개. |
| 3 | `tiles.test.ts`: `tileIndex(0,0)=0, (31,0)=31, (0,1)=32, (31,31)=1023`. `worldToChunk(511,32)={15,1,31,0}`, 무작위 1000점 왕복 항등. `encodeRoad/decodeRoad` 왕복, 0 → null. |
| 4 | `generator.test.ts`: 청크 256개, (x,y) 0..15 전 조합 1회, 배열 길이 1024, `32/1/1`. 같은 시드 `toEqual`, 다른 시드 `not.toEqual`. 전역 재조립 후 모든 도로의 connection이 이웃과 일치(청크 경계 31↔32 포함). 건물 비중첩, footprint에 도로·물 없음, 범위 안, 최대 변 ≤ 6, 수 ≥ 3,000. UUID v4 정규식 + 유일성. |
| 5 | CDP 스크린샷(기본 줌 중앙)에 3색 지형, 2색 도로 + 방향 표시, 4색 건물이 보인다(사람이 확인). `console.error`/예외 0건. |
| 6 | HUD에 `FPS, Avg, Chunks a/256 (+p), Calls, Geo, Tex`가 보인다(스크린샷). `__lcDebug.stats()`가 같은 키를 반환한다. |
| 7 | `visibility.test.ts`: `active = visible ∪ 8-이웃`(범위 clip), §5의 세 해상도 상한, 카메라를 +x로 64 옮기면 앞쪽 키 추가·뒤쪽 키 제거. `ChunkManager.test.ts`: `sync(20개)` 후 추가 sync 없이 `update()` 3회 → `activeCount 20, pendingCount 0`. 첫 update 후 8개이고 visible이 링보다 먼저 활성화된다. 대기 중 목표에서 빠진 키는 끝까지 활성화되지 않는다. CDP: 기본 줌 `activeChunks` ≤ 64, 패닝 중 `activeKeys` 변화 기록. |
| 8 | `node scripts/cdp-pan-check.mjs` exit 0: 5회 왕복 후(대기열 소진 대기 `pendingChunks === 0`) geometries·textures ≤ 기준선 + 2. heap 판정은 **`최종(GC 후) ≤ 기준선(GC 후, 첫 왕복 전) × 1.15` 하나만** 쓴다. 회차별 추세는 보고만 한다. `ChunkManager.test.ts`: sync(4) → sync(∅) 후 청크 geometry·InstancedMesh `dispose` 이벤트 각 1회, 공유 자원 0회, `dispose()` 후 공유 자원 1회, 대기 중 해제된 키는 자원 생성 0회. |
| 9 | `buildingStyle.test.ts`: `{tileX:10,tileY:20,width:3,height:2}` → position `[11.5,0,21]`, scale `[3, boxHeight, 2]`. `mapper.test.ts`: (31,0) 앵커, 폭 3 건물은 `buildingsByChunk['0,0']`에만 있고, 전체 등장 합 = 건물 수. 경계 건물 스크린샷 1장. |
| 10 | 단위: `ChunkManager.test.ts`에서 건물 1개 청크와 500개 청크 모두 활성화 후 `root`에 그 청크의 자식이 정확히 2개(지면 + InstancedMesh 1개), 건물 0개 청크는 1개. CDP: 모든 측정 지점(기본·최소 줌)에서 `calls ≤ 2 × activeChunks + 5`, 측정값 보고. |
| 11 | CDP: `screenPointOf(id)`에 `Input.dispatchMouseEvent` mousePressed/mouseReleased(`button:'left', clickCount: 1`) → `selectedId() === id`, 패널 텍스트 `Selected: <id> (<TYPE>)`. 같은 점에서 눌러 60px 이동 후 release → 선택 유지. `screenPointOfTile`로 물 타일 중앙 클릭 → `null`. 하이라이트 스크린샷. |
| 12 | `yarn typecheck && yarn lint && yarn test && yarn build` 통과. 헤드리스 FPS(idle 5초 Avg, 패닝 중) 참고값 보고. 데스크톱 FPS는 사용자가 측정한다. |

---

## 8. 위험과 완화, 사용자 게이트

| 위험 | 완화 |
|---|---|
| 동시 활성화(예: 최소 줌 점프)로 프레임 끊김 | 대기열 + 프레임당 8개 상한. visible 먼저, 중심 거리순. HUD에 pending 표시 |
| 클릭 시 그룹 재귀 레이캐스트가 활성 InstancedMesh를 모두 훑음 | 클릭에만 발생(hover 핸들러 없음). 지면은 raycast noop. instance 행렬 설정 후 `computeBoundingSphere`로 청크 단위 조기 탈락 |
| InstancedMesh 버퍼 누수가 `gl.info`에 안 보임 | dispose spy 단위 테스트 + heap 기준선 비교 |
| 카메라 리사이즈 시 가시성 갱신 누락 | 재계산 키에 `projectionMatrix.elements` 포함 |
| headless WebGL 미지원 | `--use-angle=swiftshader --enable-unsafe-swiftshader`. `CHROME_PATH` 환경변수, 기본값은 Playwright 캐시의 `Google Chrome for Testing`. FPS는 참고값 |
| 앵커 청크 비활성 시 경계 건물 잘림 | 1칸 링 + 최대 변 6 테스트 고정 |
| A1이 스펙 문구와 다름 | Q3. 거부 시 A3로 지면만 교체 |

### 사용자 게이트 (T0 전에 질문, TBD 추측 금지)

| # | 질문 | 권장 답 |
|---|---|---|
| Q1 | 건물 `status` 허용 값이 문서·코드 어디에도 없다(`docs/02-domain/02-world.md`에는 "status"만, `building.py:29`는 String(32)). Mock 값은? | 임시값 `'ACTIVE'`를 `MOCK_BUILDING_STATUS` 상수 1곳에 두고, 도메인 문서에는 "값 목록 미정(TBD)"으로 남긴다. 값 목록 확정은 시민·기업 phase로 미룬다. |
| Q2 | Building DTO에 `BaseEntity`의 `created_at/updated_at`(`base.py:16-21`)을 넣을까? | 넣지 않는다. `ChunkRead`도 이 둘을 노출하지 않으므로(`city.py:9-20`) 같은 관례를 따른다. 건물 API가 생기면 그 스키마에 맞춘다. |
| Q3 | 지면을 청크별 병합 지오메트리(A1)로 그려도 되나? 스펙 문구는 "반복되는 지형 InstancedMesh"다. | A1 승인. draw call이 청크당 2(A3는 4)이고, 공개 인터페이스가 같아 필요하면 A3로 바꿀 수 있다. |
| Q4 | 기본 줌 14→20, MIN_ZOOM 6→12(최대 축소 범위가 줄어든다)로 바꿔도 되나? | 승인. 512 맵에서 MIN_ZOOM 6이면 1920×1080에서 맵 대부분(200청크 이상)이 보여 컬링 목적이 사라진다. 전체 조망은 미니맵 등 후속 기능으로 다룬다. |

---

## 9. 검증 단계

### 단위 테스트 (Vitest, env node)
- `map/tiles.test.ts`, `map/prng.test.ts`(결정성, [0,1), uuid 형식), `map/mapper.test.ts`, `map/generator.test.ts`
- `chunks/visibility.test.ts`(링, 3개 해상도 상한, 이동 시 추가/제거)
- `chunks/groundGeometry.test.ts`: 모든 normal = (0,1,0). y 값 집합 ⊆ {0, 0.02, 0.04}, terrain 정점은 0, 도로는 0.02, 표시는 0.04. 정점 수 = 1024×4 + Σ(도로 4 + 팔 4×연결 수 + 표시 4×max(연결 수,1)). 물 타일 색 = `new Color(WATER_HEX)` rgb. 인덱스 < 65,536.
- `chunks/ChunkManager.test.ts`: 대기열(AC 7), dispose spy(AC 8), 자식 수(AC 10), 0건물 청크에 InstancedMesh 없음, `setSelected` 색 반영/복원, 비활성 청크의 선택이 activate 때 반영, `buildingIdAt`.
- `buildings/buildingStyle.test.ts`, `city-map/coords.test.ts`(MAP_CENTER `[256,0,256]`), `perf/fps.test.ts`(유지). `buildings/buildingData.test.ts`는 삭제.

### CDP 스크립트 `frontend/scripts/cdp-pan-check.mjs` (의존성 없음, Node 24 내장 `WebSocket`/`fetch`)
1. 인자: `--url`(기본 `http://localhost:5173`, `yarn dev` 선실행), `--out`(기본 `os.tmpdir()/lc-cdp`, `.omc` 아래 금지), `--rounds 5`.
2. Chrome: `--headless=new --remote-debugging-port=9223 --window-size=1280,720 --use-angle=swiftshader --enable-unsafe-swiftshader --user-data-dir=<tmp>`. `/json/new?<url>` → WebSocket. `Runtime`, `HeapProfiler`, `Page`를 enable하고 콘솔 에러/예외를 수집한다.
3. `__lcDebug` 준비와 `pendingChunks === 0`을 대기한 뒤 2초 안정화. `HeapProfiler.collectGarbage` → 기준선 `{stats(), heap: Runtime.getHeapUsage().usedSize}`.
4. 왕복 1회 = `panTo`로 (32,256)→(480,256)→(480,480)→(32,32)→(256,256)을 16타일 간격으로 이동, 스텝마다 rAF 2회 대기. 5회 반복. 회차 끝마다 pending 0 대기 → GC → `{geometries, textures, heap, activeChunks, calls}` 기록.
5. 판정: AC 8(geometries/textures ≤ 기준선 + 2, 최종 heap ≤ 기준선 × 1.15). AC 10(모든 기록점에서 `calls ≤ 2×active + 5`, 최소 줌 1회 측정 포함). 결과는 stdout JSON, 실패 시 exit 1.
6. AC 11 클릭 검사(`clickCount: 1`), 스크린샷 `center.png`, `border-building.png`, `selected.png`를 `--out`에 저장한다.
7. FPS: idle 5초 `stats().avg`, 패닝 중 `stats().fps` 최소/평균.
8. 종료 시 Chrome과 임시 프로필을 정리한다.

### 보고 항목
건물 수, 생성 시간, 기본·최소 줌의 활성/보이는 청크 수와 calls, 5회 왕복 geometries/textures/heap 표(추세 포함), 헤드리스 FPS, 스크린샷 경로, yarn 4개 명령 결과.

---

## 10. ADR

- **결정**: 청크별 병합 지면 BufferGeometry(Lambert + vertex color + 상향 normal) + 청크별 건물 InstancedMesh(건물 있을 때만)를 그린다. 생명주기는 순수 TS `ChunkManager`(프레임당 8개 활성화 대기열)가 소유한다. 가시성은 프러스텀 vs 청크 AABB + 1칸 링이다. 렌더 소유권은 앵커 청크다.
- **동인**: (1) draw call 최소화와 건물 수 무관성, (2) 잦은 이동에서 누수·끊김 없음, (3) 인스턴스 클릭 역매핑과 경계 건물 1회 렌더.
- **검토한 대안**: A2 전역 인스턴스 풀, A3 청크별 레이어별 InstancedMesh, A4 청크 전체 병합, B2 청크별 React 컴포넌트, C2 화면 모서리 unproject AABB(기각 사유는 §2).
- **선택 이유**: A1은 청크당 draw call 2로 A3의 절반이고, 클릭 대상이 아닌 지면만 병합해 역매핑 비용이 없다. B1은 생성·해제·대기열을 한 파일에 두어 node 테스트로 누수 부재를 증명할 수 있다. C1은 보수적이고 256회 검사로 충분히 싸다.
- **결과**: draw call은 약 2 × 활성 청크로 건물 수와 무관하다. `gl.info`는 instance 버퍼와 미렌더 geometry를 세지 않으므로 누수 판정은 단위 spy + 기준선 비교에 의존한다. 줌 범위가 좁아진다(Q4). 타일 스키마 v1이 문서 계약이 되어 백엔드 생성기도 따라야 한다.
- **후속 작업**: REST 범위 조회 연결(같은 mapper, id 중복 제거), 건물 read API·스키마 확정 시 DTO 정렬(Q1/Q2), draw call이 병목이면 A2 재검토, 전체 조망(미니맵), 건물 status 값 목록 확정.

---

## 11. 변경 이력

- **v2 (Architect/Critic 반영)**
  1. `ChunkManager.update()`와 프레임당 8개 활성화 대기열 추가(visible 우선·중심 거리순, 목표 밖 키 제거), `activeCount`/`pendingCount` 분리, HUD에 pending 표시, 대기열 테스트 추가.
  2. 지면 사양 명시: Lambert + normal (0,1,0), `new Color(hex)` 선형 rgb, 층 높이 0/0.02/0.04, 중심 0.5 quad + 팔, 표시 치수. groundGeometry 테스트에 normal·높이 검사 추가.
  3. "geometries = 활성 + 1" 주장 삭제. 렌더된 geometry만 집계된다는 한계, 기준선 비교 판정, spy가 instance 버퍼 누수 증거임을 명시.
  4. AC 10을 `calls ≤ 2×activeChunks + 5`(전 줌)로 변경. 시드 비교 대신 건물 1개/500개 청크의 자식 수 = 2 단위 테스트로 교체.
  5. 가시성 재계산 키 = projectionMatrix + matrixWorld. C1 표현을 "보수적(약간 과대 선택)"으로 수정. 2560×1440 MIN_ZOOM ≤ 160 테스트 추가.
  6. 건물 0개 청크는 InstancedMesh 미생성. `setColorAt` → `computeBoundingSphere` → `root.add` 순서 명시.
  7. T4가 `<MapControls makeDefault>` 추가를 명시.
  8. `screenPointOfTile(x,y)` 훅 추가. CDP 마우스 이벤트에 `clickCount: 1` 명시.
  9. heap 판정을 `최종 ≤ 기준선 × 1.15` 하나로 단순화하고 추세는 보고만.
  10. mapper가 건물 `type`을 검증(모르는 값 → 기본 스타일 + 경고 1회). DTO `type: string`으로 변경.
  11. T0 문서에 조회 규칙 vs 앵커 렌더 소유권 구분과 id 중복 제거 규칙 추가. T0 모델을 haiku → sonnet으로 변경.
  12. A1 근거를 draw call 감소·지면 일괄 처리로 교체. A3를 문서화된 대체안으로 유지.
  13. 사용자 게이트 Q1–Q4를 권장 답과 함께 정리(Q2 BaseEntity 필드, Q4 줌 변경 추가). T0 선행 조건으로 지정.
  14. ADR 섹션 추가.
- **v1**: 초안.

---

## 12. 상태

**approved (2026-11-18, 사용자 승인: Q1·Q2·Q3·Q4 모두 권장 답)** — §8 사용자 게이트 Q1–Q4 답변 후 T0부터 실행한다.

### v3 (리드 반영, Critic 승인 후 Minor 3건)
- `ChunkLayer`/`DebugMeter` 연결 계약(`managerRef`, `city`)을 고정했다.
- 경고 횟수 규칙을 '타일 값 1회 + 건물 타입 1회'로 통일했다(AC2와 일치).
- type null 건물은 패널에 `(UNKNOWN)`으로 표시한다.
