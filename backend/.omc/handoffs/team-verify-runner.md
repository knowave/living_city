## 핸드오프: team-verify → 완료 (runner)

- **결정**: lead 검증. pytest 169 passed + soak 1(별도 실행 통과). 실제 uvicorn + 임시 DB 스모크: PATCH RUNNING 후 x4 4초 → tick 16, x16 3초 → 16씩 커밋, 정상 종료 확인 후 DB 삭제.
- **수정**: runner INFO 로그가 출력되지 않던 문제(uvicorn은 자기 로거만 설정) → app/main.py에 `app` 로거 핸들러 추가.
- **위험**: 타이밍 기반 통합 테스트(AC4 처리량, AC6 상한)는 부하 큰 CI에서 여유값 조정 필요 가능. 소유 World당 전용 연결 1개(NullPool). runner 상태는 소유 프로세스만 앎.
- **측정**: 720 Tick 1회 compute 118ms / persist 623ms. Runner 주기(x16): compute 12–22ms, persist 36–71ms. soak 8656 Tick 43초, Snapshot 15개, RSS 104MB.
- **남은 것**: SSE(world_events 커서), frontend Mock 시민 → 실제 데이터.
