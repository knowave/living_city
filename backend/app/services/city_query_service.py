from uuid import UUID

from app.core.exceptions import DomainValidationError, NotFoundError
from app.maps import tiles
from app.repositories.interfaces import UnitOfWork
from app.schemas.city import (
    BuildingDetailRead,
    BuildingRangeQuery,
    BuildingRead,
    ChunkRangeQuery,
    ChunkRead,
    CitizenDetailRead,
    CitizenFilter,
    CitizenQuery,
    CitizenRead,
    CitySummaryRead,
    CompanyCountsRead,
    CompanyDetailRead,
    CompanyRead,
    EngineAreaRead,
    MapMetaRead,
    MetricQuery,
    MetricRead,
    Page,
    WorldViewRead,
)
from app.schemas.enums import AccountOwnerType, CompanyStatus
from app.schemas.world import WorldRead, WorldStateRead
from app.usecases.city import CityQueryUseCase


class CityQueryService(CityQueryUseCase):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def _require_world(self, world_id: UUID) -> WorldRead:
        world = self._uow.worlds.get(world_id)

        if world is None:
            raise NotFoundError("WORLD_NOT_FOUND", "World not found")

        return world

    def _begin(self, world_id: UUID) -> tuple[WorldRead, int, int]:
        """Consistent-read transaction first, then (world, as_of_tick, event_cursor)."""
        self._uow.begin_consistent_read()
        world = self._require_world(world_id)
        return world, world.current_tick, self._uow.events.max_sequence(world_id)

    def _enrich(self, world_id: UUID, citizens: list[CitizenRead]) -> list[CitizenRead]:
        ids = [c.id for c in citizens]
        balances = self._uow.accounts.cash_balances(world_id, AccountOwnerType.CITIZEN, ids)
        jobs = self._uow.citizens.employments(world_id, ids)
        moves = self._uow.citizens.movements(
            world_id, [c.id for c in citizens if c.current_activity == "MOVING"]
        )
        return [
            c.model_copy(
                update={
                    "cash_balance": balances.get(c.id),
                    "employment": jobs.get(c.id),
                    "movement": moves.get(c.id) if c.current_activity == "MOVING" else None,
                }
            )
            for c in citizens
        ]

    def _companies_with_cash(self, world_id: UUID, companies: list[CompanyRead]) -> list[CompanyRead]:
        balances = self._uow.accounts.cash_balances(
            world_id, AccountOwnerType.COMPANY, [c.id for c in companies]
        )
        return [c.model_copy(update={"cash_balance": balances.get(c.id)}) for c in companies]

    def get_map(self, world_id: UUID) -> MapMetaRead:
        self._require_world(world_id)
        x, y, w, h = tiles.ENGINE_AREA
        return MapMetaRead(
            width=tiles.MAP_SIZE,
            height=tiles.MAP_SIZE,
            chunk_size=tiles.CHUNK_SIZE,
            chunks_x=tiles.CHUNKS_PER_SIDE,
            chunks_y=tiles.CHUNKS_PER_SIDE,
            tile_schema_version=tiles.TILE_SCHEMA_VERSION,
            engine_area=EngineAreaRead(x=x, y=y, width=w, height=h),
        )

    def get_chunks(self, world_id: UUID, query: ChunkRangeQuery) -> list[ChunkRead]:
        self._require_world(world_id)

        for lo, hi in ((query.x_min, query.x_max), (query.y_min, query.y_max)):
            if lo is not None and hi is not None and lo > hi:
                raise DomainValidationError("INVALID_CHUNK_RANGE", "min must be <= max")

        return self._uow.chunks.list(world_id, query)

    def get_buildings(self, world_id: UUID, query: BuildingRangeQuery) -> list[BuildingRead]:
        self._require_world(world_id)

        for lo, hi in ((query.x_min, query.x_max), (query.y_min, query.y_max)):
            if lo is not None and hi is not None and lo > hi:
                raise DomainValidationError("INVALID_TILE_RANGE", "min must be <= max")

        return self._uow.buildings.list(world_id, query)

    def get_building(self, world_id: UUID, building_id: UUID) -> BuildingDetailRead:
        self._require_world(world_id)
        building = self._uow.buildings.get(world_id, building_id)

        if building is None:
            raise NotFoundError("BUILDING_NOT_FOUND", "Building not found")

        return BuildingDetailRead(
            **building.model_dump(),
            company_ids=self._uow.buildings.company_ids(world_id, building_id),
            household_count=self._uow.buildings.household_count(world_id, building_id),
        )

    def list_citizens(
        self, world_id: UUID, query: CitizenQuery, limit: int, offset: int
    ) -> Page[CitizenRead]:
        _, tick, cursor = self._begin(world_id)
        rows, total = self._uow.citizens.list(
            world_id, CitizenFilter(**query.model_dump()), limit, offset
        )
        return Page[CitizenRead](
            items=self._enrich(world_id, rows),
            total=total, limit=limit, offset=offset, as_of_tick=tick, event_cursor=cursor,
        )

    def get_citizen(self, world_id: UUID, citizen_id: UUID) -> CitizenDetailRead:
        _, tick, cursor = self._begin(world_id)
        citizen = self._uow.citizens.get(world_id, citizen_id)

        if citizen is None:
            raise NotFoundError("CITIZEN_NOT_FOUND", "Citizen not found")

        (full,) = self._enrich(world_id, [citizen])
        return CitizenDetailRead(**full.model_dump(), as_of_tick=tick, event_cursor=cursor)

    def list_companies(
        self, world_id: UUID, status: str | None, industry: str | None, limit: int, offset: int
    ) -> Page[CompanyRead]:
        _, tick, cursor = self._begin(world_id)
        rows, total = self._uow.companies.list(world_id, status, industry, limit, offset)
        return Page[CompanyRead](
            items=self._companies_with_cash(world_id, rows),
            total=total, limit=limit, offset=offset, as_of_tick=tick, event_cursor=cursor,
        )

    def get_company(self, world_id: UUID, company_id: UUID) -> CompanyDetailRead:
        _, tick, cursor = self._begin(world_id)
        company = self._uow.companies.get(world_id, company_id)

        if company is None:
            raise NotFoundError("COMPANY_NOT_FOUND", "Company not found")

        (full,) = self._companies_with_cash(world_id, [company])
        return CompanyDetailRead(
            **full.model_dump(),
            active_employees=self._uow.companies.active_employees(world_id, company_id),
            as_of_tick=tick,
            event_cursor=cursor,
        )

    def list_company_employees(
        self, world_id: UUID, company_id: UUID, limit: int, offset: int
    ) -> Page[CitizenRead]:
        _, tick, cursor = self._begin(world_id)

        if self._uow.companies.get(world_id, company_id) is None:
            raise NotFoundError("COMPANY_NOT_FOUND", "Company not found")

        rows, total = self._uow.citizens.list(
            world_id, CitizenFilter(company_id=company_id), limit, offset
        )
        return Page[CitizenRead](
            items=self._enrich(world_id, rows),
            total=total, limit=limit, offset=offset, as_of_tick=tick, event_cursor=cursor,
        )

    def get_summary(self, world_id: UUID) -> CitySummaryRead:
        _, tick, cursor = self._begin(world_id)
        population = self._uow.citizens.count(world_id)
        employed = self._uow.citizens.count_employed(world_id)
        by_status = self._uow.companies.count_by_status(world_id)
        return CitySummaryRead(
            as_of_tick=tick,
            event_cursor=cursor,
            population=population,
            employed=employed,
            unemployment_rate=(population - employed) / population if population else 0.0,
            companies=CompanyCountsRead(
                active=by_status.get(CompanyStatus.ACTIVE.value, 0),
                distressed=by_status.get(CompanyStatus.DISTRESSED.value, 0),
                bankrupt=by_status.get(CompanyStatus.BANKRUPT.value, 0),
            ),
            government_treasury=self._uow.accounts.government_treasury(world_id),
            city_internal_money=self._uow.accounts.city_internal_money(world_id),
            latest_metrics=self._uow.metrics.latest_monthly(world_id),
        )

    def get_view(self, world_id: UUID) -> WorldViewRead:
        world, tick, cursor = self._begin(world_id)
        policy = self._uow.policies.current(world_id, tick)

        if policy is None:
            raise NotFoundError("POLICY_NOT_FOUND", "World has no policy")

        citizens, _ = self._uow.citizens.list(world_id, CitizenFilter(), None, 0)
        companies, _ = self._uow.companies.list(world_id, None, None, None, 0)
        return WorldViewRead(
            as_of_tick=tick,
            event_cursor=cursor,
            world=WorldStateRead(
                world_id=world.id, status=world.status, current_tick=tick, speed=world.speed,
                event_cursor=cursor, current_policy=policy,
            ),
            citizens=self._enrich(world_id, citizens),
            buildings=self._uow.buildings.list(world_id, BuildingRangeQuery()),
            companies=self._companies_with_cash(world_id, companies),
        )

    def get_metrics(self, world_id: UUID, query: MetricQuery) -> list[MetricRead]:
        self._require_world(world_id)

        if (
            query.from_tick is not None
            and query.to_tick is not None
            and query.from_tick > query.to_tick
        ):
            raise DomainValidationError("INVALID_TICK_RANGE", "from_tick must be <= to_tick")

        return self._uow.metrics.list(world_id, query)
