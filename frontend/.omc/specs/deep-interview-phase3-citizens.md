# Deep Interview Spec: Phase 3 — Citizen Rendering & Movement (Mock)

## Metadata
- Interview ID: lc-fe-phase3-citizens-20261119
- Rounds: 4 (+ Round 0 topology)
- Final Ambiguity Score: 17.2%
- Type: brownfield
- Generated: 2026-11-19
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: yes (user brief condensed; all goals/constraints/AC preserved below)
- Status: PASSED (pending approval)

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.88 | 0.35 | 0.308 |
| Constraint Clarity | 0.78 | 0.25 | 0.195 |
| Success Criteria | 0.82 | 0.25 | 0.205 |
| Context Clarity | 0.80 | 0.15 | 0.120 |
| **Total Clarity** | | | **0.828** |
| **Ambiguity** | | | **0.172** |

## Topology
| Component | Status | Description | Coverage |
|-----------|--------|-------------|----------|
| ⓪ Docs + data model | active | Docs first; citizen logical state (CitizenRead DTO + front-only MovementEvent) separated from render state; DTO→domain mapper | AC 1-3 |
| ① Mock citizen generator / mock engine | active | Seeded citizens (0/100/500/1000), issues movements (dest + integer arrival tick) | AC 4 |
| ② PathFinder | active | A* over road tiles using road connection bits; entrance road tile per building | AC 5 |
| ③ MovementSystem + SimClock | active | Fractional tick clock, time-based interpolation along path, right-side "sidewalk" offset | AC 6-7 |
| ④ CitizenRenderer + CitizenInstanceManager | active | One low-poly geometry + material, one InstancedMesh, no per-frame React | AC 8-9 |
| ⑤ Citizen visibility | active | Reuse Phase 2 chunk visible set; compact visible citizens into instance buffer | AC 10 |
| ⑥ Selection panel + measurement | active | Click citizen → panel (ID + state); 0/100/500/1000 perf table vs Phase 2 | AC 11-15 |

## Goal
On top of the unchanged Phase 2 chunked 512×512 city, render 100→1,000 seeded mock citizens with one shared low-poly geometry/material in a single InstancedMesh, moving along the road network (A*) with time-based interpolation driven by a logical SimClock that keeps running off-screen, show only citizens inside visible chunks, allow clicking a citizen to see its ID and state in a React panel, never re-render React per frame, and measure FPS / draw calls / CPU / memory at 0/100/500/1000 citizens against the Phase 2 baseline — with a data model that later accepts REST `CitizenRead` + SSE `citizen.movement.started` unchanged.

## Data Model (docs first)
- Citizen DTO = backend `CitizenRead` (backend/app/schemas/city.py) field-for-field, snake_case: id, world_id, household_id, name, age, home_building_id, current_building_id, employment_status, employer_id, happiness, health, skills, risk_tolerance, consumption_preference, current_activity, current_destination, arrival_tick, cash_balance. Domain = camelCase via mapper (same pattern as Phase 2 `map/mapper.ts`).
- Logical location is building-based (`current_building_id`); moving ⇔ `current_destination != null` and `arrival_tick != null`.
- Front-only `MovementEvent` DTO: `{ citizen_id, from_building_id, to_building_id, start_tick, arrival_tick }` (integer ticks, matching BigInteger `arrival_tick`). Documented as "frontend assumption; proposed payload for SSE `citizen.movement.started`; backend not yet defined". Backend NOT modified.
- Render state (world position, heading, instance slot) is derived each frame from (MovementEvent, SimClock tick, path); never stored back into logical state or sent anywhere.
- Idle citizens are drawn standing beside their current building's entrance road tile (visible, clickable).

## Time Model
- `SimClock`: fractional current tick; `MOCK_TICK_SECONDS = 10` (1 tick = 10 real seconds at speed 1), speed 1/4/16 (UI control). Documented as TBD / mock-only; replaced by server tick under SSE later.
- Movement interpolates uniformly along the path over [start_tick, arrival_tick] (speed varies with path length).
- Mock engine: arrival_tick = start_tick + max(1, ceil(pathTiles / 40)); after arrival, dwell an integer number of ticks (seeded), then pick a new random destination building (seeded); unreachable → pick another. No economic/decision logic.
- Off-screen, tab-hidden, slow-frame cases all derive from the same clock → no drift.

