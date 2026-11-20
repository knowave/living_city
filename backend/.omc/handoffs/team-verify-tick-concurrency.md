## 핸드오프: team-verify → 완료 (tick-concurrency)

- **결정**: lead 직접 검증. pytest 138 passed(통합 32는 3회 반복 안정), 엔진·app/models 변경 없음, service는 sqlalchemy/psycopg import 없음, 임시 DB 없음.
- **거절**: 요청 ID 멱등성(보류, docs 후속 과제), 이미 반영 시 200 재생.
- **위험**: 엔진 실패 경로의 rollback→재잠금 사이 끼어들기(엔진 결정성으로 영향 작음). `SET LOCAL lock_timeout`은 잠금 이후 같은 트랜잭션의 다른 문장에도 적용됨. HTTP 병렬 테스트는 TestClient 스레드 호출 기반.
- **파일**: app/core/config.py, app/schemas/world.py, app/repositories/interfaces.py, app/repositories/sqlalchemy/repositories.py, app/services/world_service.py, app/api/deps.py, app/usecases/world.py, tests/services/*, tests/integration/test_engine_integration.py, tests/integration/test_concurrency.py, docs 4개.
- **남은 것**: Runner(expected_tick 계약 사용, WORLD_BUSY는 다음 주기 재시도).
