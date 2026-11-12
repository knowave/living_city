# Deep Interview Spec: Living City Frontend Environment Setup

## Metadata
- Interview ID: lc-fe-setup-20261111
- Rounds: 2 (+ Round 0 topology)
- Final Ambiguity Score: 19.5%
- Type: greenfield
- Generated: 2026-11-11
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: yes
- Status: PASSED (pending approval)

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.85 | 0.40 | 0.340 |
| Constraint Clarity | 0.75 | 0.30 | 0.225 |
| Success Criteria | 0.80 | 0.30 | 0.240 |
| **Total Clarity** | | | **0.805** |
| **Ambiguity** | | | **0.195** |

## Topology
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| Project foundation | active | Vite + React + TS + Tailwind, lint, Vitest, dev proxy | AC 1-6 |
| Rendering foundation | skeleton | PixiJS 8, pixi-viewport, @pixi/tilemap | Deps installed + `src/render/` only; no canvas (user, Round 0: "골격만") |
| Tiled map pipeline | skeleton | Tiled JSON/tileset loading | `src/map/` + `public/maps/` only; no loader |
| Data layer | skeleton | Zustand, TanStack Query, SSE | Deps installed + `src/stores/`, `src/api/`; QueryClientProvider wired in main; no stores/hooks |

## Goal
Scaffold `living_city/frontend` as a working Vite + React + TypeScript app, styled with Tailwind, with every stack dependency from the README installed and empty folders reserved for rendering, map, state, and API code.

## Constraints
- Package manager: Yarn 4 pinned via corepack (`packageManager` field), `.yarnrc.yml` with `nodeLinker: node-modules`. No pnpm/npm lockfiles.
- Node 24 (installed).
- Dev proxy: `/api` → `http://localhost:8000` (backend FastAPI, prefix `/api/v1`, no CORS configured — proxy is required).
- Tailwind CSS v4 via `@tailwindcss/vite`.
- ESLint flat config from the Vite react-ts template.
- Runtime deps: react, react-dom, pixi.js@8, pixi-viewport, @pixi/tilemap, zustand, @tanstack/react-query. SSE uses native `EventSource` (no dep). Tiled is an external editor (no dep).

## Non-Goals
- No Pixi canvas / viewport mounted, no isometric math, no chunk manager.
- No Tiled map loader, no sample map assets.
- No Zustand stores, no SSE hook, no API query hooks beyond what is needed to verify the proxy.

## Acceptance Criteria
- [ ] `yarn install` succeeds with Yarn 4, producing `node_modules/` and `yarn.lock`.
- [ ] `yarn dev` serves a blank page with a visible Tailwind-styled element.
- [ ] With backend running on :8000, `GET /api/v1/health` through the Vite dev server returns `{"status":"ok"}`.
- [ ] `yarn typecheck`, `yarn lint`, `yarn test` (Vitest, ≥1 trivial test), `yarn build` all pass.
- [ ] `src/render/`, `src/map/`, `src/stores/`, `src/api/` exist (with `.gitkeep`), plus `public/maps/`.
- [ ] All README stack packages present in `package.json` (pixi.js 8.x).

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| Build all four components now | Round 0 topology | Only foundation; others skeleton |
| pnpm (installed) | Round 1 | User: use yarn |
| Yarn classic (installed 1.22) | Round 2 | Yarn 4 + node-modules linker |

## Technical Context
- Backend: `../backend/app/main.py` FastAPI, `API_V1_STR="/api/v1"`, uvicorn :8000, only `/health` exists.
- README: 64×32 iso tiles, 32×32 chunks, REST + SSE `GET /worlds/{id}/events`.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Frontend project | core | package.json, scripts | uses PackageManager, proxies to Backend API |
| PackageManager | supporting | Yarn 4, node-modules linker | installs stack deps |
| DevProxy | supporting | /api → :8000 | forwards to Backend API |
| Backend API | external | /api/v1/health | consumed by frontend |
| Folder skeleton | supporting | render, map, stores, api | reserved for later phases |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 5 | 5 | - | - | - |
| 2 | 5 | 0 | 0 | 5 | 100% |

## Interview Transcript
<details>
<summary>Full Q&A (3 rounds)</summary>

### Round 0
**Q:** 4 components (foundation / rendering / Tiled / data layer) — topology right?
**A:** 골격만 (foundation only; others deps + folders)

### Round 1
**Q:** Done = blank Tailwind page, proxy to /api/v1/health, typecheck/lint/test/build pass, folders exist?
**A:** pnpm이 아니라 yarn 패키지를 사용하는 방향으로 해줘
**Ambiguity:** 24%

### Round 2
**Q:** Yarn 4 via corepack with node-modules linker?
**A:** Yarn 4 + node-modules
**Ambiguity:** 19.5%
</details>
