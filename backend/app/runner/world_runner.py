import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from uuid import UUID

from app.core.exceptions import ConflictError, DomainError, InvalidStateError, NotFoundError
from app.runner.backoff import next_delay
from app.schemas.world import RunnerStatusRead
from app.usecases.world import WorldUseCase

logger = logging.getLogger(__name__)

_STOP_CODES = {"WORLD_NOT_RUNNING", "WORLD_NOT_RUNNABLE"}
_FATAL_CODES = {"SNAPSHOT_MISMATCH", "SIMULATION_FAILED"}


class WorldRunner:
    """Advances one running world every interval (no catch-up) until it stops or fails fatally."""

    def __init__(
        self,
        world_id: UUID,
        use_case_scope: Callable[[], AbstractContextManager[WorldUseCase]],
        interval_ms: int,
        backoff_max_ms: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.world_id = world_id
        self._scope = use_case_scope
        self._interval = interval_ms / 1000
        self._backoff_max_ms = backoff_max_ms
        self._clock = clock
        self._sleep = sleep
        self._stop = asyncio.Event()
        self._state = "running"
        self._failures = 0
        self._last_error: str | None = None
        self._compute_ms: float | None = None
        self._persist_ms: float | None = None
        self._last_tick: int | None = None

    @property
    def status(self) -> RunnerStatusRead:
        return RunnerStatusRead(
            state=self._state,
            consecutive_failures=self._failures,
            last_error=self._last_error,
            last_compute_ms=self._compute_ms,
            last_persist_ms=self._persist_ms,
            last_tick=self._last_tick,
        )

    def stop(self) -> None:
        self._stop.set()

    def _read_tick(self) -> int:
        with self._scope() as uc:
            return uc.get_world(self.world_id).current_tick

    def _advance(self, expected_tick: int):
        with self._scope() as uc:
            return uc.advance_running(self.world_id, expected_tick)

    async def _wait(self, seconds: float) -> None:
        """Sleep that returns early when stop() is called."""
        sleeper = asyncio.ensure_future(self._sleep(seconds))
        stopper = asyncio.ensure_future(self._stop.wait())
        _, pending = await asyncio.wait({sleeper, stopper}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()

    async def run(self) -> None:
        expected: int | None = None
        next_start = self._clock()
        try:
            while not self._stop.is_set():
                delay = next_start - self._clock()
                if delay > 0:
                    await self._wait(delay)
                    if self._stop.is_set():
                        break
                start = self._clock()
                next_start = max(start + self._interval, start)
                try:
                    if expected is None:
                        expected = await asyncio.to_thread(self._read_tick)
                    result = await asyncio.to_thread(self._advance, expected)
                except Exception as e:  # noqa: BLE001 - classified below
                    kind = self._classify(e)
                    if kind == "stop":
                        break
                    if kind == "resync":
                        details = e.details if isinstance(e.details, dict) else {}
                        expected = details.get("current_tick")
                        next_start = self._clock()
                    else:
                        next_start = self._clock() + next_delay(self._failures, self._backoff_max_ms) / 1000
                    continue
                expected = result.to_tick
                self._state, self._failures, self._last_error = "running", 0, None
                self._compute_ms, self._persist_ms = result.compute_ms, result.persist_ms
                self._last_tick = result.to_tick
                next_start = max(next_start, self._clock())
                logger.info(
                    "tick committed world_id=%s from_tick=%s to_tick=%s compute_ms=%s persist_ms=%s",
                    self.world_id, result.from_tick, result.to_tick, result.compute_ms, result.persist_ms,
                )
        finally:
            self._state = "stopped"

    def _classify(self, e: Exception) -> str:
        """Returns 'stop', 'resync' (TICK_MISMATCH) or 'retry'; updates status fields."""
        if isinstance(e, NotFoundError) or (
            isinstance(e, InvalidStateError) and e.code in _STOP_CODES
        ):
            logger.info("runner stopping world_id=%s code=%s", self.world_id, e.code)
            return "stop"
        if isinstance(e, ConflictError) and e.code in _FATAL_CODES:
            self._last_error = e.code
            logger.error("runner stopped world_id=%s code=%s: %s", self.world_id, e.code, e)
            return "stop"
        if isinstance(e, ConflictError) and e.code == "TICK_MISMATCH":
            return "resync"
        self._failures += 1
        self._state = "retrying"
        self._last_error = e.code if isinstance(e, DomainError) else f"{type(e).__name__}: {e}"
        logger.warning(
            "runner transient error world_id=%s failures=%s: %s", self.world_id, self._failures, self._last_error
        )
        return "retry"
