"""통합 테스트: AC6, AC12, AC14, AC15, AC16, AC18."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from collections import defaultdict

from simulation_engine.clock import TICKS_PER_MONTH
from simulation_engine.economy import AccountOwnerType, AccountType
from simulation_engine.engine import PolicyChangeCommand, SimulationEngine
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.generator import generate_world
from simulation_engine.world.state import WorldState

CFG = SimulationConfig()
CMD = {100: [PolicyChangeCommand(income_tax_rate=2000, welfare_amount=500_000, effective_tick=105)]}


def new_engine(seed=42):
    return SimulationEngine(generate_world(seed, CFG).state, CFG)


def trace(results):
    """결정성 비교용: 이벤트/거래/원장 시퀀스."""
    out = []
    for r in results:
        out.append((
            r.tick,
            [(e.sequence, e.type, e.tick, e.payload) for e in r.events],
            [(t.transaction_type, t.tick, t.idempotency_key, t.metadata) for t in r.transactions],
            [(l.account_id, l.entry_no, l.amount) for l in r.ledger_entries],
        ))
    return out


class InvariantTests(unittest.TestCase):
    def test_ac12_three_months(self):
        eng = new_engine()
        s = eng.state
        for _ in range(3 * TICKS_PER_MONTH):
            r = eng.step()
            self.assertEqual(s.total_balance(), 0)
            for a in s.accounts.values():
                if not (a.owner_type == AccountOwnerType.SYSTEM and a.account_type == AccountType.ISSUANCE):
                    self.assertGreaterEqual(a.balance, 0)
            sums = defaultdict(int)
            for l in r.ledger_entries:
                sums[l.transaction_id] += l.amount
            self.assertEqual({t.id for t in r.transactions}, set(sums))
            self.assertTrue(all(v == 0 for v in sums.values()))
            active = defaultdict(list)
            for e in s.employments.values():
                if e.status == "ACTIVE":
                    active[e.citizen_id].append(e)
            per_company = defaultdict(int)
            for lst in active.values():
                self.assertEqual(len(lst), 1)
                per_company[lst[0].company_id] += 1
            for co in s.companies.values():
                self.assertEqual(co.employee_count, per_company[co.id])
            for c in s.citizens.values():
                if c.id in active:
                    self.assertEqual(c.employment_status, "EMPLOYED")
                    self.assertEqual(c.employer_id, active[c.id][0].company_id)
                else:
                    self.assertEqual(c.employment_status, "UNEMPLOYED")
                    self.assertIsNone(c.employer_id)

    def test_ac6_movement_payload(self):
        eng = new_engine()
        n = 0
        for r in eng.run(TICKS_PER_MONTH):
            for e in r.events:
                if e.type == "citizen.movement.started":
                    n += 1
                    p = e.payload
                    for k in ("citizen_id", "from_building_id", "to_building_id", "start_tick", "arrival_tick"):
                        self.assertIn(k, p)
                    self.assertEqual(p["start_tick"], e.tick)
                    self.assertGreaterEqual(p["arrival_tick"], p["start_tick"] + 1)
        self.assertGreater(n, 0)

    def test_ac18_no_bankruptcy_36_months(self):
        for seed in (42, 1, 7):
            with self.subTest(seed=seed):
                eng = new_engine(seed)
                eng.run(36 * TICKS_PER_MONTH)
                bankrupt = [c.name for c in eng.state.companies.values() if c.status == "BANKRUPT"]
                self.assertEqual(bankrupt, [])


class ReproducibilityTests(unittest.TestCase):
    def test_ac14_same_seed_identical(self):
        a, b = new_engine(), new_engine()
        ra, rb = a.run(TICKS_PER_MONTH, CMD), b.run(TICKS_PER_MONTH, CMD)
        self.assertEqual(trace(ra), trace(rb))
        self.assertEqual(a.state.to_snapshot().state_data, b.state.to_snapshot().state_data)
        self.assertTrue(any(e.type == "policy.updated" for r in ra for e in r.events))

    def test_ac14_different_seed_differs(self):
        a, b = new_engine(42), new_engine(43)
        a.run(TICKS_PER_MONTH)
        b.run(TICKS_PER_MONTH)
        self.assertNotEqual(a.state.to_snapshot().state_data, b.state.to_snapshot().state_data)

    def test_ac15_snapshot_resume(self):
        n, k = TICKS_PER_MONTH + 100, 400  # k는 월 중간, n은 월말 이후
        a = new_engine()
        ra = a.run(n, CMD)
        b = new_engine()
        b.run(k, CMD)
        data = json.loads(json.dumps(b.state.to_snapshot().state_data))
        snap = b.state.to_snapshot()
        snap.state_data = data
        c = SimulationEngine(WorldState.from_snapshot(snap), CFG)
        rc = c.run(n - k, CMD)
        self.assertEqual(trace(ra[k:]), trace(rc))
        self.assertEqual(a.state.to_snapshot().state_data, c.state.to_snapshot().state_data)


class PurityTests(unittest.TestCase):
    def test_ac16_no_framework_imports(self):
        code = (
            "import pkgutil, sys, simulation_engine\n"
            "for m in pkgutil.walk_packages(simulation_engine.__path__, 'simulation_engine.'):\n"
            "    __import__(m.name)\n"
            "bad = [m for m in sys.modules if m.split('.')[0] in ('fastapi','sqlalchemy','psycopg','psycopg2','asyncpg','app')]\n"
            "print(bad)\n"
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                             env={"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}, check=True).stdout.strip()
        self.assertEqual(out, "[]")


if __name__ == "__main__":
    unittest.main()
