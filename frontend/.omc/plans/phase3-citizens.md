# 계획: Phase 3 — 시민 렌더링·이동 (Mock, Chunk 가시성 재사용)

- 스펙(요구사항 단일 출처): `frontend/.omc/specs/deep-interview-phase3-citizens.md` (AC1–15)
- 선행 계획: `frontend/.omc/plans/chunk-rendering.md` (Phase 2, approved)
- 모드: RALPLAN short / 버전 v2 / 작성 2026-11-19
- 경로 표기: 별도 언급 없으면 `frontend/` 기준

## 1. 요구사항 요약

Phase 2의 512×512 Chunk 도시(동작 변경 없음) 위에 seed 고정 Mock 시민 0/100/500/1000명을 공유 저폴리 geometry·material 1개, InstancedMesh 1개로 그린다. 시민은 도로 경로(A*)를 따라 이동하고, 위치는 프레임이 아니라 논리 시계(`SimClock`)에서 계산한다. 그래서 화면 밖이나 탭이 숨겨진 동안에도 같은 위치로 이어진다. 보이는 Chunk 안의 시민만 instance 버퍼에 압축해 올린다. 시민을 클릭하면 패널에 ID와 상태가 나온다. React는 프레임마다 다시 렌더링되지 않는다. 데이터 모델은 나중에 REST `CitizenRead`와 SSE `citizen.movement.started`를 그대로 받을 수 있게 둔다.

| 스펙 AC | 이 계획에서 다루는 곳 |
|---|---|
| 1 문서 선행 | §8 T0 |
| 2 DTO == CitizenRead, mapper 테스트, MovementEvent | §3, §9 AC2 (런타임 키 대조) |
| 3 논리 상태에 좌표 없음, 같은 입력이면 같은 위치 | §3 `CitizenStore`, §6 `positionAt` |
| 4 Mock 생성·이동 결정성 | §4, §9 AC4 |
| 5 PathFinder | §5 |
| 6 MovementSystem | §6 |
| 7 화면 밖 연속성 | §9 P3-AC7 (독립 기대값 + 시계 드리프트) |
| 8 Mesh·geometry·material 각 1개 | §7, P3-AC8 |
| 9 React 렌더 횟수 불변 | §3 패널 ref 갱신, P3-AC9 (시민 선택 상태에서 측정) |
| 10 가시성 압축, draw call +2 이하 | §3, P3-AC10 |
| 11 선택 | §2 옵션 D, P3-AC11 |
| 12 0/100/500/1000, `?citizens=` | §3, P3-AC12 |
| 13 성능표 | P3-AC13 (x1, x16 행) |
| 14 기존 AC1–12 PASS | §9 (AC1–4는 `yarn test`와 문서, AC5–12는 CDP) |
| 15 typecheck/lint/test/build | §9 |

## 2. RALPLAN-DR 요약

### 원칙
1. 논리와 렌더 분리: 논리 상태(`Citizen`, `MovementEvent`)에는 좌표를 두지 않는다. 좌표는 (event, tick, path)에서 매 프레임 계산한다.
2. 시계 기반 결정성: 논리 상태는 `seed + 정수 tick`만으로 정해진다. 프레임 속도, 화면 가시성, 경로 계산 시점은 결과에 영향을 주지 않는다.
3. Phase 2 재사용, 비침습: `ChunkManager`, `visibility.ts`, 카메라는 수정하지 않는다. 가시성은 `computeChunkSets` 결과 하나만 쓴다.
4. 프레임 경로에서 할당과 React를 없앤다: 매 프레임 작업은 typed array와 instance 버퍼 쓰기만 한다.
5. 최소 코드: 새 의존성을 넣지 않는다. `prng.ts`, `tiles.ts`, `mapper` 패턴, three addons `BufferGeometryUtils`를 재사용한다.

### 결정 동인 (상위 3)
1. 1000명일 때 시민 CPU(전체 프레임 작업) 평균 2 ms 미만, long task 0건 (AC13). 숨김 탭에서 돌아올 때와 x16 포함.
2. 화면 밖 연속성과 결정성 (AC4, AC7)
3. Phase 2 AC1–12 회귀 없음 (AC14), draw call +2 이하 (AC10)

### 옵션 A — instance 구성과 가시성 컬링
- **A1 (채택) 단일 InstancedMesh(max 1000) + 매 프레임 압축(`count` = 그릴 수 있는 보이는 시민 수)**
  - 장점: draw call 1개. 화면 밖 시민은 업로드하지 않는다(`addUpdateRange(0, count*16)`). 레이캐스트는 `count`개만 검사한다(`node_modules/three/src/objects/InstancedMesh.js:261,279`).
  - bounds 처리:
    - `boundingSphere`는 지도를 덮는 고정 구(center (256,0,256), r = 365 ≥ 256·√2)로 생성 시 1번만 설정하고 **절대 null로 만들지 않는다**.
    - 이유: `WebGLRenderer.js:1934-1936`은 sortObjects일 때 null이면 매 프레임 `computeBoundingSphere()`(O(count))를 호출한다.
    - 레이캐스트도 이 구를 1차 판정에 쓰므로(`InstancedMesh.js:270`) 항상 통과하고, 이후 instance별 판정을 한다.
    - `frustumCulled = false`(Chunk mask로 이미 컬링했다).
  - 단점: slot→citizen 매핑을 매 프레임 다시 쓴다(1000개 루프, 비용 무시 가능).
- **A2 Chunk별 시민 InstancedMesh**: 시민이 Chunk 사이를 오가므로 재할당이 생기고, draw call이 최대 52개 늘어 AC10을 위반한다. **기각**.
- **A3 컬링 없음(count = 전체)**: AC10("off-screen not uploaded")을 위반한다. **기각**.

### 옵션 B — 프레임 상태 저장 위치
- **B1 (채택) 순수 TS `CitizenSystem`의 SoA Float32Array(`x`, `z`, `heading`)와 시민별 polyline 참조 배열 `polyOf[i]`**
  - 장점: GC 할당이 없고 Vitest(node)로 테스트할 수 있다.
  - 단점: id↔index 매핑을 관리해야 한다.
- **B2 시민별 객체**: GC와 캐시 효율이 나쁘고 논리와 렌더 상태가 섞인다(원칙 1). **기각**.

### 옵션 C — 도착 tick 산정과 경로 계산 시점 (게이트 G5)
- **C1 (권장) Manhattan 도착 + 지연(lazy) A***
  - 논리: `arrival_tick = start + max(1, ceil(manhattan(입구from, 입구to) / 40))`. 엔진은 A*를 전혀 쓰지 않는다. 목적지는 같은 도로 연결 요소로 제한하므로 항상 도달할 수 있다.
  - 렌더: A*는 **이동 중이면서 active Chunk(visible + 1 링) 안에 있는 시민**에 대해서만 요청한다. 시민의 Chunk는 두 입구 사이 직선 보간 위치로 판정한다. 프레임당 1 ms 예산(최소 1건)으로 처리한다.
  - 경로가 아직 준비되지 않은 이동 중 시민은 **그 프레임에 그리지 않는다**. 직선 보간으로 그리면 건물을 관통하므로 선택하지 않았다.
  - 장점: 숨김 탭에서 돌아오거나 x16으로 따라잡을 때 A*가 0회다. 비용이 화면에 비례한다.
  - 단점: 스펙 시간 모델("pathTiles/40")과 다르다. 경로가 Manhattan보다 길면 시각 속도가 빨라진다. 화면에 들어온 직후 1–수 프레임 동안 보이지 않을 수 있다.
