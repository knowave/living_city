import secrets
from uuid import UUID

from app.core.exceptions import DomainValidationError, InvalidStateError, NotFoundError
from app.repositories.interfaces import NewPolicy, NewWorld, UnitOfWork
from app.schemas.enums import WorldStatus
from app.schemas.world import (
    PolicyRead,
    PolicyUpdate,
    SimulationUpdate,
    WorldCreate,
    WorldRead,
    WorldStateRead,
)
from app.usecases.world import WorldUseCase

ALLOWED_SPEEDS = {1, 4, 16}
MAX_TAX_RATE = 10000
INITIAL_TAX_RATE = 1500

S = WorldStatus
ALLOWED_TRANSITIONS = {
    S.INITIALIZED: {S.RUNNING, S.ARCHIVED},
    S.RUNNING: {S.PAUSED, S.ARCHIVED},
    S.PAUSED: {S.RUNNING, S.ARCHIVED},
    S.FAILED: set(),
    S.ARCHIVED: set(),
}


class WorldService(WorldUseCase):
    def __init__(self, uow: UnitOfWork, engine_version_default: str) -> None:
        self._uow = uow
        self._engine_version_default = engine_version_default

    def _world(self, world_id: UUID) -> WorldRead:
        world = self._uow.worlds.get(world_id)
        
        if world is None:
            raise NotFoundError("WORLD_NOT_FOUND", "World not found")
        
        return world

    def create_world(self, data: WorldCreate) -> WorldRead:
        seed = data.seed if data.seed is not None else secrets.randbits(63)
        
        world = self._uow.worlds.add(
            NewWorld(
                name=data.name,
                seed=seed,
                engine_version=data.engine_version or self._engine_version_default,
            )
        )

        self._uow.policies.add(
            NewPolicy(
                world_id=world.id,
                income_tax_rate=INITIAL_TAX_RATE,
                welfare_amount=0,
                effective_tick=0,
                version=1,
            )
        )
        
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
        )

    def change_simulation(self, world_id: UUID, data: SimulationUpdate) -> WorldRead:
        if data.status is None and data.speed is None:
            raise DomainValidationError(
                "INVALID_SIMULATION_UPDATE", "status or speed is required"
            )
        
        if data.speed is not None and data.speed not in ALLOWED_SPEEDS:
            raise DomainValidationError("INVALID_SPEED", "speed must be one of 1, 4, 16")
        
        world = self._world(world_id)
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
        
        world = self._world(world_id)
        
        if world.status == S.ARCHIVED:
            raise InvalidStateError("INVALID_STATE_TRANSITION", "World is archived")
        
        latest = self._uow.policies.latest(world_id)
        
        if latest is None:
            raise NotFoundError("POLICY_NOT_FOUND", "World has no policy")
        
        policy = self._uow.policies.add(
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