## Path / Sidewalk
- Tile schema v1 unchanged. Walkable = road tiles (LOCAL, ARTERIAL incl. bridges over water). A* on 4-neighbour grid using road connection bits; uniform cost 1; Manhattan heuristic.
- Endpoint = first road tile edge-adjacent to the building footprint (generator guarantees one).
- "Sidewalk" is visual only: citizens walk offset ~0.35 tile to the right of travel direction. Docs: "보행로 = 도로 타일 가장자리의 시각적 표현".
- Path cache allowed (by from/to building pair) with bounded size.

## Constraints
- Docs first: update `docs/05-phases/phase-03-citizen-movement.md` (scope = mock, tasks, done criteria from this spec; SSE-based criteria moved to Phase 4~5), `docs/03-architecture/04-map-rendering.md` §8.4 (citizen rendering, visibility, sidewalk, time model), `docs/02-domain/03-citizen.md` (logical vs render state, MovementEvent as frontend assumption, tick seconds TBD). Never touch `.omc/backup/README.original.md`.
- Do not modify simulation_engine, backend, or the 14 entity schemas. No REST/SSE. No economic/decision logic in frontend.
- Reuse Phase 2: ChunkManager untouched in behaviour; citizen visibility consumes the existing `computeChunkSets` result (no second camera-frustum system); existing camera controls/AC1-12 must keep passing.
- Per-frame updates in `useFrame` mutate instance buffers only; React state changes only on selection, citizen-count change, speed change. HUD stays on its 500 ms interval.
- One shared geometry + one material for citizens; one InstancedMesh sized to the max count (1000), `count` = visible citizens; instanceMatrix usage DynamicDraw; dispose on unmount / count change.
- No new dependencies. Naming: avoid colliding with `chunks/visibility.ts` (e.g. `citizens/citizenVisibility.ts`).
- `.omc` only at frontend root.

## Non-Goals
- REST/SSE wiring, server tick sync, backend/engine/schema changes.
- Citizen decision-making, economy, households, schedules.
- Vehicles, crowd avoidance/collisions, skeletal animation, LOD models.
- Tile schema change for sidewalks.

## Acceptance Criteria
- [ ] 1. Docs updated first (phase-03, 04-map-rendering §8.4, 03-citizen) incl. MovementEvent assumption, tick seconds TBD, sidewalk definition.
- [ ] 2. Citizen DTO fields == `CitizenRead`; mapper DTO→domain unit-tested; MovementEvent type defined.
- [ ] 3. Logical state contains no world coordinates; render state computed from (event, tick, path) — unit test: same inputs ⇒ same position.
- [ ] 4. Mock generator: same seed ⇒ identical citizens and movement sequence; counts 100/500/1000; every citizen has unique UUID, home/current building, and a destination when moving.
- [ ] 5. PathFinder: path only over road tiles, consecutive tiles 4-adjacent and connected per road bits, starts/ends at building entrance tiles; unreachable returns null; unit tests incl. bridge over water.
- [ ] 6. MovementSystem: position at start_tick = path start, at arrival_tick = path end, monotonic progress; sidewalk offset applied; unit-tested.
- [ ] 7. Off-screen continuity: a citizen hidden for N ticks reappears at the position the clock dictates (CDP check vs computed expectation).
- [ ] 8. One InstancedMesh, one geometry, one material for all citizens (scene inspection via dev hook).
- [ ] 9. React: during 10 s of movement at 1000 citizens, CityScene / panels render count does not increase (dev render counter).
- [ ] 10. Visibility: instance `count` == citizens inside visible chunks; off-screen citizens not uploaded; draw calls 0→1000 citizens increase by ≤ 2.
- [ ] 11. Selection: clicking a citizen shows ID, name, current_activity, moving/idle, current building, destination, arrival_tick (+ current tick); highlight; empty click clears; drag ≠ click; building selection still works (one selection at a time).
- [ ] 12. Stepped rendering 0/100/500/1000 via dev HUD buttons and `?citizens=`.
- [ ] 13. Perf table (real GPU, 1920×1080) for 0/100/500/1000: FPS, draw calls, triangles, geometries, heap after GC, movement+visibility CPU ms (avg/max per frame); movement CPU avg < 2 ms/frame at 1000; 0 long tasks during continuous pan/zoom.
- [ ] 14. Existing CDP checks AC1–AC12 still PASS with citizens enabled.
- [ ] 15. `yarn typecheck`, `yarn lint`, `yarn test`, `yarn build` pass; report known limitations.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| Citizens have a "current position" | Schema only has building ids + arrival_tick | Building-based logical location; coordinates are render state (R1) |
| Start tick / origin exist | Not in CitizenRead; SSE payload undefined | Front-only MovementEvent, documented as proposal (R1) |
| Tick real-time known | Not in docs (TBD) | MOCK_TICK_SECONDS=10, speed 1/4/16, mock-only (R2) |
| arrival_tick fractional | Schema is integer | Integer start/arrival; fractional only for interpolation; departures cluster at tick boundaries (known limitation) (R2) |
| Sidewalk tiles exist | Schema v1 has none | Walk on road tiles, visual right-side offset, no schema change (R3) |
| Instanced culling is automatic | InstancedMesh culls as one sphere | Compact visible citizens via chunk visible set; count = visible (R4) |
| Panel contents / model / dual selection | Not asked (threshold met) | Panel fields per AC11; low-poly = merged cylinder body + head, colour by employment_status; single shared selection between building & citizen — flag if user disagrees |