- **C2 (대체안) 스펙 그대로(pathTiles/40) + 프레임 분할 따라잡기**
  - 출발 처리에 경로 길이가 필요하다. 따라잡기를 프레임당 예산으로 나눠 처리하고, 처리가 끝날 때까지 해당 시민을 숨긴다.
  - 단점: 숨김 탭 2.7 h(960 tick)에서 돌아오면 A*가 수만 건이다. 그동안 시민이 사라지고 구현 상태가 하나 늘어난다.
  - G5에서 사용자가 스펙 유지를 고를 때만 쓴다.
- **C3 출발 시 동기 A*(v1)**: 따라잡기 때 수천 건의 동기 A*로 long task가 생긴다. **기각**.
- 경로 표현: offset을 미리 적용한 꺾이는 점 polyline과 누적 길이 `cum`(Float32Array)을 쓴다. 프레임 비용은 이분 탐색과 lerp뿐이다. 해결되면 `polyOf[i]`에 참조를 넣는다. **프레임 루프는 PathService나 LRU를 조회하지 않는다**. 캐시(키 (from, to), LRU 2048)는 같은 쌍을 다시 쓸 때만 쓴다. 대안이던 프레임별 offset 계산과 스플라인은 기각한다.

### 옵션 D — 선택 공존
- **D1 (채택) `CityScene`의 단일 `useState<Selection>`**
  - `ChunkLayer`는 기존 props 그대로 건물 id만 받는다(`chunks/ChunkLayer.tsx:9-13`).
  - 시민 클릭은 CitizenLayer group의 `onClick`이 처리한다. 가까운 교차가 먼저 오고, 처리한 쪽이 `stopPropagation`한다.
  - 드래그는 `e.delta > 4`로 무시한다(`ChunkLayer.tsx:52`). 빈 곳 클릭은 기존 `onPointerMissed`로 지운다(`CityScene.tsx:20`).
- **D2 선택 분리 후 서로 지우기**: 동기화 버그가 생기기 쉽다. **기각**.
- **D3 zustand store**: 상태 하나에는 과하다. **기각**.

## 3. 모듈 설계

### 파일 배치 (`src/render/citizens/`, `*`는 테스트 동반)
컨벤션의 `citizens/` 예정 위치와 같다(`docs/04-development/03-frontend-convention.md:28`).

| 파일 | 내용 |
|---|---|
| `types.ts` | `CitizenDTO`, `Citizen`, `MovementEventDTO`, `MovementEvent`, `Selection`, `CitizenLayerApi` |
| `mapper.ts`* | `toCitizen`, `toMovementEvent` (신뢰 경계 검증) |
| `CitizenStore.ts`* | 논리 상태(좌표 없음) |
| `SimClock.ts`* | 소수 tick 시계, `MOCK_TICK_SECONDS = 10` |
| `roadGrid.ts`* | 전역 연결 비트, 연결 요소, 건물 입구 |
| `pathFinder.ts`* | A*(이진 힙, typed array) |
| `sidewalk.ts`* | 타일 경로 → offset polyline, `samplePolyline` |
| `PathService.ts`* | LRU, 요청 큐, `drain(budget)`, 해결 콜백 |
| `mockEngine.ts`* | `generateCitizens`, `MockEngine.advanceTo` (A* 없음) |
| `MovementSystem.ts`* | `positionAt`, SoA 갱신, idle 배치, `polyOf` |
| `citizenVisibility.ts`* | `chunkMask`, `compactVisible` |
| `CitizenSystem.ts`* | 프레임 코어(React·WebGL 없음) |
| `citizenGeometry.ts` | 병합 저폴리 geometry, 색상표 |
| `CitizenInstanceManager.ts` | InstancedMesh 소유, 쓰기, dispose |
| `CitizenLayer.tsx` | `<group ref onClick>` + `useFrame` 1개 |
| `CitizenPanel.tsx` | 선택된 시민 정보(휘발 필드는 ref로 갱신) |
| `CitizenControls.tsx` | 수, 속도 버튼 |

- 수정 파일: `CityScene.tsx`, `chunks/ChunkLayer.tsx`(선택 prop `setsRef`와 1줄, 렌더 카운터), `perf/{DebugMeter,DebugHud}.tsx`, `buildings/SelectionPanel.tsx`(카운터), 신규 `perf/renderCount.ts`, `scripts/cdp-pan-check.mjs`.
- 변경 없음: `chunks/ChunkManager.ts`, `chunks/visibility.ts`, `camera/IsometricCamera.tsx`(`onControlsChange` 모듈 스코프 유지, `:36-39`), `map/*`.

