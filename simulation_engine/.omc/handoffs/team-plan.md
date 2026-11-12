## Handoff: team-plan → team-exec

- **Decided**: 스펙 deep-interview-engine-skeleton.md 그대로 실행. 3 worker 파일 단위 분할 — skeleton(haiku): simulation_engine/{pyproject.toml,README.md,src/**,tests/**} / docs-engine(sonnet): docs/03-architecture/03-simulation-engine.md, docs/04-development/04-simulation-convention.md / docs-rules(sonnet): docs/02-domain/07-simulation-rules.md, docs/03-architecture/02-tech-stack.md, docs/04-development/06-testing-guide.md, 루트 README.md, 루트 CLAUDE.md.
- **Rejected**: team-prd 단계(스펙에 AC 11개 이미 있음), 별도 planner(분해가 자명).
- **Risks**: Tick=1시간 변경이 문서 간 불일치 유발 가능 → 두 docs worker에 동일 결정 전달. OMC MCP state 도구가 ~/.omc로 해석됨 → 팀 state는 이 파일로 대체.
- **Files**: 위 목록
- **Remaining**: team-verify — 리드가 AC 1–11 직접 검증 (unittest 실행, .omc 위치, docs 일관성).
