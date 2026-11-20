import secrets
import time
from uuid import UUID

from app.core.exceptions import (
    ConflictError,
    DomainValidationError,
    InvalidStateError,
    NotFoundError,
)
from app.maps.generator import generate_map
from app.maps.validate import MapValidationError, validate_map
from app.repositories.interfaces import NewPolicy, NewWorld, UnitOfWork
from app.simulation.interfaces import (
    PolicyCommandInput,
    SimulationEngineError,
    SimulationEnginePort,
)
from app.runner.interfaces import RunnerStatusProvider
from app.schemas.enums import WorldStatus
from app.schemas.world import (
    PolicyRead,
    PolicyUpdate,
    SimulationUpdate,
    TickAdvanceRead,
    TickAdvanceRequest,
    WorldCreate,
    WorldRead,
    WorldStateRead,
)
from app.usecases.world import WorldUseCase

ALLOWED_SPEEDS = {1, 4, 16}
MAX_TAX_RATE = 10000

S = WorldStatus
ALLOWED_TRANSITIONS = {
    S.INITIALIZED: {S.RUNNING, S.ARCHIVED},
    S.RUNNING: {S.PAUSED, S.ARCHIVED},
    S.PAUSED: {S.RUNNING, S.ARCHIVED},
    S.FAILED: set(),
    S.ARCHIVED: set(),
}


