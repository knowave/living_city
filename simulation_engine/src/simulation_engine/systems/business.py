"""기업 월말 처리: 운영비 지급과 상태 평가."""

from simulation_engine.economy import AccountOwnerType as OT
from simulation_engine.economy import AccountType, TransactionType
from simulation_engine.economy.ledger import post_transaction
from simulation_engine.entities import CompanyStatus
from simulation_engine.policies.employment import OPERATING, active_by_company


def pay_operating_expenses(ctx) -> None:
    """운영비 = operating_cost. 정부 몫 = amount×gov_bps//10000, B2B 몫 = amount×b2b_bps//10000,
    나머지(floor 잔여 + 공급자 없는 B2B 몫)는 외부(SYSTEM CASH). B2B 몫은 같은 업종 공급자에 균등,
    나머지 원은 id 순 1원씩. 수취인마다 거래 1건. 잔액 < 운영비이면 아무것도 지급하지 않고 미납 처리."""
    state, cfg, acc = ctx.state, ctx.config, ctx.state.month_accumulators
    government = state.account_of(OT.GOVERNMENT, None, AccountType.TREASURY)
    external = state.account_of(OT.SYSTEM, None, AccountType.CASH)
    companies = state.ordered("companies")
    for co in companies:
        if co.status not in OPERATING or acc.get(f"payroll_failed:{co.id}"):
            continue
        amount = co.operating_cost
        co_acc = state.account_of(OT.COMPANY, co.id)
        if amount <= 0:
            state.unpaid_opex[co.id] = 0
            continue
        if co_acc.balance < amount:
            state.unpaid_opex[co.id] = amount
            continue
        state.unpaid_opex[co.id] = 0
        b2b = amount * cfg.opex_b2b_bps // 10_000
        gov = amount * cfg.opex_government_bps // 10_000
        suppliers = [s for s in companies if s.industry == cfg.supplier_of.get(co.industry) and s.id != co.id and s.status in OPERATING]
        paid_b2b = 0
        if suppliers:
            share, rem = divmod(b2b, len(suppliers))
            for i, s in enumerate(suppliers):
                amt = share + (1 if i < rem else 0)
                if amt:
                    _pay(ctx, co, co_acc, state.account_of(OT.COMPANY, s.id), amt, "b2b", s.id)
                    acc[f"revenue_b2b:{s.id}"] = acc.get(f"revenue_b2b:{s.id}", 0) + amt
            paid_b2b = b2b
        if gov:
            _pay(ctx, co, co_acc, government, gov, "government", None)
        ext = amount - paid_b2b - gov
        if ext:
            _pay(ctx, co, co_acc, external, ext, "external", None)
        acc["opex_b2b_total"] = acc.get("opex_b2b_total", 0) + paid_b2b
        acc["opex_government_total"] = acc.get("opex_government_total", 0) + gov
        acc["opex_external_total"] = acc.get("opex_external_total", 0) + ext
        acc[f"opex_paid:{co.id}"] = amount


def _pay(ctx, co, co_acc, to_acc, amt, category, supplier_id) -> None:
    key = f"OPERATING_EXPENSE:{ctx.tick}:{co.id}:{category}" + (f":{supplier_id}" if supplier_id else "")
    post_transaction(ctx, TransactionType.OPERATING_EXPENSE, [(co_acc.id, -amt), (to_acc.id, amt)], key,
                     {"expense_category": category, "supplier_company_id": str(supplier_id) if supplier_id else None,
                      "period_tick": ctx.tick, "company_id": str(co.id)})


def _set_status(ctx, co, new: str) -> None:
    ctx.emit("company.status.changed", {"company_id": str(co.id), "from_status": co.status, "to_status": new})
    co.status = new


def evaluate_status(ctx) -> None:
    """월 고정비 = 활성 고용 급여 합 + operating_cost.
    ACTIVE→DISTRESSED(현금<고정비 또는 미납, 연속 월수 1), DISTRESSED→ACTIVE(현금>=고정비×2, 월수 0),
    DISTRESSED 유지 시 월수+1. 급여 미지급 또는 월수>=3이면 BANKRUPT(고용 전부 종료)."""
    state, cfg, acc = ctx.state, ctx.config, ctx.state.month_accumulators
    by_company = active_by_company(state)
    for co in state.ordered("companies"):
        if co.status not in OPERATING:
            continue
        cash = state.account_of(OT.COMPANY, co.id).balance
        fixed = sum(e.salary for e in by_company.get(co.id, [])) + co.operating_cost
        months = state.distressed_months.get(co.id, 0)
        bankrupt = bool(acc.get(f"payroll_failed:{co.id}"))
        if not bankrupt:
            worsening = cash < fixed * cfg.distress_cash_months or state.unpaid_opex.get(co.id, 0) > 0
            if co.status == CompanyStatus.ACTIVE.value:
                if worsening:
                    _set_status(ctx, co, CompanyStatus.DISTRESSED.value)
                    months = 1
            elif not worsening and cash >= fixed * cfg.recovery_cash_months:  # 미납 달에는 회복하지 않는다
                _set_status(ctx, co, CompanyStatus.ACTIVE.value)
                months = 0
            else:
                months += 1
            bankrupt = months >= cfg.bankrupt_distressed_months
        state.distressed_months[co.id] = months
        if bankrupt:
            for e in by_company.get(co.id, []):
                e.status = "TERMINATED"
                e.terminated_tick = ctx.tick
                c = state.citizens[e.citizen_id]
                c.employment_status = "UNEMPLOYED"
                c.employer_id = None
                ctx.emit("citizen.employment.changed", {"citizen_id": str(c.id), "company_id": str(co.id),
                                                        "employment_status": "UNEMPLOYED", "reason": "bankruptcy"})
            co.employee_count = 0
            _set_status(ctx, co, CompanyStatus.BANKRUPT.value)
            acc["bankrupt_count"] = acc.get("bankrupt_count", 0) + 1
