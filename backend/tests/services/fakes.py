import uuid
from datetime import UTC, datetime

from app.core.exceptions import ConflictError
from app.repositories import interfaces as i
from app.schemas.city import (
    BuildingRead,
    ChunkRead,
    CitizenRead,
    CompanyRead,
    EmploymentRead,
    MetricRead,
    MovementRead,
)
from app.schemas.enums import MetricPeriod, WorldStatus
from app.schemas.world import PolicyRead, WorldRead
from app.simulation.interfaces import EngineBatch, SimulationEngineError, SimulationEnginePort


class FakeWorlds(i.WorldRepository):
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, WorldRead] = {}
        self.stale = False  # simulate concurrent update
        self.busy = False  # simulate row lock held by another transaction
        self.lock_calls: list[tuple[bool, int | None]] = []

    def add(self, data):
        now = datetime.now(UTC)
        w = WorldRead(
            id=uuid.uuid4(), name=data.name, seed=data.seed, current_tick=0, speed=1,
            status=WorldStatus.INITIALIZED, engine_version=data.engine_version, version=1,
            created_at=now, updated_at=now,
        )
        self.items[w.id] = w
        return w

    def get(self, world_id):
        return self.items.get(world_id)

    def lock_for_update(self, world_id, *, nowait, timeout_ms=None):
        self.lock_calls.append((nowait, timeout_ms))
        if self.busy:
            raise ConflictError("WORLD_BUSY", "World is busy with another write")
        return self.items.get(world_id)

    def update_simulation(self, world_id, status, speed, expected_version):
        w = self.items[world_id]
        if self.stale or w.version != expected_version:
            raise ConflictError("CONCURRENT_UPDATE")
        w = w.model_copy(update={"status": status, "speed": speed, "version": w.version + 1})
        self.items[world_id] = w
        return w

    def advance_tick(self, world_id, new_tick, expected_version):
        w = self.items[world_id]
        if self.stale or w.version != expected_version:
            raise ConflictError("CONCURRENT_UPDATE")
        w = w.model_copy(update={"current_tick": new_tick, "version": w.version + 1})
        self.items[world_id] = w
        return w

    def list_ids_by_status(self, status):
        return [w.id for w in self.items.values() if w.status == status]

    def mark_failed(self, world_id):
        w = self.items[world_id]
        self.items[world_id] = w.model_copy(
            update={"status": WorldStatus.FAILED, "version": w.version + 1}
        )


class FakePolicies(i.WorldPolicyRepository):
    def __init__(self) -> None:
        self.items: list[PolicyRead] = []

    def add(self, data):
        if any(p.world_id == data.world_id and p.version == data.version for p in self.items):
            raise ConflictError("CONCURRENT_UPDATE")
        p = PolicyRead(id=uuid.uuid4(), **data.__dict__)
        self.items.append(p)
        return p

    def _of(self, world_id):
        return [p for p in self.items if p.world_id == world_id]

    def latest(self, world_id):
        return max(self._of(world_id), key=lambda p: p.version, default=None)

    def current(self, world_id, tick):
        ok = [p for p in self._of(world_id) if p.effective_tick <= tick]
        return max(ok, key=lambda p: p.effective_tick, default=None)

    def all(self, world_id):
        return sorted(self._of(world_id), key=lambda p: p.version)

    def upsert_pending(self, data):
        for n, p in enumerate(self.items):
            if p.world_id == data.world_id and p.effective_tick == data.effective_tick:
                self.items[n] = p.model_copy(update={k: v for k, v in data.__dict__.items()})
                return self.items[n]
        return self.add(data)


class FakeSnapshotRepository(i.WorldSnapshotRepository):
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, i.SnapshotRecord] = {}

    def latest(self, world_id):
        return self.items.get(world_id)


