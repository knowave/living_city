# Frontend 컨벤션

> 근거: README §8, §9, §11.3. frontend/에는 Vite + React 스켈레톤이 있으며, `src/render/`, `src/stores/`, `src/map/`, `src/api/`, `public/maps/`는 현재 `.gitkeep`만 있는 빈 폴더다. (코드 기준)

- 타일 좌표(건물 배치·도로 연결성·경로 계산)와 화면 좌표(렌더링·마우스 선택·이동 애니메이션)를 분리한다. (README §8.1)
- 렌더링 계층은 Terrain, Road, World Entities, Overlay, React UI로 나눈다. (README §8.3)
- 렌더링 프레임 속도와 시뮬레이션 Tick은 독립적으로 동작한다. (README §8.4)
- 클라이언트가 계산한 애니메이션 위치는 영속 상태를 변경하지 않는다. (README §9.4)
- 중복 SSE 이벤트는 Sequence 기준으로 무시한다. (README §9.4)
- 시민의 매 프레임 위치는 서버와 주고받지 않는다. (README §9.2)

## 기술 스택 (코드 기준)

- 언어: TypeScript. `tsconfig.app.json`에서 `noUnusedLocals`, `noUnusedParameters`, `verbatimModuleSyntax`, `erasableSyntaxOnly`를 켠다. (`frontend/tsconfig.app.json`)
- 빌드 / 개발 서버: Vite 8 + `@vitejs/plugin-react` + `@tailwindcss/vite`. `yarn build`는 `tsc -b && vite build`를 실행한다. (`frontend/package.json`, `frontend/vite.config.ts`)
- 패키지 매니저: Yarn 4.18.1, `nodeLinker: node-modules`. (`frontend/package.json` packageManager, `frontend/.yarnrc.yml`)
- 스타일: Tailwind CSS v4. (`frontend/src/index.css`)
- 상태 / 서버 데이터: zustand, @tanstack/react-query. (`frontend/package.json`, `frontend/src/main.tsx`)
- 린터: oxlint. 규칙은 `react/rules-of-hooks`(error), `react/only-export-components`(warn)다. `yarn lint`로 실행한다. (`frontend/.oxlintrc.json`, `frontend/package.json`)
- 타입 검사: `yarn typecheck` = `tsc -b --noEmit`. (`frontend/package.json`)
- 테스트: Vitest 5, environment `node`. `yarn test`로 실행한다. (`frontend/vite.config.ts`, `frontend/src/smoke.test.ts`)
- 개발 프록시: `/api` 요청을 `http://localhost:8000`으로 넘긴다. (`frontend/vite.config.ts`)

## 디렉터리 구조 (코드 기준)

- `src/App.tsx`, `src/main.tsx`(StrictMode, QueryClientProvider 설정), `src/index.css`
- `src/render/`, `src/stores/`, `src/map/`, `src/api/`: 빈 폴더 (`.gitkeep`만 있음)
- `public/maps/`: 빈 폴더 (`.gitkeep`만 있음), `public/favicon.svg`

## 미정

- 코드 포매터 / 스타일 규칙(예: 들여쓰기, 세미콜론): TBD. 포매터 설정 파일이 없다. (코드 기준)
- 컴포넌트 배치 규칙(`src/render`와 `src/map`의 경계): TBD. 폴더가 비어 있다. (코드 기준)
