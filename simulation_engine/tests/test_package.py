"""패키지 import smoke 테스트."""

import importlib
import unittest

import simulation_engine

SUBMODULES = [
    "simulation_engine.engine",
    "simulation_engine.clock",
    "simulation_engine.context",
    "simulation_engine.entities",
    "simulation_engine.entities.citizen",
    "simulation_engine.entities.company",
    "simulation_engine.entities.world",
    "simulation_engine.entities.household",
    "simulation_engine.entities.employment",
    "simulation_engine.entities.policy",
    "simulation_engine.economy",
    "simulation_engine.economy.account",
    "simulation_engine.economy.transaction",
    "simulation_engine.economy.ledger",
    "simulation_engine.world.snapshot",
    "simulation_engine.world.map_chunk",
    "simulation_engine.metrics",
    "simulation_engine.metrics.models",
    "simulation_engine.entities.government",
    "simulation_engine.entities.building",
    "simulation_engine.world",
    "simulation_engine.world.state",
    "simulation_engine.world.config",
    "simulation_engine.world.generator",
    "simulation_engine.systems",
    "simulation_engine.systems.behavior",
    "simulation_engine.systems.employment",
    "simulation_engine.systems.payroll",
    "simulation_engine.systems.consumption",
    "simulation_engine.systems.business",
    "simulation_engine.systems.government",
    "simulation_engine.systems.movement",
    "simulation_engine.events",
    "simulation_engine.events.models",
    "simulation_engine.events.generator",
    "simulation_engine.policies",
    "simulation_engine.policies.taxation",
    "simulation_engine.policies.employment",
    "simulation_engine.utils",
    "simulation_engine.utils.probability",
    "simulation_engine.utils.random",
]


class PackageSmokeTest(unittest.TestCase):
    def test_version_is_non_empty_string(self):
        self.assertIsInstance(simulation_engine.__version__, str)
        self.assertTrue(simulation_engine.__version__)

    def test_all_submodules_import(self):
        for name in SUBMODULES:
            with self.subTest(module=name):
                importlib.import_module(name)


if __name__ == "__main__":
    unittest.main()
