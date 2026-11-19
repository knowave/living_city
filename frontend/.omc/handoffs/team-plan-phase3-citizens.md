## Handoff: team-plan → team-exec (phase3-citizens)

- **Decided**: Plan .omc/plans/phase3-citizens.md v2+v3+§13(v4 user decisions, highest priority). G1 EMPLOYED/UNEMPLOYED + IDLE/MOVING mock-only; G2 default 100; G3 ±2 chunk same component; G4 panel via refs; G5 Manhattan arrival with TILES_PER_TICK=40 (domain rule, engine-owned) implemented ONLY in citizens/mock/ as temporary mock; render layer never replays past trips; PathFinder scheduler (visible moving only, cache, cancel, per-frame budget, straight-line fallback until path ready); generator validates every building entrance in main road component (Phase 2 map/generator.ts change, owned by T2).
- **Order**: T0 docs → T1 ∥ T2 → T3 (opus) → T4 ∥ T5 → T6 → lead verify (real GPU CDP, perf table).
- **Rejected**: arrival from A* path length (catch-up blowup), per-chunk citizen meshes, hiding citizens without path.
- **Risks**: R3F raycast/drag on moving instances, fixed boundingSphere, instanceColor before first render, StrictMode, Phase 2 CDP AC1–12 regressions.
- **Rule**: .omc only at frontend root; no new deps; backend/engine untouched.
