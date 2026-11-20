# Deep Interview Spec: Simulation Engine v1

## Metadata
- Interview ID: engine-v1-2026-11-19
- Rounds: 10 (+ Round 0 topology)
- Final Ambiguity Score: 15%
- Type: brownfield
- Generated: 2026-11-19
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: yes
- Status: PASSED — pending approval

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| Goal Clarity | 0.90 | 0.35 | 0.315 |
| Constraint Clarity | 0.85 | 0.25 | 0.213 |
| Success Criteria | 0.80 | 0.25 | 0.200 |
| Context Clarity | 0.85 | 0.15 | 0.128 |
| **Total Clarity** | | | **0.855** |
| **Ambiguity** | | | **0.145** |

## Topology
| Component | Status | Description | Coverage |
|---|---|---|---|
| 세계 생성 | active | 시드로 건물·시민·가구·기업·계좌·초기 자본 생성 | AC1–AC3 |
| Tick 실행·재현·Snapshot | active | 1/N Tick 진행, Tick 경계 명령, 결정적 RNG, Snapshot 복구 | AC4, AC14–AC16 |
| 시민 행동 | active | 출근·귀가·소비·취업·실직, 이동 출발/도착 Tick | AC5–AC7 |
| 경제 | active | 급여·소득세·운영비(B2B/정부/외부)·복지·공공 조달·기업 상태 | AC8–AC12 |
| 출력 | active | Domain Event, 도시 통계 | AC13, AC17 |
| 성능 측정 | active (비필수) | 100/1k/10k Tick 시간·메모리 측정, 통과 조건 아님 | AC19 |

## Goal
FastAPI·PostgreSQL 없이 Pure Python으로 동작하는 시뮬레이션 엔진 v1을 만든다. 시드로 시민 100명·기업 10개 도시를 생성하고, 1 Tick 또는 N Tick 진행 시 시민·기업·정부가 고용·출퇴근·소비·급여·세금·운영비(B2B 중심)·복지·공공 조달로 상호작용하며, 모든 자금 이동은 합계 0인 원장 거래로 기록되고, 상태 변경은 Domain Event와 통계로 제공되며, 같은 입력이면 같은 결과가, Snapshot 복구 후에도 같은 결과가 나온다.

## Constraints
- 작업 순서: 현황 분석 → 기존 CLAUDE.md·docs 유지하며 엔진 전용 Phase 계획 → 구현. 설계 변경은 코드보다 docs 먼저.
- DB 스키마는 엔진 편의로 바꾸지 않는다. 실제 충돌이 확인될 때만 변경 검토.
- 엔진은 표준 라이브러리만 사용, backend/DB import 금지. 화폐는 정수(원), 비율은 bps.
- 전역 random 금지. 주입된 시드 RNG만 사용, 시민·기업 순회는 id 순.
- 1 Tick = 1시간, 하루 24 Tick, 월 30일, 연 12개월.
- 맵: 엔진은 건물(유형·타일 좌표)만 생성. 도로·MapChunk 생성은 v1 제외. 이동 시간은 03-citizen §4.4 맨해튼 공식(TILES_PER_TICK=40, 최소 1).
- 아래 수치는 모두 설정값(config)으로 둔다.

### 확정 규칙
**시민 상태 값**: employment_status = EMPLOYED, UNEMPLOYED. current_activity = AT_HOME, MOVING, WORKING, SHOPPING. 목적지는 current_destination으로 구분.

**하루 일과**
- 취업자: 08시 집 출발(MOVING) → 도착 시 WORKING. 18시 귀가 출발 → 도착 시 AT_HOME.
- 실직자: AT_HOME.
- 소비: 소비일당 1회. 소비일 = 19시 경계 기준(hour ≥ 19면 그날, 아니면 전날). (a) 19시에 AT_HOME이거나 (b) 19시 이후 집에 도착했을 때, 그 소비일에 아직 소비하지 않았으면 시드 RNG로 고른 운영 중(ACTIVE/DISTRESSED) RETAIL·RESTAURANT로 이동 → 도착 시 SHOPPING, PURCHASE 거래 → 귀가. 마감 시각 없음. 마지막 소비일은 엔진 내부 값(state.last_shop_day, snapshot 포함). 08시에 AT_HOME이 아니면(소비 이동 중) 그날 출근은 건너뛴다(급여 영향 없음). (2026-11-19 변경: 128 맵에서 19시까지 귀가하는 취업자가 약 16%뿐이어서)
- 일 소비액 = floor(지난달 세후 소득 × consumption_preference ÷ 10000 ÷ 30), 잔액 상한, 0원이면 외출 안 함. 지난달 소득 = 세후 급여 + 복지금. 첫 달: 취업자 월급의 85%, 실직자 0.