### 공개 인터페이스 (요지)
```ts
// types.ts — backend/app/schemas/city.py:30-50 CitizenRead와 1:1 (snake_case)
export interface CitizenDTO { id: string; world_id: string; household_id: string | null; name: string; age: number
  home_building_id: string | null; current_building_id: string | null; employment_status: string; employer_id: string | null
  happiness: number; health: number; skills: Record<string, unknown>; risk_tolerance: number; consumption_preference: number
  current_activity: string; current_destination: string | null; arrival_tick: number | null; cash_balance: number | null }
export const CITIZEN_DTO_KEYS = { id: true, /* … 전 필드 */ } satisfies Record<keyof CitizenDTO, true> // AC2 런타임 대조
export interface Citizen { /* camelCase 동일 필드, 좌표 없음 */ }
// 프런트 가정: SSE citizen.movement.started 제안 payload (백엔드 미정의)
export interface MovementEventDTO { citizen_id: string; from_building_id: string; to_building_id: string; start_tick: number; arrival_tick: number }
export interface MovementEvent { citizenId: string; fromBuildingId: string; toBuildingId: string; startTick: number; arrivalTick: number }
export type Selection = { kind: 'building' | 'citizen'; id: string } | null
export interface CitizenDebugInfo { moving: boolean; pathReady: boolean; tick: number; slot: number | null
  rendered: { x: number; z: number } | null; current: { x: number; z: number } }
export interface CitizenLayerApi {
  perf: { cpuMs: number; simMs: number; pathMs: number; moveMs: number; pathQueue: number; pathMisses: number } // 직전 프레임
  visibleCount: number; total: number; tick: number; speed: number
  ids(): string[]; citizen(id: string): Citizen | null; info(id: string): CitizenDebugInfo | null
  expectedFresh(id: string, tick: number): { x: number; z: number } | null // 새 MockEngine 기반 독립 계산
}

// mapper.ts — 비정수 tick, arrival<=start, 빈 id이면 null을 반환하고 warn
export function toCitizen(dto: CitizenDTO): Citizen
export function toMovementEvent(dto: MovementEventDTO, warn?: (m: string) => void): MovementEvent | null

// CitizenStore.ts
export class CitizenStore { readonly citizens: Citizen[]; readonly index: Map<string, number>; readonly moving: (MovementEvent | null)[]
  constructor(list: Citizen[]); applyMovement(e: MovementEvent): void; applyArrival(citizenId: string, buildingId: string): void }

// SimClock.ts — tick = base + (now − t0)/1000/MOCK_TICK_SECONDS·speed, now 주입
export const MOCK_TICK_SECONDS = 10
export class SimClock { constructor(nowMs: number, speed?: 1 | 4 | 16); tickAt(nowMs: number): number
  setSpeed(speed: 1 | 4 | 16, nowMs: number): void; get speed(): number }

// roadGrid / pathFinder / sidewalk — 타일 인덱스 = y*512+x (map/tiles.ts:7)
export interface RoadGrid { conn: Uint8Array; component: Int32Array }
export function buildRoadGrid(city: CityMap): RoadGrid
export function entranceTile(grid: RoadGrid, b: Building): number // 없으면 -1
export function findPath(grid: RoadGrid, from: number, to: number): Int32Array | null
export interface Polyline { xs: Float32Array; zs: Float32Array; cum: Float32Array; length: number }
export function toSidewalk(path: Int32Array, offset?: number): Polyline // 0.35
export function samplePolyline(p: Polyline, s: number, out: { x: number; z: number; heading: number }): void

// PathService.ts — 프레임 루프 밖에서만 호출
export class PathService { constructor(grid: RoadGrid, city: CityMap, max?: number)
  request(citizen: number, fromId: string, toId: string): void // 캐시 hit이면 즉시 onResolved
  cancel(citizen: number): void
  drain(budgetMs: number, now?: () => number): number
  onResolved: (citizen: number, p: Polyline | null) => void
  readonly stats: { cacheSize: number; queued: number } }

// mockEngine.ts — "서버" 역할. 출력은 DTO 콜백뿐(SSE 대체 지점), A*는 쓰지 않는다
export function generateCitizens(city: CityMap, grid: RoadGrid, seed: number, count: number): CitizenDTO[]
export interface EngineSink { movement(e: MovementEventDTO): void; arrival(citizenId: string, buildingId: string): void }
export class MockEngine { constructor(city: CityMap, grid: RoadGrid, seed: number, initial: CitizenDTO[], sink: EngineSink)
  advanceTo(tick: number): void } // 정수, 단조 증가

// MovementSystem.ts
export const CITIZEN_Y = 0.05 // 도로 0.02 / 표시 0.04 위 (chunks/groundGeometry.ts:6-7)
export function positionAt(e: MovementEvent, p: Polyline, tick: number, out: { x: number; z: number; heading: number }): void
export function approxPosition(e: MovementEvent, grid: RoadGrid, city: CityMap, tick: number, out: { x: number; z: number }): void // 입구 간 직선, 가시성 판정 전용
export class MovementSystem { readonly x: Float32Array; readonly z: Float32Array; readonly heading: Float32Array
  readonly drawable: Uint8Array; readonly polyOf: (Polyline | null)[]
  update(tick: number, activeMask: Uint8Array, paths: PathService): void } // 경로 없는 이동 시민: active이면 request, drawable=0

// citizenVisibility.ts
export function chunkMask(keys: Set<ChunkKey>, out: Uint8Array): void // out[cx*16+cz]
export function compactVisible(x: Float32Array, z: Float32Array, drawable: Uint8Array, n: number, mask: Uint8Array, slots: Int32Array): number

// CitizenSystem.ts
export class CitizenSystem { constructor(city: CityMap, seed: number, count: number, nowMs: number, speed: 1 | 4 | 16)
  readonly store: CitizenStore; readonly movement: MovementSystem; readonly paths: PathService; readonly clock: SimClock
  readonly slots: Int32Array; readonly colorIdx: Uint8Array; visibleCount: number; lastTick: number
  frame(nowMs: number, sets: ChunkSets | null): void } // setsRef null이면 visibleCount = 0

// CitizenInstanceManager.ts
export class CitizenInstanceManager { constructor(max: number) // mesh, instanceColor, 고정 boundingSphere 생성
  readonly mesh: THREE.InstancedMesh
  write(slots: Int32Array, count: number, x: Float32Array, z: Float32Array, heading: Float32Array, colorIdx: Uint8Array, selected: number): void
  citizenAt(instanceId: number): number; dispose(): void }
```

### 데이터 흐름
```
generateCitizens ─CitizenDTO[]─▶ toCitizen ─▶ CitizenStore (논리, 좌표 없음)
MockEngine.advanceTo(⌊tick⌋) ─MovementEventDTO─▶ toMovementEvent ─▶ store.applyMovement ; movement.polyOf[i]=null
                             └─arrival─▶ store.applyArrival ; polyOf[i]=null ; paths.cancel(i)
SimClock.tickAt(now) ─▶ MovementSystem.update:
     idle → 입구 옆 고정 위치(drawable=1)
     moving & polyOf[i] → positionAt (drawable=1)
     moving & !polyOf[i] → approxPosition으로 active 여부 판정 → active이면 paths.request (drawable=0)
paths.drain(1 ms) → onResolved → polyOf[i] = p
ChunkLayer(view 변경 시) ─setsRef.current = sets─▶ chunkMask(visible), chunkMask(active) (sets identity가 바뀔 때만)
compactVisible → slots[0..count) ─▶ CitizenInstanceManager.write → InstancedMesh
```
- 한 프레임 순서(`CitizenSystem.frame`): `engine.advanceTo` → `paths.drain(1 ms)` → `movement.update` → `compactVisible`. 이어 CitizenLayer가 `manager.write`를 부른다. `citizenCpuMs`는 CitizenLayer에서 이 전체를 `performance.now()`로 감싸 잰다.
- `ChunkLayer` 수정: prop `setsRef?: { current: ChunkSets | null }`를 추가하고 `ChunkLayer.tsx:40` 직후 `if (setsRef) setsRef.current = sets` 한 줄을 넣는다. `ChunkManager.sync`의 조건과 호출은 그대로다. 1프레임 지연은 허용한다.

### React 통합
- `CityScene` state:
  - `selection`, `citizenCount`(초기값 `?citizens=`, 0/100/500/1000만 허용, 그 밖이면 기본값 G2), `speed`.
  - `apiRef: { current: CitizenLayerApi | null }`, `setsRef`.
  - 수가 바뀌면 시민 선택을 지운다(`selection?.kind === 'citizen'`이면 null).
- `CitizenLayer`는 ChunkLayer 패턴(`ChunkLayer.tsx:20-30, 61`)을 따른다.
  - JSX는 `<group ref={groupRef} onClick={onClick} />`이다.
  - `useEffect([city, count])`가 `CitizenSystem`(현재 `speed`를 인자로 전달)과 `CitizenInstanceManager`를 만들고 `group.add(mesh)`한다. cleanup에서 remove하고 dispose한다.
  - `<primitive>`나 `useMemo`로 생성하지 않는다(StrictMode 이중 마운트 안전).
  - `speed`와 `selectedCitizenId`는 별도 effect가 기존 인스턴스에 반영한다.
