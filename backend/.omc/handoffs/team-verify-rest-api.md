## 핸드오프: team-verify → 완료 (rest-api)

- **결정**: lead 검증. pytest 217 passed(soak·perf 2 deselected), perf 1회 통과. 엔진·app/models·frontend 변경 없음. 임시 DB 없음.
- **보충**: MOVING 부등식 `start_tick < as_of_tick <= arrival_tick`을 07-rest-sse.md에 기록(테스트 작성 중 확인된 엔진 의미).
- **측정 p95(ms, Runner x16 중)**: /view 26.5, /chunks(256) 59.0, /citizens 31.2, /citizens/{id} 15.6, /companies 19.8, /summary 21.7. 맵 생성 평균 145ms, create_world 277ms. 시드 40개 맵 검증 40/40.
- **위험**: `.distinct(cid)` SQLAlchemy deprecation 경고(repositories.py:508). 호수 지형은 단순 타원. 최대 도로 연결 요소 밖 간선 조각은 버림.
- **남은 것**: SSE(event_cursor 이후 재생), frontend 연동(512 맵 API 연결, Mock 교체).