**월말 정산 순서** (월말 Tick 1회, 연쇄 없음)
1. 급여(SALARY) + 소득세(INCOME_TAX, WorldPolicy.income_tax_rate 기본 1500bps) → 정부 TREASURY. 급여 전액 미지급 기업은 BANKRUPT.
2. 운영비(OPERATING_EXPENSE): companies.operating_cost = 월 기준 운영비, 급여 미포함. 분배 B2B 70% / 정부(공공요금) 20% / 외부(SYSTEM CASH) 10%.
   - 공급 관계: RETAIL·RESTAURANT → WHOLESALE, WHOLESALE → BUSINESS_SERVICE, BUSINESS_SERVICE → WHOLESALE.
   - 동일 업종 공급자 여럿이면 운영 중인 곳에 균등 분할(나머지 원단위 id 순), 없으면 그 몫은 외부로.
   - 잔액 부족 시 미납 처리(음수 잔액·임의 매출 금지) → 재무 악화 판정에 반영.
   - metadata: expense_category, supplier_company_id, period_tick.
   - B2B 매출은 그 달 안에서 새 운영비를 만들지 않고 다음 평가에 반영.
3. 복지(WELFARE): 실직자에게 welfare_amount(기본 100만 원). 정부 잔액 부족 시 id 순으로 가능한 만큼.
4. 공공 조달(PUBLIC_PROCUREMENT): 예산 = (정부 잔액 − 다음 달 예상 복지액) × 50%. ACTIVE·DISTRESSED인 WHOLESALE·BUSINESS_SERVICE에 균등 분할, 나머지 id 순.
5. 기업 상태 평가 (월 고정비 = 급여 총액 + operating_cost)
   - ACTIVE → DISTRESSED: 현금 < 월 고정비 × 1 또는 운영비 미납.
   - DISTRESSED → ACTIVE: 현금 ≥ 월 고정비 × 2.
   - → BANKRUPT: 급여 전액 미지급 또는 DISTRESSED 3개월 연속. 모든 고용 종료, 거래 중단, 잔액은 계좌에 유지.
   - CLOSED: v1 미사용.
6. 채용·해고
   - 채용: ACTIVE, 방금 마감한 회계월의 잉여(매출 − 급여 − 실제 지급 운영비) > 0, 정원 여유 → 월 1명. 매출 = 시민 소비 + B2B + 공공 조달(통계는 세 항목을 따로 집계). 공공 조달은 상태 평가보다 먼저 실행되므로 당월 재무 상태와 채용 판단에 반영된다. 실직자 중 시드 RNG로 선택, salary = base_wage. 기업은 id 순 처리.
   - 해고: DISTRESSED → 월 1명, 최근 채용자부터.

### 2026-11-19 추가 결정 (12개월 실측 후)
배경: 기본 설정에서 BUSINESS_SERVICE가 5개월째 파산하고 연쇄 파산이 발생. 원인은 (1) B2B 기업 인원 과다, (2) 시민 저축 누적(소득 기반 소비만 존재), (3) 외부 유출만 있고 유입 없음. 유지: 운영비 70:20:10, 조달 50%, 소득세 15%, 기업 상태·파산 규칙, 기본 소비 성향 5000~9000bps.
- **누적 현금 추가 소비**: 월 소비 예산 = ⌊지난달 세후 소득 × 성향 / 10000⌋ + ⌊max(0, 보유 현금 − 생활 예비금) × 추가 소비율 / 10000⌋. 보유 현금은 월말 정산(급여·복지) 직후 값으로 고정해 월 1회 계산하고 엔진 내부 값 state.monthly_budget(snapshot 포함)에 저장. 일 소비액 = min(잔액, ⌊월 예산 / 30⌋). 시작값: 생활 예비금 4,000,000원, 추가 소비율 2000bps — 보정 대상. 첫 달 예산은 generator가 같은 식으로 초기 현금 기준 계산.
- **외부 자금 재유입(간소화 수출)**: 월말 공공 조달 다음, 상태 평가 전에 외부(SYSTEM/CASH) 잔액 × 수출 비율(bps, 보정 대상)을 운영 중 기업에 균등 분할(나머지 원단위 id 순). 거래 유형 EXPORT를 코드에만 추가(테이블 변경 없음). 매출 통계는 소비/B2B/조달/수출 네 항목으로 구분, 채용 잉여의 매출에 수출 포함, TOTAL_COMPANY_REVENUE에 포함.
- **초기 정원**: J1 수준(WHOLESALE 6, BUSINESS_SERVICE 2, RETAIL·RESTAURANT 12)을 출발점으로 보정. 초기 고용 = min(initial_employed, 정원 합).
- 보정 결과 수치는 사용자 승인 후 config 기본값과 docs에 기록.
- **승인된 보정안 C1 (2026-11-19)**: 기업당 정원 WHOLESALE 6, BUSINESS_SERVICE 2, RETAIL·RESTAURANT 12; 초기 고용 88명(정원 합); cash_reserve 1,000,000원; extra_spend_bps 3000; export_bps 5000. 결과: 시드 15개 36개월 파산 0, 내부 자금·국고·시민 현금 수렴, 외부 순유출 0. 알려진 한계: 60개월에는 12개 중 7개 시드에서 45~50개월째 소매·식당 손님 분배 편차로 연쇄 파산(신규 기업 설립 부재와 결합).

