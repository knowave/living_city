import uuid

import pytest

from app.core.exceptions import DomainValidationError, NotFoundError
from app.schemas.city import ChunkRangeQuery, ChunkRead, CitizenRead, CompanyRead, MetricQuery, MetricRead
from app.schemas.enums import AccountOwnerType, MetricCode, MetricPeriod, MetricUnit
from app.schemas.world import WorldCreate
from app.services import CityQueryService, WorldService
from tests.services.fakes import FakeUnitOfWork


@pytest.fixture
def uow():
    return FakeUnitOfWork()


@pytest.fixture
def wid(uow):
    return WorldService(uow, "0").create_world(WorldCreate(name="w")).id


@pytest.fixture
def svc(uow, wid):
    uow.commits = 0
    return CityQueryService(uow)


def chunk(wid, x, y):
    return ChunkRead(id=uuid.uuid4(), world_id=wid, chunk_x=x, chunk_y=y, chunk_size=16,
                     terrain_tiles=[], road_tiles=[], schema_version=1, revision=1)


def citizen(wid):
    return CitizenRead(
        id=uuid.uuid4(), world_id=wid, household_id=None, name="c", age=30, home_building_id=None,
        current_building_id=None, employment_status="EMPLOYED", employer_id=None, happiness=50,
        health=50, skills={}, risk_tolerance=0.5, consumption_preference=0.5,
        current_activity="IDLE", current_destination=None, arrival_tick=None)


def company(wid):
    return CompanyRead(id=uuid.uuid4(), world_id=wid, name="co", industry="X", building_id=None,
                       employee_capacity=5, employee_count=1, base_wage=100, operating_cost=10,
                       status="ACTIVE")


def test_world_not_found_everywhere(svc):
    other = uuid.uuid4()
    calls = [
        lambda: svc.get_chunks(other, ChunkRangeQuery()),
        lambda: svc.get_citizen(other, uuid.uuid4()),
        lambda: svc.get_company(other, uuid.uuid4()),
        lambda: svc.get_metrics(other, MetricQuery()),
    ]
    for c in calls:
        with pytest.raises(NotFoundError) as e:
            c()
        assert e.value.code == "WORLD_NOT_FOUND"


def test_chunks_filter(svc, uow, wid):
    uow.chunks.items += [chunk(wid, x, y) for x in range(3) for y in range(3)]
    uow.chunks.items.append(chunk(uuid.uuid4(), 0, 0))
    assert len(svc.get_chunks(wid, ChunkRangeQuery())) == 9
    got = svc.get_chunks(wid, ChunkRangeQuery(x_min=1, x_max=2, y_max=0))
    assert {(c.chunk_x, c.chunk_y) for c in got} == {(1, 0), (2, 0)}


@pytest.mark.parametrize("q", [ChunkRangeQuery(x_min=2, x_max=1), ChunkRangeQuery(y_min=5, y_max=0)])
def test_chunks_invalid_range(svc, wid, q):
    with pytest.raises(DomainValidationError) as e:
        svc.get_chunks(wid, q)
    assert e.value.code == "INVALID_CHUNK_RANGE"


def test_citizen_balance(svc, uow, wid):
    c = citizen(wid)
    uow.citizens.items.append(c)
    uow.accounts.items[(wid, AccountOwnerType.CITIZEN, c.id)] = 1234
    assert svc.get_citizen(wid, c.id).cash_balance == 1234


def test_citizen_missing_balance_none(svc, uow, wid):
    c = citizen(wid)
    uow.citizens.items.append(c)
    assert svc.get_citizen(wid, c.id).cash_balance is None


def test_citizen_other_world_and_unknown(svc, uow, wid):
    other = WorldService(uow, "0").create_world(WorldCreate(name="o")).id
    c = citizen(other)
    uow.citizens.items.append(c)
    for cid in (c.id, uuid.uuid4()):
        with pytest.raises(NotFoundError) as e:
            svc.get_citizen(wid, cid)
        assert e.value.code == "CITIZEN_NOT_FOUND"


def test_company(svc, uow, wid):
    c = company(wid)
    uow.companies.items.append(c)
    uow.accounts.items[(wid, AccountOwnerType.COMPANY, c.id)] = 99
    assert svc.get_company(wid, c.id).cash_balance == 99
    with pytest.raises(NotFoundError) as e:
        svc.get_company(wid, uuid.uuid4())
    assert e.value.code == "COMPANY_NOT_FOUND"


def test_metrics_filters(svc, uow, wid):
    def m(tick, code, period):
        return MetricRead(tick=tick, metric_code=code, metric_value=1, unit=MetricUnit.COUNT,
                          period=period, definition_version=1)

    uow.metrics.items += [
        (wid, m(1, MetricCode.POPULATION, MetricPeriod.HOURLY)),
        (wid, m(5, MetricCode.POPULATION, MetricPeriod.DAILY)),
        (wid, m(5, MetricCode.AVERAGE_SALARY, MetricPeriod.DAILY)),
        (uuid.uuid4(), m(5, MetricCode.POPULATION, MetricPeriod.DAILY)),
    ]
    assert len(svc.get_metrics(wid, MetricQuery())) == 3
    assert len(svc.get_metrics(wid, MetricQuery(metric_code=MetricCode.POPULATION))) == 2
    assert len(svc.get_metrics(wid, MetricQuery(period=MetricPeriod.DAILY, from_tick=2, to_tick=5))) == 2
    assert len(svc.get_metrics(wid, MetricQuery(from_tick=5, to_tick=5))) == 2


def test_metrics_invalid_range(svc, wid):
    with pytest.raises(DomainValidationError) as e:
        svc.get_metrics(wid, MetricQuery(from_tick=5, to_tick=1))
    assert e.value.code == "INVALID_TICK_RANGE"


def test_reads_do_not_commit(svc, uow, wid):
    svc.get_chunks(wid, ChunkRangeQuery())
    svc.get_metrics(wid, MetricQuery())
    assert uow.commits == 0 and uow.rollbacks == 0
