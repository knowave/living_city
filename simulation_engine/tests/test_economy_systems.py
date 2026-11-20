import unittest

from tests.helpers import add_building, add_citizen, add_company, employ, fund, make_ctx, make_state
from simulation_engine.economy import AccountOwnerType as OT, AccountType
from simulation_engine.systems import business, employment, external, government, payroll
from simulation_engine.world.config import BUSINESS_SERVICE, RETAIL, WHOLESALE


def bal(state, ot, oid=None, at=AccountType.CASH):
    return state.account_of(ot, oid, at).balance


def treasury(state):
    return bal(state, OT.GOVERNMENT, None, AccountType.TREASURY)


class Base(unittest.TestCase):
    def setUp(self):
        self.s = make_state()
        self.b = add_building(self.s)
        self.ctx = make_ctx(self.s, tick=719)

    def zero(self):
        self.assertEqual(self.s.total_balance(), 0)
        for a in self.s.accounts.values():
            if a.account_type != AccountType.ISSUANCE:
                self.assertGreaterEqual(a.balance, 0)


class PayrollTest(Base):
    def test_tax_and_zero_sum(self):
        co = add_company(self.s, self.b, balance=10_000_000, base_wage=2_400_000)
        c = add_citizen(self.s, self.b)
        employ(self.s, c, co)
        payroll.run(self.ctx)
        self.assertEqual(treasury(self.s), 360_000)
        self.assertEqual(bal(self.s, OT.CITIZEN, c.id), 2_040_000)
        self.assertEqual(self.s.last_month_income[c.id], 2_040_000)
        self.assertEqual(self.s.month_accumulators[f"payroll:{co.id}"], 2_400_000)
        self.assertEqual(self.s.month_accumulators["tax_total"], 360_000)
        self.zero()

    def test_failure_bankrupt(self):
        co = add_company(self.s, self.b, balance=3_000_000, base_wage=2_400_000)
        cs = [add_citizen(self.s, self.b) for _ in range(2)]
        for c in cs:
            employ(self.s, c, co)
        payroll.run(self.ctx)
        self.assertEqual(bal(self.s, OT.COMPANY, co.id), 3_000_000)
        self.assertEqual(self.s.last_month_income[cs[0].id], 0)
        business.pay_operating_expenses(self.ctx)
        self.assertNotIn(co.id, self.s.unpaid_opex)
        business.evaluate_status(self.ctx)
        self.assertEqual(co.status, "BANKRUPT")
        self.assertEqual(co.employee_count, 0)
        self.assertTrue(all(e.status == "TERMINATED" and e.terminated_tick == 719 for e in self.s.employments.values()))
        self.assertTrue(all(c.employment_status == "UNEMPLOYED" and c.employer_id is None for c in cs))
        self.assertEqual(self.s.month_accumulators["bankrupt_count"], 1)
        self.zero()