class WorldService(WorldUseCase):
    def __init__(
        self,
        uow: UnitOfWork,
        engine: SimulationEnginePort,
        engine_version_default: str,
        lock_timeout_ms: int = 5000,
        runner_status: RunnerStatusProvider | None = None,
    ) -> None:
        self._runner_status = runner_status
        self._lock_timeout_ms = lock_timeout_ms
        self._uow = uow
        self._engine = engine
        self._engine_version_default = engine_version_default

    def _world(self, world_id: UUID) -> WorldRead:
        world = self._uow.worlds.get(world_id)
        
        if world is None:
            raise NotFoundError("WORLD_NOT_FOUND", "World not found")
        
        return world

    def _lock_world(self, world_id: UUID, *, nowait: bool = False) -> WorldRead:
        world = self._uow.worlds.lock_for_update(
            world_id, nowait=nowait, timeout_ms=None if nowait else self._lock_timeout_ms
        )

        if world is None:
            raise NotFoundError("WORLD_NOT_FOUND", "World not found")

        return world

    def create_world(self, data: WorldCreate) -> WorldRead:
        seed = data.seed if data.seed is not None else secrets.randbits(63)
        
        # 엔진 생성을 먼저 해서, 실패하면 World 행을 만들지 않는다.
        try:
            batch = self._engine.generate(seed, data.name)
        except SimulationEngineError as exc:
            raise ConflictError("WORLD_GENERATION_FAILED", "Simulation engine failed to generate the world") from exc

        try:
            game_map = generate_map(seed, batch.buildings)
            validate_map(game_map, batch.buildings)
        except MapValidationError as exc:
            raise ConflictError("WORLD_GENERATION_FAILED", f"Map generation failed: {exc.reason}") from exc

        world = self._uow.worlds.add(
            NewWorld(
                name=data.name,
                seed=seed,
                engine_version=data.engine_version or self._engine_version_default,
            )
        )
        self._uow.simulation.save_generation(world.id, batch)
        self._uow.chunks.save_all(world.id, game_map.chunks())

        self._uow.commit()
        
        return world

    def get_world(self, world_id: UUID) -> WorldRead:
        return self._world(world_id)

    def get_world_state(self, world_id: UUID) -> WorldStateRead:
        world = self._world(world_id)
        
        policy = self._uow.policies.current(world_id, world.current_tick)
        
        if policy is None:
            raise NotFoundError("POLICY_NOT_FOUND", "World has no policy")
        
        return WorldStateRead(
            world_id=world.id,
            status=world.status,
            current_tick=world.current_tick,
            speed=world.speed,
            event_cursor=self._uow.events.max_sequence(world_id),
            current_policy=policy,
            runner=self._runner_status.get(world_id) if self._runner_status else None,
        )

    def change_simulation(self, world_id: UUID, data: SimulationUpdate) -> WorldRead:
        if data.status is None and data.speed is None:
            raise DomainValidationError(
                "INVALID_SIMULATION_UPDATE", "status or speed is required"
            )
        
        if data.speed is not None and data.speed not in ALLOWED_SPEEDS:
            raise DomainValidationError("INVALID_SPEED", "speed must be one of 1, 4, 16")
        
        world = self._lock_world(world_id)
        status = world.status
        
        if data.status is not None and data.status != world.status:
            if data.status not in ALLOWED_TRANSITIONS[world.status]:
                raise InvalidStateError(
                    "INVALID_STATE_TRANSITION",
                    f"Cannot change status {world.status} -> {data.status}",
                )
            
            status = data.status
        
        if data.speed is not None and world.status in (S.ARCHIVED, S.FAILED):
            raise InvalidStateError(
                "INVALID_STATE_TRANSITION", f"Cannot change speed of {world.status} world"
            )
        
        updated = self._uow.worlds.update_simulation(
            world_id,
            status,
            data.speed if data.speed is not None else world.speed,
            expected_version=world.version,
        )
        
        self._uow.commit()
        
        return updated

    def change_policy(self, world_id: UUID, data: PolicyUpdate) -> PolicyRead:
        if data.income_tax_rate is None and data.welfare_amount is None:
            raise DomainValidationError("INVALID_POLICY", "at least one field is required")
        
        if data.income_tax_rate is not None and not 0 <= data.income_tax_rate <= MAX_TAX_RATE:
            raise DomainValidationError("INVALID_POLICY", "income_tax_rate must be 0..10000")
        
        if data.welfare_amount is not None and data.welfare_amount < 0:
            raise DomainValidationError("INVALID_POLICY", "welfare_amount must be >= 0")
        
        world = self._lock_world(world_id)
        
        if world.status == S.ARCHIVED:
            raise InvalidStateError("INVALID_STATE_TRANSITION", "World is archived")
        
        latest = self._uow.policies.latest(world_id)
        
        if latest is None:
            raise NotFoundError("POLICY_NOT_FOUND", "World has no policy")
        
        policy = self._uow.policies.upsert_pending(
            NewPolicy(
                world_id=world_id,
                income_tax_rate=(
                    latest.income_tax_rate
                    if data.income_tax_rate is None
                    else data.income_tax_rate
                ),
                welfare_amount=(
                    latest.welfare_amount if data.welfare_amount is None else data.welfare_amount
                ),
                effective_tick=world.current_tick + 1,
                version=latest.version + 1,
            )
        )
        
        self._uow.commit()
        
        return policy

    def advance_ticks(self, world_id: UUID, data: TickAdvanceRequest) -> TickAdvanceRead:
        return self._advance(
            world_id, data.expected_tick, data.count, require_running=False, require_paused=True
        )

    def advance_running(self, world_id: UUID, expected_tick: int) -> TickAdvanceRead:
        return self._advance(world_id, expected_tick, None, require_running=True)

    def list_running_world_ids(self) -> list[UUID]:
        return self._uow.worlds.list_ids_by_status(S.RUNNING)

    def _advance(
        self,
        world_id: UUID,
        expected_tick: int,
        count: int | None,
        *,
        require_running: bool,
        require_paused: bool = False,
    ) -> TickAdvanceRead:
        world = self._lock_world(world_id, nowait=True)

        if require_running and world.status != S.RUNNING:
            raise InvalidStateError("WORLD_NOT_RUNNING", f"World is {world.status}")

        if require_paused and world.status != S.PAUSED:
            raise InvalidStateError("WORLD_NOT_PAUSED", f"World is {world.status}")

        if world.status in (S.FAILED, S.ARCHIVED):
            raise InvalidStateError("WORLD_NOT_RUNNABLE", f"World is {world.status}")

        if world.current_tick != expected_tick:
            raise ConflictError(
                "TICK_MISMATCH",
                f"expected_tick {expected_tick} != current_tick {world.current_tick}",
                details={"current_tick": world.current_tick},
            )

        snapshot = self._uow.snapshots.latest(world_id)

        if snapshot is None or snapshot.tick != world.current_tick:
            raise ConflictError("SNAPSHOT_MISMATCH", "Snapshot does not match current tick")

        policies = [
            PolicyCommandInput(
                income_tax_rate=p.income_tax_rate,
                welfare_amount=p.welfare_amount,
                effective_tick=p.effective_tick,
                version=p.version,
            )
            for p in self._uow.policies.all(world_id)
        ]

        started = time.perf_counter()
        try:
            batch = self._engine.advance(
                snapshot.state_data, policies, world.speed if count is None else count
            )
        except SimulationEngineError as exc:
            self._uow.rollback()
            self._lock_world(world_id)
            self._uow.worlds.mark_failed(world_id)
            self._uow.commit()
            raise ConflictError("SIMULATION_FAILED", "Simulation engine failed") from exc

        compute_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        self._uow.simulation.save_advance(world_id, batch)
        self._uow.worlds.advance_tick(
            world_id, new_tick=batch.to_tick, expected_version=world.version
        )
        self._uow.commit()
        persist_ms = (time.perf_counter() - started) * 1000

        return TickAdvanceRead(
            from_tick=batch.from_tick,
            to_tick=batch.to_tick,
            event_count=batch.event_count,
            last_event_sequence=batch.last_event_sequence,
            transaction_count=batch.transaction_count,
            compute_ms=compute_ms,
            persist_ms=persist_ms,
        )
