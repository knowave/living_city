import unittest
from decimal import Decimal

from simulation_engine.economy import AccountOwnerType, AccountType
from simulation_engine.entities import CompanyStatus
from simulation_engine.metrics.calculator import city_internal_money, compute_monthly, revenue_breakdown
from simulation_engine.metrics.models import MetricCode, MetricPeriod, MetricUnit

from tests.helpers import add_building, add_citizen, add_company, employ, fund, make_ctx, make_state

OT = AccountOwnerType


def values(metrics):
    return {m.metric_code: m for m in metrics}


class MonthlyMetricsTest(unittest.TestCase):
    def setUp(self):
        self.state = make_state(seed=3)
        home = add_building(self.state, "RESIDENTIAL")
        shop = add_building(self.state, "COMMERCIAL", 5, 5)
        self.c1 = add_citizen(self.state, home, balance=1000)
        self.c2 = add_citizen(self.state, home, balance=3000)
        self.c3 = add_citizen(self.state, home, balance=0)
        self.co_active = add_company(self.state, shop, status=CompanyStatus.ACTIVE.value)
        self.co_distressed = add_company(self.state, shop, status=CompanyStatus.DISTRESSED.value)
        self.co_bankrupt = add_company(self.state, shop, status=CompanyStatus.BANKRUPT.value)
        employ(self.state, self.c1, self.co_active, salary=500)
        employ(self.state, self.c2, self.co_active, salary=1001)
        for c, h in ((self.c1, 40), (self.c2, 50), (self.c3, 60)):
            c.happiness = h

    def test_each_metric_value(self):
        s = self.state
        s.month_accumulators.update({
            "consumption_total": 1234,
            "revenue_consumer:" + str(self.co_active.id): 100,
            "revenue_b2b:" + str(self.co_active.id): 200,
            "revenue_procurement:" + str(self.co_distressed.id): 300,
            "tax_total": 150,
            "opex_government_total": 20,
            "welfare_total": 30,
            "procurement_total": 40,
            "bankrupt_count": 2,
        })
        ctx = make_ctx(s, tick=719)
        metrics = compute_monthly(ctx)
        by = values(metrics)

        self.assertEqual(len(metrics), 12)
        self.assertEqual(len(by), 12)
        for m in metrics:
            self.assertEqual(m.tick, 719)
            self.assertEqual(m.period, MetricPeriod.MONTHLY)
            self.assertEqual(m.definition_version, 1)
            self.assertIsInstance(m.metric_value, Decimal)

        self.assertEqual(by[MetricCode.POPULATION].metric_value, Decimal(3))
        self.assertEqual(by[MetricCode.EMPLOYED_POPULATION].metric_value, Decimal(2))
        self.assertEqual(by[MetricCode.UNEMPLOYMENT_RATE].metric_value, Decimal("33.333333"))
        self.assertEqual(by[MetricCode.UNEMPLOYMENT_RATE].unit, MetricUnit.PERCENT)
        self.assertEqual(by[MetricCode.AVERAGE_SALARY].metric_value, Decimal(750))  # 1501 // 2
        self.assertEqual(by[MetricCode.AVERAGE_WEALTH].metric_value, Decimal(1333))  # 4000 // 3
        self.assertEqual(by[MetricCode.TOTAL_CONSUMPTION].metric_value, Decimal(1234))
        self.assertEqual(by[MetricCode.TOTAL_COMPANY_REVENUE].metric_value, Decimal(600))
        self.assertEqual(by[MetricCode.ACTIVE_COMPANIES].metric_value, Decimal(2))  # ACTIVE + DISTRESSED
        self.assertEqual(by[MetricCode.BANKRUPT_COMPANIES].metric_value, Decimal(2))
        self.assertEqual(by[MetricCode.GOVERNMENT_REVENUE].metric_value, Decimal(170))
        self.assertEqual(by[MetricCode.GOVERNMENT_EXPENDITURE].metric_value, Decimal(70))
        self.assertEqual(by[MetricCode.AVERAGE_HAPPINESS].metric_value, Decimal("50.000000"))
        self.assertEqual(by[MetricCode.AVERAGE_HAPPINESS].unit, MetricUnit.INDEX)

    def test_ids_are_unique_and_deterministic_order(self):
        first = [m.metric_code for m in compute_monthly(make_ctx(self.state, tick=719))]
        self.assertEqual(len(set(first)), 12)
        ids = [m.id for m in compute_monthly(make_ctx(self.state, tick=719))]
        self.assertEqual(len(set(ids)), 12)

    def test_empty_world_is_zero(self):
        state = make_state(seed=9)
        by = values(compute_monthly(make_ctx(state, tick=719)))
        self.assertEqual(len(by), 12)
        for code, m in by.items():
            self.assertEqual(m.metric_value, Decimal(0), code)
        self.assertEqual(by[MetricCode.UNEMPLOYMENT_RATE].metric_value, Decimal("0.000000"))

    def test_revenue_breakdown(self):
        self.state.month_accumulators.update({
            "revenue_consumer:a": 5,
            "revenue_consumer:b": 7,
            "revenue_b2b:a": 11,
            "revenue_procurement:b": 13,
            "payroll:a": 999,
        })
        self.assertEqual(revenue_breakdown(self.state), {"consumer": 12, "b2b": 11, "procurement": 13, "export": 0})

    def test_internal_money_excludes_system(self):
        s = self.state
        before = city_internal_money(s)
        self.assertEqual(before, 4000)  # citizens only; the company accounts are empty
        fund(s, s.account_of(OT.COMPANY, self.co_active.id), 500)
        fund(s, s.account_of(OT.GOVERNMENT, None, AccountType.TREASURY), 700)
        fund(s, s.account_of(OT.SYSTEM, None), 900)  # SYSTEM CASH: external sink, must be excluded
        self.assertEqual(city_internal_money(s), 4000 + 500 + 700)
        self.assertEqual(s.total_balance(), 0)  # ledger sum stays zero (ISSUANCE is negative)


if __name__ == "__main__":
    unittest.main()
