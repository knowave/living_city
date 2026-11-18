## Handoff: team-plan → team-exec
- **Decided**: 3 workers in parallel. docs (sonnet) edits only /docs + root CLAUDE.md; deps (haiku) owns package.json/yarn.lock + removes src/map, public/maps; scene (sonnet) owns src/render/**, src/App.tsx, src/index.css, new tests.
- **Rejected**: sequential docs→code (user asked parallel; design already fixed in spec, files disjoint).
- **Risks**: scene worker must wait for deps install before running checks; R3F/drei versions vs React 19.
- **Files**: spec .omc/specs/deep-interview-3d-rendering-setup.md
