# Deep Interview Spec: Chunk-based 512×512 City Rendering (Mock data, REST-ready model)

## Metadata
- Interview ID: lc-fe-chunk-render-20261118
- Rounds: 5 (+ Round 0 topology)
- Final Ambiguity Score: 16.3%
- Type: brownfield
- Generated: 2026-11-18
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED (pending approval)

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.87 | 0.35 | 0.3045 |
| Constraint Clarity | 0.80 | 0.25 | 0.200 |
| Success Criteria | 0.82 | 0.25 | 0.205 |
| Context Clarity | 0.85 | 0.15 | 0.1275 |
| **Total Clarity** | | | **0.837** |
| **Ambiguity** | | | **0.163** |

## Topology
| Component | Status | Description | Coverage |
|-----------|--------|-------------|----------|
| ⓪ Docs + data model | active | Docs first (tile ID schema v1, phase-02), then TS DTO (snake_case) + domain (camelCase) types + mapper | AC 1-3 |
| ① MapGenerator | active | Seeded deterministic 512×512 map: 256 chunk DTOs + building DTOs | AC 4 |
| ② ChunkManager | active | Activate/deactivate chunks by camera, dispose GPU resources on release | AC 6-7 |
| ③ VisibilityManager | active | Visible chunk set from camera view + 1-chunk prefetch ring | AC 6, 8 |
| ④ ChunkRenderer | active | Per-chunk terrain + road (with direction/class) rendering | AC 5 |
| ⑤ BuildingRenderer + InstanceManager | active | Buildings by position/type/size; InstancedMesh for repeated terrain/buildings; click select kept | AC 9-10 |
| ⑥ Verification | active | Debug HUD, automated pan round-trip leak script, unit tests, FPS report | AC 6-12 |

## Goal
Replace the 64×64 hardcoded prototype with a chunked 512×512 city (32×32-tile chunks, 256 total) generated from a seed by a mock MapGenerator whose output matches backend `ChunkRead` / `buildings` shapes exactly, rendered through ChunkManager + VisibilityManager (only visible chunks + 1 ring), ChunkRenderer (terrain + directional/class roads), and BuildingRenderer/InstanceManager (InstancedMesh, minimal draw calls), without memory leaks under frequent camera movement — so that later the REST `GET /worlds/{id}/chunks` response can be plugged in through the same mapper.

## Data Model (schema_version 1) — must be written to docs first
- Chunk DTO = backend `ChunkRead` (backend/app/schemas/city.py): `id (uuid str), world_id, chunk_x, chunk_y, chunk_size (=32), terrain_tiles: number[1024], road_tiles: number[1024], schema_version, revision`. Tile index = `local_y * 32 + local_x`. World tile = `chunk_x*32 + local_x`.
- Building DTO = backend `Building` model (backend/app/models/building.py; no API yet): `id (uuid str), world_id, type (RESIDENTIAL|COMMERCIAL|OFFICE|PUBLIC), tile_x, tile_y, width, height, capacity, occupied_capacity, status`.
- Frontend domain types are camelCase (`chunkX`, `terrainTiles`, `tileX`, `occupiedCapacity`…); a pure mapper converts DTO → domain. MapGenerator emits DTOs (snake_case) and the app always goes through the mapper, so a REST response can replace the generator 1:1.
- terrain_tiles: 0 = GRASS, 1 = WATER, 2 = SAND.
- road_tiles: `value = (class << 5) | connection`; 0 = no road. connection: 1–15 = direction bitmask N(−y)=1, E(+x)=2, S(+y)=4, W(−x)=8; 16 = isolated road. class: 0 = LOCAL (values 1–16), 1 = ARTERIAL (values 33–48); future classes use 2+. Connection is computed against neighboring road tiles regardless of class, including across chunk borders.
- Unknown terrain/road values render as GRASS / no road and log one console warning.