class FakeSimulationPersistence(i.SimulationPersistence):
    def __init__(self) -> None:
        self.generations: list[tuple[uuid.UUID, EngineBatch]] = []
        self.advances: list[tuple[uuid.UUID, EngineBatch]] = []
        self.error: Exception | None = None

    def save_generation(self, world_id, batch):
        if self.error:
            raise self.error
        self.generations.append((world_id, batch))

    def save_advance(self, world_id, batch):
        if self.error:
            raise self.error
        self.advances.append((world_id, batch))


def make_batch(from_tick=0, to_tick=0, events=0, txs=0, seq=0) -> EngineBatch:
    return EngineBatch(
        from_tick=from_tick, to_tick=to_tick, event_count=events, transaction_count=txs,
        last_event_sequence=seq, snapshot_tick=to_tick, snapshot_state_data={"tick": to_tick},
        raw=None,
    )


class FakeEnginePort(SimulationEnginePort):
    def __init__(self) -> None:
        self.batch = make_batch()
        self.error: SimulationEngineError | None = None
        self.generated: list[tuple[int, str]] = []
        self.advance_calls: list[tuple[dict, list, int]] = []

    def generate(self, seed, name):
        self.generated.append((seed, name))
        if self.error:
            raise self.error
        return self.batch

    def advance(self, snapshot_state_data, policies, count):
        self.advance_calls.append((snapshot_state_data, policies, count))
        if self.error:
            raise self.error
        return self.batch


class FakeEvents(i.WorldEventRepository):
    def __init__(self) -> None:
        self.seq: dict[uuid.UUID, int] = {}

    def max_sequence(self, world_id):
        return self.seq.get(world_id, 0)


class FakeChunks(i.MapChunkRepository):
    def __init__(self) -> None:
        self.items: list[ChunkRead] = []
        self.saved: list = []

    def save_all(self, world_id, chunks):
        self.saved.append((world_id, chunks))

    def count(self, world_id):
        return sum(len(c) for w, c in self.saved if w == world_id)

    def list(self, world_id, query):
        def ok(v, lo, hi):
            return (lo is None or v >= lo) and (hi is None or v <= hi)

        return [
            c for c in self.items
            if c.world_id == world_id
            and ok(c.chunk_x, query.x_min, query.x_max)
            and ok(c.chunk_y, query.y_min, query.y_max)
        ]


class FakeBuildings(i.BuildingRepository):
    def __init__(self) -> None:
        self.items: list[BuildingRead] = []
        self.company_ids_by_building: dict[uuid.UUID, list[uuid.UUID]] = {}
        self.households: dict[uuid.UUID, int] = {}

    def list(self, world_id, query):
        def hit(t, size, lo, hi):
            return (lo is None or t + size - 1 >= lo) and (hi is None or t <= hi)

        return sorted(
            (
                b for b in self.items
                if b.world_id == world_id
                and hit(b.tile_x, b.width, query.x_min, query.x_max)
                and hit(b.tile_y, b.height, query.y_min, query.y_max)
            ),
            key=lambda b: b.id,
        )

    def get(self, world_id, building_id):
        return next((b for b in self.items if b.world_id == world_id and b.id == building_id), None)

    def company_ids(self, world_id, building_id):
        return self.company_ids_by_building.get(building_id, [])

    def household_count(self, world_id, building_id):
        return self.households.get(building_id, 0)


def _page(items, limit, offset):
    items = sorted(items, key=lambda x: x.id)
    return (items if limit is None else items[offset : offset + limit]), len(items)