class OpexTest(Base):
    def test_split_with_suppliers(self):
        r = add_company(self.s, self.b, RETAIL, balance=10_000_000)
        w1 = add_company(self.s, self.b, WHOLESALE)
        w2 = add_company(self.s, self.b, WHOLESALE)
        business.pay_operating_expenses(self.ctx)
        self.assertEqual(treasury(self.s), 1_000_000)
        self.assertEqual(bal(self.s, OT.SYSTEM), 500_000)
        self.assertEqual(bal(self.s, OT.COMPANY, w1.id) + bal(self.s, OT.COMPANY, w2.id), 3_500_000)
        self.assertEqual(bal(self.s, OT.COMPANY, w1.id), 1_750_000)
        self.assertEqual(bal(self.s, OT.COMPANY, r.id), 5_000_000)
        acc = self.s.month_accumulators
        self.assertEqual(acc[f"revenue_b2b:{w1.id}"], 1_750_000)
        self.assertEqual(acc[f"opex_paid:{r.id}"], 5_000_000)
        self.assertEqual(self.s.unpaid_opex[r.id], 0)
        metas = [t.metadata for t in self.ctx.transactions]
        self.assertEqual({m["expense_category"] for m in metas}, {"b2b", "government", "external"})
        self.zero()

    def _mapping(self, payer, supplier, other):
        p = add_company(self.s, self.b, payer, balance=10_000_000)
        sup = add_company(self.s, self.b, supplier)
        oth = add_company(self.s, self.b, other)
        business.pay_operating_expenses(self.ctx)
        self.assertEqual(bal(self.s, OT.COMPANY, sup.id), 3_500_000)
        self.assertEqual(bal(self.s, OT.COMPANY, oth.id), 0)
        self.assertEqual(bal(self.s, OT.SYSTEM), 500_000)
        self.zero()

    def test_wholesale_pays_business_service(self):
        self._mapping(WHOLESALE, BUSINESS_SERVICE, RETAIL)

    def test_business_service_pays_wholesale(self):
        self._mapping(BUSINESS_SERVICE, WHOLESALE, RETAIL)

    def test_no_supplier_goes_external(self):
        add_company(self.s, self.b, RETAIL, balance=10_000_000)
        business.pay_operating_expenses(self.ctx)
        self.assertEqual(bal(self.s, OT.SYSTEM), 4_000_000)
        self.assertEqual(self.s.month_accumulators["opex_external_total"], 4_000_000)
        self.zero()

    def test_odd_remainder_by_id(self):
        r = add_company(self.s, self.b, RETAIL, balance=10_000_000, operating_cost=1001)
        ws = [add_company(self.s, self.b, WHOLESALE) for _ in range(2)]
        business.pay_operating_expenses(self.ctx)  # b2b=700 -> 350 each; gov=200; ext=101
        self.assertEqual(bal(self.s, OT.SYSTEM), 101)
        self.assertEqual(sum(bal(self.s, OT.COMPANY, w.id) for w in ws), 700)
        self.zero()

    def test_unpaid(self):
        r = add_company(self.s, self.b, RETAIL, balance=1_000_000)
        business.pay_operating_expenses(self.ctx)
        self.assertEqual(self.s.unpaid_opex[r.id], 5_000_000)
        self.assertEqual(bal(self.s, OT.COMPANY, r.id), 1_000_000)
        business.evaluate_status(self.ctx)
        self.assertEqual(r.status, "DISTRESSED")
        self.assertEqual(self.ctx.events[-1].type, "company.status.changed")
        self.zero()


class StatusTest(Base):
    def test_recovery_and_three_months(self):
        co = add_company(self.s, self.b, balance=1_000_000)  # fixed 5M
        self.s.unpaid_opex[co.id] = 0
        business.evaluate_status(self.ctx)
        self.assertEqual((co.status, self.s.distressed_months[co.id]), ("DISTRESSED", 1))
        business.evaluate_status(self.ctx)
        self.assertEqual(self.s.distressed_months[co.id], 2)
        fund(self.s, self.s.account_of(OT.COMPANY, co.id), 10_000_000)
        business.evaluate_status(self.ctx)
        self.assertEqual((co.status, self.s.distressed_months[co.id]), ("ACTIVE", 0))

    def test_three_months_bankrupt(self):
        co = add_company(self.s, self.b, balance=1_000_000)
        c = add_citizen(self.s, self.b)
        employ(self.s, c, co, salary=0)
        for _ in range(3):
            business.evaluate_status(self.ctx)
        self.assertEqual(co.status, "BANKRUPT")
        self.assertEqual(c.employment_status, "UNEMPLOYED")
        self.assertEqual(self.s.month_accumulators["bankrupt_count"], 1)
        ev = [e.payload for e in self.ctx.events if e.type == "citizen.employment.changed"]
        self.assertEqual(ev[-1]["employment_status"], "UNEMPLOYED")
        self.assertEqual(ev[-1]["reason"], "bankruptcy")

    def test_unpaid_month_blocks_recovery(self):
        # 2026-11-19: 미납은 재무 악화 조건 — 현금이 2배를 넘어도 그 달에는 회복하지 않는다
        co = add_company(self.s, self.b, balance=100_000_000, status="DISTRESSED")
        self.s.distressed_months[co.id] = 1
        self.s.unpaid_opex[co.id] = co.operating_cost
        business.evaluate_status(self.ctx)
        self.assertEqual((co.status, self.s.distressed_months[co.id]), ("DISTRESSED", 2))
        self.s.unpaid_opex[co.id] = 0
        business.evaluate_status(self.ctx)
        self.assertEqual((co.status, self.s.distressed_months[co.id]), ("ACTIVE", 0))

    def test_unpaid_third_month_is_bankrupt(self):
        co = add_company(self.s, self.b, balance=100_000_000, status="DISTRESSED")
        self.s.distressed_months[co.id] = 2
        self.s.unpaid_opex[co.id] = co.operating_cost
        business.evaluate_status(self.ctx)
        self.assertEqual(co.status, "BANKRUPT")


