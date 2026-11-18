# Deep Interview Spec: 3D Rendering Environment (Three.js + R3F)

## Metadata
- Interview ID: lc-fe-3d-render-20261117
- Rounds: 3 (+ Round 0 topology)
- Final Ambiguity Score: 19.5%
- Type: brownfield
- Generated: 2026-11-17
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED (pending approval)

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.85 | 0.35 | 0.2975 |
| Constraint Clarity | 0.80 | 0.25 | 0.200 |
| Success Criteria | 0.75 | 0.25 | 0.1875 |
| Context Clarity | 0.80 | 0.15 | 0.120 |
| **Total Clarity** | | | **0.805** |
| **Ambiguity** | | | **0.195** |

## Topology
| Component | Status | Description | Coverage |
|-----------|--------|-------------|----------|
| ① Docs update | active | PixiJS-based docs → Three.js/R3F, done BEFORE code (CLAUDE.md rule) | AC 1 |
| ② 3D environment | active | Install three/R3F/drei, remove Pixi deps, module folders under `src/render/` | AC 2-3 |
| ③ Scene rendering | active | Ortho isometric camera, 64×64 terrain grid, sample roads, ~10 box buildings | AC 4-6 |
| ④ Camera controls | active | drei MapControls: drag pan, cursor zoom, no rotate, limits | AC 7 |

## Goal
Replace the PixiJS rendering plan with a Three.js + React Three Fiber rendering module living inside the frontend (`src/render/`, not a separate app), and render a navigable isometric city prototype: a 64×64 tile terrain with sample roads and ~10 type-colored box buildings, viewed through a fixed-angle OrthographicCamera with drag-pan and zoom.

## Constraints
- 3D engine is an internal frontend module, rendered from `App.tsx` via R3F `<Canvas>`. Not a separate package/app.
- Module root: `frontend/src/render/` with subfolders created now: `city-map/` (terrain + roads), `buildings/`, `camera/`. Do NOT create `citizens/`, `animation/` yet.
- Remove: deps `pixi.js`, `pixi-viewport`, `@pixi/tilemap`; folders `src/map/`, `public/maps/`.
- Add deps: `three`, `@react-three/fiber`, `@react-three/drei`, dev `@types/three`. Versions must be mutually compatible with React 19.
- Coordinates: 1 tile = 1 world unit. Tile (x, y) maps to world XZ plane; Y is up. Tile coords stay separate from world coords (docs principle) via one small conversion function.
- Camera: `OrthographicCamera`, fixed isometric angle (yaw 45°, pitch ≈35.264° = atan(1/√2)), looking at map center.
- Controls: drei `MapControls` — left-drag pan, wheel zoom toward cursor (`zoomToCursor`), `enableRotate=false`, min/max zoom, pan target clamped to the 64×64 map bounds.
- Sample data hardcoded in source (no API, no Tiled). Buildings typed by `RESIDENTIAL | COMMERCIAL | OFFICE | PUBLIC` (docs/02-domain), each type with distinct color and height; buildings have tileX, tileY, width, height (footprint).
- Roads: sample road tiles rendered in a distinct color on top of terrain.
- Yarn 4, oxlint, Vitest, Tailwind unchanged. `.omc` stays only at frontend root.

## Non-Goals
- Chunk loading/unloading, 512×512 performance map.
- Building/tile selection (picking), citizens, animation, pathfinding.
- REST/SSE integration, Zustand stores.
- Camera rotation, perspective camera, textures/models (boxes and flat colors only).

