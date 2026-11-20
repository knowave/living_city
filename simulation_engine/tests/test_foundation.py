import unittest

from simulation_engine import clock
from simulation_engine.economy import AccountOwnerType, AccountType, TransactionType
from simulation_engine.economy.ledger import InsufficientFunds, post_transaction
from simulation_engine.engine import InvariantViolation, PolicyChangeCommand, SimulationEngine
from simulation_engine.utils.random import derive_rng
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.state import WorldState

from tests.helpers import add_building, add_citizen, add_company, employ, fund, make_ctx, make_state

OT = AccountOwnerType


def small_world():
    state = make_state(seed=7)
    home = add_building(state, "RESIDENTIAL")
    shop = add_building(state, "COMMERCIAL", 5, 5)
    c = add_citizen(state, home, balance=1000)
    co = add_company(state, shop, balance=5000)
    employ(state, c, co)
    return state, c, co


class RandomTest(unittest.TestCase):
    def test_deterministic_and_independent(self):
        a = [derive_rng(1, "shop", 3, "x").random() for _ in range(2)]
        self.assertEqual(a[0], a[1])
        self.assertNotEqual(derive_rng(1, "shop", 3, "x").random(), derive_rng(1, "shop", 3, "y").random())
        self.assertNotEqual(derive_rng(1, "a").random(), derive_rng(2, "a").random())


class ClockTest(unittest.TestCase):
    def test_helpers(self):
        self.assertEqual((clock.hour_of(26), clock.day_of(26), clock.month_of(719), clock.month_of(720)), (2, 1, 0, 1))
        self.assertTrue(clock.is_month_end(719))
        self.assertFalse(clock.is_month_end(720))
        self.assertTrue(clock.is_month_end(1439))


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.state, self.citizen, self.company = small_world()
        self.ctx = make_ctx(self.state)
        self.a = self.state.account_of(OT.CITIZEN, self.citizen.id)
        self.b = self.state.account_of(OT.COMPANY, self.company.id)

    def test_transfer(self):
        tx = post_transaction(self.ctx, TransactionType.PURCHASE, [(self.a.id, -300), (self.b.id, 300)], "k1", {"m": 1})
        self.assertEqual((self.a.balance, self.b.balance), (700, 5300))
        self.assertEqual([e.entry_no for e in self.ctx.ledger_entries], [1, 2])
        self.assertEqual(tx.metadata, {"m": 1})
        self.assertEqual(self.state.total_balance(), 0)

    def test_insufficient_funds_is_atomic(self):
        with self.assertRaises(InsufficientFunds):
            post_transaction(self.ctx, TransactionType.PURCHASE, [(self.b.id, 1001), (self.a.id, -1001)], "k")
        self.assertEqual((self.a.balance, self.b.balance), (1000, 5000))
        self.assertEqual((self.ctx.transactions, self.ctx.ledger_entries), ([], []))

    def test_validation(self):
        for entries in ([(self.a.id, -5), (self.b.id, 4)], [(self.a.id, 0), (self.b.id, 0)], [(self.a.id, -5), (self.a.id, 5)]):
            with self.assertRaises(ValueError):
                post_transaction(self.ctx, TransactionType.PURCHASE, entries, "k")
        self.assertEqual(self.a.balance, 1000)

    def test_ids_are_deterministic(self):
        s2, c2, co2 = small_world()
        self.assertEqual(sorted(self.state.accounts), sorted(s2.accounts))


class ContextTest(unittest.TestCase):
    def test_event_sequence(self):
        state = make_state()
        ctx = make_ctx(state)
        seqs = [ctx.emit("x").sequence for _ in range(3)]
        self.assertEqual(seqs, [1, 2, 3])
        self.assertEqual(state.to_snapshot().last_event_sequence, 3)
        self.assertEqual(len({e.id for e in ctx.events}), 3)