class FakeCitizens(i.CitizenRepository):
    def __init__(self) -> None:
        self.items: list[CitizenRead] = []
        self.employment_by_citizen: dict[uuid.UUID, EmploymentRead] = {}
        self.movement_by_citizen: dict[uuid.UUID, MovementRead] = {}
        self.movement_queries: list[list[uuid.UUID]] = []

    def get(self, world_id, citizen_id):
        return next((c for c in self.items if c.world_id == world_id and c.id == citizen_id), None)

    def list(self, world_id, flt, limit, offset):
        def ok(c):
            return (
                c.world_id == world_id
                and (flt.employment_status is None or c.employment_status == flt.employment_status)
                and (flt.current_activity is None or c.current_activity == flt.current_activity)
                and (flt.building_id is None or c.current_building_id == flt.building_id)
                and (
                    flt.company_id is None
                    or (c.id in self.employment_by_citizen
                        and self.employment_by_citizen[c.id].company_id == flt.company_id)
                )
            )

        return _page([c for c in self.items if ok(c)], limit, offset)

    def movements(self, world_id, citizen_ids):
        self.movement_queries.append(list(citizen_ids))
        return {k: v for k, v in self.movement_by_citizen.items() if k in citizen_ids}

    def employments(self, world_id, citizen_ids):
        return {k: v for k, v in self.employment_by_citizen.items() if k in citizen_ids}

    def count(self, world_id):
        return sum(c.world_id == world_id for c in self.items)

    def count_employed(self, world_id):
        return len(self.employment_by_citizen)


class FakeCompanies(i.CompanyRepository):
    def __init__(self) -> None:
        self.items: list[CompanyRead] = []
        self.active: dict[uuid.UUID, int] = {}

    def get(self, world_id, company_id):
        return next((c for c in self.items if c.world_id == world_id and c.id == company_id), None)

    def list(self, world_id, status, industry, limit, offset):
        rows = [
            c for c in self.items
            if c.world_id == world_id
            and (status is None or c.status == status)
            and (industry is None or c.industry == industry)
        ]
        return _page(rows, limit, offset)

    def active_employees(self, world_id, company_id):
        return self.active.get(company_id, 0)

    def count_by_status(self, world_id):
        out: dict[str, int] = {}
        for c in self.items:
            if c.world_id == world_id:
                out[c.status.value] = out.get(c.status.value, 0) + 1
        return out


class FakeAccounts(i.AccountRepository):
    def __init__(self) -> None:
        self.items: dict[tuple, int] = {}
        self.treasury = 0
        self.internal = 0

    def cash_balance(self, world_id, owner_type, owner_id):
        return self.items.get((world_id, owner_type, owner_id))

    def cash_balances(self, world_id, owner_type, owner_ids):
        return {
            k: self.items[(world_id, owner_type, k)]
            for k in owner_ids if (world_id, owner_type, k) in self.items
        }

    def government_treasury(self, world_id):
        return self.treasury

    def city_internal_money(self, world_id):
        return self.internal


class FakeMetrics(i.WorldMetricRepository):
    def __init__(self) -> None:
        self.items: list[tuple[uuid.UUID, MetricRead]] = []

    def list(self, world_id, query):
        return [
            m for w, m in self.items
            if w == world_id
            and (query.metric_code is None or m.metric_code == query.metric_code)
            and (query.period is None or m.period == query.period)
            and (query.from_tick is None or m.tick >= query.from_tick)
            and (query.to_tick is None or m.tick <= query.to_tick)
        ]

    def latest_monthly(self, world_id):
        monthly = [m for w, m in self.items if w == world_id and m.period == MetricPeriod.MONTHLY]
        top = max((m.tick for m in monthly), default=None)
        return [m for m in monthly if m.tick == top]


class FakeUnitOfWork(i.UnitOfWork):
    def __init__(self) -> None:
        self.worlds = FakeWorlds()
        self.policies = FakePolicies()
        self.events = FakeEvents()
        self.chunks = FakeChunks()
        self.buildings = FakeBuildings()
        self.citizens = FakeCitizens()
        self.companies = FakeCompanies()
        self.accounts = FakeAccounts()
        self.metrics = FakeMetrics()
        self.snapshots = FakeSnapshotRepository()
        self.simulation = FakeSimulationPersistence()
        self.commits = 0
        self.rollbacks = 0
        self.consistent_reads = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def begin_consistent_read(self):
        self.consistent_reads += 1
