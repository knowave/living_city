"""월간 도시 지표 계산. 월말 Tick에 month_accumulators를 읽고 엔진이 비우기 전에 호출한다."""

from decimal import Decimal

from simulation_engine.economy import AccountOwnerType, AccountType
from simulation_engine.entities import CompanyStatus
from simulation_engine.metrics.models import MetricCode, MetricPeriod, MetricUnit, WorldMetric

_SIX_PLACES = Decimal("0.000001")
# 운영 중 기업 = ACTIVE + DISTRESSED. BANKRUPT·CLOSED는 제외한다.
_OPERATING = {CompanyStatus.ACTIVE.value, CompanyStatus.DISTRESSED.value}
_INTERNAL_OWNERS = {
    AccountOwnerType.CITIZEN,
    AccountOwnerType.HOUSEHOLD,
    AccountOwnerType.COMPANY,
    AccountOwnerType.GOVERNMENT,
}
_REVENUE_KINDS = {"revenue_consumer": "consumer", "revenue_b2b": "b2b", "revenue_procurement": "procurement",
                  "revenue_export": "export"}


def revenue_breakdown(state) -> dict[str, int]:
    """이번 달 기업 매출을 최종 소비·B2B·조달·수출로 나눈다 (지표 코드 없음, AC17 보조)."""
    out = {"consumer": 0, "b2b": 0, "procurement": 0, "export": 0}
    for key, amount in state.month_accumulators.items():
        kind, sep, _ = key.partition(":")
        if sep and kind in _REVENUE_KINDS:
            out[_REVENUE_KINDS[kind]] += amount
    return out


def city_internal_money(state) -> int:
    """도시 내부 자금 = CITIZEN/HOUSEHOLD/COMPANY/GOVERNMENT 계정 잔액 합. SYSTEM 계정은 제외한다."""
    return sum(a.balance for a in state.accounts.values() if a.owner_type in _INTERNAL_OWNERS)


def _metric(ctx, code: MetricCode, value, unit: MetricUnit) -> WorldMetric:
    return WorldMetric(
        id=ctx.state.new_id("metric"),
        tick=ctx.tick,
        metric_code=code,
        metric_value=Decimal(value),
        unit=unit,
        period=MetricPeriod.MONTHLY,
        definition_version=1,
    )


def compute_monthly(ctx) -> list[WorldMetric]:
    state = ctx.state
    acc = state.month_accumulators
    citizens = state.ordered("citizens")
    population = len(citizens)
    employed = sum(1 for c in citizens if c.employment_status == "EMPLOYED")
    unemployment = (Decimal((population - employed) * 100) / population if population else Decimal(0)).quantize(_SIX_PLACES)

    salaries = [e.salary for e in state.ordered("employments") if e.status == "ACTIVE"]
    avg_salary = sum(salaries) // len(salaries) if salaries else 0

    wealth = [a.balance for a in state.ordered("accounts")
              if a.owner_type == AccountOwnerType.CITIZEN and a.account_type == AccountType.CASH]
    avg_wealth = sum(wealth) // len(wealth) if wealth else 0

    happiness = [c.happiness for c in citizens]
    avg_happiness = (Decimal(sum(happiness)) / len(happiness)).quantize(_SIX_PLACES) if happiness else Decimal(0)

    companies = state.ordered("companies")
    revenue = revenue_breakdown(state)

    return [
        _metric(ctx, MetricCode.POPULATION, population, MetricUnit.COUNT),
        _metric(ctx, MetricCode.EMPLOYED_POPULATION, employed, MetricUnit.COUNT),
        _metric(ctx, MetricCode.UNEMPLOYMENT_RATE, unemployment, MetricUnit.PERCENT),
        _metric(ctx, MetricCode.AVERAGE_SALARY, avg_salary, MetricUnit.KRW),
        _metric(ctx, MetricCode.AVERAGE_WEALTH, avg_wealth, MetricUnit.KRW),
        _metric(ctx, MetricCode.TOTAL_CONSUMPTION, acc.get("consumption_total", 0), MetricUnit.KRW),
        _metric(ctx, MetricCode.TOTAL_COMPANY_REVENUE,
                sum(revenue.values()), MetricUnit.KRW),
        _metric(ctx, MetricCode.ACTIVE_COMPANIES,
                sum(1 for co in companies if co.status in _OPERATING), MetricUnit.COUNT),
        _metric(ctx, MetricCode.BANKRUPT_COMPANIES, acc.get("bankrupt_count", 0), MetricUnit.COUNT),
        _metric(ctx, MetricCode.GOVERNMENT_REVENUE,
                acc.get("tax_total", 0) + acc.get("opex_government_total", 0), MetricUnit.KRW),
        _metric(ctx, MetricCode.GOVERNMENT_EXPENDITURE,
                acc.get("welfare_total", 0) + acc.get("procurement_total", 0), MetricUnit.KRW),
        _metric(ctx, MetricCode.AVERAGE_HAPPINESS, avg_happiness, MetricUnit.INDEX),
    ]
