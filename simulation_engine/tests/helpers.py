"""수동 세계 빌더. 작업자별 단위 테스트에서 작은 세계를 만들 때 쓴다."""

import uuid

from simulation_engine import __version__
from simulation_engine.context import TickContext
from simulation_engine.economy import Account, AccountOwnerType, AccountType, TransactionType
from simulation_engine.economy.ledger import post_transaction
from simulation_engine.entities import (
    Building,
    Citizen,
    Company,
    CompanyStatus,
    Employment,
    Household,
    World,
    WorldPolicy,
)
from simulation_engine.world.config import RETAIL, SimulationConfig
from simulation_engine.world.state import WorldState

OT = AccountOwnerType


def make_state(seed: int = 1, tax_bps: int = 1500, welfare: int = 0) -> WorldState:
    """정책 v1과 GOVERNMENT/TREASURY, SYSTEM/ISSUANCE, SYSTEM/CASH 계좌만 있는 빈 세계."""
    world = World(id=uuid.UUID(int=seed), name="test", seed=seed, engine_version=__version__)
    state = WorldState(world=world)
    policy = WorldPolicy(id=state.new_id("policy"), income_tax_rate=tax_bps, welfare_amount=welfare)
    state.policies[policy.id] = policy
    state.add_account(Account(id=state.new_id("account"), owner_type=OT.GOVERNMENT, account_type=AccountType.TREASURY))
    state.add_account(Account(id=state.new_id("account"), owner_type=OT.SYSTEM, account_type=AccountType.ISSUANCE))
    state.add_account(Account(id=state.new_id("account"), owner_type=OT.SYSTEM, account_type=AccountType.CASH))
    return state


def make_ctx(state: WorldState, config: SimulationConfig | None = None, tick: int | None = None) -> TickContext:
    return TickContext(state=state, config=config or SimulationConfig(), tick=state.tick if tick is None else tick)


def fund(state: WorldState, account: Account, amount: int, tick: int = 0) -> None:
    """SYSTEM/ISSUANCE에서 OPENING_BALANCE로 잔액을 채운다."""
    issuance = state.account_of(OT.SYSTEM, None, AccountType.ISSUANCE)
    post_transaction(
        make_ctx(state, tick=tick),
        TransactionType.OPENING_BALANCE,
        [(issuance.id, -amount), (account.id, amount)],
        f"opening:{account.id}",
    )


def add_building(state: WorldState, type: str = "COMMERCIAL", x: int = 0, y: int = 0, capacity: int = 10) -> Building:
    b = Building(id=state.new_id("building"), type=type, tile_x=x, tile_y=y, width=1, height=1, capacity=capacity, status="ACTIVE")
    state.buildings[b.id] = b
    return b


def add_citizen(state: WorldState, home: Building, balance: int = 0, preference: int = 7000) -> Citizen:
    household = Household(id=state.new_id("household"), residence_building_id=home.id)
    state.households[household.id] = household
    c = Citizen(
        id=state.new_id("citizen"),
        household_id=household.id,
        name="c",
        age=30,
        home_building_id=home.id,
        current_building_id=home.id,
        employment_status="UNEMPLOYED",
        happiness=50,
        health=100,
        risk_tolerance=5000,
        consumption_preference=preference,
        current_activity="AT_HOME",
    )
    state.citizens[c.id] = c
    acc = state.add_account(Account(id=state.new_id("account"), owner_type=OT.CITIZEN, citizen_id=c.id))
    if balance:
        fund(state, acc, balance)
    return c


def add_company(
    state: WorldState,
    building: Building,
    industry: str = RETAIL,
    balance: int = 0,
    base_wage: int = 2_400_000,
    operating_cost: int = 5_000_000,
    capacity: int = 10,
    status: str = CompanyStatus.ACTIVE.value,
) -> Company:
    co = Company(
        id=state.new_id("company"),
        name="co",
        industry=industry,
        building_id=building.id,
        employee_capacity=capacity,
        base_wage=base_wage,
        operating_cost=operating_cost,
        status=status,
    )
    state.companies[co.id] = co
    acc = state.add_account(Account(id=state.new_id("account"), owner_type=OT.COMPANY, company_id=co.id))
    if balance:
        fund(state, acc, balance)
    return co


def employ(state: WorldState, citizen: Citizen, company: Company, salary: int | None = None, tick: int = 0) -> Employment:
    e = Employment(
        id=state.new_id("employment"),
        citizen_id=citizen.id,
        company_id=company.id,
        salary=company.base_wage if salary is None else salary,
        hired_tick=tick,
        status="ACTIVE",
    )
    state.employments[e.id] = e
    citizen.employment_status = "EMPLOYED"
    citizen.employer_id = company.id
    company.employee_count += 1
    return e
