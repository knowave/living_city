import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_city_query_use_case, get_world_use_case
from app.schemas.city import (
    BuildingDetailRead,
    BuildingRangeQuery,
    BuildingRead,
    ChunkRangeQuery,
    ChunkRead,
    CitizenDetailRead,
    CitizenQuery,
    CitizenRead,
    CitySummaryRead,
    CompanyDetailRead,
    CompanyRead,
    MapMetaRead,
    MetricQuery,
    MetricRead,
    Page,
    WorldViewRead,
)
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
from app.usecases.city import CityQueryUseCase
from app.usecases.world import WorldUseCase

router = APIRouter(prefix="/worlds", tags=["worlds"])

Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]


@router.post("", status_code=201, response_model=WorldRead)
def create_world(body: WorldCreate, use_case: WorldUseCase = Depends(get_world_use_case)):
    return use_case.create_world(body)


@router.get("/{world_id}", response_model=WorldRead)
def get_world(world_id: uuid.UUID, use_case: WorldUseCase = Depends(get_world_use_case)):
    return use_case.get_world(world_id)


@router.get("/{world_id}/state", response_model=WorldStateRead)
def get_world_state(world_id: uuid.UUID, use_case: WorldUseCase = Depends(get_world_use_case)):
    return use_case.get_world_state(world_id)


@router.get("/{world_id}/chunks", response_model=list[ChunkRead])
def get_chunks(
    world_id: uuid.UUID,
    query: Annotated[ChunkRangeQuery, Query()],
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.get_chunks(world_id, query)


@router.get("/{world_id}/map", response_model=MapMetaRead)
def get_map(world_id: uuid.UUID, use_case: CityQueryUseCase = Depends(get_city_query_use_case)):
    return use_case.get_map(world_id)


@router.get("/{world_id}/buildings", response_model=list[BuildingRead])
def get_buildings(
    world_id: uuid.UUID,
    query: Annotated[BuildingRangeQuery, Query()],
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.get_buildings(world_id, query)


@router.get("/{world_id}/buildings/{building_id}", response_model=BuildingDetailRead)
def get_building(
    world_id: uuid.UUID,
    building_id: uuid.UUID,
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.get_building(world_id, building_id)


@router.get("/{world_id}/citizens", response_model=Page[CitizenRead])
def list_citizens(
    world_id: uuid.UUID,
    query: Annotated[CitizenQuery, Query()],
    limit: Limit = 100,
    offset: Offset = 0,
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.list_citizens(world_id, query, limit, offset)


@router.get("/{world_id}/citizens/{citizen_id}", response_model=CitizenDetailRead)
def get_citizen(
    world_id: uuid.UUID,
    citizen_id: uuid.UUID,
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.get_citizen(world_id, citizen_id)


@router.get("/{world_id}/companies", response_model=Page[CompanyRead])
def list_companies(
    world_id: uuid.UUID,
    status: str | None = None,
    industry: str | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.list_companies(world_id, status, industry, limit, offset)


@router.get("/{world_id}/companies/{company_id}", response_model=CompanyDetailRead)
def get_company(
    world_id: uuid.UUID,
    company_id: uuid.UUID,
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.get_company(world_id, company_id)


@router.get("/{world_id}/companies/{company_id}/employees", response_model=Page[CitizenRead])
def list_company_employees(
    world_id: uuid.UUID,
    company_id: uuid.UUID,
    limit: Limit = 100,
    offset: Offset = 0,
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.list_company_employees(world_id, company_id, limit, offset)


@router.get("/{world_id}/summary", response_model=CitySummaryRead)
def get_summary(world_id: uuid.UUID, use_case: CityQueryUseCase = Depends(get_city_query_use_case)):
    return use_case.get_summary(world_id)


@router.get("/{world_id}/view", response_model=WorldViewRead)
def get_view(world_id: uuid.UUID, use_case: CityQueryUseCase = Depends(get_city_query_use_case)):
    return use_case.get_view(world_id)


@router.get("/{world_id}/metrics", response_model=list[MetricRead])
def get_metrics(
    world_id: uuid.UUID,
    query: Annotated[MetricQuery, Query()],
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.get_metrics(world_id, query)


@router.patch("/{world_id}/simulation", response_model=WorldRead)
def change_simulation(
    world_id: uuid.UUID,
    body: SimulationUpdate,
    use_case: WorldUseCase = Depends(get_world_use_case),
):
    return use_case.change_simulation(world_id, body)


@router.patch("/{world_id}/policies", response_model=PolicyRead)
def change_policy(
    world_id: uuid.UUID,
    body: PolicyUpdate,
    use_case: WorldUseCase = Depends(get_world_use_case),
):
    return use_case.change_policy(world_id, body)


@router.post("/{world_id}/ticks", status_code=200, response_model=TickAdvanceRead)
def advance_ticks(
    world_id: uuid.UUID,
    body: TickAdvanceRequest,
    use_case: WorldUseCase = Depends(get_world_use_case),
):
    return use_case.advance_ticks(world_id, body)