- **2026-11-19 마무리 결정**: (1) 상점 도착 Tick에 구매하고 SHOPPING으로 그 Tick을 마친 뒤 다음 Tick에 귀가 출발(화면 표시용 1 Tick 체류). (2) 복지는 국고 부족 시 id 순으로 전액 지급 가능한 시민까지만, 부분 지급 없음 — 확정.
- **2026-11-19 TBD 확정**: 운영비 부분 지급 없음(전액 미납) — 미납은 재무 악화 조건이며 최종 상태는 급여 미지급(즉시 BANKRUPT)·DISTRESSED 3개월(BANKRUPT)을 함께 평가해 결정, 미납 달에는 회복 없음. 조달: R = 복지금 × 실직자 수(복지 직후·채용 전), B = max(0, 국고 − R), P = ⌊B × 0.5⌋. TOTAL_COMPANY_REVENUE = 기업 수령 총매출(소비+B2B+조달+수출), GDP 아님, GDP 산정 v1 제외. employments.status 종료값 TERMINATED 단일, 사유는 이벤트 reason(hired/fired/bankruptcy), 이벤트 employment_status는 시민 상태(EMPLOYED/UNEMPLOYED). happiness 50·health 100 초기값 고정, 변화 규칙 v1 제외, AVERAGE_HAPPINESS는 초기 기준 지표.

**계좌·거래**
- 거래 유형 코드에 OPERATING_EXPENSE, PUBLIC_PROCUREMENT 추가 (엔진·backend enum, VARCHAR(32)·CHECK 없음 → 테이블 변경 없음).
- 외부 공급자 = SYSTEM/CASH 계좌, 초기 자본 = SYSTEM/ISSUANCE에서 OPENING_BALANCE (uq_accounts_system이 account_type별 1개 허용).
- 전체 계좌 합계 = 0 항상. 도시 내부 자금(시민+기업+정부)은 외부 유출만큼 감소 가능, 별도 집계.
- 통계에서 기업 매출은 최종 소비 / B2B / 공공 조달로 구분 (GDP 중복 방지).

**초기값**
- 시민 100명: 나이 20–64, consumption_preference 5000–9000bps(시드). 1인 1가구.
- 건물: 주거 10(정원 10), 상업 6, 사무 4, 공공 1. 128×128 타일 안 시드 배치.
- 기업 10개: RETAIL 3, RESTAURANT 3(상업 건물), WHOLESALE 2, BUSINESS_SERVICE 2(사무 건물). 정원 10, 초기 고용 90명.
- base_wage: RETAIL·RESTAURANT 240만, WHOLESALE 300만, BUSINESS_SERVICE 360만. operating_cost 기업당 월 500만.
- OPENING_BALANCE: 시민 300만, 기업 월 고정비 3개월치, 정부 5,000만.
- 보정 기준: 기본 시드로 3개월 진행 시 파산 0개. 안 맞으면 수치 조정 후 docs 기록.

## Non-Goals
- 도로·MapChunk 생성, 경로 탐색 (frontend 담당).
- 주거비(RENT), 공급망 4단계(생산 능력·거래처 변경·원자재 부족), 외부 투자 유입, CLOSED 상태.
- 신규 기업 설립 (파산은 비가역 — 장기 시뮬레이션의 알려진 한계로 docs에 기록).
- Simulation Runner, REST/SSE, DB 저장, 실시간 Tick 간격 (backend 영역).
- 10,000명 지원을 완료 조건으로 두는 것.
- 스키마 테이블 변경 (충돌 확인 시에만 별도 검토).