- 수를 바꾸면 tick이 0부터 다시 시작한다(새 엔진). 알려진 한계로 문서화한다.
- `useFrame` 1개: `t0` → `system.frame(performance.now(), setsRef.current)` → `manager.write(…)` → `cpuMs = now − t0`. `apiRef.current.perf`에 기록한다.
- React state가 바뀌는 경우는 선택, 수 변경, 속도 변경뿐이다.
- `CitizenPanel`:
  - 정적 필드(id, name, 집)는 선택이 바뀔 때만 렌더링한다.
  - 휘발 필드(tick, moving/idle, activity, destination, arrival_tick)는 자체 500 ms `setInterval`이 `apiRef`를 읽어 span ref의 `textContent`에 직접 쓴다. setState를 쓰지 않는다(G4).
- `perf/renderCount.ts`: DEV에서 `useRenderCount(name)`가 카운터를 증가시킨다. CityScene, ChunkLayer, CitizenLayer, SelectionPanel, CitizenPanel에 붙인다.

### instance 버퍼 규칙
- 생성자에서 처리한다:
  - `instanceMatrix.setUsage(DynamicDrawUsage)`
  - `instanceColor = new InstancedBufferAttribute(Float32Array(max·3), 3)`(DynamicDraw)를 첫 렌더 전에 만든다
  - 고정 `boundingSphere`, `frustumCulled=false`, `userData.citizens = true`
- `write`는 매 프레임 slot `[0, count)`의 행렬과 색을 모두 다시 쓴다. 이어서 `addUpdateRange(0, count·16)`, `addUpdateRange(0, count·3)`, 두 attribute에 `needsUpdate = true`를 건다.
- `count === 0`이면 `mesh.visible = false`이고 아니면 true다.
- 선택된 시민은 색 `#ffd400`, scale 1.5.

### dispose
- `CitizenInstanceManager.dispose()`: group에서 제거하고 `mesh.dispose()`, geometry 1개, material 1개를 dispose한다. 수 변경이나 언마운트 때 effect cleanup에서 호출한다.
- `CitizenSystem`은 GPU 자원이 없으므로 참조만 버린다.

### 디버그 훅 (`window.__lcDebug` 확장, DEV, `DebugMeter`가 소유하고 `apiRef`를 읽음)
- `DebugStats`에 추가: `citizensVisible`, `citizensTotal`, `tick`, `speed`, `citizenCpuAvg`, `citizenCpuMax`, `pathQueue`, `pathMisses`(이동 중이지만 경로 미준비로 숨긴 수). 500 ms 창 집계.
- 함수 추가: `setCitizenCount(n)`, `setSpeed(s)`, `selection()`, `citizenIds()`, `citizenInfo(id)`, `expectedFresh(id, tick)`, `screenPointOfCitizen(id)`, `visibleKeys()`, `isQuietTile(x, y)`(건물 아님, Chebyshev 2 안에 도로 없음), `citizenMeshes()`(scene traverse, `userData.citizens` → meshes/geometries/materials), `renderCounts()`, `glRenderer()`(`WEBGL_debug_renderer_info`).
- `selectedId()`는 **건물 id만** 반환한다(기존 스크립트 호환).

### HUD / 컨트롤
- `DebugHud`에 추가하는 줄:
  - `Citizens {visible}/{total}`
  - `Tick {tick.toFixed(2)} x{speed}`
  - `CPU {avg}/{max} ms`
  - `Path q{queue} miss{misses}`
- `CitizenControls`(`pointer-events-auto`, 우하단): `[0][100][500][1000]`, `[x1][x4][x16]`.
- 건물 패널 문구 `Selected: <id> (<TYPE>)`는 유지한다(`buildings/SelectionPanel.tsx:7`, CDP 정규식 `scripts/cdp-pan-check.mjs:193`). 시민 패널은 `Citizen: <id>`로 시작한다.

## 4. Mock 엔진 알고리즘 (A* 없음)
- 시민별 독립 난수열 `rng_i = mulberry32(hash(seed, i))`(`map/prng.ts:1`, `Math.imul` 혼합)을 쓴다. 처리 순서와 무관하다. `count=100`은 `count=1000`의 앞 100명과 같다.
- 생성: 건물 순서는 `city.buildingById` 삽입 순서다(`map/mapper.ts:76-87`). 입구가 있는 건물만 쓴다. 필드는 다음과 같다.
  - `id = uuidV4(rng_i)`, `home` = 무작위 RESIDENTIAL, `current = home`
  - `employment_status`: EMPLOYED 80% / UNEMPLOYED (G1)
  - `employer_id`, `household_id`, `cash_balance`는 null(화폐 값을 만들지 않는다)
  - `happiness`, `health`: 정수 50–100. `skills {}`. 두 성향 값은 [0,1)
  - `current_activity 'IDLE'`, destination/arrival은 null. 이름은 음절표로 만든다.
- 초기 다음 출발 tick은 `randInt(1, 6)`이다(tick 0에 몰리지 않게).
- `advanceTo(T)`: 시민마다 `while`로 처리한다.
  1. 이동 중이고 `arrival ≤ T`이면 `sink.arrival`, `nextDepart = arrival + randInt(1, 6)`.
  2. idle이고 `nextDepart ≤ T`이면 목적지를 고른다. `start = nextDepart`(처리 시점이 아니라 예정 tick), `arrival = start + max(1, ceil(manhattan(입구from, 입구to)/40))`, `sink.movement(DTO)`.
- 목적지 후보: 현재 건물 anchor chunk ±2 안, `≠ 현재`, 입구가 같은 연결 요소인 건물(G3). chunk별 후보 목록은 미리 만든다. 최대 8회 재추첨하고 실패하면 `nextDepart += randInt(1, 6)`으로 머문다.
- 경제·의사결정 로직은 없다. 정수 tick만 출력한다.
- 비용: 이벤트당 O(1)(난수 몇 회 + 후보 선택). 숨김 탭 960 tick, 1000명 따라잡기의 상한은 §9 벤치마크로 정한다.

## 5. PathFinder (렌더 전용)
- `buildRoadGrid`: `decodeRoad`(`map/tiles.ts:31`)로 전역 `conn: Uint8Array(512²)`를 만든다. 다리(수면 위 ARTERIAL, `map/generator.ts:100`)는 일반 도로와 같다. 연결 요소는 BFS로 채운다. 시작 시 1회, 목표 30 ms 미만.
- 이동 규칙: 현재 타일의 방향 비트가 켜졌을 때만 4방향으로 이동한다(비용 1, Manhattan 휴리스틱). 비트는 이웃이 도로일 때만 켜진다(`generator.ts:129-131`).
- `entranceTile`: footprint 둘레를 상 → 우 → 하 → 좌 고정 순서로 돌며 처음 만나는 도로 타일이다. 생성기가 존재를 보장한다(`generator.ts:180-183`). 건물별로 캐시한다.
- A*: `gScore`/`came`는 Int32Array, `stamp`는 Uint32Array 세대 번호다. 힙은 Int32Array 이진 힙(f, 동률이면 h, 그다음 인덱스)이다. 확장 노드가 20,000을 넘으면 null(방어 코드)이다.
- 예산: `drain(1 ms)`, 최소 1건/프레임. 목표는 경로 1건 평균 0.2 ms 이하(T2 벤치마크에서 avg/p99를 보고). active 영역의 이동 중 시민만 요청하므로 x16에서도 큐가 화면 규모로 묶인다.
- 캐시: 숫자 키 `from*65536+to`, `Map` 삽입 순서 LRU 2048(약 1 MB). 해결 결과는 `onResolved`로 `polyOf[i]`에 넣는다.

