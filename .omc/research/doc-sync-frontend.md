# doc-sync: frontend 문서 변경 로그

| 문서 | 변경 전 | 변경 후 | 코드 근거 |
|---|---|---|---|
| docs/04-development/03-frontend-convention.md | 근거 줄: "frontend/ 디렉터리는 비어 있다." | frontend 스켈레톤 존재, 하위 폴더는 `.gitkeep`만 있는 빈 폴더라고 명시 | frontend/src/, frontend/public/maps/ |
| docs/04-development/03-frontend-convention.md | "## 미정: 언어, 빌드 도구, 디렉터리 구조 TBD" | "## 기술 스택 (코드 기준)" 섹션 추가: TypeScript, Vite 8, Yarn 4.18.1, Tailwind v4, zustand/react-query, oxlint 규칙, typecheck, Vitest, dev 프록시 | frontend/package.json, frontend/tsconfig.app.json, frontend/vite.config.ts, frontend/.yarnrc.yml, frontend/.oxlintrc.json, frontend/src/main.tsx, frontend/src/index.css, frontend/src/smoke.test.ts |
| docs/04-development/03-frontend-convention.md | (없음) | "## 디렉터리 구조 (코드 기준)" 섹션 추가 | frontend/src/, frontend/public/ |
| docs/04-development/03-frontend-convention.md | "## 미정: 코드 스타일 / 린터 / 컴포넌트 규칙 TBD" | 린터는 기술 스택으로 이동, 포매터 및 컴포넌트 배치 규칙만 TBD로 남김 | frontend/ 에 prettier/editorconfig 설정 없음 |

docs/03-architecture/04-map-rendering.md: 변경 없음.

## 확인했으나 변경하지 않은 항목

- 04-map-rendering.md의 렌더링 라이브러리: 문서에 라이브러리 명시가 없다. 코드(`pixi.js` ^8, `@pixi/tilemap`, `pixi-viewport`)와 모순되지 않으므로 손대지 않았다.
- 04-map-rendering.md의 "카메라 기준 Chunk 생성/해제", "타일 인덱스 index = local_y * 32 + local_x (TypeScript도 같은 규칙)": `frontend/src/map/`이 비어 있어 코드로 검증할 수 없다. 설계 내용이므로 삭제하지 않았다.
- 04-development/03-frontend-convention.md의 SSE 중복 제거, 애니메이션 위치 비영속 규칙: 프론트 코드에 SSE/stores 구현이 없어 검증 불가. 설계 규칙이므로 유지.