class ProcurementEffectTest(Base):
    def test_procurement_enables_hire(self):
        s = make_state()
        b = add_building(s)
        co = add_company(s, b, WHOLESALE, capacity=2)
        add_citizen(s, b)
        fund(s, s.account_of(OT.GOVERNMENT, None, AccountType.TREASURY), 10_000_000)
        ctx = make_ctx(s, tick=719)
        employment.run(ctx)
        self.assertEqual(co.employee_count, 0)  # 조달 전: 잉여 0
        government.procure(ctx)
        employment.run(ctx)
        self.assertEqual(co.employee_count, 1)

    def test_procurement_enables_recovery(self):
        s = make_state()
        b = add_building(s)
        co = add_company(s, b, WHOLESALE, balance=1_000_000, status="DISTRESSED")
        fund(s, s.account_of(OT.GOVERNMENT, None, AccountType.TREASURY), 20_000_000)
        ctx = make_ctx(s, tick=719)
        government.procure(ctx)  # +10M -> 현금 11M >= 고정비 5M x 2
        business.evaluate_status(ctx)
        self.assertEqual(co.status, "ACTIVE")


class ExportTest(Base):
    def _world(self, ext=10_000_001):
        s = make_state()
        b = add_building(s)
        cos = [add_company(s, b, RETAIL, balance=0) for _ in range(3)]
        cos[2].status = "BANKRUPT"
        fund(s, s.account_of(OT.SYSTEM, None, AccountType.CASH), ext)
        return s, b, cos

    def test_split_remainder_operating_only(self):
        s, b, cos = self._world()
        ctx = make_ctx(s, tick=719)
        external.pay_exports(ctx)  # 5_000_000 // 2 운영 중 기업
        self.assertEqual(s.month_accumulators["export_total"], 5_000_000)
        self.assertEqual([bal(s, OT.COMPANY, c.id) for c in cos[:2]], [2_500_000, 2_500_000])
        self.assertEqual(bal(s, OT.COMPANY, cos[2].id), 0)
        self.assertEqual(bal(s, OT.SYSTEM), 5_000_001)
        self.assertEqual({t.transaction_type for t in ctx.transactions}, {"EXPORT"})
        self.assertEqual(s.total_balance(), 0)

    def test_remainder_by_id(self):
        s, b, cos = self._world(ext=2 * 3 + 1)  # budget 3 -> 2,1 by id order
        external.pay_exports(make_ctx(s, tick=719))
        first, second = sorted(cos[:2], key=lambda c: c.id)
        self.assertEqual((bal(s, OT.COMPANY, first.id), bal(s, OT.COMPANY, second.id)), (2, 1))

    def test_zero_external_no_tx(self):
        s, b, cos = self._world(ext=1)
        ctx = make_ctx(s, tick=719)
        external.pay_exports(ctx)
        self.assertEqual(ctx.transactions, [])

    def test_export_reaches_status_and_hiring(self):
        s, b, cos = self._world(ext=40_000_000)
        cos[0].status = "DISTRESSED"
        cos[2].status = "ACTIVE"
        add_citizen(s, b)
        ctx = make_ctx(s, tick=719)
        external.pay_exports(ctx)  # 20M / 3
        employment.run(ctx)
        self.assertEqual(sum(c.employee_count for c in cos), 1)  # 수출 매출로 잉여>0
        self.assertEqual(s.month_accumulators["export_total"], 20_000_000)
        s2, _, c2 = self._world(ext=40_000_000)
        c2[0].status = "DISTRESSED"
        ctx2 = make_ctx(s2, tick=719)
        external.pay_exports(ctx2)  # 20M / 2 = 10M >= 고정비 5M x 2
        business.evaluate_status(ctx2)
        self.assertEqual(c2[0].status, "ACTIVE")


