# Deep Interview Spec: Simulation Engine 골격

## Metadata
- Interview ID: 5f3c1e2a-engine-structure
- Rounds: 6 (+ Round 0 topology)
- Final Ambiguity Score: 14.5%
- Type: brownfield (docs, backend 존재 / simulation_engine 비어 있음)
- Generated: 2026-11-11
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: yes (Round 2 사용자 설계 제안 장문 요약)
- Status: PASSED — pending approval

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.90 | 0.35 | 0.315 |
| Constraint Clarity | 0.85 | 0.25 | 0.2125 |
| Success Criteria | 0.80 | 0.25 | 0.200 |
| Context Clarity | 0.85 | 0.15 | 0.1275 |
| **Total Clarity** | | | **0.855** |
| **Ambiguity** | | | **0.145** |

## Topology
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| 패키지 골격 | active | src 레이아웃 디렉터리·빈 모듈·pyproject | AC 1–5 |
| 테스트 기반 | active | unittest import smoke | AC 6–7 |
| 엔진 문서 갱신 | active | 03-simulation-engine, 04-simulation-convention, 07-simulation-rules 등 | AC 8–11 |
| 도메인 모델 구현 | deferred | 엔티티 필드·로직 | 2026-11-11 사용자: "골격만", "구현이 아니라 골격" |
| 엔진 입출력·Tick 파이프라인 구현 | deferred | advance(), 스케줄링 | 동일 |
| 결정적 난수 구현 | deferred | 시드·스트림 분리 | 동일 |
| 경제 원장·불변식 구현 | deferred | Account/Transaction/LedgerEntry | 동일 (Phase 5) |

## Goal
최상위 `simulation_engine/`에 System 중심(경량 ECS + 도메인 중심) 구조의 **독립 Pure Python 패키지 골격**을 만든다. 디렉터리와 책임이 적힌 빈 모듈만 두고 실행 로직은 넣지 않는다. 같은 구조와 규칙을 docs에 반영한다.

## Constraints
- 위치: `/Users/ian/private/living_city/simulation_engine/` 유지. backend 안으로 옮기지 않는다.
- 레이아웃: `simulation_engine/src/simulation_engine/` (src layout), 테스트는 `simulation_engine/tests/`.
- Pure Python = 표준 라이브러리만. 엔진 코드와 테스트 모두 서드파티 없음. uv/pytest 사용 안 함. 테스트는 `unittest`.
- `pyproject.toml`은 메타데이터만: name, version, requires-python >= 3.12, dependencies = [].
- 별도 `domain/` 패키지 금지. 엔진 패키지가 도메인 모델(entities)을 소유한다.
- 모듈에는 책임을 설명하는 docstring만 둔다. 클래스, 함수, 로직은 넣지 않는다 (`__version__` 상수 제외).
- `.omc`는 `simulation_engine/` 최상단에만 둔다. `src/`, `tests/` 아래에는 절대 만들지 않는다.
- 시간 규칙: 1 Tick = 시뮬레이션 1시간. 1배속 = 현실 2초에 시뮬레이션 1일(24 Tick). 배속 단계(정지/1/4/16)와 월 30일, 연 12개월은 유지.
- 문서를 먼저 갱신하고 코드를 만든다 (CLAUDE.md 문서 유지 규칙).

## Non-Goals
- SimulationEngine.advance(), SimulationSystem Protocol, WorldState, 엔티티 필드 등 실행 코드
- 난수, 경제 원장, 스케줄링, 이벤트 생성 구현
- backend 연동 (경로 의존성, import)
- 린터·포매터 도입

## 목표 디렉터리 구조
```
simulation_engine/
├── .omc/                      # 최상단에만
├── pyproject.toml
├── README.md                  # 실행 방법 (python -m unittest)
├── src/simulation_engine/
│   ├── __init__.py            # __version__ (engineVersion)
│   ├── engine.py              # Tick 진행·System 실행 순서 관리
│   ├── clock.py               # 시뮬레이션 시간·System 실행 주기
│   ├── context.py             # Tick 실행 컨텍스트
│   ├── entities/  {citizen, business, government, building}.py
│   ├── world/     {state, config, generator}.py
│   ├── systems/   {behavior, employment, payroll, consumption, business, government, movement}.py
│   ├── events/    {models, generator}.py
│   ├── policies/  {taxation, employment}.py
│   └── utils/     {probability, random}.py
└── tests/
    └── test_package.py        # import smoke
```

