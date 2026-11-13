import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import WorldStatus


class WorldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    seed: int | None = None  # None -> service generates
    engine_version: str | None = None  # None -> settings.ENGINE_VERSION


class WorldRead(BaseModel):
    """Includes `version` (optimistic-lock counter of worlds.version) so services can pass
    expected_version back to WorldRepository.update_simulation without exposing ORM rows.
    The API layer may drop it via response_model if undesired."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    seed: int
    current_tick: int
    speed: int
    status: WorldStatus
    engine_version: str
    version: int
    created_at: datetime
    updated_at: datetime


class PolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    world_id: uuid.UUID
    income_tax_rate: int  # basis points, 1500 = 15%
    welfare_amount: int
    effective_tick: int
    version: int


class WorldStateRead(BaseModel):
    world_id: uuid.UUID
    status: WorldStatus
    current_tick: int
    speed: int
    event_cursor: int  # max world_events.sequence (0 if none)
    current_policy: PolicyRead


class SimulationUpdate(BaseModel):
    status: WorldStatus | None = None
    speed: int | None = None


class PolicyUpdate(BaseModel):
    income_tax_rate: int | None = None
    welfare_amount: int | None = None