## 6. MovementSystem
- `toSidewalk`: 직선 구간을 합쳐 꺾이는 점만 남긴다. 오른쪽 법선 `(-dz, dx)`(three XZ, Y up)으로 0.35만큼 옮긴다.
  - 90° 모서리는 miter `p + 0.35·(n_in + n_out)`로 처리한다.
  - 끝점은 인접 구간의 법선을 쓴다. 길이 0 경로는 출발점에 머문다.
  - `cum`은 offset 후의 점으로 계산한다.
- `positionAt`: `u = clamp((tick − start)/(arrival − start), 0, 1)`, `s = u·length` → `cum` 이분 탐색 → lerp. heading은 `atan2(dx, dz)`. 진행은 단조 증가다(AC6).
- idle 배치: 입구 타일 중심에서 건물 쪽으로 0.35 옮긴 뒤, index로 정한 ±0.18 jitter를 변 방향으로 더한다. 건물별로 미리 계산한다.
- `update`: 1000명을 한 번 돈다. 이동 중이면서 `polyOf[i]`가 없으면 `approxPosition`(입구 간 직선)의 Chunk가 active일 때만 `request`한다. 루프 안에서 할당하지 않는다.
- 예산: `citizenCpuMs`(엔진 + drain + 이동 + 압축 + 쓰기) 평균 2 ms/frame 미만(1000명, x1과 x16).

## 7. 저폴리 시민 geometry와 색
- `mergeGeometries`(three addons, 의존성 추가 없음)로 합친다.
  - 몸통 `CylinderGeometry(0.12, 0.16, 0.42, 6)`: 24 tris, y +0.21
  - 머리 `OctahedronGeometry(0.13)`: 8 tris, y 0.55
  - 합계 32 tris, 1000명이면 32k. geometry와 `MeshLambertMaterial` 각 1개.
- 색(instanceColor): EMPLOYED `#3a6ea5`, UNEMPLOYED `#8d8d8d`, 그 밖 `#b07cc6`. 선택은 `#ffd400`, ×1.5.
- 행렬은 Y 회전 + 이동을 직접 쓴다(`[c,0,-s,0, 0,1,0,0, s,0,c,0, x,y,z,1]`).
- bounds: 고정 구, frustumCulled=false(§2 A1). 줌 20에서 클릭 대상은 약 7×13 px다.

## 8. 작업 분해 (team, 파일 소유권 비중첩)

| ID | 담당 파일 | 선행 | 모델 |
|---|---|---|---|
| T0 문서 | `docs/05-phases/phase-03-citizen-movement.md`(범위는 Mock, 이 계획의 기준, SSE 기준은 Phase 4–5로 이동), `docs/03-architecture/04-map-rendering.md` §8.4, `docs/02-domain/03-citizen.md` §4.4(논리/렌더 분리, MovementEvent 가정, tick 초 TBD/Mock 10 s, G5 도착 산정), `docs/04-development/03-frontend-convention.md:28`, `CLAUDE.md` 디렉터리 표의 frontend 상태 줄 | 게이트 G1–G5 | sonnet |
| T1 모델·시계 | `citizens/{types,mapper,CitizenStore,SimClock}.ts` + 테스트, `perf/renderCount.ts` | T0 | sonnet |
| T2 경로 | `citizens/{roadGrid,pathFinder,sidewalk,PathService}.ts` + 테스트, A* 벤치마크 | T0 (T1 types만) | sonnet |
| T3 엔진·이동 | `citizens/{mockEngine,MovementSystem,citizenVisibility,CitizenSystem}.ts` + 테스트, 숨김 탭 벤치마크 | T1, T2 (§3 시그니처로 병렬 착수 가능) | **opus** |
| T4 렌더 | `citizens/{citizenGeometry,CitizenInstanceManager}.ts`, `citizens/CitizenLayer.tsx` | T3 | sonnet |
| T5 씬·UI·훅 | `CityScene.tsx`, `chunks/ChunkLayer.tsx`, `citizens/{CitizenPanel,CitizenControls}.tsx`, `perf/{DebugMeter,DebugHud}.tsx`, `buildings/SelectionPanel.tsx` | T4 인터페이스 (`CitizenLayerApi` 고정) | sonnet |
| T6 검증 | `scripts/cdp-pan-check.mjs`, 성능표. **예외: T0 소유 `phase-03` 문서의 "완료 기록" 절만 T0 완료 후 추가** | T5 | sonnet |

- 병렬: T1 ∥ T2 → T3 → T4 ∥ T5.
- 공통 금지: `ChunkManager.ts`, `visibility.ts`, `IsometricCamera.tsx`, `map/*`, backend, simulation_engine, `.omc/backup/README.original.md` 수정 금지. 의존성 추가 금지.

## 9. 수용 기준 (명령은 `frontend/`에서)

### 단위 테스트 (`yarn test`, Vitest env node)
- **AC2**:
  - `fs`로 `../backend/app/schemas/city.py`를 읽는다. `class CitizenRead` 블록에서 정규식 `^\s{4}(\w+):`로 필드를 뽑고, `Object.keys(CITIZEN_DTO_KEYS)`와 집합이 같아야 한다.
  - snake → camel 변환을 확인한다.
  - `toMovementEvent`는 비정수 tick, `arrival ≤ start`이면 null이고 warn을 1회 호출한다.
- **AC3** `Citizen`과 store에 x/y/z/position 키가 없다. `positionAt`은 같은 입력이면 같은 출력이다.
- **AC4**:
  - 같은 seed이면 `generateCitizens` JSON이 같다.
  - `advanceTo(0..200)`의 **시민별 이벤트 시퀀스**(citizen_id별 배열)가 같다.
  - count 100/500/1000. UUID v4이고 고유하다. 모두 home/current가 있다. moving이면 destination과 arrival이 있다.
  - 100명 결과는 1000명의 앞 100명과 같다. 1 tick씩 호출한 결과와 한 번에 200 tick 호출한 결과가 같다.
  - `arrival − start == max(1, ceil(manhattan/40))`(G5 권장안 기준).
- **AC5**:
  - 경로는 도로만 지난다. 이웃은 4방향으로 인접하고 양방향 비트가 맞다. 시작과 끝은 `entranceTile`이다.
  - 다른 연결 요소로 가면 null이다. 합성 격자에서 다리 횡단이 성공한다. 우회 경로가 최단이다.
  - 벤치마크: ±2 chunk 같은 연결 요소 무작위 1000쌍에서 avg/p99를 로그로 남긴다. 목표 avg ≤ 0.2 ms, 테스트 단언은 avg ≤ 1 ms(CI 흔들림 대비).
