"""상점 도착자의 구매와 귀가 출발."""

from simulation_engine.economy import AccountOwnerType
from simulation_engine.economy.ledger import post_transaction
from simulation_engine.economy.transaction import TransactionType
from simulation_engine.systems.movement import OPERATING, SHOP_INDUSTRIES, daily_budget, start_move


def monthly_budget(state, config, citizen) -> int:
    cash = state.account_of(AccountOwnerType.CITIZEN, citizen.id).balance
    return (
        state.last_month_income.get(citizen.id, 0) * citizen.consumption_preference // 10000
        + max(0, cash - config.cash_reserve) * config.extra_spend_bps // 10000
    )


def set_monthly_budgets(ctx) -> None:
    for c in ctx.state.ordered("citizens"):
        ctx.state.monthly_budget[c.id] = monthly_budget(ctx.state, ctx.config, c)


def depart(ctx) -> None:
    """직전 Tick부터 상점에 있던 시민의 귀가 출발. movement.run보다 먼저 호출한다."""
    for c in ctx.state.ordered("citizens"):
        if c.current_activity == "SHOPPING":
            start_move(ctx, c, c.home_building_id, "home")


def run(ctx) -> None:
    """이번 Tick에 상점에 도착한 시민의 구매. 상점에 1 Tick 머물고 다음 Tick depart에서 귀가한다."""
    state = ctx.state
    for c in state.ordered("citizens"):
        if c.current_activity != "SHOPPING":
            continue
        shop = next(
            (co for co in state.ordered("companies")
             if co.building_id == c.current_building_id and co.industry in SHOP_INDUSTRIES and co.status in OPERATING),
            None,
        )
        if shop:
            acc = state.account_of(AccountOwnerType.CITIZEN, c.id)
            amount = daily_budget(ctx, c)
            if amount > 0:
                post_transaction(
                    ctx,
                    TransactionType.PURCHASE,
                    [(acc.id, -amount), (state.account_of(AccountOwnerType.COMPANY, shop.id).id, amount)],
                    f"PURCHASE:{ctx.tick}:{c.id}",
                    {"company_id": str(shop.id), "category": "consumer"},
                )
                acc_m = state.month_accumulators
                acc_m[f"revenue_consumer:{shop.id}"] = acc_m.get(f"revenue_consumer:{shop.id}", 0) + amount
                acc_m["consumption_total"] = acc_m.get("consumption_total", 0) + amount
