"""Adapter: the only place (with the mapper) that calls simulation_engine."""
import uuid
from dataclasses import dataclass, field

from simulation_engine.engine import PolicyChangeCommand, SimulationEngine
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.generator import generate_world
from simulation_engine.world.snapshot import WorldSnapshot
from simulation_engine.world.state import WorldState

from app.simulation.interfaces import (
    BuildingFootprint,
    EngineBatch,
    PolicyCommandInput,
    SimulationEngineError,
    SimulationEnginePort,
)

_ZERO_ID = uuid.UUID(int=0)  # placeholder; to_snapshot() derives the real id


@dataclass
class EngineRaw:
    """Engine objects of one run. Interpreted only by the SQL mapper."""

    state: WorldState
    snapshot: WorldSnapshot
    transactions: list = field(default_factory=list)
    ledger_entries: list = field(default_factory=list)
    events: list = field(default_factory=list)
    metrics: list = field(default_factory=list)
    new_policies: list = field(default_factory=list)  # policies the engine created in this run


class SimulationEngineAdapter(SimulationEnginePort):
    def generate(self, seed: int, name: str) -> EngineBatch:
        try:
            result = generate_world(seed, SimulationConfig(), name=name)
            state = result.state
            snap = state.to_snapshot()
        except Exception as e:
            raise SimulationEngineError(str(e)) from e
        raw = EngineRaw(
            state, snap, result.transactions, result.ledger_entries, result.events, [], []
        )
        return EngineBatch(
            from_tick=0,
            to_tick=state.tick,
            event_count=len(result.events),
            transaction_count=len(result.transactions),
            last_event_sequence=snap.last_event_sequence,
            snapshot_tick=snap.tick,
            snapshot_state_data=snap.state_data,
            raw=raw,
            buildings=[
                BuildingFootprint(str(b.id), b.tile_x, b.tile_y, b.width, b.height)
                for b in state.buildings.values()
            ],
        )

    def advance(
        self, snapshot_state_data: dict, policies: list[PolicyCommandInput], count: int
    ) -> EngineBatch:
        try:
            old = WorldSnapshot(
                id=_ZERO_ID,
                tick=snapshot_state_data["tick"],
                last_event_sequence=snapshot_state_data["engine"]["next_event_sequence"] - 1,
                engine_version=snapshot_state_data["engine_version"],
                state_data=snapshot_state_data,
            )
            state = WorldState.from_snapshot(old)
            from_tick = state.tick
            taken = {p.effective_tick for p in state.policies.values()}
            pending = [
                PolicyChangeCommand(p.income_tax_rate, p.welfare_amount, p.effective_tick)
                for p in sorted(policies, key=lambda p: p.version)
                if p.effective_tick not in taken
            ]
            known = set(state.policies)
            results = SimulationEngine(state, SimulationConfig()).run(
                count, {from_tick: pending} if pending else None
            )
            snap = state.to_snapshot()
        except Exception as e:
            raise SimulationEngineError(str(e)) from e
        raw = EngineRaw(
            state,
            snap,
            [t for r in results for t in r.transactions],
            [x for r in results for x in r.ledger_entries],
            [x for r in results for x in r.events],
            [x for r in results for x in r.metrics],
            [p for pid, p in state.policies.items() if pid not in known],
        )
        return EngineBatch(
            from_tick=from_tick,
            to_tick=state.tick,
            event_count=len(raw.events),
            transaction_count=len(raw.transactions),
            last_event_sequence=snap.last_event_sequence,
            snapshot_tick=snap.tick,
            snapshot_state_data=snap.state_data,
            raw=raw,
        )

