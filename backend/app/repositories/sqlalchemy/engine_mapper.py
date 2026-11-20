"""Engine dataclasses -> plain row dicts for the ORM tables (ids remapped per world)."""
import enum
import uuid
from dataclasses import fields
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.simulation.engine_adapter import EngineRaw

_QUANT = Decimal("0.000001")


def db_id(world_id: UUID, engine_id: Any) -> UUID:
    """Engine ids repeat across worlds with the same seed, so namespace them by world."""
    return uuid.uuid5(world_id, str(engine_id))


def _remap(world_id: UUID, v: Any) -> Any:
    """Remap values under `*_id` keys (recursively) when they are UUID strings."""
    if isinstance(v, dict):
        return {
            k: _remap_id(world_id, x) if k.endswith("_id") else _remap(world_id, x)
            for k, x in v.items()
        }
    if isinstance(v, list):
        return [_remap(world_id, x) for x in v]
    return v


def _remap_id(world_id: UUID, v: Any) -> Any:
    if isinstance(v, str):
        try:
            return str(db_id(world_id, UUID(v)))
        except ValueError:
            return v
    return _remap(world_id, v)


def _row(world_id: UUID, obj: Any, **override: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"world_id": world_id}
    for f in fields(obj):
        v = getattr(obj, f.name)
        if isinstance(v, UUID):
            v = db_id(world_id, v)
        elif isinstance(v, enum.Enum):
            v = v.value
        row[f.name] = v
    row.update(override)
    return row


def entity_rows(world_id: UUID, raw: EngineRaw, policies: list) -> dict[str, list[dict]]:
    """Rows keyed by table name, each list in the order the persistence layer should write it."""
    st = raw.state
    w = world_id
    return {
        "buildings": [_row(w, o) for o in st.ordered("buildings")],
        "households": [_row(w, o) for o in st.ordered("households")],
        "companies": [_row(w, o) for o in st.ordered("companies")],
        "citizens": [
            _row(
                w,
                o,
                risk_tolerance=o.risk_tolerance / 10000,
                consumption_preference=o.consumption_preference / 10000,
            )
            for o in st.ordered("citizens")
        ],
        "employments": [_row(w, o) for o in st.ordered("employments")],
        "accounts": [_row(w, o) for o in st.ordered("accounts")],
        "world_policies": [_row(w, o) for o in policies],
        "transactions": [
            _row(w, o, metadata=_remap(w, o.metadata)) for o in raw.transactions
        ],
        "ledger_entries": [_row(w, o) for o in raw.ledger_entries],
        "world_events": [_row(w, o, payload=_remap(w, o.payload)) for o in raw.events],
        "world_metrics": [
            _row(w, o, metric_value=o.metric_value.quantize(_QUANT)) for o in raw.metrics
        ],
        "world_snapshots": [
            {
                "id": db_id(w, raw.snapshot.id),
                "world_id": w,
                "tick": raw.snapshot.tick,
                "last_event_sequence": raw.snapshot.last_event_sequence,
                "engine_version": raw.snapshot.engine_version,
                "state_data": raw.snapshot.state_data,
            }
        ],
    }
