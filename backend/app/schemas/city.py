import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import CompanyStatus, MetricCode, MetricPeriod, MetricUnit


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    world_id: uuid.UUID
    chunk_x: int
    chunk_y: int
    chunk_size: int
    terrain_tiles: list[int]
    road_tiles: list[int]
    schema_version: int
    revision: int


class ChunkRangeQuery(BaseModel):
    x_min: int | None = None
    x_max: int | None = None
    y_min: int | None = None
    y_max: int | None = None


class CitizenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    world_id: uuid.UUID
    household_id: uuid.UUID | None
    name: str
    age: int
    home_building_id: uuid.UUID | None
    current_building_id: uuid.UUID | None
    employment_status: str
    employer_id: uuid.UUID | None
    happiness: int
    health: int
    skills: dict
    risk_tolerance: float
    consumption_preference: float
    current_activity: str
    current_destination: uuid.UUID | None
    arrival_tick: int | None
    cash_balance: int | None = None  # filled by service from AccountRepository


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    world_id: uuid.UUID
    name: str
    industry: str
    building_id: uuid.UUID | None
    employee_capacity: int
    employee_count: int
    base_wage: int
    operating_cost: int
    status: CompanyStatus
    cash_balance: int | None = None


class MetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tick: int
    metric_code: MetricCode
    metric_value: Decimal
    unit: MetricUnit
    period: MetricPeriod
    definition_version: int


class MetricQuery(BaseModel):
    metric_code: MetricCode | None = None
    period: MetricPeriod | None = None
    from_tick: int | None = None
    to_tick: int | None = None
