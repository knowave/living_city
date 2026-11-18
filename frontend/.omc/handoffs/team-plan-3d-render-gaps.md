## Handoff: team-plan → team-exec (3d-render-gaps)

- **Decided**: 3 workers. docs-worker (haiku) edits phase-01 doc FIRST; then scene-worker (sonnet) owns Buildings.tsx, CityScene.tsx, App.tsx, new SelectionPanel + wiring; fps-worker (haiku) owns new src/render/perf/{fps.ts,fps.test.ts,FpsMeter.tsx,FpsPanel.tsx} only.
- **Interface**: `<FpsMeter onUpdate={(s: FpsStats) => void} />` inside Canvas; `<FpsPanel stats={FpsStats | null} />` outside Canvas; `FpsStats = { fps: number; avg: number }`. scene-worker wires both.
- **Rejected**: drei Stats (no cumulative avg), Zustand selection (user said local state).
- **Risks**: drag-release counted as click (use e.delta > 4 ignore); Terrain click to clear selection — use onPointerMissed on Canvas or Terrain onClick.
- **Files**: see owners above. Nothing else touched.