## Acceptance Criteria
- [ ] AC1 시드로 시민 100명·기업 10개·건물 21동·가구·계좌가 위 초기값대로 생성된다.
- [ ] AC2 초기 자본은 OPENING_BALANCE 거래로만 배분되고 생성 직후 전체 잔액 합계 = 0.
- [ ] AC3 생성 결과가 backend 14개 엔티티 필드·제약(소유자 구성, 음수 잔액 금지, employee_count ≤ capacity, 활성 고용 1개)을 만족한다.
- [ ] AC4 `step()`(1 Tick)과 `run(n)`(N Tick)이 동작하고, 정책 변경 명령은 effective_tick 경계에서 적용된다.
- [ ] AC5 취업자는 08시 출발·18시 귀가하고, 상태가 MOVING→WORKING→MOVING→AT_HOME으로 바뀐다.
- [ ] AC6 이동 시작 시 arrival_tick이 §4.4 공식과 일치하고 `citizen.movement.started` payload(citizen_id, from_building_id, to_building_id, start_tick, arrival_tick)가 나온다.
- [ ] AC7 19시 소비가 소득 기준 공식대로 PURCHASE 거래를 만들고 잔액을 넘지 않는다. 실직자(복지 없음)는 소비 0.
- [ ] AC8 월말 급여·소득세 15%가 정확히 이전되고 정부 TREASURY가 세금을 받는다.
- [ ] AC9 운영비가 70/20/10과 공급 관계대로 분배되며, 공급자 부재 시 외부로, 잔액 부족 시 미납 처리된다(음수 없음).
- [ ] AC10 복지와 공공 조달이 규칙대로 지급된다.
- [ ] AC11 기업 상태 전이(ACTIVE↔DISTRESSED, BANKRUPT)와 채용·해고가 규칙대로 일어나고, 파산 시 고용이 모두 종료된다.
- [ ] AC12 모든 Transaction의 LedgerEntry 합계 = 0, 매 Tick 전체 계좌 합계 = 0, 어떤 계좌도(ISSUANCE 제외) 음수가 아니다.
- [ ] AC13 상태 변경이 Domain Event(simulation.tick, citizen.employment.changed, citizen.movement.started, company.status.changed, economy.month.closed, metrics.updated, policy.updated)로 순서 번호와 함께 나온다.
- [ ] AC14 같은 시드·초기 상태·명령 순서·엔진 버전이면 N Tick 후 상태·이벤트·거래가 완전히 같다.
- [ ] AC15 Snapshot(RNG 상태, DISTRESSED 연속 개월, 지난달 소득, 이동 출발 Tick 포함)에서 복구 후 진행 결과가 중단 없이 진행한 결과와 같다.
- [ ] AC16 엔진 테스트가 FastAPI·SQLAlchemy·PostgreSQL 없이 `python -m unittest`로 통과하고, 엔진 패키지가 그 모듈들을 import하지 않는다.
- [ ] AC17 통계 12종 지표 코드와 매출 구분(최종 소비/B2B/조달), 도시 내부 자금을 계산한다.
- [ ] AC18 시드 42·1·7 각각 36개월 진행 시 파산 0개 (2026-11-19 강화, 보정안 C1 기준).
- [ ] AC19 (비필수) 시민 100/1,000/10,000명에서 Tick 처리 시간과 메모리를 측정해 기록한다.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|---|---|---|
| 맵은 엔진이 만든다 | 맵은 지금 frontend Mock이 생성 | 엔진은 건물만, 도로·청크는 v1 제외 |
| 운영비는 단순 지출 | 합계 0을 지키려면 받는 계좌가 필요 (반론) | B2B 70 / 정부 20 / 외부 10, 월 1회, 연쇄 없음 |
| 운영비에 거래 유형이 필요 없음 | PURCHASE+metadata로 대체 가능 | OPERATING_EXPENSE 추가 (테이블 변경 없음) |
| 기업 상태에 확률 필요 | 단순화 모드 | 결정적 규칙, 수치는 설정값 |
| 소비는 자산 기준 | 문서 예시는 소득 기준 | 지난달 세후 소득 기준 |
| 정부는 받기만 함 | 돈이 정부에 쌓임 | 복지 + 공공 조달 포함 |

