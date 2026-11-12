# Deep Interview Spec: README → docs/ 문서 분리

## Metadata
- Interview ID: li-docs-split-20261111
- Rounds: 4 (Round 0 + 3)
- Final Ambiguity Score: 18%
- Type: brownfield
- Generated: 2026-11-11
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED — pending approval

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| Goal Clarity | 0.85 | 0.35 | 0.30 |
| Constraint Clarity | 0.80 | 0.25 | 0.20 |
| Success Criteria | 0.80 | 0.25 | 0.20 |
| Context Clarity | 0.80 | 0.15 | 0.12 |
| **Total Clarity** | | | **0.82** |
| **Ambiguity** | | | **0.18** |

## Topology
| Component | Status | Description | Coverage |
|---|---|---|---|
| Content redistribution | active | README §1–§14 → docs/01-product, 02-domain, 03-architecture, 04-development/06-testing-guide | Mapping table below, verbatim rule |
| Entry docs | active | Root README.md (사람용: 소개 + 기술 스택 + 실행 방법), CLAUDE.md (AI용: 개발 지침 + 문서 참조 규칙), docs/README.md (목차 + 원본 대응표) | AC 4–6 |
| New docs | active | 04-development 01–05, .gitignore, .env.example | Evidence-only + TBD |
| Phases | active | 05-phases 5개 파일을 새 순서로 구성. 원본 Phase 1–7은 04-roadmap.md에 보존 | Phase mapping below |

## Goal
770줄짜리 단일 설계 명세 README.md를 사용자가 지정한 `docs/` 트리로 분리한다. 루트 README는 짧은 소개 문서로, CLAUDE.md는 에이전트가 읽는 진입 문서로 만든다. 원본 내용은 빠짐없이 옮긴다.

## Constraints
- 원본 문장은 수정하지 않는다. 헤딩 레벨과 번호만 조정할 수 있다. 한 섹션을 여러 파일에 중복해서 넣는 것은 허용한다.
- README에 없는 내용은 두 가지 근거로만 쓴다. (a) README에 명시된 원칙, (b) backend 코드에서 확인된 사실(Python ≥3.12, uv, FastAPI, pydantic-settings, pytest+httpx, `app/{api/v1,core,crud,db,models,schemas,services,utils}`, `.env` 키 `PROJECT_NAME`, `API_V1_STR`). 근거가 없는 부분은 `TBD`로 표시한다.
- **README.md는 사람이 읽는 문서다.** 프로젝트 소개, backend·frontend·simulation_engine 기술 스택, 실행 방법만 적는다. 실행 방법은 확인된 사실만 쓴다. backend는 `uv sync`, `uv run uvicorn app.main:app --reload`, `uv run pytest`이고, `.env.example`을 복사하라고 안내한다. frontend와 simulation_engine은 아직 비어 있으므로 TBD로 둔다. 상세 내용은 docs/README.md 링크 하나로 넘긴다.
- **CLAUDE.md는 AI가 읽는 문서다.** AI 개발 지침과 문서 참조 규칙을 담는다. 구성은 다음과 같다.
  1. 프로젝트 한 줄 요약과 핵심 원칙: §14 요약, 엔진의 프레임워크 독립, 정수 화폐, 자금 보존, 결정성, 서버가 최종 권한
  2. 문서 참조 규칙: 작업 종류별로 반드시 먼저 읽을 docs 파일 표. 도메인/엔진/렌더링/API/DB/테스트/phase 작업 각각에 대응 파일을 둔다.
  3. 개발 지침: 04-development 컨벤션 파일로 연결하고, 디렉터리별 책임(backend/frontend/simulation_engine)을 적는다.
  4. 문서 유지 규칙: 설계가 바뀌면 해당 docs 파일을 먼저 갱신하고, 문서와 코드가 충돌하면 사용자에게 확인한다.
- 원본을 덮어쓰기 전에 `.omc/backup/README.original.md`에 백업한다(git 저장소가 아니기 때문).
- `backend/.env.example`에는 (루트가 아닌 backend 전용으로 이동) 기존 키와 PostgreSQL 접속 정보 자리를 넣되 값은 비워 둔다. 실제 `backend/.env`의 값은 복사하지 않는다.
- 루트 `.gitignore`에는 Python, Node, env, OS, IDE 항목을 넣는다. `backend/.gitignore`는 그대로 둔다.

## Non-Goals
- 코드 변경, git init
- 명세 내용의 수정, 보완, 재설계
- 근거 없는 컨벤션 창작

