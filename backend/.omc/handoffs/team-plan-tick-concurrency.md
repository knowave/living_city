## 핸드오프: team-plan → team-exec (tick-concurrency)

- **결정**: 스펙 `backend/.omc/specs/deep-interview-tick-concurrency.md`(가정 1–7 승인). 순서: W1 docs → W2 구현·단위 테스트 → W3 Postgres 병렬 통합 테스트.
- **거절**: 프로세스 내부 Lock, advisory lock, 요청 ID 테이블(보류), 이미 반영 시 200 재생.
- **위험**: rollback이 행 잠금을 풀어 mark_failed 경로에서 재잠금 필요. psycopg 오류 55P03 식별. SET LOCAL lock_timeout은 트랜잭션 범위.
- **남은 것**: 요청 ID 멱등성(후속 과제), Runner.

# 공유 계약
- 설정: `Settings.WORLD_LOCK_TIMEOUT_MS: int = 5000` (`app/core/config.py`), `.env` 불필요.
- repository ABC (`app/repositories/interfaces.py`, `WorldRepository`):
  `lock_for_update(self, world_id: UUID, *, nowait: bool, timeout_ms: int | None = None) -> WorldRead | None`
  - 행을 `SELECT … FOR UPDATE [NOWAIT]`로 잠그고 최신 값을 돌려준다(없으면 None).
  - 대기형은 `SET LOCAL lock_timeout = '<ms>ms'` 후 FOR UPDATE.
  - 잠금 실패(PG SQLSTATE 55P03 `lock_not_available`, NOWAIT·timeout 모두) → `ConflictError("WORLD_BUSY", ...)`. 잠금 실패 후 세션은 rollback 상태로 만든다.
  - SQLAlchemy 구현: `select(World).where(World.id == id).with_for_update(nowait=nowait).execution_options(populate_existing=True)`.
- 오류 코드(409): `WORLD_BUSY`, `TICK_MISMATCH`(details `{"current_tick": n}`). 기존 `CONCURRENT_UPDATE`, `WORLD_NOT_RUNNABLE`, `SNAPSHOT_MISMATCH`, `SIMULATION_FAILED` 유지.
- 스키마: `TickAdvanceRequest(count: int = Field(ge=1, le=720), expected_tick: int = Field(ge=0))` — 필수.
- `WorldService.advance_ticks` 순서: `lock_for_update(nowait=True)` → None이면 404 → 상태 → `current_tick != expected_tick`이면 TICK_MISMATCH → snapshot → engine → save_advance → advance_tick(expected_version=잠금 후 읽은 version) → commit.
  - 엔진 실패: rollback → `lock_for_update(nowait=False, timeout_ms=설정)` → mark_failed → commit → SIMULATION_FAILED.
  - 저장 중 `IntegrityError`는 repository 구현(`SqlSimulationPersistence`)에서 잡아 `ConflictError("CONCURRENT_UPDATE")`로 바꾼다(service는 sqlalchemy import 금지).
- `change_policy`, `change_simulation`: 시작 시 `lock_for_update(nowait=False, timeout_ms=설정)`로 잠그고, 그 반환값(최신 World)으로 검증·계산. 기존 version 검증 유지.
- `WorldService` 생성자에 `lock_timeout_ms: int` 인자 추가(기본값 5000), deps.py에서 `settings.WORLD_LOCK_TIMEOUT_MS` 주입.