## Technical Context
- 엔진 `simulation_engine/src/simulation_engine/`: 14개 backend 테이블을 미러링한 dataclass와 Account·LedgerEntry 검증만 있다. engine, clock, context, world/{state,config,generator}, systems/*, policies/*, events/generator, utils/*는 빈 스텁이다. 기존 테스트 24개는 데이터 구조만 검사한다.
- backend `backend/app/models/`: 14개 테이블. transaction_type은 String(32)이고 CHECK 제약이 없다. SYSTEM 계좌는 (world, account_type, currency)별로 하나씩 둘 수 있다. Company에는 매출 필드가 없어서 원장에서 계산한다.
- frontend Mock: `frontend/src/render/map/generator.ts`가 맵을 만든다. `citizens/types.ts`의 MovementEventDTO가 movement 이벤트의 데이터 형식이다.
- 계획 단계에서 정할 것:
  - 이벤트 sequence를 누가 매길지. 추천은 엔진이 매기고 snapshot의 last_event_sequence와 맞추는 것입니다.
  - Snapshot state_data 형식
  - RNG 스트림 분리 방식
  - 명령 목록. v1은 정책 변경만 다룹니다.
- 같이 갱신할 docs:
  - 03-citizen: TBD로 남은 상태 값 목록을 채웁니다.
  - 06-economy: 운영비, 조달, 외부 계좌, 매출 구분을 추가합니다.
  - 04-business: 상태 전이 규칙을 추가합니다.
  - 05-government: 복지와 조달을 추가합니다.
  - 03-simulation-engine: 월말 순서를 추가합니다.
  - 엔진 전용 phase 문서와 docs/README 목차를 갱신합니다.
- 같이 바꿀 backend 코드: TransactionType enum에 2개 값을 추가합니다.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|---|---|---|---|
| World | core | seed, current_tick, engine_version | 모든 엔티티 소유 |
| Building | core | type, tile_x, tile_y, capacity | 가구 거주, 기업 입주 |
| Citizen | core | employment_status, current_activity, current_destination, arrival_tick, consumption_preference | Household 소속, Employment 보유, Account 보유 |
| Company | core | industry, base_wage, operating_cost, status, employee_capacity | Employment, Account, 공급 관계 |
| Industry | supporting | RETAIL, RESTAURANT, WHOLESALE, BUSINESS_SERVICE | 공급 관계 정의 |
| Employment | core | salary, hired_tick, terminated_tick, status | Citizen–Company |
| Account | core | owner_type, account_type, balance | 시민·기업·정부·SYSTEM(ISSUANCE, CASH=외부) |
| Transaction / LedgerEntry | core | type, tick, idempotency_key, metadata / amount | 합계 0 |
| WorldPolicy | supporting | income_tax_rate, welfare_amount, effective_tick | 세금·복지 |
| WorldEvent | output | sequence, tick, type, payload | 상태 변경 기록 |
| WorldMetric | output | metric_code, value, period | 통계 |
| WorldSnapshot | output | tick, last_event_sequence, state_data | 복구 |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability |
|---|---|---|---|---|---|
| 1 | 9 | 9 | - | - | N/A |
| 4 | 12 | 3 | 0 | 9 | 75% |
| 7 | 12 | 0 | 0 | 12 | 100% |
| 10 | 12 | 0 | 0 | 12 | 100% |

## Interview Transcript
<details><summary>10 rounds</summary>

- R0 구성 요소 6개 → 그대로 확정
- R1 맵 → 엔진이 건물만 생성 (41%→37%)
- R2 규칙 수치 → 인터뷰에서 하나씩 결정 (36%)
- R3 상태 값 → EMPLOYED/UNEMPLOYED, AT_HOME/MOVING/WORKING/SHOPPING (33%)
- R4 운영비(반론) → B2B 중심 + 정부 + 외부, OPERATING_EXPENSE, 월 1회, 미납 시 재무 악화, 매출 구분 (29%)
- R5 업종 → 4업종, 공급 관계, 70/20/10 (26%)
- R6 기업 상태(단순화) → 결정적 전이·채용·해고 규칙 (22%)
- R7 일과·소비 → 일과 추천안, 소비는 지난달 세후 소득 기준 (20.6%)
- R8 정부 지출 → 복지 + 공공 조달 (21%)
- R9 조달 규칙 → 추천안 (19%)
- R10 초기값·매칭 → 추천안 (15%)
</details>