- **AC6**:
  - start에서 시작점, arrival에서 끝점이다. 100개 샘플에서 진행이 단조 증가한다.
  - 직선 구간에서 오른쪽으로 0.35 떨어진다. 모서리는 miter다. 길이 0 경로도 처리한다.
- **SimClock**: speed 변경 때 tick이 연속이다. 큰 `now` 간격에서도 선형이다.
- **숨김 탭 벤치마크(T3)**: 1000명. `now`를 주입해 1 프레임에 +960 tick(x1 기준 2.7 h)을 진행한다. `system.frame()` 1회의 비용이 ≤ 50 ms다(로그 + 단언). 그 프레임의 A* 호출은 0회다(엔진은 A*를 쓰지 않음). 이후 프레임의 drain은 1 ms 예산을 지킨다.
- **`compactVisible`**: mask 밖 시민과 `drawable=0` 시민은 slot에 없다. **`CitizenSystem.frame(now, null)`**이면 `visibleCount === 0`이다.
- **PathService**: LRU 상한, `drain` 예산, `cancel`, hit이면 즉시 해결된다.

### CDP (`node scripts/cdp-pan-check.mjs --url 'http://localhost:5173/?citizens=1000'`)
- **AC14**:
  - 기존 AC5–AC12가 citizens=1000에서 PASS다. AC1–4는 `yarn test`와 T0 문서 diff로 확인한다.
  - 스크립트 수정 1 — AC11 건물 스캔은 `selection()`이 citizen인 타일을 건너뛴다.
  - 스크립트 수정 2 — 빈 타일은 `isQuietTile(x,y)`가 참인 타일 중에서 고른다. 클릭 후 `selection() !== null`이면 다른 조용한 타일로 최대 5회 재시도한다.
  - AC10 `calls ≤ 2·active + 5`는 그대로 유지한다.
- **P3-AC7 화면 밖 연속성**:
  1. `setSpeed(16)`, `arrival − tick ≥ 2`인 moving 시민 하나를 고른다.
  2. 256 tiles 이상 떨어진 곳으로 `panTo`하고 `citizenInfo.slot === null`을 확인한다.
  3. tick이 1 이상 증가할 때까지 기다린 뒤 `current` 위치로 `panTo`한다.
  4. `slot !== null`이 될 때까지 최대 30프레임 기다린다(지연 A*).
  5. `|rendered − expectedFresh(id, info.tick)| < 1e-3`이다. `expectedFresh`는 같은 seed로 **새 MockEngine**을 만들어 `⌊tick⌋`까지 진행하고, 새 경로로 계산한 독립 기대값이다.
  6. 시계 드리프트: speed를 고정한 2 s 구간에서 `|Δtick − Δwall·speed/10| ≤ speed·0.05/10`(약 1–3 프레임)이다.
- **P3-AC8** `citizenMeshes()`가 `{meshes:1, geometries:1, materials:1}`다(StrictMode dev).
- **P3-AC9** citizens=1000, **시민 1명 선택 상태**, 10 s 동안 CityScene/ChunkLayer/CitizenLayer/SelectionPanel/CitizenPanel 렌더 증가량이 0이다. 같은 구간에서 패널의 tick 텍스트는 변해야 한다(ref 갱신 확인).
- **P3-AC10**:
  - `citizensVisible === mesh.count`이고, 브라우저 안에서 `citizenInfo`(drawable, `current`) + `visibleKeys()`로 다시 센 값과 같다.
  - 같은 뷰에서 `?citizens=0` 대비 `?citizens=1000`의 calls 차이가 2 이하다.
- **P3-AC11**:
  - idle 시민을 클릭하면 `selection().kind === 'citizen'`이고 패널에 `Citizen: <id>`, name, activity, tick이 보인다.
  - 이어서 건물을 클릭하면 building으로 바뀐다(하나만 선택).
  - 시민 위에서 60 px 드래그하면 선택이 유지된다. 조용한 타일을 클릭하면 null이다.
- **P3-AC12**:
  - `setCitizenCount`를 0/100/500/1000으로 바꿀 때마다 `citizensTotal`이 일치한다. 시민이 선택된 상태에서 수를 바꾸면 선택이 지워진다. tick이 0부터 다시 시작하고 speed는 유지된다.
  - 4회 전환 후 `geometries ≤ 기준 + 2`다. 0명이면 `mesh.visible === false`다. `?citizens=500` URL과 DOM 버튼 1회도 확인한다.

### P3-AC13 성능표 (`--gpu --perf-table`)
- 환경: Chrome `--use-angle=metal`, 1920×1080, DPR 1, 줌 20, 중심 (256,256). `glRenderer()` 문자열을 기록해 실제 GPU인지 확인한다(SwiftShader이면 실패).
- 행: citizens {0, 100, 500, 1000} × speed {x1, x16}, 8행.
- 각 행 측정 절차:
  1. 새로 로드하고 `pendingChunks === 0`이 된 뒤 3 s 기다린다.
  2. 10 s 동안 FPS avg/min, calls, tris, geometries, `citizenCpuAvg`/`citizenCpuMax`, `pathQueue` 최대, `pathMisses` 평균을 잰다.
  3. GC 후 heap을 잰다.
  4. 연속 pan/zoom 10 s(드래그 5회 + 휠) 동안 long task 수를 센다(`addScriptToEvaluateOnNewDocument`로 `PerformanceObserver('longtask')`).
- 합격: 1000명의 x1과 x16 모두 `citizenCpuAvg < 2`(max는 보고만), pan/zoom 중 long task 0건, calls(1000) − calls(0) ≤ 2.
- 표는 Phase 2 기준선(52 chunks, 49 calls, 약 66k tris, 25 geom, 60 FPS, 약 29 MB)과 함께 phase-03 문서 완료 기록 절에 적는다(T6).

### 빌드
- **AC15** `yarn typecheck && yarn lint && yarn test && yarn build`가 모두 0 exit. 알려진 한계를 보고한다.

## 10. 위험, 완화, 알려진 한계

| 위험 | 완화 |
|---|---|
| 따라잡기(숨김 탭, x16) 때 동기 A*가 폭증한다 | C1: 엔진에서 A*를 없앴다(Manhattan 도착). A*는 active 영역의 이동 중 시민만 1 ms/frame 예산으로 처리한다. 숨김 탭 벤치마크로 확인한다 |
| boundingSphere가 null이면 three가 매 프레임 O(n)으로 다시 계산한다 | 지도를 덮는 고정 구를 1회 설정하고 null로 만들지 않는다. `frustumCulled=false` |
| StrictMode 이중 effect로 mesh가 중복되거나 새어 나간다 | ChunkLayer 패턴(effect에서 생성, `group.add`, cleanup에서 dispose). P3-AC8 |
| instanceColor가 첫 렌더 후에 생기면 셰이더 재컴파일과 색 누락이 생긴다 | 생성자에서 instanceColor를 만들고, 매 프레임 범위 업데이트를 한다 |
| 기존 AC11 스캔이 시민을 클릭해 오판한다 | `selectedId()`는 건물 전용으로 두고 `selection()`과 `isQuietTile`로 재시도한다 |
| AC8 heap ≤ 1.15×가 경로 캐시 때문에 실패한다 | LRU 2048(약 1 MB) < 기준선 15%(4.4 MB) |
| `onControlsChange` identity가 깨져 드래그가 끊긴다 | 카메라 파일 수정 금지, AC12 연속 드래그 |

