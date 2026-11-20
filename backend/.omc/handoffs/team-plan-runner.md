## 핸드오프: team-plan → team-exec (runner)

- **결정**: 스펙 `backend/.omc/specs/deep-interview-runner.md`(가정 1–10 승인). 순서: W1 docs → [W2 서비스·인프라 ∥ W3 runner 패키지] → W4 통합·soak 테스트.
- **거절**: 프로세스 내부 잠금만으로 소유권, x8 배속, Catch-up, Snapshot 전부 보관, N회 실패 시 PAUSED.
- **위험**: advisory lock은 세션 범위 → 전용 연결 유지 필요. asyncio + sync DB는 to_thread. runner는 sqlalchemy를 import하지 않으므로 인프라 오류는 "DomainError가 아닌 예외 = 일시 오류"로 분류.
- **남은 것**: SSE, frontend 실제 데이터 연동.

# 공유 계약 (이름·시그니처·코드 그대로 사용)

## 설정 (`app/core/config.py`)
`RUNNER_ENABLED: bool = True`, `RUNNER_TICK_INTERVAL_MS: int = 1000`, `RUNNER_DISCOVERY_INTERVAL_MS: int = 1000`, `RUNNER_BACKOFF_MAX_MS: int = 30000`, `RUNNER_SHUTDOWN_TIMEOUT_MS: int = 10000`, `SNAPSHOT_KEEP_LATEST: int = 3`. 테스트 conftest는 RUNNER_ENABLED=false.

## 스키마 (`app/schemas/world.py`)
- `TickAdvanceRead`에 `compute_ms: float | None = None`, `persist_ms: float | None = None` 추가.
- `RunnerStatusRead(state: Literal["running","retrying","stopped"], consecutive_failures: int, last_error: str | None, last_compute_ms: float | None, last_persist_ms: float | None, last_tick: int | None)`.
- `WorldStateRead`에 `runner: RunnerStatusRead | None = None` 추가.

## Use case (`app/usecases/world.py`, `WorldService` 구현) — W2
- `advance_running(world_id: UUID, expected_tick: int) -> TickAdvanceRead`: NOWAIT 행 잠금 → 404 → status != RUNNING이면 `InvalidStateError("WORLD_NOT_RUNNING")`(409) → expected_tick → snapshot → 엔진(count=world.speed) → 저장 → version → 커밋. `advance_ticks`와 공통 내부 함수 사용. 측정값(compute_ms=engine.advance, persist_ms=save_advance+advance_tick+commit) 채움(advance_ticks도 채움).
- `list_running_world_ids() -> list[UUID]`: repository `worlds.list_ids_by_status(WorldStatus.RUNNING)`.
- `get_world_state`: `runner` = 주입된 `RunnerStatusProvider.get(world_id)`(없으면 None).
- `WorldService(uow, engine, engine_version_default, lock_timeout_ms=5000, runner_status: RunnerStatusProvider | None = None)`.

## Runner 포트 (`app/runner/interfaces.py`) — W3가 만든다(W2는 이 이름으로 import)
```python
class RunnerStatusProvider(ABC):
    @abstractmethod
    def get(self, world_id: UUID) -> RunnerStatusRead | None: ...

class OwnershipHandle(ABC):
    @abstractmethod
    def release(self) -> None: ...

class OwnershipLock(ABC):
    @abstractmethod
    def try_acquire(self, world_id: UUID) -> OwnershipHandle | None:
        """pg_try_advisory_lock on a dedicated connection; None if owned elsewhere."""
```
W3가 이 파일을 먼저(작업 시작 직후) 만든다. W2는 없으면 잠시 기다렸다 import.

## 인프라 구현 — W2
- `app/repositories/sqlalchemy/ownership.py`: `PgAdvisoryOwnershipLock(engine)` → `try_acquire`는 `engine.connect()`로 전용 연결을 열고 `SELECT pg_try_advisory_lock(:k)`; 실패면 연결 닫고 None. 키 = `int.from_bytes(world_id.bytes[:8], "big", signed=True)`. handle.release()는 `pg_advisory_unlock` 후 연결 닫기(예외 무시).
- Snapshot 보관: `SqlSimulationPersistence.save_advance`가 저장 후 같은 트랜잭션에서 `tick % 720 != 0`이면서 최신 `keep_latest`개에 들지 않는 world_snapshots 행을 삭제. `SqlAlchemyUnitOfWork(session, snapshot_keep_latest=3)`로 주입.
- `SqlWorldRepository.list_ids_by_status(status) -> list[UUID]`.

## Runner 패키지 — W3 (`app/runner/`)
- `backoff.py`: `next_delay(failures, base_ms=1000, max_ms)` = min(base·2^(failures-1), max).
- `world_runner.py`: `WorldRunner(world_id, use_case_scope, interval_ms, backoff_max_ms, clock, sleep)`. `use_case_scope: Callable[[], ContextManager[WorldUseCase]]`(주기마다 새 세션). 루프: 시작 시 `get_world` 로 expected_tick 동기화 → 매 주기 `to_thread(advance_running)`; 다음 시작 = 이전 시작 + interval(밀리면 즉시, 보충 없음). 오류 분류:
  - `ConflictError SIMULATION_FAILED` → stopped(종료, 세계는 이미 FAILED)
  - `InvalidStateError WORLD_NOT_RUNNING`/`WORLD_NOT_RUNNABLE`, `NotFoundError` → stopped(정상 종료)
  - `ConflictError SNAPSHOT_MISMATCH` → stopped + last_error
  - `ConflictError TICK_MISMATCH` → expected_tick = details.current_tick, 즉시 계속
  - 그 밖의 DomainError(WORLD_BUSY, CONCURRENT_UPDATE) 및 DomainError가 아닌 모든 예외 → retrying, backoff 후 재시도
  - 상태 갱신 후 INFO 로그(world_id, ticks, compute_ms, persist_ms).
- `manager.py`: `RunnerManager(use_case_scope, ownership: OwnershipLock, settings값들, clock, sleep)` — `start()`(발견 루프 task), `stop()`(신규 차단, 실행 중 주기 완료 대기 RUNNER_SHUTDOWN_TIMEOUT_MS, 소유권 해제), `RunnerStatusProvider` 구현(`get`). 발견: `list_running_world_ids()` → 미소유면 `ownership.try_acquire` → 성공 시 WorldRunner 시작; runner 종료 시 handle.release.
- 조립: `app/api/deps.py`에 `world_use_case_scope()`(contextmanager, SessionLocal) 와 `build_runner_manager()`(싱글턴) 추가, `get_world_use_case`는 manager를 RunnerStatusProvider로 주입. `app/main.py` lifespan: RUNNER_ENABLED면 `build_runner_manager().start()`, 종료 시 `await stop()`.
- 계층: `app/runner/*`는 sqlalchemy·simulation_engine·app.models·app.repositories.sqlalchemy import 금지(architecture 테스트에 추가).
