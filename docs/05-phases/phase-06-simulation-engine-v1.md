# Phase 6 — 시뮬레이션 엔진 v1
> 원본: 설계 인터뷰 스펙 `simulation_engine/.omc/specs/deep-interview-engine-v1.md` (규칙·수치·AC의 단일 출처)

## 목표
FastAPI·PostgreSQL 없이 Pure Python으로 동작하는 시뮬레이션 엔진 v1을 만든다. 시드로 시민 100명·기업 10개 도시를 생성하고, 1 Tick 또는 N Tick 진행 시 고용·출퇴근·소비·급여·세금·운영비·복지·공공 조달이 합계 0인 원장 거래로 기록되며, 같은 입력이면 Snapshot 복구 후에도 같은 결과가 나온다.

## 범위
- 세계 생성: 건물 21동(주거 10, 상업 6, 사무 4, 공공 1), 가구, 시민 100명, 기업 10개, 계좌, 초기 자본.
- Tick 실행: `step()`(1 Tick), `run(n)`(N Tick). 정책 변경 명령은 effective_tick 경계에서 적용한다.
- 시민 행동: 출근, 귀가, 소비, 이동 출발·도착 Tick.
- 경제: 급여와 소득세, 운영비(B2B·정부·외부), 복지, 공공 조달, 수출 재유입, 기업 상태 전이, 채용·해고, 파산.
- 출력: Domain Event, 도시 통계 12종, 매출 구분, 도시 내부 자금.
- 검증: 단위 테스트, 결정성, Snapshot 복구, 경제 불변식, 36개월 보정.