class SnapshotTest(unittest.TestCase):
    def test_round_trip(self):
        state, c, co = small_world()
        state.distressed_months[co.id] = 2
        state.last_month_income[c.id] = 123
        state.movement_starts[c.id] = 8
        state.unpaid_opex[co.id] = 5
        state.month_accumulators["x:1"] = 9
        make_ctx(state).emit("e")
        snap = state.to_snapshot()
        restored = WorldState.from_snapshot(snap)
        self.assertEqual(restored.to_snapshot().state_data, snap.state_data)
        self.assertEqual(restored.citizens, state.citizens)
        self.assertEqual(restored.accounts, state.accounts)
        self.assertEqual(restored.companies, state.companies)
        self.assertEqual(restored.world, state.world)
        self.assertEqual(restored.distressed_months, state.distressed_months)
        self.assertEqual(restored.account_of(OT.COMPANY, co.id).balance, 5000)
        self.assertEqual(restored.new_id("citizen"), state.new_id("citizen"))
        self.assertIs(type(restored.account_of(OT.GOVERNMENT, None, AccountType.TREASURY).owner_type), OT)


class EngineTest(unittest.TestCase):
    def test_step_and_run_with_stubs(self):
        state, _, _ = small_world()
        engine = SimulationEngine(state, SimulationConfig())
        r = engine.step()
        self.assertEqual((r.tick, state.tick), (0, 1))
        self.assertEqual([e.type for e in r.events], ["simulation.tick"])
        results = engine.run(720)
        self.assertEqual(state.tick, 721)
        types = [e.type for e in results[-2].events]
        self.assertEqual(types[-3:], ["economy.month.closed", "metrics.updated", "simulation.tick"])
        seqs = [e.sequence for res in results for e in res.events]
        self.assertEqual(seqs, sorted(seqs))

    def test_policy_command_effective_tick(self):
        state, _, _ = small_world()
        engine = SimulationEngine(state, SimulationConfig())
        results = engine.run(5, {1: [PolicyChangeCommand(2000, 500, effective_tick=3)]})
        self.assertEqual([e.type for e in results[1].events], ["policy.updated", "simulation.tick"])
        self.assertEqual(state.current_policy(2).income_tax_rate, 1500)
        self.assertEqual((state.current_policy(3).income_tax_rate, state.current_policy(3).version), (2000, 2))
        with self.assertRaises(ValueError):
            engine.step([PolicyChangeCommand(1, 1, effective_tick=0)])

    def test_policy_command_rejections_are_atomic(self):
        state, _, _ = small_world()
        engine = SimulationEngine(state, SimulationConfig())
        ok = PolicyChangeCommand(2000, 0, effective_tick=5)
        bad = [
            [PolicyChangeCommand(-1, 0, 5)],
            [PolicyChangeCommand(10001, 0, 5)],
            [PolicyChangeCommand(1500, -1, 5)],
            [PolicyChangeCommand(1500, 0, 0)],  # 초기 정책과 같은 effective_tick
            [ok, PolicyChangeCommand(1000, 0, 5)],  # 같은 step 안 중복
        ]
        for cmds in bad:
            with self.assertRaises(ValueError):
                engine.step(cmds)
            self.assertEqual((len(state.policies), state.tick, state.next_event_sequence), (1, 0, 1))
        r = engine.step([PolicyChangeCommand(0, 0, 5), PolicyChangeCommand(10000, 0, 6)])
        self.assertEqual(len(state.policies), 3)
        self.assertEqual([e.type for e in r.events], ["policy.updated"] * 2 + ["simulation.tick"])

    def test_invariant_violation(self):
        state, c, _ = small_world()
        engine = SimulationEngine(state, SimulationConfig())
        state.account_of(OT.CITIZEN, c.id).balance += 1  # 합계 0 위반
        with self.assertRaises(InvariantViolation):
            engine.step()
        state.account_of(OT.CITIZEN, c.id).balance -= 1
        state.account_of(OT.CITIZEN, c.id).balance = -1
        state.account_of(OT.SYSTEM, None, AccountType.ISSUANCE).balance += 1001
        with self.assertRaises(InvariantViolation):
            engine.step()


if __name__ == "__main__":
    unittest.main()
