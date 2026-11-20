"""Engine port. Must not import simulation_engine (adapter does)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicyCommandInput:
    """Command input built from a DB policy row."""

    income_tax_rate: int
    welfare_amount: int
    effective_tick: int
    version: int


@dataclass(frozen=True)
class BuildingFootprint:
    engine_id: str
    tile_x: int
    tile_y: int
    width: int
    height: int


@dataclass
class EngineBatch:
    """Engine run result. Opaque to services; only the mapper interprets `raw`."""

    from_tick: int  # 0 for generation
    to_tick: int  # WorldState.tick after the run (0 for generation)
    event_count: int
    transaction_count: int
    last_event_sequence: int  # snapshot.last_event_sequence
    snapshot_tick: int
    snapshot_state_data: dict
    raw: object  # GenerationResult, or list[TickResult] + WorldState
    buildings: list[BuildingFootprint] = field(default_factory=list)  # generate only


class SimulationEngineError(Exception):
    """Engine failure wrapped by the adapter (not a DomainError)."""


class SimulationEnginePort(ABC):
    @abstractmethod
    def generate(self, seed: int, name: str) -> EngineBatch: ...

    @abstractmethod
    def advance(
        self, snapshot_state_data: dict, policies: list[PolicyCommandInput], count: int
    ) -> EngineBatch:
        """Restore WorldState from the snapshot, apply policies lacking an effective_tick in the
        snapshot (version order, as PolicyChangeCommand on the first tick), then run(count).
        Engine exceptions are wrapped in SimulationEngineError."""