## Section → File Mapping
| 원본 | 대상 |
|---|---|
| 헤더(Version 등), §1 | 01-product/01-overview.md |
| §14 | 01-product/01-overview.md, 03-architecture/01-system-architecture.md |
| §2.1, §11.1, §11.2, §13 | 01-product/02-requirements.md |
| §2.2, §2.3 | 01-product/03-features.md |
| §12 (Phase 1–7 전체) | 01-product/04-roadmap.md (+ 05-phases와의 대응 표) |
| §3 개요(엔티티 목록·관계, 새로 작성한 연결 문서) | 02-domain/01-domain-overview.md |
| §3.1, §3.6, §3.9, §3.10 | 02-domain/02-world.md |
| §3.2, §3.3, §4 | 02-domain/03-citizen.md |
| §3.4, §3.5, §5 | 02-domain/04-business.md |
| §3.7 | 02-domain/05-government.md |
| §3.8, §6 | 02-domain/06-economy.md |
| §2.1 시간 규칙(Tick·달력·배속), §6.3, §7.3, 정책의 Tick 경계 적용 | 02-domain/07-simulation-rules.md |
| §7.4, §11.2, §14 | 03-architecture/01-system-architecture.md |
| 기술 스택(§7.1, §8, §10, §14 + backend 사실) | 03-architecture/02-tech-stack.md |
| §7 | 03-architecture/03-simulation-engine.md |
| §8 | 03-architecture/04-map-rendering.md |
| §4.4, §7.2(9–10단계), §8.4, §9.3, §9.4 | 03-architecture/05-data-flow.md |
| §10 | 03-architecture/06-database.md |
| §9.1, §9.2 | 03-architecture/07-rest-sse.md |
| §11.3 | 04-development/06-testing-guide.md |

## Phase Mapping (05-phases)
| 파일 | 원본 출처 |
|---|---|
| phase-01-map-prototype | Phase 1 프로젝트 기반, Phase 2 PixiJS 초기화, 타일·도로, 카메라, 타일 선택 |
| phase-02-chunk-rendering | Phase 2 Chunk Manager, 건물 렌더링·깊이 정렬, 512×512 검증 |
| phase-03-citizen-movement | Phase 6 시민 이동 시각화, §4.4, §8.4 |
| phase-04-simulation-engine | Phase 1 도메인·엔진 인터페이스, Phase 3 전체 |
| phase-05-economic-system | Phase 4 전체 |
각 파일은 목표, 작업, 완료 기준으로 구성한다. 5개 파일 어디에도 들어가지 않는 Phase 5(REST/SSE), Phase 6의 나머지 항목, Phase 7은 04-roadmap.md에서 "향후 phase"로 표시한다.

## Acceptance Criteria
- [ ] 사용자가 지정한 트리의 모든 파일이 존재한다(docs 하위 30개 + 루트 4개).
- [ ] `.omc/backup/README.original.md`가 원본 README와 byte 단위로 동일하다.
- [ ] 원본 §1–§14의 모든 `###` 소절이 docs 안에 최소 한 번 존재하고, 본문 문장이 원문과 같다(스크립트로 검증).
- [ ] docs/README.md에 목차와 '원본 섹션 → 대상 파일' 대응표가 있다.
- [ ] 루트 README.md에는 소개, 3개 컴포넌트의 기술 스택, 실행 방법만 있다. backend 실행 명령은 실제로 동작한다(`uv run pytest` 통과).
- [ ] CLAUDE.md에 AI 개발 지침과 작업 종류별 문서 참조 규칙 표가 있고, 모든 링크가 실제 파일을 가리킨다.
- [ ] 04-development의 새 내용은 각각 README나 backend 근거로 추적할 수 있고, 근거가 없는 부분은 `TBD`로 표시되어 있다.
- [ ] `backend/.env.example`에 실제 비밀값이 없다.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|---|---|---|
| phase 파일 = README Phase | 구성과 순서가 다름 | 5개로 재구성하고 원본은 roadmap에 보존 |
| 컨벤션 문서는 채워야 함 | README에 근거가 없음 | 근거 기반으로 쓰고 나머지는 TBD |
| 원본 README를 줄여도 됨 | 복구 수단이 없음(git 아님) | .omc/backup에 백업하고 대응표 작성 |

## Technical Context
README.md 1개 파일(14개 섹션). backend: FastAPI 골격, alembic, pytest(test_health). frontend/와 simulation_engine/은 빈 디렉터리. 루트에는 CLAUDE.md, .gitignore, .env.example, docs/가 없음.

## Ontology
| Entity | Type | Relationships |
|---|---|---|
| Source README | core | 섹션이 docs 파일로 나뉨 |
| Docs file | core | 원본 섹션을 하나 이상 가짐 |
| Root README | supporting | 소개 + 기술 스택 |
| CLAUDE.md | supporting | 모든 docs 파일로 연결 |
| Phase | core | Roadmap 항목에서 파생 |
| Roadmap | supporting | 원본 Phase 1–7 보존 |
| Backup | supporting | Source README의 사본 |

## Ontology Convergence
| Round | Entities | New | Stable | Stability |
|---|---|---|---|---|
| 0 | 5 | 5 | - | - |
| 1 | 6 | 1 | 5 | 83% |
| 2 | 6 | 0 | 6 | 100% (+TBD policy) |
| 3 | 7 | 1 | 6 | 86% |

## Interview Transcript
<details><summary>4 rounds</summary>

- R0: 구성 확인 → README는 소개 + backend/frontend/simulation engine 기술 스택만, CLAUDE.md는 소개 + docs 읽기 안내.
- R1: 05-phases를 새 순서로 재구성하고 원본은 04-roadmap에 → 수락 (43%)
- R2: 새 문서는 근거 기반 + TBD → 수락 (32%)
- R3: 원문 유지, 대응표, 백업 → 수락 (18%)
- 추가 지시: CLAUDE.md = AI 개발 지침과 문서 참조 규칙, README.md = 사람이 읽는 프로젝트 소개와 실행 방법 → Constraints와 AC에 반영
</details>