알려진 한계(문서화):
- 출발과 도착이 정수 tick 경계에 맞춰진다. 초기 출발과 dwell을 분산해 완화한다.
- idle 위치와 path 시작·끝(보도 offset) 사이에 약 0.5–0.7 tile 시각 점프가 있다.
- Manhattan 도착 때문에 경로가 길면 시각 속도가 빨라진다(G5).
- 화면에 들어온 이동 시민은 경로가 준비될 때까지 1–수 프레임 보이지 않는다.
- x16에서 빠른 시민은 클릭하기 어렵다.
- 수를 바꾸면 tick이 0부터 다시 시작한다.
- 숨김 탭에서 돌아온 첫 프레임에 엔진 따라잡기 비용(≤ 50 ms)이 1회 생긴다.
- 충돌 회피는 없다.

### 사용자 게이트 (T0 전에 확인, TBD 추측 금지)
- **G1** `employment_status`와 `current_activity` 값은 문서상 str·TBD다(`docs/04-development/04-simulation-convention.md:39`). Mock 전용으로 EMPLOYED/UNEMPLOYED, IDLE/MOVING을 쓰고 모르는 값은 기본색으로 둘지. **권장: 예.**
- **G2** `?citizens`가 없을 때 기본 수. **권장: 100**(회귀와 성능 측정은 URL로 1000 지정).
- **G3** 목적지를 ±2 chunk 안, 같은 도로 연결 요소로 제한할지. **권장: 예**(A* 비용 상한, 도달 보장).
- **G4** 패널이 선택 중에도 React로 다시 렌더링되지 않게 할지(휘발 필드는 ref/textContent) 아니면 2 Hz 재렌더를 허용할지. **권장: ref 방식**(AC9를 선택 상태에서도 엄격히 지킴).
- **G5** 스펙 시간 모델 변경 여부: `arrival = start + max(1, ceil(manhattan/40))` + 지연 A*(C1)로 할지, 스펙 그대로 `pathTiles/40` + 프레임 분할 따라잡기(C2)로 할지. **권장: C1**(따라잡기 비용이 화면 규모에 묶이고, 엔진과 경로를 분리해 서버 대체가 쉽다).

## 11. 검증 단계
1. T0 후 문서 diff를 확인한다(G1–G5 반영, 백업 파일 미수정, CLAUDE.md 상태 줄).
2. T1–T3: `yarn test`(벤치마크 로그 포함), `yarn typecheck`.
3. T4–T5: `yarn dev?citizens=1000`을 육안 점검한다. 이동, 보도 offset, 색, 선택, 패널 tick 갱신, HUD.
4. T6: `node scripts/cdp-pan-check.mjs --url 'http://localhost:5173/?citizens=1000'`가 RESULT: PASS인지 확인한다.
5. T6: `node scripts/cdp-pan-check.mjs --gpu --perf-table`로 8행 표를 만들고 GPU 문자열을 확인한다.
6. `yarn typecheck && yarn lint && yarn test && yarn build`.
7. 성능표와 알려진 한계를 phase-03 완료 기록에 남긴다.

## ADR
- **결정**:
  - 단일 InstancedMesh(고정 bounds) + Chunk visible mask 압축
  - SoA 상태와 `polyOf`를 가진 순수 TS `CitizenSystem`
  - Manhattan 도착 산정 + 화면 영역 지연 A*(offset polyline, LRU)
  - `CityScene` 단일 `Selection`, 패널 휘발 필드는 ref 갱신
- **동인**: 시민 CPU 평균 2 ms 미만(따라잡기 포함) / 결정성·화면 밖 연속성 / Phase 2 무회귀.
- **검토한 대안**:
  - Chunk별 시민 mesh: draw call 증가로 기각
  - 컬링 없음: AC10 위반으로 기각
  - 시민별 객체: GC 부담으로 기각
  - 출발 시 동기 A*: 따라잡기 폭증으로 기각
  - 스펙 그대로 + 프레임 분할 따라잡기: 대체안으로 유지(G5)
  - 프레임별 offset 계산: CPU 증가로 기각
  - 선택 분리, zustand: 동기화 부담과 과잉으로 기각
  - 패널 2 Hz 재렌더: G4 대체안
- **선택 이유**: 비용이 화면 규모에 묶여 계측할 수 있다. 엔진(논리)이 경로(렌더)에 의존하지 않아 SSE로 바꿀 때 엔진만 교체하면 된다. 기존 계약(`ChunkLayer` props, `selectedId()`)을 유지한다.
- **결과**:
  - 스펙 시간 모델을 Manhattan 기반으로 바꾼다(G5 승인 시 문서 반영).
  - 경로 준비 전 시민이 잠깐 보이지 않는다.
  - `ChunkLayer`에 선택 prop 1개가 추가된다.
  - 디버그 훅 표면이 늘어난다.
  - 수를 바꾸면 tick이 다시 시작된다.
- **후속**: Phase 4–5에서 `MockEngine`을 SSE 수신기로 바꾼다(`EngineSink` 유지). 서버 tick으로 `SimClock` 기준점을 바꾼다. 백엔드와 MovementEvent payload 및 도착 산정 방식을 확정한다. Web Worker 경로 계산은 필요할 때만 한다.

## 변경 이력
- **v2 (Architect APPROVE_WITH_CHANGES, Critic REVISE 반영)**
  1. 도착을 Manhattan/40으로 바꾸고 엔진에서 A*를 없앴다. A*는 active 영역의 이동 중 시민만 지연 실행하고, 미준비면 그리지 않는다. 스펙 그대로인 대체안 C2를 문서화했다. 숨김 탭 벤치마크(960 tick ≤ 50 ms)를 추가했다(G5).
  2. boundingSphere를 지도를 덮는 고정 구로 바꿨다(`WebGLRenderer.js:1934-1936` 근거). §2, §7, §10을 수정했다.
  3. mesh 생성을 ChunkLayer 패턴(`<group ref onClick>` + effect)으로 바꿨다. `<primitive>`와 useMemo 생성을 금지했다.
  4. `polyOf[i]`를 추가했다. 프레임 루프는 PathService나 LRU를 조회하지 않는다.
  5. instanceColor를 선생성하고 매 프레임 범위 업데이트한다. count 0이면 visible=false, setsRef null이면 visibleCount 0이다.
  6. 수를 바꿀 때 speed 유지, 시민 선택 해제, tick 0 재시작을 정했다. 초기 출발은 randInt(1,6)이다.
  7. `citizenCpuMs`를 전체 시민 프레임 작업으로 정의했다. 성능표에 x1/x16 행, 경로 큐와 miss, long task, GL renderer 문자열을 넣었다. A* 벤치마크 목표는 avg/p99 0.2 ms다.
  8. 패널 휘발 필드를 ref/textContent로 갱신하게 했다. P3-AC9는 선택 상태에서 측정한다(G4).
  9. P3-AC7에 `expectedFresh`(새 엔진 독립 기대값)와 시계 드리프트 검사를 추가했다.
  10. `CitizenLayerApi`와 `write` 시그니처를 고정했다. `renderCount.ts`를 T1 소유로 옮겼다. T6의 phase-03 완료 기록 예외를 명시했다.
  11. AC4는 시민별 이벤트 시퀀스로 비교한다. AC2는 backend 파일 정규식 대조와 `satisfies Record<keyof CitizenDTO, true>`로 확인한다. `cash_balance: number | null`.
  12. CDP 빈 타일은 `isQuietTile`로 고르고 재시도한다. AC14의 AC1–4 확인 경로를 명시했다.
  13. 알려진 한계를 추가했다(시각 점프 0.5–0.7 tile, x16 클릭 난이도, tick 재시작 등).
  14. T3 모델을 opus로 올렸다. T0에 CLAUDE.md frontend 상태 줄 갱신을 넣었다.
  15. 게이트를 G1–G5로 정리하고 각각 권장안을 적었다.
