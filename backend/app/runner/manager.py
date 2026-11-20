import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from uuid import UUID

from app.runner.interfaces import OwnershipHandle, OwnershipLock, RunnerStatusProvider
from app.runner.world_runner import WorldRunner
from app.schemas.world import RunnerStatusRead
from app.usecases.world import WorldUseCase

logger = logging.getLogger(__name__)


class RunnerManager(RunnerStatusProvider):
    def __init__(
        self,
        use_case_scope: Callable[[], AbstractContextManager[WorldUseCase]],
        ownership: OwnershipLock,
        tick_interval_ms: int,
        discovery_interval_ms: int,
        backoff_max_ms: int,
        shutdown_timeout_ms: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._scope = use_case_scope
        self._ownership = ownership
        self._tick_interval_ms = tick_interval_ms
        self._discovery_interval = discovery_interval_ms / 1000
        self._backoff_max_ms = backoff_max_ms
        self._shutdown_timeout = shutdown_timeout_ms / 1000
        self._clock = clock
        self._sleep = sleep
        self._runners: dict[UUID, WorldRunner] = {}  # kept after stop for final status
        self._tasks: dict[UUID, asyncio.Task] = {}  # active only
        self._discovery: asyncio.Task | None = None
        self._stopping = False

    def get(self, world_id: UUID) -> RunnerStatusRead | None:
        runner = self._runners.get(world_id)
        return runner.status if runner else None

    def start(self) -> None:
        if self._discovery is None:
            self._discovery = asyncio.create_task(self._discover_loop())

    async def stop(self) -> None:
        self._stopping = True
        if self._discovery:
            self._discovery.cancel()
            await asyncio.gather(self._discovery, return_exceptions=True)
        for runner in self._runners.values():
            runner.stop()
        tasks = list(self._tasks.values())
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=self._shutdown_timeout)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _discover_loop(self) -> None:
        while not self._stopping:
            try:
                await self._discover_once()
            except Exception as e:  # noqa: BLE001 - DB may be down; retry next round
                logger.warning("runner discovery failed: %s", e)
            await self._sleep(self._discovery_interval)

    def _list_running(self) -> list[UUID]:
        with self._scope() as uc:
            return uc.list_running_world_ids()

    async def _discover_once(self) -> None:
        for world_id in await asyncio.to_thread(self._list_running):
            if self._stopping:
                return
            if world_id in self._tasks:
                continue
            handle = await asyncio.to_thread(self._ownership.try_acquire, world_id)
            if handle is None:
                continue
            runner = WorldRunner(
                world_id, self._scope, self._tick_interval_ms, self._backoff_max_ms, self._clock, self._sleep
            )
            self._runners[world_id] = runner
            self._tasks[world_id] = asyncio.create_task(self._run(world_id, runner, handle))

    async def _run(self, world_id: UUID, runner: WorldRunner, handle: OwnershipHandle) -> None:
        try:
            await runner.run()
        except Exception:  # noqa: BLE001
            logger.exception("runner crashed world_id=%s", world_id)
        finally:
            handle.release()
            self._tasks.pop(world_id, None)