class GovernmentTest(Base):
    def test_welfare_limited_by_treasury(self):
        s = make_state(welfare=1_000_000)
        b = add_building(s)
        cs = [add_citizen(s, b) for _ in range(3)]
        fund(s, s.account_of(OT.GOVERNMENT, None, AccountType.TREASURY), 2_500_000)
        ctx = make_ctx(s, tick=719)
        government.pay_welfare(ctx)
        order = sorted(c.id for c in cs)
        self.assertEqual([bal(s, OT.CITIZEN, i) for i in order], [1_000_000, 1_000_000, 0])
        self.assertEqual(treasury(s), 500_000)
        self.assertEqual(s.last_month_income[order[0]], 1_000_000)
        self.assertEqual(s.month_accumulators["welfare_total"], 2_000_000)
        self.assertEqual(s.total_balance(), 0)

    def test_procurement(self):
        s = make_state(welfare=1_000_000)
        b = add_building(s)
        add_citizen(s, b)
        w = [add_company(s, b, WHOLESALE) for _ in range(2)]
        add_company(s, b, BUSINESS_SERVICE)
        add_company(s, b, RETAIL)
        fund(s, s.account_of(OT.GOVERNMENT, None, AccountType.TREASURY), 10_000_001)
        ctx = make_ctx(s, tick=719)
        government.procure(ctx)  # (10_000_001-1_000_000)*50% = 4_500_000 (floor) / 3
        self.assertEqual(s.month_accumulators["procurement_total"], 4_500_000)
        self.assertEqual(bal(s, OT.COMPANY, w[0].id), 1_500_000)
        self.assertEqual(treasury(s), 5_500_001)
        self.assertEqual(s.total_balance(), 0)


class EmploymentTest(Base):
    def test_hire(self):
        co = add_company(self.s, self.b, capacity=2)
        cs = [add_citizen(self.s, self.b) for _ in range(3)]
        self.s.month_accumulators[f"revenue_consumer:{co.id}"] = 100
        employment.run(self.ctx)
        self.assertEqual(co.employee_count, 1)
        e = next(iter(self.s.employments.values()))
        self.assertEqual((e.salary, e.hired_tick, e.status), (co.base_wage, 719, "ACTIVE"))
        self.assertEqual(self.ctx.events[-1].payload["reason"], "hired")

    def test_no_hire_without_surplus_or_capacity_or_distressed(self):
        co = add_company(self.s, self.b, capacity=1)
        add_citizen(self.s, self.b)
        employment.run(self.ctx)  # surplus 0
        self.assertEqual(co.employee_count, 0)
        self.s.month_accumulators[f"revenue_consumer:{co.id}"] = 100
        co.status = "DISTRESSED"
        employment.run(self.ctx)
        self.assertEqual(co.employee_count, 0)
        co.status = "ACTIVE"
        co.employee_capacity = 0
        employment.run(self.ctx)
        self.assertEqual(co.employee_count, 0)

    def test_fire_latest(self):
        co = add_company(self.s, self.b, status="DISTRESSED")
        cs = [add_citizen(self.s, self.b) for _ in range(2)]
        e1 = employ(self.s, cs[0], co, tick=1)
        e2 = employ(self.s, cs[1], co, tick=5)
        employment.run(self.ctx)
        self.assertEqual((e1.status, e2.status), ("ACTIVE", "TERMINATED"))
        self.assertEqual(e2.terminated_tick, 719)
        self.assertEqual(co.employee_count, 1)
        self.assertEqual(cs[1].employment_status, "UNEMPLOYED")
        self.assertEqual(self.ctx.events[-1].payload["reason"], "fired")


if __name__ == "__main__":
    unittest.main()
