"""초기 월드를 생성하는 책임을 담는다. 같은 (seed, config)이면 항상 같은 세계가 나온다."""

import hashlib
import uuid
from dataclasses import dataclass, field

from simulation_engine import __version__
from simulation_engine.context import TickContext
from simulation_engine.economy import Account, AccountOwnerType, AccountType, LedgerEntry, Transaction, TransactionType
from simulation_engine.economy.ledger import post_transaction
from simulation_engine.entities import (
    Building,
    BuildingType,
    Citizen,
    Company,
    Employment,
    Household,
    World,
    WorldPolicy,
)
from simulation_engine.events.models import WorldEvent
from simulation_engine.systems import consumption
from simulation_engine.utils.random import derive_rng
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.state import WorldState

OT = AccountOwnerType
BUILDING_SIZE = 2  # 모든 건물은 2x2 타일
INITIAL_HAPPINESS = 50  # 고정값. 시민 간 차이는 소비 성향·나이로 둔다.
INITIAL_HEALTH = 100
INITIAL_RISK_TOLERANCE_RANGE = (2000, 8000)  # bps


@dataclass(slots=True)
class GenerationResult:
    state: WorldState
    transactions: list[Transaction] = field(default_factory=list)  # tick 0 OPENING_BALANCE 거래
    ledger_entries: list[LedgerEntry] = field(default_factory=list)
    events: list[WorldEvent] = field(default_factory=list)


def _place_buildings(state: WorldState, config: SimulationConfig) -> dict[str, list[Building]]:
    plan = (
        (BuildingType.RESIDENTIAL, config.residential_buildings, config.residential_capacity),
        (BuildingType.COMMERCIAL, config.commercial_buildings, 0),
        (BuildingType.OFFICE, config.office_buildings, 0),
        (BuildingType.PUBLIC, config.public_buildings, 0),
    )
    limit = config.map_size - BUILDING_SIZE
    taken: list[tuple[int, int]] = []
    by_type: dict[str, list[Building]] = {}
    for kind, count, capacity in plan:
        for i in range(count):
            for attempt in range(10_000):  # shortcut: 거절 샘플링 상한, 맵이 꽉 차면 실패 처리
                rng = derive_rng(state.seed, "building", kind.value, i, attempt)
                x, y = rng.randint(0, limit), rng.randint(0, limit)
                if all(abs(x - tx) >= BUILDING_SIZE or abs(y - ty) >= BUILDING_SIZE for tx, ty in taken):
                    break
            else:
                raise ValueError("건물을 겹치지 않게 배치할 수 없음: map_size가 너무 작음")
            taken.append((x, y))
            b = Building(
                id=state.new_id("building"),
                type=kind.value,
                tile_x=x,
                tile_y=y,
                width=BUILDING_SIZE,
                height=BUILDING_SIZE,
                capacity=capacity,
                status="ACTIVE",
            )
            state.buildings[b.id] = b
            by_type.setdefault(kind.value, []).append(b)
    return by_type


