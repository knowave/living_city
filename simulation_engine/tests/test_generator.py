import json
import unittest
from collections import Counter

from simulation_engine.economy import AccountOwnerType as OT
from simulation_engine.economy import AccountType, TransactionType
from simulation_engine.engine import SimulationEngine
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.generator import generate_world


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = SimulationConfig()
        cls.result = generate_world(42, cls.config)
        cls.state = cls.result.state

    def test_counts(self):
        s = self.state
        self.assertEqual(len(s.citizens), 100)
        self.assertEqual(len(s.households), 100)
        self.assertEqual(len(s.companies), 10)
        self.assertEqual(len(s.buildings), 21)
        self.assertEqual(len(s.policies), 1)
        self.assertEqual(
            Counter(c.industry for c in s.companies.values()),
            {"RETAIL": 3, "RESTAURANT": 3, "WHOLESALE": 2, "BUSINESS_SERVICE": 2},
        )
        # citizen 100 + company 10 + gov 1 + system 2
        self.assertEqual(len(s.accounts), 113)

    def test_buildings(self):
        bs = list(self.state.buildings.values())
        self.assertEqual(
            Counter(b.type for b in bs), {"RESIDENTIAL": 10, "COMMERCIAL": 6, "OFFICE": 4, "PUBLIC": 1}
        )
        for b in bs:
            self.assertTrue(0 <= b.tile_x and b.tile_x + b.width <= 128)
            self.assertTrue(0 <= b.tile_y and b.tile_y + b.height <= 128)
        for i, a in enumerate(bs):
            for b in bs[i + 1 :]:
                apart = a.tile_x + a.width <= b.tile_x or b.tile_x + b.width <= a.tile_x
                apart = apart or a.tile_y + a.height <= b.tile_y or b.tile_y + b.height <= a.tile_y
                self.assertTrue(apart)
        for b in bs:
            if b.type == "RESIDENTIAL":
                self.assertEqual((b.capacity, b.occupied_capacity), (10, 10))

    def test_employment(self):
        s = self.state
        self.assertEqual(sum(c.employment_status == "EMPLOYED" for c in s.citizens.values()), 88)
        active = Counter(e.citizen_id for e in s.employments.values() if e.status == "ACTIVE")
        self.assertEqual(len(active), 88)
        self.assertTrue(all(n == 1 for n in active.values()))
        for co in s.companies.values():
            self.assertLessEqual(co.employee_count, co.employee_capacity)
            self.assertEqual(co.employee_count, sum(e.company_id == co.id for e in s.employments.values()))
        for c in s.citizens.values():
            self.assertEqual(c.employer_id is not None, c.employment_status == "EMPLOYED")
            self.assertEqual(c.current_building_id, c.home_building_id)
            self.assertEqual(c.current_activity, "AT_HOME")
        self.assertEqual(sum(1 for v in s.last_month_income.values() if v == 2_040_000), 72)  # 소매·식당 6개 x 12명

    def test_accounts_and_balances(self):
        s = self.state
        self.assertEqual(s.total_balance(), 0)
        for tx in self.result.transactions:
            self.assertEqual(tx.transaction_type, TransactionType.OPENING_BALANCE)
            self.assertEqual(tx.tick, 0)
            self.assertEqual(sum(e.amount for e in self.result.ledger_entries if e.transaction_id == tx.id), 0)
        self.assertEqual(len(self.result.transactions), 111)
        self.assertEqual(s.account_of(OT.GOVERNMENT, None, AccountType.TREASURY).balance, 50_000_000)
        funded = sum(a.balance for a in s.accounts.values() if a.account_type != AccountType.ISSUANCE)
        self.assertEqual(s.account_of(OT.SYSTEM, None, AccountType.ISSUANCE).balance, -funded)
        for c in s.citizens.values():
            self.assertEqual(s.account_of(OT.CITIZEN, c.id).balance, 3_000_000)
        for co in s.companies.values():
            expected = 3 * (co.employee_count * co.base_wage + co.operating_cost)
            self.assertEqual(s.account_of(OT.COMPANY, co.id).balance, expected)
        for a in s.accounts.values():
            if not (a.owner_type == OT.SYSTEM and a.account_type == AccountType.ISSUANCE):
                self.assertGreaterEqual(a.balance, 0)

    def test_determinism(self):
        a = generate_world(7).state.to_snapshot().state_data
        b = generate_world(7).state.to_snapshot().state_data
        c = generate_world(8).state.to_snapshot().state_data
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertNotEqual(a, c)

    def test_engine_steps_24_ticks(self):
        r = generate_world(3)
        engine = SimulationEngine(r.state, SimulationConfig())
        engine.run(24)
        self.assertEqual(r.state.tick, 24)
        self.assertEqual(r.state.total_balance(), 0)


if __name__ == "__main__":
    unittest.main()
