# Deep Interview Spec: 3D Render Gaps (20 buildings, click-to-ID, average FPS)

## Metadata
- Interview ID: lc-fe-3d-gaps-20261118
- Rounds: 2 (+ Round 0 topology)
- Final Ambiguity Score: 16.5%
- Type: brownfield
- Generated: 2026-11-18
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED (pending approval)

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.88 | 0.35 | 0.308 |
| Constraint Clarity | 0.80 | 0.25 | 0.200 |
| Success Criteria | 0.80 | 0.25 | 0.200 |
| Context Clarity | 0.85 | 0.15 | 0.1275 |
| **Total Clarity** | | | **0.8355** |
| **Ambiguity** | | | **0.165** |

## Topology
| Component | Status | Description | Coverage |
|-----------|--------|-------------|----------|
| ① Docs update | active | Add 20 buildings / click-to-ID / average FPS to phase-01 doc before code (CLAUDE.md rule) | AC 1 |
| ② 20 buildings | active | Grow hardcoded `BUILDINGS` in `src/render/buildings/Buildings.tsx` from 10 to 20 | AC 2 |
| ③ Click → ID | active | Click a building to show its ID/type in a top-left HTML panel, highlight it | AC 3-5 |
| ④ Average FPS | active | useFrame-based counter, top-right HTML panel with current FPS and cumulative average | AC 6-7 |

## Goal
Close the three gaps found by verification in the `src/render/` prototype: render 20 basic-geometry (box) buildings, show the clicked building's ID, and display average FPS — with docs updated first.

## Constraints
- Docs first: update `docs/05-phases/phase-01-map-prototype.md` (deliverables / done criteria) before code. Do not touch `.omc/backup/README.original.md`.
- Buildings: keep b1–b10 unchanged; add b11–b20 as hardcoded sample data, boxGeometry only, mixing the 4 types (RESIDENTIAL/COMMERCIAL/OFFICE/PUBLIC). Footprints must not overlap roads (row 20, column 30) or each other, and stay inside 64×64.
- Click: R3F pointer events on building meshes. Selected state lives in component state (no Zustand). Top-left HTML overlay (outside `<Canvas>`, Tailwind) shows e.g. `Selected: b7 (OFFICE)`. Selected building gets a highlight color. Clicking empty ground (terrain) clears the selection. A drag-pan release must not count as a click (use R3F `event.delta` threshold, e.g. > 4px ignored).
- FPS: no new dependency. Count frames in `useFrame` inside the Canvas; publish to a top-right HTML overlay every 0.5s: `FPS` = frames in the last ~1s, `Avg` = total frames ÷ elapsed seconds since mount. No performance target.
- Existing camera behavior (pan/zoom/clamp/no-rotate) must keep working. Yarn 4, oxlint, Vitest unchanged. `.omc` only at frontend root.

## Non-Goals
- Zustand store, building detail panel beyond ID/type, tile selection, hover effects.
- Performance targets, stats.js / drei `<Stats />`, frame-time graphs.
- Building data from API, InstancedMesh refactor for buildings.

## Acceptance Criteria
- [ ] 1. `phase-01-map-prototype.md` lists 20 sample buildings, click-to-show-ID, and average FPS display; docs updated before code.
- [ ] 2. Scene shows 20 box buildings (b1–b20), no overlap with roads/each other, all within the map.
- [ ] 3. Clicking a building shows `Selected: <id> (<TYPE>)` in a top-left panel and highlights that building.
- [ ] 4. Clicking empty terrain clears the selection (panel shows none/hidden, highlight removed).
- [ ] 5. Drag-panning the camera and releasing over a building does not change the selection.
- [ ] 6. Top-right panel shows `FPS` and `Avg` numbers updating about every 0.5s, with plausible values (> 0).
- [ ] 7. Pan, zoom-to-cursor, clamp still work; no console errors.
- [ ] 8. A small unit test covers the pure logic added (e.g. building footprints don't overlap roads/each other, or FPS average math); `yarn typecheck`, `yarn lint`, `yarn test`, `yarn build` pass.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| Docs mention FPS | grep found none in docs | Add to phase-01 doc (Round 0) |
| ID display form | Round 1 | Top-left HTML panel + highlight, empty click clears, drag ≠ click, local state |
| "Average" FPS meaning | Round 2 | Current (1s) + cumulative average, useFrame, 0.5s refresh, no target |
| Placement of new 10 buildings | Not asked (threshold met) | Keep b1–b10, add b11–b20 non-overlapping, mixed types — flag if user disagrees |

## Technical Context
- `src/render/buildings/Buildings.tsx`: `BUILDINGS` array (b1–b10), `STYLE` per type, one `<mesh>` + `boxGeometry` per building.
- `src/render/CityScene.tsx`: `<Canvas>` with lights, `IsometricCamera`, `Terrain`, `Roads`, `Buildings`. `src/App.tsx` wraps it in `h-screen w-screen` div — overlays go here.
- `src/render/city-map/coords.ts`: `MAP_SIZE`, `tileRectToWorld`. Roads: row 20 and column 30.
- Camera: drei `MapControls` (left-drag pan) — click vs drag must be distinguished.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Building | core | id, type, tileX, tileY, width, height | 20 placed on Terrain; clickable |
| Selection | supporting | selected building id or null | set by building click, cleared by terrain click |
| SelectionPanel | supporting | id, type text | shows Selection (top-left) |
| FpsMeter | supporting | frames, elapsed, current, average | counts in useFrame |
| FpsPanel | supporting | FPS, Avg | shows FpsMeter (top-right) |
| Docs | supporting | phase-01 doc | updated first |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 5 | 5 | - | - | - |
| 2 | 6 | 1 | 0 | 5 | 83% |

## Interview Transcript
<details>
<summary>Full Q&A (3 rounds)</summary>

### Round 0
**Q:** 4 components: docs / 20 buildings / click-ID / average FPS?
**A:** 4개 모두 진행

### Round 1
**Q:** Top-left panel `Selected: b7 (OFFICE)`, highlight, empty click clears, drag ≠ click, local state?
**A:** 예, 그대로
**Ambiguity:** 25.5%

### Round 2
**Q:** useFrame counter, top-right panel with FPS (1s) + cumulative Avg, 0.5s refresh, no target?
**A:** 예, 그대로
**Ambiguity:** 16.5%
</details>