## Constraints
- Docs first (CLAUDE.md): update `docs/03-architecture/04-map-rendering.md` (tile ID schema v1, road encoding, chunk managers), `docs/03-architecture/06-database.md` (map_chunks tile value meaning), `docs/05-phases/phase-02-chunk-rendering.md` (tasks + done criteria from this spec) before code. Do not touch `.omc/backup/README.original.md`. Backend code is NOT changed.
- Mock only: no fetch, no REST, no SSE, no TanStack Query wiring. Seed is a code constant.
- MapGenerator: deterministic PRNG (e.g. mulberry32/sfc32 seeded), deterministic UUIDs derived from the PRNG (valid v4 format). Same seed ⇒ deep-equal output; different seed ⇒ different. Produces a road network (arterial grid + local streets), water/sand areas, and buildings placed only on non-road, non-water tiles, non-overlapping, footprint within map; buildings may span chunk borders.
- Chunk geometry/material/InstancedMesh resources created on activate must be disposed on deactivate (no orphaned GPU resources). Shared materials/geometries are reused, not recreated per chunk.
- Visibility: visible chunk set from the orthographic camera's view footprint on the ground plane, plus one ring of neighbors for prefetch; everything else inactive. Recompute on camera change (throttled/when chunk set changes).
- Camera: clamp to 0..512, start at map center, zoom limits chosen so even max zoom-out shows a bounded subset (not all 256 chunks).
- Click selection kept: clicking an instanced building shows `Selected: <id> (<TYPE>)` and highlights it (instanceId → building id); empty click clears; drag ≠ click.
- Existing FPS panel kept and extended into a debug HUD: FPS/Avg, active chunks / 256, draw calls (`gl.info.render.calls`), geometries/textures (`gl.info.memory`).
- New code under `src/render/` (e.g. `src/render/map/` for model/generator/mapper, `src/render/chunks/`, `src/render/buildings/`). No new dependencies. Yarn 4, oxlint, Vitest. `.omc` only at frontend root.

## Non-Goals
- Backend API/SSE connection, building endpoint, DB changes.
- Citizens, animation, pathfinding, road meshes with curves/sidewalks, textures/3D models beyond boxes.
- Tile editing, chunk revision updates, LOD beyond culling.
- 60 FPS guarantee.

## Acceptance Criteria
- [ ] 1. Docs updated first with tile ID schema v1, road encoding, chunk managers, phase-02 tasks/done criteria.
- [ ] 2. TS DTO types match backend `ChunkRead` and `Building` field-for-field (snake_case); camelCase domain types + mapper; mapper unit-tested (incl. unknown value fallback).
- [ ] 3. Tile index helpers (`local_y*32+local_x`, world↔chunk↔local) unit-tested.
- [ ] 4. MapGenerator: 256 chunks (chunk_x/y 0..15), each array length 1024, chunk_size 32, schema_version 1, revision 1; same seed deep-equal, different seed differs; road connection values consistent with neighbors (incl. cross-chunk); buildings non-overlapping, off road/water, in bounds — all unit-tested.
- [ ] 5. Screen shows terrain (3 colors), roads with class colors and direction marks, buildings with per-type color/height on a 512×512 map; no console errors.
- [ ] 6. Debug HUD shows FPS, Avg, active chunks/256, draw calls, geometries, textures.
- [ ] 7. Panning across the map loads chunks ahead and unloads behind; at default zoom active chunks = visible + 1 ring, ≪ 256.
- [ ] 8. Automated CDP round-trip script (pan across map ≥ 5 times and back): geometry/texture counts return to baseline (± small constant), JS heap does not grow monotonically (compare after forced GC if available).
- [ ] 9. Buildings appear at correct tile position and size (unit test of placement transform + screenshot); buildings spanning chunk borders render once.
- [ ] 10. Draw calls stay low and roughly constant w.r.t. building count (instanced: O(active chunks × layers), not O(buildings)); measured value reported.
- [ ] 11. Click selection works on instanced buildings (panel + highlight; empty click clears; drag ≠ click).
- [ ] 12. FPS measured (headless reference value reported; desktop measured by user); `yarn typecheck`, `yarn lint`, `yarn test`, `yarn build` pass.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| Tile ID meanings exist | Not defined in docs/code (TBD-like) | Defined by user: terrain 0/1/2; road `(class<<5)|connection` (Rounds 1-3) |
| Roads are on/off | User wanted direction + class | 4-dir bitmask + isolated 16 + LOCAL/ARTERIAL |
| How to prove no leak / culling | Round 4 | Debug HUD + CDP round-trip script + unit tests |
| Keep 64×64 prototype | Round 5 | Replace with 512 map; keep click select; camera clamp 512 |
| snake_case everywhere | Round 5 | camelCase domain + mapper from snake_case DTO |
| Buildings API shape | No buildings endpoint exists | Mirror backend Building model fields; flag when API is added |