## Technical Context
- Phase 2: `src/render/map/{types,tiles,mapper,generator,prng}.ts` (CityMap, buildingById, buildingsByChunk, road decode), `chunks/{visibility.ts (computeChunkSets), ChunkManager.ts, ChunkLayer.tsx}`, `perf/{DebugMeter,DebugHud,fps}.tsx` (window.__lcDebug), `CityScene.tsx` (selectedId state, statsRef), `camera/IsometricCamera.tsx` (stable onChange), `scripts/cdp-pan-check.mjs` (AC5–AC12).
- Phase 2 baseline (real GPU, 1920×1080, zoom 20): 52 active chunks, 49 draw calls, ~66k tris, 25 geometries, 60 FPS, heap ≈29 MB, 0 long tasks during interaction; startup long tasks 70–116 ms.
- Backend: `CitizenRead` (schemas/city.py), `GET /worlds/{id}/citizens/{citizenId}`; SSE event name `citizen.movement.started` with undefined payload; "시민의 매 프레임 위치는 전송하지 않는다" (07-rest-sse.md).
- Docs: 1 Tick = 1 sim hour (07-simulation-rules.md); §4.4 / §8.4 movement principles.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Citizen (logical) | core | CitizenRead fields | located at Building; has 0..1 active MovementEvent |
| MovementEvent | core | citizen_id, from_building_id, to_building_id, start_tick, arrival_tick | produced by mock engine (later SSE) |
| SimClock | core | currentTick (fractional), speed, MOCK_TICK_SECONDS | drives MovementSystem |
| Path | supporting | road tile sequence | computed by PathFinder between building entrances |
| CitizenRenderState | supporting | position, heading, instance slot | derived per frame; never persisted |
| CitizenInstanceManager | supporting | InstancedMesh, count, slot→citizen map | renders visible citizens |
| Chunk visible set | supporting | from computeChunkSets | filters citizens |
| CitizenPanel | supporting | selected citizen id/state | React, updates on selection |
| Building | core (existing) | id, tileX, tileY, width, height | origin/destination; entrance road tile |
| RoadTile | core (existing) | class, connection bits | walkable graph |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 8 | 8 | - | - | - |
| 2 | 9 | 1 (SimClock) | 0 | 8 | 89% |
| 3 | 10 | 1 (RoadTile) | 0 | 9 | 90% |
| 4 | 10 | 0 | 0 | 10 | 100% |

## Known Limitations (accepted)
- Departures/arrivals align to integer tick boundaries (schema), so movement starts cluster every 10 s at speed 1.
- Citizens pass through each other (no avoidance); sidewalk is a visual offset only.
- Tick-seconds and MovementEvent payload are frontend assumptions until backend defines them.

## Interview Transcript
<details>
<summary>Full Q&A (5 rounds)</summary>

### Round 0
**Q:** 7 components (docs+model, mock generator, PathFinder, MovementSystem, renderer/instance, visibility, selection+measurement)?
**A:** 이대로 진행

### Round 1
**Q:** CitizenRead DTO, building-based logical location, front-only MovementEvent, render position derived, idle citizens at entrance?
**A:** 예 — Ambiguity 41%

### Round 2
**Q:** SimClock fractional tick, MOCK_TICK_SECONDS=10, speed 1/4/16, uniform interpolation to arrival_tick, mock engine 40 tiles/tick + seeded dwell/redestination?
**A:** 예 — Ambiguity 33%

### Round 3
**Q:** Road tiles walkable, A* with road connection bits, entrance tile, right-side visual sidewalk offset, no schema change?
**A:** 예 — Ambiguity 27%

### Round 4 (contrarian: is instanced culling automatic?)
**Q:** Chunk-visible compaction into instance buffer, 0/100/500/1000 HUD+URL, measurement table & thresholds?
**A:** 예 — Ambiguity 17.2%
</details>
