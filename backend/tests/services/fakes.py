import uuid
from datetime import UTC, datetime

from app.core.exceptions import ConflictError
from app.repositories import interfaces as i
from app.schemas.city import ChunkRead, CitizenRead, CompanyRead, MetricRead
from app.schemas.enums import WorldStatus
from app.schemas.world import PolicyRead, WorldRead


class FakeWorlds(i.WorldRepository):
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, WorldRead] = {}
        self.stale = False  # simulate concurrent update

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

    def update_simulation(self, world_id, status, speed, expected_version):
        w = self.items[world_id]
        if self.stale or w.version != expected_version:
            raise ConflictError("CONCURRENT_UPDATE")
        w = w.model_copy(update={"status": status, "speed": speed, "version": w.version + 1})
        self.items[world_id] = w
        return w


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


class FakeEvents(i.WorldEventRepository):
    def __init__(self) -> None:
        self.seq: dict[uuid.UUID, int] = {}

    def max_sequence(self, world_id):
        return self.seq.get(world_id, 0)


class FakeChunks(i.MapChunkRepository):
    def __init__(self) -> None:
        self.items: list[ChunkRead] = []

    def list(self, world_id, query):
        def ok(v, lo, hi):
            return (lo is None or v >= lo) and (hi is None or v <= hi)

        return [
            c for c in self.items
            if c.world_id == world_id
            and ok(c.chunk_x, query.x_min, query.x_max)
            and ok(c.chunk_y, query.y_min, query.y_max)
        ]


class FakeCitizens(i.CitizenRepository):
    def __init__(self) -> None:
        self.items: list[CitizenRead] = []

    def get(self, world_id, citizen_id):
        return next((c for c in self.items if c.world_id == world_id and c.id == citizen_id), None)


class FakeCompanies(i.CompanyRepository):
    def __init__(self) -> None:
        self.items: list[CompanyRead] = []

    def get(self, world_id, company_id):
        return next((c for c in self.items if c.world_id == world_id and c.id == company_id), None)


class FakeAccounts(i.AccountRepository):
    def __init__(self) -> None:
        self.items: dict[tuple, int] = {}

    def cash_balance(self, world_id, owner_type, owner_id):
        return self.items.get((world_id, owner_type, owner_id))


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


class FakeUnitOfWork(i.UnitOfWork):
    def __init__(self) -> None:
        self.worlds = FakeWorlds()
        self.policies = FakePolicies()
        self.events = FakeEvents()
        self.chunks = FakeChunks()
        self.citizens = FakeCitizens()
        self.companies = FakeCompanies()
        self.accounts = FakeAccounts()
        self.metrics = FakeMetrics()
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1
