"""Tick 실행 컨텍스트. 시스템은 이것으로 상태·RNG·이벤트·거래 기록에 접근한다."""

import random
from dataclasses import dataclass, field
from typing import Any

from simulation_engine.economy import LedgerEntry, Transaction
from simulation_engine.events.models import WorldEvent
from simulation_engine.metrics.models import WorldMetric
from simulation_engine.utils.random import derive_rng
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.state import WorldState


@dataclass(slots=True)
class TickContext:
    state: WorldState
    config: SimulationConfig
    tick: int
    transactions: list[Transaction] = field(default_factory=list)
    ledger_entries: list[LedgerEntry] = field(default_factory=list)
    events: list[WorldEvent] = field(default_factory=list)
    metrics: list[WorldMetric] = field(default_factory=list)

    def rng(self, *keys: object) -> random.Random:
        """예: ctx.rng("shop", ctx.tick, citizen_id)."""
        return derive_rng(self.state.seed, *keys)

    def emit(self, type: str, payload: dict[str, Any] | None = None) -> WorldEvent:
        state = self.state
        event = WorldEvent(
            id=state.new_id("event"),
            sequence=state.next_event_sequence,
            tick=self.tick,
            type=type,
            payload=payload or {},
        )
        state.next_event_sequence += 1
        self.events.append(event)
        return event