## Acceptance Criteria
- [ ] 1. 위 트리의 모든 디렉터리·파일이 존재하고, 각 하위 디렉터리에 `__init__.py`가 있다.
- [ ] 2. 각 모듈 파일에는 책임 docstring만 있다 (class/def 없음).
- [ ] 3. `__init__.py`에 `__version__` 문자열이 있다.
- [ ] 4. `pyproject.toml`의 `dependencies = []`, `requires-python = ">=3.12"`.
- [ ] 5. `simulation_engine/src`, `simulation_engine/tests` 아래 `.omc`가 없다.
- [ ] 6. `cd simulation_engine && PYTHONPATH=src python3 -m unittest`가 통과한다.
- [ ] 7. smoke 테스트가 `import simulation_engine`, `__version__` 존재, 모든 하위 모듈 import 가능을 확인한다.
- [ ] 8. `docs/03-architecture/03-simulation-engine.md`에 구성(Engine/Clock/WorldState/Entities/Systems/Events/Policies), 원칙(System은 시간 변경 금지, 전역 random 금지, 스냅샷 시 RNG 상태 복원, 외부 명령은 Tick 경계 적용), 디렉터리 구조, System 주기 표(검토안)를 반영한다.
- [ ] 9. `docs/04-development/04-simulation-convention.md`의 '패키지 구조 / 모듈 네이밍: TBD'를 채운다 (stdlib only, dataclass, Protocol, 정수 화폐). 린터는 TBD 유지.
- [ ] 10. `docs/02-domain/07-simulation-rules.md` 시간 규칙을 1 Tick = 1시간, 1배속 = 현실 2초/1일(24 Tick)로 갱신한다.
- [ ] 11. `docs/03-architecture/02-tech-stack.md`, `docs/04-development/06-testing-guide.md`, 루트 `README.md`, `CLAUDE.md`의 simulation_engine TBD/"비어 있음" 표기를 갱신한다 (Python>=3.12, stdlib only, unittest, 실행 명령).

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| uv + pytest로 backend와 통일 | 사용자: "pure python이라고 명시" | stdlib only, unittest |
| 엔진을 backend/src/living_city/simulation/에 둠 (사용자 제안) | CLAUDE.md와 .omc 규칙에 충돌 | 현재 경로 유지 |
| 1 Tick = 1일 (docs) | 사용자 제안 1시간 | 1시간으로 변경, 1배속은 2초/1일 유지 |
| 골격에도 최소 실행(advance) 포함 | 반론 모드 | 디렉터리만, 실행 코드 없음 |
| 테스트 도구 | 명시 답 없음 | 가정: unittest ("pure python" 근거) |
| `utils/random.py` 이름 | stdlib `random`과 이름 같음 | 사용자 제안 이름 유지. 패키지 내부 절대 import라 충돌 없음 |
| Household, Employment, Account 등 docs 엔티티 | 사용자 트리에 없음 | 골격에서 제외, 구현 phase에서 결정 |

## Technical Context
- docs/03-architecture/03-simulation-engine.md: 입출력과 실행 순서 11단계 정의.
- docs/04-development/04-simulation-convention.md: 패키지 구조·린터 TBD.
- backend: uv + pytest, `app/` 구조. 이번 작업에서는 손대지 않음.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| SimulationEngine | core | systems, rng | WorldState를 받아 System을 순서대로 실행 |
| SimulationClock | core | tick, 일/월/년 | Engine이 사용, System 주기 결정 |
| WorldState | core | world_id, seed, tick, citizens, businesses, government | Entities를 소유 |
| Entity | core | Citizen, Business, Government, Building | WorldState에 속함 |
| System | core | run(state, rng) -> events | Engine이 호출 |
| DomainEvent | core | - | System이 생성 |
| Policy | supporting | taxation, employment | System이 읽음 |
| TestSuite | supporting | unittest smoke | 패키지 검증 |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 4 | 4 | - | - | - |
| 2–3 | 8 | 5 | 0 | 3 | 38% |
| 4 | 8 | 0 | 0 | 8 | 100% |
| 6 | 8 | 0 | 0 | 8 | 100% |

## Interview Transcript
<details>
<summary>Q&A (6 rounds)</summary>

- R0 구성 확인 → 골격만 (1+6)
- R1 레이아웃 → src 레이아웃
- R2 개발 도구 → "uv 쓰는 이유?" → "pure python" → System 기반 설계 장문 제안
- R3 위치 → 현재 경로 유지
- R4 Tick 단위 → 1일 유지 → (사용자 정정) 1시간으로 변경
- R5 완료 기준 → 디렉터리만, 실행 코드 없음
- R6 1배속 → 하루 2초 유지. 사용자 확인: "구현이 아니라 골격"
</details>
