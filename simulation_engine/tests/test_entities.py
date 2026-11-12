import unittest
import uuid

from simulation_engine.entities import (
    Building, BuildingType, Citizen, Company, CompanyStatus, Employment,
    Household, World, WorldPolicy, WorldStatus,
)

U = uuid.uuid4


class EntityTests(unittest.TestCase):
    def test_defaults(self):
        w = World(id=U(), name="w", seed=1, engine_version="0")
        self.assertEqual((w.current_tick, w.speed, w.status), (0, 1, "INITIALIZED"))
        c = Citizen(id=U(), name="c", age=1, employment_status="x", happiness=1, health=1,
                    risk_tolerance=5000, consumption_preference=5000, current_activity="IDLE")
        self.assertEqual(c.skills, {})
        self.assertIsNot(c.skills, Citizen(id=U(), name="d", age=1, employment_status="x", happiness=1,
                                           health=1, risk_tolerance=0, consumption_preference=0,
                                           current_activity="IDLE").skills)
        self.assertIsNone(c.household_id)
        self.assertIsNone(c.arrival_tick)
        self.assertEqual(Household(id=U()).monthly_housing_cost, 0)
        co = Company(id=U(), name="n", industry="i")
        self.assertEqual((co.employee_capacity, co.employee_count, co.base_wage, co.operating_cost, co.status),
                         (0, 0, 0, 0, "ACTIVE"))
        e = Employment(id=U(), citizen_id=U(), company_id=U(), salary=1, hired_tick=0, status="ACTIVE")
        self.assertIsNone(e.terminated_tick)
        b = Building(id=U(), type="PUBLIC", tile_x=0, tile_y=0, width=1, height=1, status="x")
        self.assertEqual((b.capacity, b.occupied_capacity), (0, 0))
        p = WorldPolicy(id=U())
        self.assertEqual((p.income_tax_rate, p.welfare_amount, p.effective_tick, p.version), (1500, 0, 0, 1))

    def test_slots(self):
        objs = [World(id=U(), name="w", seed=1, engine_version="0"), Household(id=U()),
                Company(id=U(), name="n", industry="i"), WorldPolicy(id=U()),
                Employment(id=U(), citizen_id=U(), company_id=U(), salary=1, hired_tick=0, status="s"),
                Building(id=U(), type="t", tile_x=0, tile_y=0, width=1, height=1, status="s"),
                Citizen(id=U(), name="c", age=1, employment_status="x", happiness=1, health=1,
                        risk_tolerance=0, consumption_preference=0, current_activity="a")]
        for o in objs:
            self.assertTrue(hasattr(type(o), "__slots__"))
            self.assertFalse(hasattr(o, "__dict__"))

    def test_enums(self):
        self.assertEqual([s.value for s in WorldStatus],
                         ["INITIALIZED", "RUNNING", "PAUSED", "FAILED", "ARCHIVED"])
        self.assertEqual([s.value for s in CompanyStatus], ["ACTIVE", "DISTRESSED", "BANKRUPT", "CLOSED"])
        self.assertEqual([s.value for s in BuildingType], ["RESIDENTIAL", "COMMERCIAL", "OFFICE", "PUBLIC"])


if __name__ == "__main__":
    unittest.main()
