"""시민 이동 시작(start_move)과 도착 처리(arrival_tick == tick)."""

import math

from simulation_engine.clock import day_of, hour_of
from simulation_engine.economy import AccountOwnerType
from simulation_engine.events import generator as ev
from simulation_engine.world.config import RESTAURANT, RETAIL

OPERATING = ("ACTIVE", "DISTRESSED")
SHOP_INDUSTRIES = (RETAIL, RESTAURANT)


def start_move(ctx, citizen, to_building_id, purpose: str) -> None:
    """출발 건물에서 목적지로 이동을 시작한다. purpose: commute|home|shop. 이동 중에는 current_building_id=None (backend FK nullable)."""
    b = ctx.state.buildings
    src, dst = b[citizen.current_building_id], b[to_building_id]
    # shortcut: 도로 입구 없이 건물 tile 좌표 맨해튼 거리, 도로망 도입 시 입구 기준으로 교체
    dist = abs(src.tile_x - dst.tile_x) + abs(src.tile_y - dst.tile_y)
    arrival = ctx.tick + max(1, math.ceil(dist / ctx.config.tiles_per_tick))
    from_id = citizen.current_building_id
    citizen.current_activity = "MOVING"
    citizen.current_destination = to_building_id
    citizen.arrival_tick = arrival
    citizen.current_building_id = None
    ctx.state.movement_starts[citizen.id] = ctx.tick
    ctx.state.trip_purpose[citizen.id] = purpose
    ctx.emit(
        ev.CITIZEN_MOVEMENT_STARTED,
        {
            "citizen_id": str(citizen.id),
            "from_building_id": str(from_id),
            "to_building_id": str(to_building_id),
            "start_tick": ctx.tick,
            "arrival_tick": arrival,
        },
    )


def daily_budget(ctx, citizen) -> int:
    balance = ctx.state.account_of(AccountOwnerType.CITIZEN, citizen.id).balance
    return min(balance, ctx.state.monthly_budget.get(citizen.id, 0) // 30)


def try_shop(ctx, citizen) -> None:
    """집에 있는 시민이 오늘 소비일에 아직 소비 안 했고 예산이 있으면 상점으로 출발한다."""
    hour = hour_of(ctx.tick)
    shop_day = day_of(ctx.tick) if hour >= ctx.config.shop_hour else day_of(ctx.tick) - 1
    if ctx.state.last_shop_day.get(citizen.id, -2) >= shop_day or daily_budget(ctx, citizen) <= 0:
        return
    shops = [co for co in ctx.state.ordered("companies") if co.industry in SHOP_INDUSTRIES and co.status in OPERATING]
    if not shops:
        return
    ctx.state.last_shop_day[citizen.id] = shop_day
    start_move(ctx, citizen, ctx.rng("shop", ctx.tick, citizen.id).choice(shops).building_id, "shop")


def run(ctx) -> None:
    state = ctx.state
    for c in state.ordered("citizens"):
        if c.arrival_tick != ctx.tick:
            continue
        dest = c.current_destination
        c.current_building_id = dest
        c.current_destination = None
        c.arrival_tick = None
        state.movement_starts.pop(c.id, None)
        purpose = state.trip_purpose.pop(c.id, "home")
        if purpose == "home":
            c.current_activity = "AT_HOME"
            hour = hour_of(ctx.tick)
            if hour >= ctx.config.shop_hour or hour < ctx.config.work_start_hour:
                try_shop(ctx, c)  # 늦게 귀가한 시민도 그날 소비 (마감 없음)
            continue
        if purpose == "commute":
            employer = state.companies.get(c.employer_id) if c.employer_id else None
            ok = employer is not None and employer.building_id == dest and employer.status in OPERATING
            c.current_activity = "WORKING"
        else:
            ok = any(co.building_id == dest and co.industry in SHOP_INDUSTRIES and co.status in OPERATING for co in state.companies.values())
            c.current_activity = "SHOPPING"
        if not ok:  # 고용 종료·파산 등으로 의미 없는 도착: 즉시 귀가
            start_move(ctx, c, c.home_building_id, "home")
