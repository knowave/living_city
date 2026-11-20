## Handoff: team-plan → team-exec (engine-v1)

Spec: /Users/ian/private/living_city/simulation_engine/.omc/specs/deep-interview-engine-v1.md (규칙·수치·AC의 단일 출처)
Engine root: /Users/ian/private/living_city/simulation_engine/src/simulation_engine/
Test cmd (simulation_engine/): `PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest`
Backend test (backend/): `uv run pytest`
커밋 금지. 표준 라이브러리만. 엔진에서 backend/fastapi/sqlalchemy import 금지. 화폐 int, 비율 bps.

### 계획 단계 결정 (docs에도 기록)
- **RNG**: 상태를 저장하지 않는 파생 스트림. `rng(seed, *keys)` = `random.Random(int.from_bytes(sha256(repr((seed,)+keys)).digest()[:8]))`. 키 예: ("shop", tick, citizen_id), ("hire", tick, company_id). 전역 random·hash() 금지. Snapshot의 RNG 상태 = seed. 처리 순서가 바뀌어도 다른 엔티티 결과가 흔들리지 않음.
- **ID**: 결정적 UUID. `new_id(kind)` = uuid.UUID(bytes=sha256(f"{seed}:{kind}:{n}")[:16], version=4), n은 kind별 카운터(state에 저장).
- **이벤트 sequence**: 엔진이 세계별 1부터 단조 증가로 부여. state.next_event_sequence에 저장, snapshot.last_event_sequence = next_event_sequence − 1. backend는 그대로 저장.
- **거래 idempotency_key**: f"{type}:{tick}:{주체 id}[:{보조}]" — 결정적.
- **Snapshot state_data**: {"format_version":1, "engine_version", "seed", "tick", 엔티티 목록(world, policies, buildings, citizens, households, companies, employments, accounts) dataclass→dict(UUID는 str), "engine": {next_event_sequence, id_counters, distressed_months, last_month_income, movement_starts, month_accumulators, unpaid_opex}}. 거래/원장/이벤트 이력은 snapshot에 넣지 않음(backend 테이블에 있음).
- **명령**: v1은 `PolicyChangeCommand(income_tax_rate, welfare_amount, effective_tick)` 하나. Tick 시작에 적용, version+1 WorldPolicy 추가, `policy.updated` 이벤트. 현재 정책 = effective_tick ≤ tick 중 최신 version.
- **시간**: tick t의 시각 = t % 24, 일 = t // 24, 월말 Tick = 각 월의 마지막 Tick(t % 720 == 719).

### Tick 실행 순서 (engine.step)
1. 명령 적용 → 2. movement.run (arrival_tick == tick 도착 처리) → 3. consumption.run (상점 도착자 구매 후 귀가 출발) → 4. behavior.run (08 출근, 18 귀가, 19 쇼핑 출발)
5. 월말이면: payroll.run → business.pay_operating_expenses → government.pay_welfare → government.procure → business.evaluate_status → employment.run → `economy.month.closed`
6. metrics (월말 MONTHLY) → `metrics.updated`
7. 불변식 검사(전체 잔액 합 0, ISSUANCE 외 음수 없음, 거래별 원장 합 0) → `simulation.tick` → current_tick += 1
반환: TickResult(tick, events, transactions, ledger_entries, metrics)

### 인터페이스 (foundation이 만들고 나머지는 사용만)
- world/config.py `SimulationConfig` (frozen): spec 수치 전부.
- world/state.py `WorldState`: 엔티티 dict(UUID 키, 순회는 sorted), engine 보조 필드, `new_id`, `account_of(owner_type, owner_id=None, account_type=CASH)`, `current_policy(tick)`, `to_snapshot()` / `WorldState.from_snapshot()`.
- economy/ledger.py `post_transaction(ctx, type, entries:[(account_id, amount)], key, metadata=None) -> Transaction` (합 0 검증, 잔액 부족 시 `InsufficientFunds` 예외 후 아무것도 반영 안 함).
- context.py `TickContext(state, config, tick, rng(*keys), emit(type, payload), transactions, ledger_entries)`.
- systems/*.py: 각 모듈 `run(ctx)` (business는 `pay_operating_expenses`, `evaluate_status`; government는 `pay_welfare`, `procure`).
- tests/helpers.py: 작은 수동 세계 빌더(시민·기업·계좌·초기잔액).

### 파일 소유
- docs-writer(haiku): docs/*, backend/app/models/transaction.py enum, engine economy/transaction.py enum
- foundation(sonnet): utils/*, clock, config, state, context, engine, economy/ledger.py, events/generator.py, systems/* 스텁, tests/helpers.py, tests/test_foundation.py
- 2차: generator(sonnet) world/generator.py · citizen(sonnet) systems/{movement,behavior,consumption}.py · economy(sonnet) systems/{payroll,business,government,employment}.py, policies/* · metrics(haiku) metrics/calculator.py
- 3차: integration(sonnet) 결정성·snapshot·불변식·import·보정(AC18)·성능 스크립트

### Risks
- 2차 작업자가 foundation 인터페이스를 바꾸면 충돌 → 필요하면 lead에게 보고만.
- AC18 보정 수치가 바뀌면 docs도 갱신.

## Handoff: foundation → wave 2
foundation API는 코드가 기준이다: src/simulation_engine/{engine,context,clock}.py, world/{config,state}.py, economy/ledger.py, events/generator.py, tests/helpers.py. 순회는 `state.ordered("citizens")` 등 id 순. 계정은 `state.add_account`로 추가, 조회는 `state.account_of`.

### 공유 규약 (모든 2차 작업자 필수)
- `state.month_accumulators` 키 (월말 metrics 계산 후 엔진이 clear):
  - `revenue_consumer:{company_id}`, `revenue_b2b:{company_id}`, `revenue_procurement:{company_id}` — 수취 기업 기준 금액
  - `payroll:{company_id}` 지급한 급여 총액, `opex_paid:{company_id}` 실제 지급 운영비
  - 도시 합계: `consumption_total`, `tax_total`, `welfare_total`, `procurement_total`, `opex_b2b_total`, `opex_government_total`, `opex_external_total`, `bankrupt_count`(이번 달 파산 수)
- `state.last_month_income[citizen_id]`: payroll.run이 월말에 모든 시민을 세후 급여(실직자 0)로 덮어쓰고, government.pay_welfare가 지급액을 더한다. 첫 달 값은 generator가 설정(취업자 base_wage×8500bps/10000, 실직자 0).
- `state.unpaid_opex[company_id]`: 이번 월말 운영비 미납액(business가 쓰고 evaluate_status가 읽음, 다음 월말에 덮어씀).
- `state.distressed_months[company_id]`: 연속 DISTRESSED 개월 수.
- `state.movement_starts[citizen_id]`: 현재 이동의 출발 Tick.
- 이벤트 payload (snake_case, UUID는 str):
  - citizen.movement.started `{citizen_id, from_building_id, to_building_id, start_tick, arrival_tick}`
  - citizen.employment.changed `{citizen_id, company_id, employment_status, reason}` reason ∈ hired|fired|bankruptcy
  - company.status.changed `{company_id, from_status, to_status}`
- 운영 중 기업 = status ∈ {ACTIVE, DISTRESSED}. BANKRUPT 기업은 매출·지출·채용 없음.
- 기업 계정 잔액 부족은 `InsufficientFunds`로 감지(post 전 잔액 확인도 가능). 음수 잔액 금지.
