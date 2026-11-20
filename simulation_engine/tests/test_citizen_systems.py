import unittest

from simulation_engine.economy import AccountOwnerType as OT
from simulation_engine.economy.transaction import TransactionType
from simulation_engine.systems import behavior, consumption, movement
from simulation_engine.systems.movement import start_move
from tests.helpers import add_building, add_citizen, add_company, employ, make_ctx, make_state


def run_tick(state, tick):
    ctx = make_ctx(state, tick=tick)
    consumption.depart(ctx)
    movement.run(ctx)
    consumption.run(ctx)
    behavior.run(ctx)
    return ctx


def world(income=3_000_000, balance=100_000):
    s = make_state()
    home = add_building(s, "RESIDENTIAL", 0, 0)
    office = add_building(s, "OFFICE", 100, 0)
    shopb = add_building(s, "COMMERCIAL", 0, 50)
    c = add_citizen(s, home, balance=balance)
    job = add_company(s, office, industry="WHOLESALE")
    shop = add_company(s, shopb)
    s.last_month_income[c.id] = income
    s.monthly_budget[c.id] = income * 7000 // 10000
    return s, c, home, office, shopb, job, shop


class CitizenSystemsTest(unittest.TestCase):
    def test_workday_cycle(self):
        s, c, home, office, _, job, _ = world(income=0)
        employ(s, c, job)
        run_tick(s, 7)
        self.assertEqual(c.current_activity, "AT_HOME")
        ctx = run_tick(s, 8)
        self.assertEqual(c.current_activity, "MOVING")
        self.assertIsNone(c.current_building_id)
        self.assertEqual(c.arrival_tick, 11)  # ceil(100/40)=3
        self.assertEqual(s.movement_starts[c.id], 8)
        p = ctx.events[0].payload
        self.assertEqual(ctx.events[0].type, "citizen.movement.started")
        self.assertEqual(p, {"citizen_id": str(c.id), "from_building_id": str(home.id),
                             "to_building_id": str(office.id), "start_tick": 8, "arrival_tick": 11})
        run_tick(s, 10)
        self.assertEqual(c.current_activity, "MOVING")
        run_tick(s, 11)
        self.assertEqual((c.current_activity, c.current_building_id), ("WORKING", office.id))
        self.assertNotIn(c.id, s.movement_starts)
        run_tick(s, 18)
        self.assertEqual(c.current_activity, "MOVING")
        run_tick(s, 21)
        self.assertEqual((c.current_activity, c.current_building_id), ("AT_HOME", home.id))

    def test_arrival_formula(self):
        s, c, home, *_ = world()
        for (x, y, exp) in [(0, 1, 1), (40, 0, 1), (41, 0, 2), (30, 30, 2), (80, 1, 3)]:
            b = add_building(s, "COMMERCIAL", x, y)
            c.current_building_id = home.id
            start_move(make_ctx(s, tick=100), c, b.id, "shop")
            self.assertEqual(c.arrival_tick, 100 + exp, (x, y))

    def test_fired_worker_goes_home(self):
        s, c, home, office, _, job, _ = world(income=0)
        employ(s, c, job)
        run_tick(s, 8); run_tick(s, 11)
        c.employer_id = None
        c.employment_status = "UNEMPLOYED"
        run_tick(s, 18)
        self.assertEqual(c.current_activity, "MOVING")

    def test_unemployed_no_commute(self):
        s, c, *_ = world(income=0)
        ctx = run_tick(s, 8)
        self.assertEqual(c.current_activity, "AT_HOME")
        self.assertEqual(ctx.events, [])

    def test_shopping_purchase(self):
        s, c, home, _, shopb, _, shop = world(income=3_000_000, balance=100_000)
        c.consumption_preference = 7000
        run_tick(s, 19)
        self.assertEqual(c.current_destination, shopb.id)
        self.assertEqual(c.arrival_tick, 21)  # 50 tiles -> 2
        ctx = run_tick(s, 21)
        expected = 3_000_000 * 7000 // 10000 // 30  # 70000
        self.assertEqual(expected, 70_000)
        self.assertEqual(s.account_of(OT.CITIZEN, c.id).balance, 100_000 - expected)
        self.assertEqual(s.account_of(OT.COMPANY, shop.id).balance, expected)
        tx = ctx.transactions[0]
        self.assertEqual(tx.transaction_type, TransactionType.PURCHASE)
        self.assertEqual(tx.metadata, {"company_id": str(shop.id), "category": "consumer"})
        self.assertEqual(sum(e.amount for e in ctx.ledger_entries), 0)
        self.assertEqual(s.month_accumulators[f"revenue_consumer:{shop.id}"], expected)
        self.assertEqual(s.month_accumulators["consumption_total"], expected)
        self.assertEqual(c.current_activity, "SHOPPING")  # 도착 Tick은 상점에 머문다
        run_tick(s, 22)
        self.assertEqual(c.current_activity, "MOVING")
        self.assertEqual(c.current_destination, home.id)
        self.assertEqual(s.account_of(OT.COMPANY, shop.id).balance, expected)  # 머무는 동안 재구매 없음
        run_tick(s, 24)
        self.assertEqual(c.current_activity, "AT_HOME")

    def test_cap_by_balance(self):
        s, c, *_, shop = world(income=3_000_000, balance=500)
        run_tick(s, 19); run_tick(s, 21)
        self.assertEqual(s.account_of(OT.CITIZEN, c.id).balance, 0)
        self.assertEqual(s.account_of(OT.COMPANY, shop.id).balance, 500)

    def test_zero_income_no_trip(self):
        s, c, *_ = world(income=0)
        ctx = run_tick(s, 19)
        self.assertEqual(c.current_activity, "AT_HOME")
        self.assertEqual(ctx.events, [])

    def test_bankrupt_shop_skips_purchase(self):
        s, c, *_, shop = world()
        run_tick(s, 19)
        shop.status = "BANKRUPT"
        ctx = run_tick(s, 21)
        self.assertEqual(ctx.transactions, [])
        self.assertEqual(c.current_activity, "MOVING")

    def test_shop_choice_deterministic_and_operating_only(self):
        def pick():
            s, c, home, _, _, _, _ = world()
            for i in range(4):
                add_company(s, add_building(s, "COMMERCIAL", i, 0), industry="RESTAURANT")
            dead = add_company(s, add_building(s, "COMMERCIAL", 9, 9), status="BANKRUPT")
            run_tick(s, 19)
            self.assertNotEqual(c.current_destination, s.buildings[dead.building_id].id)
            return c.current_destination
        self.assertEqual(pick(), pick())

    def test_late_home_arrival_shops_once(self):
        s, c, home, office, shopb, job, shop = world(income=3_000_000, balance=100_000)
        employ(s, c, job)
        for t in range(8, 22):
            run_tick(s, t)
        # 18시 출발, 21시 귀가 도착 -> 같은 tick에 소비 출발
        self.assertEqual((c.current_activity, c.current_destination), ("MOVING", shopb.id))
        self.assertEqual(s.last_shop_day[c.id], 0)
        for t in range(22, 29):
            run_tick(s, t)
        self.assertEqual(c.current_activity, "AT_HOME")  # 재소비 없음
        self.assertEqual(s.account_of(OT.COMPANY, shop.id).balance, 70_000)  # 정확히 1회 구매

    def test_after_midnight_home_shops_prev_day(self):
        s, c, home, *_ , shop = world()
        c.current_activity, c.current_building_id = "MOVING", None
        c.current_destination, c.arrival_tick = home.id, 24 + 1
        s.last_shop_day[c.id] = -1
        run_tick(s, 25)
        self.assertEqual(c.current_activity, "MOVING")
        self.assertEqual(s.last_shop_day[c.id], 0)
        # 이미 그날 소비했다면 안 함
        c2 = add_citizen(s, home, balance=100_000)
        s.last_month_income[c2.id] = 3_000_000
        s.monthly_budget[c2.id] = 2_100_000
        c2.current_activity, c2.current_building_id = "MOVING", None
        c2.current_destination, c2.arrival_tick = home.id, 26
        s.last_shop_day[c2.id] = 0
        run_tick(s, 26)
        self.assertEqual(c2.current_activity, "AT_HOME")

    def test_last_shop_day_snapshot_roundtrip(self):
        from simulation_engine.world.state import WorldState
        s, c, *_ = world()
        s.last_shop_day[c.id] = 3
        r = WorldState.from_snapshot(s.to_snapshot())
        self.assertEqual(r.last_shop_day, {c.id: 3})

    def test_monthly_budget_formula(self):
        s, c, *_ = world(income=3_000_000, balance=0)
        cfg = make_ctx(s).config
        acc = s.account_of(OT.CITIZEN, c.id)
        mb = lambda: consumption.monthly_budget(s, cfg, c)
        self.assertEqual(mb(), 2_100_000)  # 예비금 이하: 추가 없음
        from tests.helpers import fund
        fund(s, acc, cfg.cash_reserve)
        self.assertEqual(mb(), 2_100_000)  # 정확히 예비금
        fund(s, acc, 1_000_000)
        self.assertEqual(mb(), 2_100_000 + 1_000_000 * cfg.extra_spend_bps // 10000)

    def test_set_monthly_budgets_uses_current_cash(self):
        s, c, *_ = world(income=3_000_000, balance=0)
        from tests.helpers import fund
        cfg = make_ctx(s).config
        fund(s, s.account_of(OT.CITIZEN, c.id), cfg.cash_reserve + 2_000_000)
        consumption.set_monthly_budgets(make_ctx(s))
        self.assertEqual(s.monthly_budget[c.id], 2_100_000 + 2_000_000 * cfg.extra_spend_bps // 10000)

    def test_daily_cap(self):
        s, c, *_ = world(income=3_000_000, balance=100_000)
        s.monthly_budget[c.id] = 3_000_000
        self.assertEqual(movement.daily_budget(make_ctx(s), c), 100_000)  # 잔액 cap
        s.monthly_budget[c.id] = 60_000
        self.assertEqual(movement.daily_budget(make_ctx(s), c), 2_000)
        del s.monthly_budget[c.id]
        self.assertEqual(movement.daily_budget(make_ctx(s), c), 0)

    def test_monthly_budget_snapshot_and_generation(self):
        from simulation_engine.world.config import SimulationConfig
        from simulation_engine.world.generator import generate_world
        from simulation_engine.world.state import WorldState
        cfg = SimulationConfig()
        st = generate_world(1, cfg).state
        self.assertEqual(len(st.monthly_budget), len(st.citizens))
        for c in st.ordered("citizens"):
            extra = max(0, cfg.citizen_opening_balance - cfg.cash_reserve) * cfg.extra_spend_bps // 10000
            self.assertEqual(st.monthly_budget[c.id], st.last_month_income[c.id] * c.consumption_preference // 10000 + extra)
        self.assertEqual(WorldState.from_snapshot(st.to_snapshot()).monthly_budget, st.monthly_budget)

    def test_shop_in_own_workplace_building_after_midnight(self):
        s, c, home, _, shopb, _, shop = world()
        employ(s, c, shop)  # 직장 = 쇼핑 대상 건물
        c.current_activity, c.current_building_id = "MOVING", None
        c.current_destination, c.arrival_tick = home.id, 25
        s.trip_purpose[c.id] = "home"
        s.last_shop_day[c.id] = -1
        run_tick(s, 25)  # 01시 귀가 -> 전날 소비
        self.assertEqual(c.current_destination, shopb.id)
        self.assertEqual(s.trip_purpose[c.id], "shop")
        arr = c.arrival_tick
        run_tick(s, arr)
        self.assertEqual(s.account_of(OT.COMPANY, shop.id).balance, 70_000)
        self.assertEqual(c.current_activity, "SHOPPING")
        run_tick(s, arr + 1)
        self.assertEqual(c.current_activity, "MOVING")
        self.assertEqual(s.trip_purpose[c.id], "home")
        for t in range(arr + 2, arr + 5):
            run_tick(s, t)
        self.assertEqual(c.current_activity, "AT_HOME")
        self.assertEqual(s.account_of(OT.COMPANY, shop.id).balance, 70_000)

    def test_commute_arrival_after_employment_ended_goes_home(self):
        s, c, home, office, _, job, _ = world(income=0)
        employ(s, c, job)
        run_tick(s, 8)
        c.employer_id = None
        run_tick(s, c.arrival_tick)
        self.assertEqual((c.current_activity, c.current_destination), ("MOVING", home.id))
        self.assertEqual(s.trip_purpose[c.id], "home")

    def test_trip_purpose_snapshot_roundtrip(self):
        from simulation_engine.world.state import WorldState
        s, c, *_ = world()
        s.trip_purpose[c.id] = "commute"
        self.assertEqual(WorldState.from_snapshot(s.to_snapshot()).trip_purpose, {c.id: "commute"})

    def test_no_working_at_night_seed42(self):
        from simulation_engine.world.config import SimulationConfig
        from simulation_engine.engine import SimulationEngine
        from simulation_engine.world.generator import generate_world
        from simulation_engine.clock import hour_of
        cfg = SimulationConfig()
        eng = SimulationEngine(generate_world(42, cfg).state, cfg)
        for _ in range(2160):
            r = eng.step()
            if not 9 <= hour_of(r.tick) <= 17:
                self.assertFalse([c for c in eng.state.citizens.values() if c.current_activity == "WORKING"], r.tick)


if __name__ == "__main__":
    unittest.main()
