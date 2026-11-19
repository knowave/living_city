## Handoff: team-plan → team-exec (chunk-rendering)

- **Decided**: Approved plan .omc/plans/chunk-rendering.md (Critic APPROVE, Architect changes applied, v3). User gate: Q1 status mock 'ACTIVE' const + TBD in docs; Q2 no created_at/updated_at in Building DTO; Q3 A1 merged ground geometry per chunk + per-chunk building InstancedMesh; Q4 default zoom 20, MIN_ZOOM 12.
- **Order**: T0 docs (sonnet) → T1 model (sonnet) → T2 generator ‖ T3 chunks ‖ T5 CDP script (sonnet) → T4 scene integration (sonnet) → lead verify (run CDP + screenshots).
- **Rejected**: A2 global instance pool, A3 per-layer InstancedMesh (fallback only), per-chunk React components.
- **Risks**: ground normals/linear color, pending queue drain every frame, makeDefault on MapControls, gl.info counts only rendered geometries.
- **Rule**: .omc only at frontend root; no new deps; backend untouched.
