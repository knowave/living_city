"""외부 자금 재유입(간소화 수출). 외부(SYSTEM CASH) 잔액의 export_bps를 운영 중 기업에 나눈다."""

from simulation_engine.economy import AccountOwnerType as OT
from simulation_engine.economy import AccountType, TransactionType
from simulation_engine.economy.ledger import post_transaction
from simulation_engine.policies.employment import OPERATING


def pay_exports(ctx) -> None:
    """budget = 외부 잔액 × export_bps // 10000 을 균등 분할, 나머지 원은 id 순 1원씩.
    evaluate_status보다 먼저 실행되므로 수출 수입이 당월 상태 평가와 채용 잉여에 반영된다."""
    state, acc = ctx.state, ctx.state.month_accumulators
    external = state.account_of(OT.SYSTEM, None, AccountType.CASH)
    targets = [c for c in state.ordered("companies") if c.status in OPERATING]
    budget = external.balance * ctx.config.export_bps // 10_000
    if budget <= 0 or not targets:
        return
    share, rem = divmod(budget, len(targets))
    for i, co in enumerate(targets):
        amt = share + (1 if i < rem else 0)
        if amt == 0:
            continue
        post_transaction(ctx, TransactionType.EXPORT, [(external.id, -amt), (state.account_of(OT.COMPANY, co.id).id, amt)],
                         f"EXPORT:{ctx.tick}:{co.id}", {"company_id": str(co.id), "category": "export"})
        acc[f"revenue_export:{co.id}"] = acc.get(f"revenue_export:{co.id}", 0) + amt
        acc["export_total"] = acc.get("export_total", 0) + amt
