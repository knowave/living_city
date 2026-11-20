"""정부 월말 처리: 복지와 공공 조달."""

from simulation_engine.economy import AccountOwnerType as OT
from simulation_engine.economy import AccountType, TransactionType
from simulation_engine.economy.ledger import post_transaction
from simulation_engine.policies.employment import OPERATING
from simulation_engine.world.config import BUSINESS_SERVICE, WHOLESALE


def _treasury(state):
    return state.account_of(OT.GOVERNMENT, None, AccountType.TREASURY)


def pay_welfare(ctx) -> None:
    """실직자에게 id 순으로 welfare_amount를 전액 지급. 국고가 한 명분에 모자라면 거기서 중단(부분 지급 없음)."""
    state, acc = ctx.state, ctx.state.month_accumulators
    amount = state.current_policy(ctx.tick).welfare_amount
    if amount <= 0:
        return
    treasury = _treasury(state)
    for c in state.ordered("citizens"):
        if c.employment_status != "UNEMPLOYED":
            continue
        if treasury.balance < amount:
            break
        post_transaction(ctx, TransactionType.WELFARE, [(treasury.id, -amount), (state.account_of(OT.CITIZEN, c.id).id, amount)],
                         f"WELFARE:{ctx.tick}:{c.id}", {"citizen_id": str(c.id)})
        state.last_month_income[c.id] = state.last_month_income.get(c.id, 0) + amount
        acc["welfare_total"] = acc.get("welfare_total", 0) + amount


def procure(ctx) -> None:
    """예산 = (국고 - welfare_amount × 현재 실직자 수) × bps // 10000 을 운영 중 WHOLESALE/BUSINESS_SERVICE에 균등 분할(나머지는 id 순 1원씩)."""
    state, acc = ctx.state, ctx.state.month_accumulators
    welfare = state.current_policy(ctx.tick).welfare_amount
    unemployed = sum(1 for c in state.citizens.values() if c.employment_status == "UNEMPLOYED")
    treasury = _treasury(state)
    budget = (treasury.balance - welfare * unemployed) * ctx.config.procurement_budget_bps // 10_000
    targets = [c for c in state.ordered("companies") if c.industry in (WHOLESALE, BUSINESS_SERVICE) and c.status in OPERATING]
    if budget <= 0 or not targets:
        return
    share, rem = divmod(budget, len(targets))
    for i, co in enumerate(targets):
        amt = share + (1 if i < rem else 0)
        if amt == 0:
            continue
        post_transaction(ctx, TransactionType.PUBLIC_PROCUREMENT, [(treasury.id, -amt), (state.account_of(OT.COMPANY, co.id).id, amt)],
                         f"PUBLIC_PROCUREMENT:{ctx.tick}:{co.id}", {"company_id": str(co.id)})
        acc[f"revenue_procurement:{co.id}"] = acc.get(f"revenue_procurement:{co.id}", 0) + amt
        acc["procurement_total"] = acc.get("procurement_total", 0) + amt
