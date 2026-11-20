import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import CompanyStatus, MetricCode, MetricPeriod, MetricUnit
from app.schemas.world import WorldStateRead

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    as_of_tick: int
    event_cursor: int


class EngineAreaRead(BaseModel):
    x: int
    y: int
    width: int
    height: int


class MapMetaRead(BaseModel):
    width: int
    height: int
    chunk_size: int
    chunks_x: int
    chunks_y: int
    tile_schema_version: int
    engine_area: EngineAreaRead


class BuildingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    world_id: uuid.UUID
    type: str
    tile_x: int
    tile_y: int
    width: int
    height: int
    capacity: int
    occupied_capacity: int
    status: str


class BuildingDetailRead(BuildingRead):
    company_ids: list[uuid.UUID]
    household_count: int


class BuildingRangeQuery(BaseModel):
    x_min: int | None = None
    x_max: int | None = None
    y_min: int | None = None
    y_max: int | None = None


@dataclass(frozen=True)
class CitizenFilter:
    employment_status: str | None = None
    current_activity: str | None = None
    building_id: uuid.UUID | None = None  # current_building_id == building_id
    company_id: uuid.UUID | None = None  # has an ACTIVE employment at this company


class CitizenQuery(BaseModel):
    employment_status: str | None = None
    current_activity: str | None = None
    building_id: uuid.UUID | None = None


class MovementRead(BaseModel):
    # frontend MovementEventDTO minus citizen_id (the citizen is the enclosing object)
    from_building_id: uuid.UUID
    to_building_id: uuid.UUID
    start_tick: int
    arrival_tick: int


class EmploymentRead(BaseModel):
    company_id: uuid.UUID
    salary: int
    hired_tick: int


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
    movement: MovementRead | None = None  # only while current_activity == "MOVING"
    employment: EmploymentRead | None = None  # ACTIVE employment


class CitizenDetailRead(CitizenRead):
    as_of_tick: int
    event_cursor: int


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


class CompanyDetailRead(CompanyRead):
    active_employees: int
    as_of_tick: int
    event_cursor: int


class CompanyCountsRead(BaseModel):
    active: int
    distressed: int
    bankrupt: int


class WorldViewRead(BaseModel):
    as_of_tick: int
    event_cursor: int
    world: WorldStateRead
    citizens: list[CitizenRead]
    buildings: list[BuildingRead]
    companies: list[CompanyRead]


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


class CitySummaryRead(BaseModel):
    as_of_tick: int
    event_cursor: int
    population: int
    employed: int
    unemployment_rate: float  # (population - employed) / population, 0.0 if population == 0
    companies: CompanyCountsRead
    government_treasury: int
    city_internal_money: int
    latest_metrics: list[MetricRead]
