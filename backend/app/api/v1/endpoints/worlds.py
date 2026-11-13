import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_city_query_use_case, get_world_use_case
from app.schemas.city import (
    ChunkRangeQuery,
    ChunkRead,
    CitizenRead,
    CompanyRead,
    MetricQuery,
    MetricRead,
)
from app.schemas.world import (
    PolicyRead,
    PolicyUpdate,
    SimulationUpdate,
    WorldCreate,
    WorldRead,
    WorldStateRead,
)
from app.usecases.city import CityQueryUseCase
from app.usecases.world import WorldUseCase

router = APIRouter(prefix="/worlds", tags=["worlds"])


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


@router.get("/{world_id}/citizens/{citizen_id}", response_model=CitizenRead)
def get_citizen(
    world_id: uuid.UUID,
    citizen_id: uuid.UUID,
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.get_citizen(world_id, citizen_id)


@router.get("/{world_id}/companies/{company_id}", response_model=CompanyRead)
def get_company(
    world_id: uuid.UUID,
    company_id: uuid.UUID,
    use_case: CityQueryUseCase = Depends(get_city_query_use_case),
):
    return use_case.get_company(world_id, company_id)


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