def generate_world(seed: int, config: SimulationConfig | None = None, name: str = "Living City") -> GenerationResult:
    config = config or SimulationConfig()
    world_id = uuid.UUID(bytes=hashlib.sha256(f"{seed}:world".encode()).digest()[:16], version=4)
    state = WorldState(world=World(id=world_id, name=name, seed=seed, engine_version=__version__))
    ctx = TickContext(state=state, config=config, tick=0)

    policy = WorldPolicy(
        id=state.new_id("policy"),
        income_tax_rate=config.income_tax_rate_bps,
        welfare_amount=config.welfare_amount,
        effective_tick=0,
        version=1,
    )
    state.policies[policy.id] = policy

    # 가구 계좌는 만들지 않는다: 1인 1가구이고 모든 거래 주체는 시민 계좌이다.
    gov = state.add_account(Account(id=state.new_id("account"), owner_type=OT.GOVERNMENT, account_type=AccountType.TREASURY))
    issuance = state.add_account(Account(id=state.new_id("account"), owner_type=OT.SYSTEM, account_type=AccountType.ISSUANCE))
    state.add_account(Account(id=state.new_id("account"), owner_type=OT.SYSTEM, account_type=AccountType.CASH))

    buildings = _place_buildings(state, config)

    # 기업: 업종 순서대로 해당 유형 건물에 순환 배치
    companies: list[Company] = []
    used: dict[str, int] = {}
    for ind in config.industries:
        for i in range(ind.count):
            pool = buildings[ind.building_type]
            n = used.get(ind.building_type, 0)
            used[ind.building_type] = n + 1
            co = Company(
                id=state.new_id("company"),
                name=f"{ind.industry}-{i + 1}",
                industry=ind.industry,
                building_id=pool[n % len(pool)].id,
                employee_capacity=ind.employee_capacity,
                base_wage=ind.base_wage,
                operating_cost=config.operating_cost,
            )
            state.companies[co.id] = co
            state.add_account(Account(id=state.new_id("account"), owner_type=OT.COMPANY, company_id=co.id))
            companies.append(co)

    # 시민·가구: 주거 건물을 순서대로 정원까지 채운다
    homes = buildings[BuildingType.RESIDENTIAL.value]
    if config.citizen_count > sum(b.capacity for b in homes):
        raise ValueError("주거 정원이 시민 수보다 작음")
    citizens: list[Citizen] = []
    home_iter = iter(homes)
    home = next(home_iter)
    for i in range(config.citizen_count):
        while home.occupied_capacity >= home.capacity:
            home = next(home_iter)
        rng = derive_rng(state.seed, "citizen", i)
        household = Household(id=state.new_id("household"), residence_building_id=home.id)
        state.households[household.id] = household
        c = Citizen(
            id=state.new_id("citizen"),
            household_id=household.id,
            name=f"Citizen {i + 1:03d}",
            age=rng.randint(*config.citizen_age_range),
            home_building_id=home.id,
            current_building_id=home.id,
            employment_status="UNEMPLOYED",
            happiness=INITIAL_HAPPINESS,
            health=INITIAL_HEALTH,
            risk_tolerance=rng.randint(*INITIAL_RISK_TOLERANCE_RANGE),
            consumption_preference=rng.randint(*config.consumption_preference_range),
            current_activity="AT_HOME",
        )
        home.occupied_capacity += 1
        state.citizens[c.id] = c
        state.add_account(Account(id=state.new_id("account"), owner_type=OT.CITIZEN, citizen_id=c.id))
        state.last_month_income[c.id] = 0
        citizens.append(c)

    # 초기 고용: 시드로 섞은 앞 N명을 기업에 순환 배정 (정원이 찬 기업은 건너뜀)
    order = citizens[:]
    derive_rng(state.seed, "initial_employment").shuffle(order)
    open_companies = companies[:]
    for c in order[: min(config.initial_employed, len(order))]:
        if not open_companies:
            break
        co = open_companies.pop(0)
        e = Employment(
            id=state.new_id("employment"),
            citizen_id=c.id,
            company_id=co.id,
            salary=co.base_wage,
            hired_tick=0,
            status="ACTIVE",
        )
        state.employments[e.id] = e
        c.employment_status = "EMPLOYED"
        c.employer_id = co.id
        co.employee_count += 1
        state.last_month_income[c.id] = co.base_wage * config.first_month_income_bps // 10_000
        if co.employee_count < co.employee_capacity:
            open_companies.append(co)

    # 시작 자금: 모두 ISSUANCE에서 OPENING_BALANCE로만 배분 (생성 직후 전체 합계 0)
    def open_balance(account: Account, amount: int) -> None:
        if amount > 0:
            post_transaction(
                ctx, TransactionType.OPENING_BALANCE, [(issuance.id, -amount), (account.id, amount)], f"opening:{account.id}"
            )

    open_balance(gov, config.government_opening_balance)
    for co in companies:
        monthly = co.employee_count * co.base_wage + co.operating_cost
        open_balance(state.account_of(OT.COMPANY, co.id), config.company_opening_months * monthly)
    for c in citizens:
        open_balance(state.account_of(OT.CITIZEN, c.id), config.citizen_opening_balance)
        state.monthly_budget[c.id] = consumption.monthly_budget(state, config, c)

    return GenerationResult(state, ctx.transactions, ctx.ledger_entries, ctx.events)
