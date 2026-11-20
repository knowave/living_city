## Handoff: team-verify → complete (engine-v1)
- **Decided**: 독립 verifier 재검증 PASS(차단 0). 엔진 95 tests, backend 76 passed, AC18 36개월×3시드 파산 0, backend diff = transaction.py enum 3줄.
- **Fixed in loop 1**: D1 trip_purpose 기반 도착 처리(IDLE 제거), D2 정책 명령 검증·원자성, D3 docs(36개월, AC19 표, 4개 activity 값).
- **Open (사용자 확인)**: O1 SHOPPING이 Tick 종료 시 관측되지 않음, O3 복지 부분 지급 없음, docs TBD(운영비 부분 지급, 예상 복지액 식, 조달 0 이하, 매출 합계 지표), TERMINATED 상태값, happiness 50/health 100 기본값.
- **Known limits**: 60개월 시 7/12 시드 연쇄 파산(손님 분배 편차 + 신규 기업 없음). 10,000명 Tick ~150–200ms(N^1.7).
- **Files**: src/simulation_engine/**, tests/**, scripts/**, docs/**, CLAUDE.md(phase 링크·상태 칸), backend/app/models/transaction.py. 커밋 없음.
- **Post-close (lead, 2026-11-19)**: 사용자 결정으로 SHOPPING 1 Tick 체류(consumption.depart 추가, engine 순서 depart→movement→consumption) + 복지 부분 지급 없음 확정. docs(03-citizen, 03-simulation-engine §7.2.1, 05-government)·spec 갱신, 테스트 3개 기대값 수정. 95 tests OK, 시드 42 3개월 SHOPPING 관측 8,951 = PURCHASE 8,951, 파산 0.
- **Checklist verify (2026-11-20)**: 독립 verifier 5명(v-status, v-events, v-shopping, v-snapshot, v-regression) 체크리스트 9항목 모두 PASS, 코드 결함 0. 문서 누락 1건(§7.10 engine.trip_purpose 행) lead가 보완. 검증 스크립트: scratchpad/verify/ (세션 임시).