## Acceptance Criteria
- [ ] 1. Docs updated before code: `docs/03-architecture/02-tech-stack.md`, `04-map-rendering.md`, `docs/04-development/03-frontend-convention.md`, `docs/05-phases/phase-01-map-prototype.md`, `docs/01-product/01-overview.md`, `docs/03-architecture/01-system-architecture.md`, `docs/01-product/04-roadmap.md` (and root `CLAUDE.md` frontend status/stack lines) no longer describe PixiJS/pixi-viewport/@pixi/tilemap/Tiled as the frontend renderer; they describe Three.js + R3F + OrthographicCamera isometric view, `src/render/` layout, 1 tile = 1 world unit. Chunk design (32×32) is kept. `.omc/backup/README.original.md` untouched.
- [ ] 2. `package.json` has three, @react-three/fiber, @react-three/drei, @types/three; no pixi packages. `yarn install` succeeds.
- [ ] 3. `src/render/{city-map,buildings,camera}/` exist with code; `src/map/` and `public/maps/` removed.
- [ ] 4. `yarn dev` shows a full-window canvas: 64×64 grid terrain, sample roads in a different color, ~10 box buildings with per-type color/height, no console errors.
- [ ] 5. View is isometric via OrthographicCamera (no perspective distortion; parallel edges stay parallel).
- [ ] 6. Unit test (Vitest) for tile→world coordinate conversion (tile center, map center) passes.
- [ ] 7. Left-drag pans the map, wheel zooms toward cursor within min/max limits, rotation impossible, panning cannot leave the map bounds far.
- [ ] 8. `yarn typecheck`, `yarn lint`, `yarn test`, `yarn build` all pass.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| Docs (PixiJS) are source of truth | README changed to Three.js; CLAUDE.md says ask on conflict | User: update docs to Three.js as part of this work (Round 0) |
| Keep Pixi deps alongside | Round 0 option | Remove Pixi deps and Tiled folders (Round 3) |
| Scene content | Round 1 | 64×64 flat grid + sample roads + ~10 typed box buildings |
| Hand-rolled controls | Round 2 | drei MapControls, no rotation, bounded |
| Module root | Round 3 | `src/render/` with only needed subfolders |
| 64×32px isometric tile size (docs) | Not asked; 2D sprite unit doesn't apply to 3D | Docs restated as 1 tile = 1 world unit with ortho iso camera — flag if user disagrees |

## Technical Context
- `frontend/`: Vite 8, React 19, TS ~7.0, Yarn 4.18.1 (node-modules), oxlint, Vitest 5 (env node), Tailwind 4; `main.tsx` has StrictMode + QueryClientProvider; `App.tsx` is a single Tailwind `<h1>`.
- README dir structure: `frontend/3D Rendering Engine (Three.js)`: city-map, buildings, citizens, camera, animation.
- Domain: Building type RESIDENTIAL/COMMERCIAL/OFFICE/PUBLIC, tileX, tileY, width, height (docs/02-domain, README §3.6).

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Terrain | core | 64×64 tiles, grid | contains Roads, hosts Buildings |
| Road | core | tile coords | rendered on Terrain |
| Building | core | type, tileX, tileY, width, height | placed on Terrain tiles |
| Tile coordinate | supporting | x, y | converted to world coords |
| OrthographicCamera | supporting | yaw 45°, pitch ≈35.26°, zoom | controlled by MapControls |
| MapControls | supporting | pan, zoom, limits | drives OrthographicCamera |
| Docs | supporting | 7 files + CLAUDE.md | updated before code |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 6 | 6 | - | - | - |
| 2 | 7 | 1 | 0 | 6 | 86% |
| 3 | 7 | 0 | 0 | 7 | 100% |

## Interview Transcript
<details>
<summary>Full Q&A (4 rounds)</summary>

### Round 0
**Q:** 4 components: docs update / 3D env / scene / camera controls?
**A:** 4개 모두 진행

### Round 1
**Q:** 64×64 flat grid, ~10 hardcoded typed box buildings, fixed iso ortho camera?
**A:** 도로도 포함
**Ambiguity:** 34.5%

### Round 2
**Q:** drei MapControls, drag pan, cursor zoom with limits, no rotation, bounded pan?
**A:** 예
**Ambiguity:** 27.75%

### Round 3
**Q:** Root `src/render/` with city-map/buildings/camera; remove src/map, public/maps, Pixi deps?
**A:** 예
**Ambiguity:** 19.5%
</details>