## Non-Goals
- 도로·MapChunk 생성과 경로 탐색 (frontend 담당).
- 주거비(RENT), 공급망 4단계(생산 능력·거래처 변경·원자재 부족), 외부 투자 유입, CLOSED 상태.
- 신규 기업 설립. 파산은 비가역이며 장기 시뮬레이션의 알려진 한계다 ([알려진 한계](#알려진-한계)).
- Simulation Runner, REST/SSE, DB 저장, 실시간 Tick 간격 (backend 영역).
- 10,000명 지원을 완료 조건으로 두지 않는다.
- DB 스키마 테이블 변경. 충돌이 확인될 때만 별도 검토한다.
- 엔진 패키지에서 FastAPI, SQLAlchemy, PostgreSQL import.

## 결정 사항 요약
세부 규칙은 각 문서를 따른다. 여기에는 요지와 위치만 적는다.

| 주제 | 결정 | 문서 |
|---|---|---|
| 시민 상태 값 | EMPLOYED/UNEMPLOYED, AT_HOME/MOVING/WORKING/SHOPPING | [03-citizen §4.5](../02-domain/03-citizen.md) |
| 하루 일과와 소비 | 08시 출근, 18시 귀가, 소비일당 1회 소비 출발(19시 이후 집에 있거나 도착). 월 소비 예산 = 지난달 소득 기반 + 누적 현금 기반 추가 소비 | [03-citizen §4.5](../02-domain/03-citizen.md) |
| 기업 업종과 상태 | 업종 4개, ACTIVE·DISTRESSED·BANKRUPT 전이, 채용·해고·파산 | [04-business §3.6, §5.4–5.6](../02-domain/04-business.md) |
| 운영비 | B2B 70% · 정부 20% · 외부 10%, 공급 관계, 월 1회, 연쇄 없음 | [06-economy §6.5](../02-domain/06-economy.md) |
| 복지와 공공 조달 | 복지 기본 100만 원, 조달 예산 = (잔액 − 예상 복지액) × 50% | [05-government §3.7.2–3.7.3](../02-domain/05-government.md) |
| 월말 정산 순서 | 급여 → 운영비 → 복지 → 조달 → 수출 → 상태 평가 → 채용·해고 → 소비 예산 계산 | [06-economy §6.8](../02-domain/06-economy.md) |
| 수출 재유입 | 외부 잔액 × 수출 비율(5000bps = 50%/월, 보정 설정값)을 운영 중 기업에 균등 분할. 거래 유형 EXPORT. 테이블 변경 없음 | [06-economy §6.6](../02-domain/06-economy.md) |
| 초기 정원·고용 | 기업당 WHOLESALE 6, BUSINESS_SERVICE 2, RETAIL·RESTAURANT 12. 초기 고용 88명 (보정안 C1) | [04-business §3.6](../02-domain/04-business.md) |
| 소비 예비금·추가 소비율 | 생활 예비금 1,000,000원, 추가 소비율 3000bps (보정안 C1) | [03-citizen §4.5](../02-domain/03-citizen.md) |
| 거래 유형 | OPERATING_EXPENSE, PUBLIC_PROCUREMENT, EXPORT 추가. 테이블 변경 없음 | [06-economy](../02-domain/06-economy.md) |
| 외부 계정과 내부 자금 | 외부 = SYSTEM/CASH 1개. 내부 자금 = 시민 + 기업 + 정부. 내부 자금 변화 = 외부 유입 − 외부 유출 | [06-economy §6.6](../02-domain/06-economy.md) |
| 엔진 내부 Tick 순서 | 명령 → 이동 → 소비 → 행동 → 월말 → 지표 → 불변식 | [03-simulation-engine §7.2.1](../03-architecture/03-simulation-engine.md) |
| RNG | 상태를 저장하지 않는 파생 스트림 (`rng(seed, *keys)`) | [03-simulation-engine §7.3](../03-architecture/03-simulation-engine.md) |
| 이벤트 sequence | 엔진이 세계별 1부터 부여. snapshot에 다음 번호 저장 | [03-simulation-engine §7.3](../03-architecture/03-simulation-engine.md) |
| 결정적 ID·멱등 키 | 시드 기반 UUID, `{type}:{tick}:{주체 id}[:{보조}]` | [03-simulation-engine §7.3](../03-architecture/03-simulation-engine.md) |
| Snapshot | `state_data` 형식과 복구 조건 | [03-simulation-engine §7.10](../03-architecture/03-simulation-engine.md) |
| 명령 | v1은 정책 변경(`PolicyChangeCommand`)만 다룬다. Tick 시작에 적용하고 `policy.updated`를 낸다. 현재 정책은 effective_tick ≤ tick 중 가장 최신 version이다 | 이 문서 |

### 초기값

모든 수치는 설정값(config)이다.

- 시민 100명: 나이 20–64, consumption_preference 5000–9000bps. 1인 1가구.
- 건물: 주거 10(정원 10), 상업 6, 사무 4, 공공 1. 128×128 타일 안에 시드로 배치한다.
- 기업 10개: RETAIL 3, RESTAURANT 3, WHOLESALE 2, BUSINESS_SERVICE 2. 기업당 정원은 RETAIL·RESTAURANT 12, WHOLESALE 6, BUSINESS_SERVICE 2이고, 초기 고용은 88명(정원 합)이다 ([04-business §3.6](../02-domain/04-business.md)).
- OPENING_BALANCE: 시민 300만 원, 기업은 월 고정비 3개월치, 정부 5,000만 원. 외부 계정은 0이다.
- 보정 기준: 시드 42·1·7 각각 36개월 진행 시 파산 0개 (AC18). 보정안 C1을 승인받아 config 기본값과 docs에 기록했다.

## 작업 웨이브

1. **Foundation**: 설정, 세계 상태, 컨텍스트, 원장(`post_transaction`), RNG와 ID 생성, 이벤트 sequence, 시스템 인터페이스, 테스트 헬퍼.
2. **병렬 구현**
   - generator: 세계 생성 (건물, 시민, 가구, 기업, 계좌, 초기 자본)
   - citizen: 이동, 출근·귀가, 소비 예산과 소비
   - economy: 급여·소득세, 운영비, 복지, 공공 조달, 수출, 기업 상태, 채용·해고, 정책
   - metrics: 도시 통계 12종, 매출 구분 4항목, 도시 내부 자금
3. **Integration**: 결정성, Snapshot 복구, 불변식, import 검사, 36개월 보정(AC18), 성능 측정(AC19).

## 완료 기준

- [ ] AC1 시드로 시민 100명·기업 10개·건물 21동·가구·계좌가 위 초기값대로 생성된다.
- [ ] AC2 초기 자본은 OPENING_BALANCE 거래로만 배분되고, 생성 직후 전체 잔액 합계는 0이다.
- [ ] AC3 생성 결과가 backend 14개 엔티티의 필드와 제약(소유자 구성, 음수 잔액 금지, employee_count ≤ capacity, 활성 고용 1개)을 만족한다.
- [ ] AC4 `step()`(1 Tick)과 `run(n)`(N Tick)이 동작하고, 정책 변경 명령은 effective_tick 경계에서 적용된다.
- [ ] AC5 취업자는 08시에 출발하고 18시에 귀가하며, 상태가 MOVING → WORKING → MOVING → AT_HOME으로 바뀐다.
- [ ] AC6 이동 시작 시 arrival_tick이 §4.4 공식과 일치하고, `citizen.movement.started` payload(citizen_id, from_building_id, to_building_id, start_tick, arrival_tick)가 나온다.
- [ ] AC7 소비 출발이 월 소비 예산 공식대로 PURCHASE 거래를 만들고 잔액을 넘지 않는다. 복지 없는 실직자는 소비하지 않는다.
- [ ] AC8 월말 급여와 소득세 15%가 정확히 이전되고, 정부 TREASURY가 세금을 받는다.
- [ ] AC9 운영비가 70/20/10과 공급 관계대로 분배되고, 공급자가 없으면 외부로 간다. 잔액이 부족하면 미납 처리되며 음수는 생기지 않는다.
- [ ] AC10 복지와 공공 조달이 규칙대로 지급된다.
- [ ] AC11 기업 상태 전이(ACTIVE ↔ DISTRESSED, BANKRUPT)와 채용·해고가 규칙대로 일어나고, 파산하면 고용이 모두 종료된다.
- [ ] AC12 모든 Transaction의 LedgerEntry 합계는 0이고, 매 Tick 전체 계좌 합계는 0이며, ISSUANCE를 제외한 어떤 계좌도 음수가 아니다.
- [ ] AC13 상태 변경이 Domain Event(simulation.tick, citizen.employment.changed, citizen.movement.started, company.status.changed, economy.month.closed, metrics.updated, policy.updated)로 순서 번호와 함께 나온다.
- [ ] AC14 같은 시드, 초기 상태, 명령 순서, 엔진 버전이면 N Tick 후 상태·이벤트·거래가 완전히 같다.
- [ ] AC15 Snapshot(RNG 상태, DISTRESSED 연속 개월, 지난달 소득, 이동 출발 Tick 포함)에서 복구한 뒤 진행한 결과가, 중단 없이 진행한 결과와 같다.
- [ ] AC16 엔진 테스트가 FastAPI·SQLAlchemy·PostgreSQL 없이 `python -m unittest`로 통과하고, 엔진 패키지가 그 모듈들을 import하지 않는다.
- [ ] AC17 통계 12종 지표 코드, 매출 구분 4항목(최종 소비·B2B·공공 조달·수출), 도시 내부 자금을 계산한다.
- [ ] AC18 시드 42·1·7 각각 36개월 진행 시 파산 기업은 0개다 (보정안 C1 기준).
- [ ] AC19 (비필수) 시민 100·1,000·10,000명에서 Tick 처리 시간과 메모리를 측정해 기록한다. 통과 조건이 아니다.

## 알려진 한계

- 파산은 비가역이다. 파산한 기업은 되살아나지 않는다. 신규 기업 설립도 v1 범위 밖이다.
- 따라서 장기 실행에서는 기업 수가 줄어든다. v1은 이 한계를 알려진 상태로 둔다.
- 60개월 결과: 12개 시드 중 7개에서 45~50개월째에 소매·식당 손님 분배 편차로 연쇄 파산이 일어난다. 신규 기업 설립이 없어 회복하지 못하는 것과 결합된다.

## 12개월 실측 분석

기본 설정으로 12개월을 돌리자 BUSINESS_SERVICE가 5개월째 파산했고 연쇄 파산이 이어졌다. 원인은 세 가지다.

1. B2B 기업의 인원이 과다하다.
2. 시민 저축이 쌓인다. 소비가 소득에만 비례하므로 현금이 기업으로 돌아오지 않는다.
3. 외부로 나가는 돈만 있고 들어오는 돈이 없다.

대응은 다음과 같다.

- 누적 현금 기반 추가 소비: [03-citizen §4.5](../02-domain/03-citizen.md)
- 수출 재유입: [06-economy §6.6](../02-domain/06-economy.md)
- 정원 보정: [04-business §3.6](../02-domain/04-business.md)

실측과 보정에 쓰는 스크립트는 다음과 같다.

- [company_pnl.py](../../simulation_engine/scripts/company_pnl.py): 기업별 손익
- [calibrate.py](../../simulation_engine/scripts/calibrate.py): 보정

### 보정안 C1 결과

- 설정: 기업당 정원 WHOLESALE 6, BUSINESS_SERVICE 2, RETAIL·RESTAURANT 12, 초기 고용 88명, 생활 예비금 1,000,000원, 추가 소비율 3000bps, 수출 비율 5000bps.
- 시드 15개, 36개월: 파산 0.
- 내부 자금, 국고, 시민 현금이 수렴한다. 외부 순유출은 0이다.
- 재현 (`simulation_engine/`에서 실행):

```bash
PYTHONPATH=src:scripts uv run --no-project --python 3.12 python scripts/economy_report.py C1 36 42
```

시드를 생략하면 42·1·7을 쓴다. 인자 `C1`은 보정 프리셋이다 (`scripts/calibrate.py`의 `PRESETS`).

## 성능 측정 (AC19, 비필수)

측정 도구는 `simulation_engine/scripts/perf.py`다. 시민 수에 맞춰 건물과 기업 수를 비례 확대하고, `map_size`는 √배 키워서 건물 밀도를 유지한다. 따라서 이동 거리 증가 효과가 포함된다. 720 Tick을 진행했다.

| 시민 수 | 평균 ms/Tick | p95 ms | 월말 Tick ms | 피크 RSS |
|---:|---:|---:|---:|---:|
| 100 | 0.15 | 0.43 | 1.9 | 24 MB |
| 1,000 | 3.3 | 6.0 | 34 | 31 MB |
| 10,000 | 147 | 222 | 1,942 | 325 MB |

- 시민 10배당 Tick 시간은 약 44~57배다 (N^1.7).
- 1배속 Tick 간격 약 83ms 기준으로 1,000명까지 여유가 있다.
- 10,000명은 v1 필수 조건이 아니다.
- 같은 명령을 다른 부하 상태에서 다시 재면 시간 값이 달라진다. 10,000명 재측정 한 번은 평균 195 ms, p95 387 ms, 월말 2,689 ms, RSS 317 MB였다. 메모리 규모는 같았다.

재측정 (`simulation_engine/`에서 실행, 인자는 `시민수:Tick수`):

```bash
PYTHONPATH=src uv run --no-project --python 3.12 python scripts/perf.py 100:720 1000:720 10000:720
```

## 참고 문서
- [03-citizen](../02-domain/03-citizen.md)
- [04-business](../02-domain/04-business.md)
- [05-government](../02-domain/05-government.md)
- [06-economy](../02-domain/06-economy.md)
- [07-simulation-rules](../02-domain/07-simulation-rules.md)
- [03-simulation-engine](../03-architecture/03-simulation-engine.md)
- [06-database](../03-architecture/06-database.md)
- [04-simulation-convention](../04-development/04-simulation-convention.md)
- [06-testing-guide](../04-development/06-testing-guide.md)