## Technical Context
- backend: `app/models/map_chunk.py` (CHUNK_SIZE 32, arrays len 1024 CHECK), `app/schemas/city.py` (`ChunkRead`, `ChunkRangeQuery`), `GET /api/v1/worlds/{id}/chunks?x_min..y_max`; `app/models/building.py` (no read schema / endpoint).
- frontend: `src/render/CityScene.tsx` (Canvas, selection state, FpsMeter/FpsPanel), `camera/IsometricCamera.tsx` (MapControls, clamp uses MAP_SIZE 64), `city-map/{coords.ts,Terrain.tsx,Roads.tsx}`, `buildings/{buildingData.ts,Buildings.tsx,SelectionPanel.tsx}`, `perf/{fps.ts,FpsMeter.tsx,FpsPanel.tsx}`.
- Docs: `04-map-rendering.md` §8.2 (256 chunks for 512 map), `06-database.md` map_chunks, `phase-02-chunk-rendering.md`.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| ChunkDTO / Chunk | core | id, worldId, chunkX, chunkY, chunkSize, terrainTiles, roadTiles, schemaVersion, revision | 256 per world |
| Tile | core | index, terrainId, roadId | 1024 per chunk |
| TerrainId | supporting | GRASS/WATER/SAND | value in terrainTiles |
| RoadId | supporting | class, connection mask | value in roadTiles |
| RoadClass | supporting | LOCAL, ARTERIAL | part of RoadId |
| BuildingDTO / Building | core | id, worldId, type, tileX, tileY, width, height, capacity, occupiedCapacity, status | placed on tiles, may span chunks |
| DTO Mapper | supporting | toChunk, toBuilding | DTO → domain |
| MapGenerator | supporting | seed | produces DTOs |
| Camera/Visibility | supporting | view footprint, ring | selects active chunks |
| InstancedMesh | supporting | per chunk/layer | renders tiles/buildings |
| DebugHUD | supporting | fps, avg, chunks, calls, memory | shows metrics |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 9 | 9 | - | - | - |
| 2 | 9 | 0 | 0 | 9 | 100% |
| 3 | 10 | 1 | 0 | 9 | 90% |
| 4 | 10 | 0 | 0 | 10 | 100% |
| 5 | 11 | 1 | 0 | 10 | 91% |

## Interview Transcript
<details>
<summary>Full Q&A (6 rounds)</summary>

### Round 0
**Q:** 7 components (docs+model, generator, chunk mgr, visibility, chunk renderer, building/instance, verification)?
**A:** 이대로 진행

### Round 1
**Q:** Tile IDs: terrain 0/1/2, road 0/1?
**A:** 도로 방향까지 포함 — Ambiguity 38%

### Round 2
**Q:** Road direction bitmask N1 E2 S4 W8, isolated 16?
**A:** 도로 종류도 구분 — Ambiguity 34%

### Round 3
**Q:** road = (class<<5)|connection, LOCAL 0 / ARTERIAL 1?
**A:** 예 — Ambiguity 30.8%

### Round 4
**Q:** Verify via debug HUD, CDP round-trip leak script, unit tests, FPS report?
**A:** 예 — Ambiguity 22%

### Round 5
**Q:** Replace 64 scene, keep click select, camera 512 clamp, snake_case types?
**A:** camelCase 변환 (domain camelCase + mapper; rest accepted) — Ambiguity 16.3%
</details>
