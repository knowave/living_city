import copy

import pytest

from simulation_engine.engine import PolicyChangeCommand, SimulationEngine
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.generator import generate_world

from app.simulation.engine_adapter import SimulationEngineAdapter
from app.simulation.interfaces import PolicyCommandInput, SimulationEngineError

adapter = SimulationEngineAdapter()


def test_generate_batch():
    b = adapter.generate(42, "t")
    assert (b.from_tick, b.to_tick, b.snapshot_tick) == (0, 0, 0)
    assert b.transaction_count == 111
    assert b.snapshot_state_data["tick"] == 0


def test_advance_matches_direct_engine():
    snap = adapter.generate(42, "t").snapshot_state_data
    b = adapter.advance(copy.deepcopy(snap), [], 30)
    direct = generate_world(42, SimulationConfig(), name="t").state
    results = SimulationEngine(direct, SimulationConfig()).run(30)
    assert b.to_tick == direct.tick == 30 and b.from_tick == 0
    assert b.snapshot_state_data == direct.to_snapshot().state_data
    assert b.event_count == sum(len(r.events) for r in results)
    assert b.transaction_count == sum(len(r.transactions) for r in results)


def test_pending_policy_applied_once():
    snap = adapter.generate(42, "t").snapshot_state_data
    pols = [
        PolicyCommandInput(1500, 0, 0, 1),  # already in snapshot -> skipped
        PolicyCommandInput(2000, 100, 3, 2),
    ]
    b = adapter.advance(snap, pols, 5)
    assert [e.type for e in b.raw.events].count("policy.updated") == 1
    assert [p.effective_tick for p in b.raw.new_policies] == [3]
    # next advance from the new snapshot: nothing pending anymore
    b2 = adapter.advance(b.snapshot_state_data, pols, 1)
    assert not b2.raw.new_policies
    assert "policy.updated" not in [e.type for e in b2.raw.events]


def test_engine_error_wrapped():
    with pytest.raises(SimulationEngineError):
        adapter.advance({"tick": 0}, [], 1)
    snap = adapter.generate(42, "t").snapshot_state_data
    with pytest.raises(SimulationEngineError) as ei:
        adapter.advance(snap, [PolicyCommandInput(20000, 0, 5, 2)], 1)
    assert isinstance(ei.value.__cause__, ValueError)
