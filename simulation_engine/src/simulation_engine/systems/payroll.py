"""월말 급여와 소득세.

규칙: 회사 잔액 < 급여 총액이면 아무도 지급하지 않고 `payroll_failed:{company_id}`=1 로 표시한다
(evaluate_status가 BANKRUPT 처리). 소득세는 gross×rate_bps//10000 (floor).
"""

from simulation_engine.economy import AccountOwnerType as OT
from simulation_engine.economy import TransactionType
from simulation_engine.economy.ledger import post_transaction
from simulation_engine.policies.employment import OPERATING, active_by_company
from simulation_engine.policies.taxation import income_tax


def run(ctx) -> None:
    state, acc = ctx.state, ctx.state.month_accumulators
    rate = state.current_policy(ctx.tick).income_tax_rate
    treasury = state.account_of(OT.GOVERNMENT, None, "TREASURY")
    for c in state.citizens:
        state.last_month_income[c] = 0
    by_company = active_by_company(state)
    for company in state.ordered("companies"):
        if company.status not in OPERATING:
            continue
        emps = by_company.get(company.id, [])
        co_acc = state.account_of(OT.COMPANY, company.id)
        if co_acc.balance < sum(e.salary for e in emps):
            acc[f"payroll_failed:{company.id}"] = 1
            continue
        for e in emps:
            c_acc = state.account_of(OT.CITIZEN, e.citizen_id)
            key = f"{ctx.tick}:{e.id}"
            post_transaction(ctx, TransactionType.SALARY, [(co_acc.id, -e.salary), (c_acc.id, e.salary)],
                             f"SALARY:{key}", {"company_id": str(company.id), "citizen_id": str(e.citizen_id)})
            tax = income_tax(e.salary, rate)
            if tax:
                post_transaction(ctx, TransactionType.INCOME_TAX, [(c_acc.id, -tax), (treasury.id, tax)],
                                 f"INCOME_TAX:{key}", {"citizen_id": str(e.citizen_id), "rate_bps": rate})
            state.last_month_income[e.citizen_id] += e.salary - tax
            acc[f"payroll:{company.id}"] = acc.get(f"payroll:{company.id}", 0) + e.salary
            acc["tax_total"] = acc.get("tax_total", 0) + tax