- **v1**: 초안.

## 12. 상태
**pending approval** — 사용자 게이트 G1–G5 답변 후 T0부터 실행한다.

### v3 (리드 반영, Critic APPROVE 후 Minor 정정 — 실행 시 그대로 따른다)
1. P3-AC7 드리프트 검사: 훅이 `{ now: performance.now(), tick: clock.tickAt(now) }`를 한 번의 evaluate 안에서 함께 반환하고, 그 쌍으로 Δ를 계산한다(직전 프레임 `lastTick` 사용 금지).
2. G5 = C2가 선택되면 §3·§4·§9를 고친 v3 재검토를 먼저 한다(이 계획은 C1 전제).
3. 문구 정정: "프레임 루프는 PathService/LRU를 조회하지 않는다" → "그려지는 시민의 위치 계산은 PathService/LRU를 조회하지 않는다". `paths.request(i, …)`는 시민별 멱등(이미 큐/해결된 요청은 무시)이어야 한다.
4. 모호함 정리: `CitizenDebugInfo.current` = SoA x/z(경로 미준비면 approx 표기). `expectedFresh`는 T3(CitizenSystem)가 구현. 숨김 동안 도착한 시민은 `expectedFresh`가 idle 위치를 반환. 줄 번호: ChunkLayer.tsx `:40`→`:43`, `:52`→`:54`. `isQuietTile` 후보가 없으면 스캔 반경을 늘리고, 그래도 없으면 물 타일 허용. AC2의 `../backend` 읽기는 로컬 전용(현재 CI 없음).

## 13. 사용자 게이트 결정 (v4, 2026-11-19) — 이 절이 앞선 절과 충돌하면 이 절이 우선한다

- **G1**: Mock 전용 값 `employment_status` EMPLOYED/UNEMPLOYED, `current_activity` IDLE/MOVING. 문서에는 값 목록 TBD 유지, 모르는 값은 기본색.
- **G2**: `?citizens=` 없으면 100명. 측정은 URL로 0/100/500/1000.
- **G3**: 권장안(±2 chunk + 같은 도로망 연결 요소) 채택.
- **G4**: 권장안(ref/textContent로 0.5 s 갱신, React 재렌더 0) 채택.
- **G5 = C1 + 사용자 보강 규칙**:
  1. 도착 시간 산정 공식: `arrivalTick = departureTick + max(1, ceil((|x2−x1| + |y2−y1|) / TILES_PER_TICK))`, `TILES_PER_TICK = 40`. 40은 **"시뮬레이션 1 Tick당 시민이 이동할 수 있는 타일 수"라는 도메인 규칙**으로 문서(02-domain, 07-simulation-rules 또는 03-citizen §4.4)에 명시한다. 좌표는 출발/도착 건물 입구 도로 타일.
  2. **이 공식의 소유자는 Python 시뮬레이션 엔진이다.** 프론트는 departure/arrival Tick을 받아 표현만 한다. Phase 3의 공식 구현은 `src/render/citizens/mock/` 아래 Mock 엔진에만 두고 "임시 Mock, 영구 도메인 로직 아님, Phase 4~5에서 엔진 값으로 대체"라고 주석·문서에 명시한다. 렌더/이동 모듈은 이 공식을 import하지 않는다(테스트로 import 경계 확인). 엔진 코드는 이번에 수정하지 않는다(문서에 Python 참고 구현 시그니처만 기록).
  3. **과거 이동 재실행 금지(렌더 쪽)**: 화면 복귀·배속·숨김 탭 후에는 현재 Tick만 조회한다. 이미 끝난 이동은 즉시 도착(idle) 상태로 표시하고, 진행 중인 이동만 보간한다. 렌더 계층은 지난 이동의 경로를 절대 계산하지 않는다. Mock 엔진이 자기 일정(출발/도착 Tick 산술, A* 없음)을 진행하는 것은 엔진 대역 역할로 허용하되 O(밀린 이동 수) 산술만 하고, 렌더 쪽 비용과 분리해 측정한다.
  4. **PathFinder 스케줄러** (ChunkManager의 프레임당 8개처럼 별도 작업 예산):
     - 화면에 보이는(visible chunk 내) **이동 중** 시민만 경로 요청 등록.
     - 같은 (출발 건물, 도착 건물) 경로는 캐시 재사용.
     - 카메라 이동으로 대상에서 빠지면 대기 중 요청 **취소**.
     - 프레임당 처리량 제한(시간 예산 1 ms 또는 N건, 상수로 노출).
     - 경로가 아직 없으면 **간략한 위치 표시**(출발·도착 입구 사이 직선 보간, 시간은 동일)로 그리고, 경로가 준비되면 다음 프레임부터 경로 위치로 전환. (§3의 "경로 미준비 시 그리지 않음"을 대체한다. 알려진 한계: 짧은 순간 직선 이동이 건물 위를 지날 수 있음.)
     - 경로 탐색이 실측 병목이면 Web Worker 이전을 후속 작업으로 기록(이번 범위 아님).
  5. **도로망 접근성 검증**: 맵 생성/건물 배치 단계에서 모든 건물 입구가 유효한(주 연결 요소) 도로망에 연결되는지 검증한다. 연결되지 않은 건물은 생성기에서 배치하지 않거나(권장) 목적지 후보에서 제외. 생성기 테스트에 "모든 건물 입구 ∈ 주 연결 요소" 단언 추가. (Phase 2 `map/generator.ts` 수정 — 작업 T2에 포함, 시드 결과가 바뀌므로 건물 수 하한 테스트 재조정.)
  6. 정확한 교통 시뮬레이션은 목표가 아니므로 Manhattan 기반 시간과 실제 경로 길이 차이(시각 속도 차이)는 초기에는 허용한다(알려진 한계 유지).
- 확장성 메모(문서): 렌더 비용(보이는 시민 수에 비례)과 시뮬레이션 비용(엔진 소유)을 분리해 시민 10만 명까지 독립적으로 관리한다는 원칙을 phase-03 문서에 적는다.
- 상태: **approved — 사용자 승인(2026-11-19), team 실행.**
