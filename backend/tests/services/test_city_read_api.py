import uuid

import pytest

from app.core.exceptions import DomainValidationError, NotFoundError
from app.repositories.interfaces import NewPolicy
from app.schemas.city import (
    BuildingRangeQuery,
    BuildingRead,
    CitizenQuery,
    CitizenRead,
    CompanyRead,
    EmploymentRead,
    MetricRead,
    MovementRead,
)
from app.schemas.enums import AccountOwnerType, MetricCode, MetricPeriod, MetricUnit
from app.schemas.world import WorldCreate
from app.services import CityQueryService, WorldService
from tests.services.fakes import FakeEnginePort, FakeUnitOfWork


@pytest.fixture
def uow():
    return FakeUnitOfWork()


@pytest.fixture
def wid(uow):
    w = WorldService(uow, FakeEnginePort(), "0").create_world(WorldCreate(name="w"))
    uow.policies.add(NewPolicy(w.id, 1500, 0, 0, 1))
    return w.id


@pytest.fixture
def svc(uow, wid):
    uow.consistent_reads = 0
    return CityQueryService(uow)


def cit(wid, activity="IDLE", status="EMPLOYED", building=None):
    return CitizenRead(
        id=uuid.uuid4(), world_id=wid, household_id=None, name="c", age=30, home_building_id=None,
        current_building_id=building, employment_status=status, employer_id=None, happiness=50,
        health=50, skills={}, risk_tolerance=0.5, consumption_preference=0.5,
        current_activity=activity, current_destination=None, arrival_tick=None)


def comp(wid, status="ACTIVE", industry="X"):
    return CompanyRead(id=uuid.uuid4(), world_id=wid, name="co", industry=industry, building_id=None,
                       employee_capacity=5, employee_count=1, base_wage=100, operating_cost=10,
                       status=status)


def bld(wid, x, y, w=2, h=2):
    return BuildingRead(id=uuid.uuid4(), world_id=wid, type="OFFICE", tile_x=x, tile_y=y, width=w,
                        height=h, capacity=1, occupied_capacity=0, status="ACTIVE")


def test_map_meta(svc, wid):
    m = svc.get_map(wid)
    assert (m.width, m.chunk_size, m.chunks_x, m.engine_area.width) == (512, 32, 16, 128)


def test_world_not_found_everywhere(svc):
    other = uuid.uuid4()
    calls = [
        lambda: svc.get_map(other),
        lambda: svc.get_buildings(other, BuildingRangeQuery()),
        lambda: svc.get_building(other, uuid.uuid4()),
        lambda: svc.list_citizens(other, CitizenQuery(), 10, 0),
        lambda: svc.list_companies(other, None, None, 10, 0),
        lambda: svc.list_company_employees(other, uuid.uuid4(), 10, 0),
        lambda: svc.get_summary(other),
        lambda: svc.get_view(other),
    ]
    for c in calls:
        with pytest.raises(NotFoundError) as e:
            c()
        assert e.value.code == "WORLD_NOT_FOUND"


def test_building_range_overlap_and_detail(svc, uow, wid):
    a, b, c = bld(wid, 0, 0), bld(wid, 10, 10), bld(wid, 5, 0, 4, 1)
    uow.buildings.items += [a, b, c]
    uow.buildings.company_ids_by_building[a.id] = [uuid.uuid4()]
    uow.buildings.households[a.id] = 3
    assert len(svc.get_buildings(wid, BuildingRangeQuery())) == 3
    # a covers x 0..1; c covers x 5..8: range 1..5 overlaps both, not b
    got = svc.get_buildings(wid, BuildingRangeQuery(x_min=1, x_max=5, y_min=0, y_max=0))
    assert {x.id for x in got} == {a.id, c.id}
    d = svc.get_building(wid, a.id)
    assert d.household_count == 3 and len(d.company_ids) == 1
    with pytest.raises(NotFoundError) as e:
        svc.get_building(wid, uuid.uuid4())
    assert e.value.code == "BUILDING_NOT_FOUND"
    with pytest.raises(DomainValidationError):
        svc.get_buildings(wid, BuildingRangeQuery(x_min=3, x_max=1))


def test_citizen_page_boundaries_and_cursor(svc, uow, wid):
    uow.citizens.items += [cit(wid) for _ in range(5)]
    uow.events.seq[wid] = 42
    p = svc.list_citizens(wid, CitizenQuery(), 2, 4)
    assert (len(p.items), p.total, p.limit, p.offset) == (1, 5, 2, 4)
    assert (p.as_of_tick, p.event_cursor) == (0, 42)
    assert svc.list_citizens(wid, CitizenQuery(), 2, 5).items == []
    assert svc.list_citizens(wid, CitizenQuery(), 500, 0).total == 5
    assert uow.consistent_reads == 3


def test_citizen_filters(svc, uow, wid):
    b = uuid.uuid4()
    uow.citizens.items += [cit(wid, "MOVING", "UNEMPLOYED", b), cit(wid), cit(wid, building=b)]
    assert svc.list_citizens(wid, CitizenQuery(employment_status="UNEMPLOYED"), 10, 0).total == 1
    assert svc.list_citizens(wid, CitizenQuery(current_activity="IDLE"), 10, 0).total == 2
    assert svc.list_citizens(wid, CitizenQuery(building_id=b), 10, 0).total == 2


def test_movement_only_for_moving_set_based(svc, uow, wid):
    mover, idle = cit(wid, "MOVING"), cit(wid)
    uow.citizens.items += [mover, idle]
    mv = MovementRead(from_building_id=uuid.uuid4(), to_building_id=uuid.uuid4(), start_tick=1, arrival_tick=9)
    uow.citizens.movement_by_citizen = {mover.id: mv, idle.id: mv}  # stale event of idle citizen
    items = {c.id: c for c in svc.list_citizens(wid, CitizenQuery(), 10, 0).items}
    assert items[mover.id].movement == mv and items[idle.id].movement is None
    assert uow.citizens.movement_queries == [[mover.id]]  # one query, MOVING ids only


def test_citizen_detail(svc, uow, wid):
    c = cit(wid)
    uow.citizens.items.append(c)
    uow.accounts.items[(wid, AccountOwnerType.CITIZEN, c.id)] = 7
    uow.citizens.employment_by_citizen[c.id] = EmploymentRead(company_id=uuid.uuid4(), salary=5, hired_tick=2)
    uow.events.seq[wid] = 3
    d = svc.get_citizen(wid, c.id)
    assert (d.cash_balance, d.employment.salary, d.movement, d.event_cursor) == (7, 5, None, 3)
    with pytest.raises(NotFoundError) as e:
        svc.get_citizen(wid, uuid.uuid4())
    assert e.value.code == "CITIZEN_NOT_FOUND"


def test_company_list_detail_employees(svc, uow, wid):
    a, b = comp(wid, "ACTIVE", "A"), comp(wid, "BANKRUPT", "B")
    uow.companies.items += [a, b]
    uow.companies.active[a.id] = 2
    uow.accounts.items[(wid, AccountOwnerType.COMPANY, a.id)] = 50
    assert svc.list_companies(wid, "BANKRUPT", None, 10, 0).total == 1
    assert svc.list_companies(wid, None, "A", 10, 0).items[0].cash_balance == 50
    d = svc.get_company(wid, a.id)
    assert (d.active_employees, d.cash_balance) == (2, 50)
    e1, e2 = cit(wid), cit(wid)
    uow.citizens.items += [e1, e2, cit(wid)]
    for e in (e1, e2):
        uow.citizens.employment_by_citizen[e.id] = EmploymentRead(company_id=a.id, salary=1, hired_tick=0)
    assert svc.list_company_employees(wid, a.id, 1, 0).total == 2
    assert svc.list_company_employees(wid, b.id, 10, 0).total == 0
    with pytest.raises(NotFoundError) as ex:
        svc.list_company_employees(wid, uuid.uuid4(), 10, 0)
    assert ex.value.code == "COMPANY_NOT_FOUND"
    with pytest.raises(NotFoundError) as ex:
        svc.get_company(wid, uuid.uuid4())
    assert ex.value.code == "COMPANY_NOT_FOUND"


def test_summary(svc, uow, wid):
    uow.citizens.items += [cit(wid) for _ in range(4)]
    uow.citizens.employment_by_citizen = {
        uow.citizens.items[0].id: EmploymentRead(company_id=uuid.uuid4(), salary=1, hired_tick=0)
    }
    uow.companies.items += [comp(wid, "ACTIVE"), comp(wid, "DISTRESSED"), comp(wid, "BANKRUPT")]
    uow.accounts.treasury, uow.accounts.internal = 10, 99

    def m(tick):
        return MetricRead(tick=tick, metric_code=MetricCode.POPULATION, metric_value=1,
                          unit=MetricUnit.COUNT, period=MetricPeriod.MONTHLY, definition_version=1)

    uow.metrics.items += [(wid, m(5)), (wid, m(9))]
    s = svc.get_summary(wid)
    assert (s.population, s.employed, s.unemployment_rate) == (4, 1, 0.75)
    assert (s.companies.active, s.companies.distressed, s.companies.bankrupt) == (1, 1, 1)
    assert (s.government_treasury, s.city_internal_money) == (10, 99)
    assert [x.tick for x in s.latest_metrics] == [9]


def test_summary_empty_world(svc, wid):
    assert svc.get_summary(wid).unemployment_rate == 0.0


def test_view(svc, uow, wid):
    uow.citizens.items.append(cit(wid))
    uow.buildings.items.append(bld(wid, 0, 0))
    uow.companies.items.append(comp(wid))
    v = svc.get_view(wid)
    assert (len(v.citizens), len(v.buildings), len(v.companies)) == (1, 1, 1)
    assert v.world.world_id == wid and v.world.event_cursor == v.event_cursor
