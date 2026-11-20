from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import ConflictError
from app.maps.generator import ChunkData
from app.maps.tiles import CHUNK_SIZE, TILE_SCHEMA_VERSION
from app.models import (
    Account,
    Building,
    Citizen,
    Company,
    Employment,
    Household,
    LedgerEntry,
    MapChunk,
    Transaction,
    World,
    WorldEvent,
    WorldMetric,
    WorldPolicy,
    WorldSnapshot,
)
from app.repositories.sqlalchemy.engine_mapper import entity_rows
from app.repositories.interfaces import (
    AccountRepository,
    BuildingRepository,
    CitizenRepository,
    CompanyRepository,
    MapChunkRepository,
    NewPolicy,
    NewWorld,
    SimulationPersistence,
    SnapshotRecord,
    UnitOfWork,
    WorldEventRepository,
    WorldMetricRepository,
    WorldPolicyRepository,
    WorldRepository,
    WorldSnapshotRepository,
)
from app.schemas.city import (
    BuildingRangeQuery,
    BuildingRead,
    ChunkRangeQuery,
    ChunkRead,
    CitizenFilter,
    CitizenRead,
    CompanyRead,
    EmploymentRead,
    MetricQuery,
    MetricRead,
    MovementRead,
)
from app.schemas.enums import AccountOwnerType, WorldStatus
from app.schemas.world import PolicyRead, WorldRead
from app.simulation.interfaces import EngineBatch


def _conflict() -> ConflictError:
    return ConflictError("CONCURRENT_UPDATE")


class SqlWorldRepository(WorldRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, data: NewWorld) -> WorldRead:
        row = World(name=data.name, seed=data.seed, engine_version=data.engine_version)
        
        self._s.add(row)
        self._s.flush()
        self._s.refresh(row)
        
        return WorldRead.model_validate(row, from_attributes=True)

    def get(self, world_id: UUID) -> WorldRead | None:
        row = self._s.get(World, world_id)
        return WorldRead.model_validate(row, from_attributes=True) if row else None

    def lock_for_update(
        self, world_id: UUID, *, nowait: bool, timeout_ms: int | None = None
    ) -> WorldRead | None:
        try:
            if not nowait and timeout_ms is not None:
                # SET LOCAL does not accept bind params; timeout_ms is an int.
                self._s.execute(text(f"SET LOCAL lock_timeout = '{int(timeout_ms)}ms'"))
            row = self._s.scalar(
                select(World)
                .where(World.id == world_id)
                .with_for_update(nowait=nowait)
                .execution_options(populate_existing=True)
            )
        except DBAPIError as e:
            if getattr(e.orig, "sqlstate", None) == "55P03":
                self._s.rollback()
                raise ConflictError("WORLD_BUSY", "World is busy with another write") from e
            raise
        return WorldRead.model_validate(row, from_attributes=True) if row else None

    def update_simulation(
        self, world_id: UUID, status: WorldStatus, speed: int, expected_version: int
    ) -> WorldRead:
        row = self._s.get(World, world_id)
        
        if row is None or row.version != expected_version:
            raise _conflict()
        
        row.status = status.value
        row.speed = speed
        
        try:
            self._s.flush()
        except StaleDataError as e:
            raise _conflict() from e
        
        self._s.refresh(row)
        return WorldRead.model_validate(row, from_attributes=True)


    def advance_tick(self, world_id: UUID, new_tick: int, expected_version: int) -> WorldRead:
        row = self._s.get(World, world_id)

        if row is None or row.version != expected_version:
            raise _conflict()

        row.current_tick = new_tick

        try:
            self._s.flush()
        except StaleDataError as e:
            raise _conflict() from e

        self._s.refresh(row)
        return WorldRead.model_validate(row, from_attributes=True)

    def list_ids_by_status(self, status: WorldStatus) -> list[UUID]:
        return list(
            self._s.scalars(select(World.id).where(World.status == status.value).order_by(World.id))
        )

    def mark_failed(self, world_id: UUID) -> None:
        row = self._s.get(World, world_id)

        if row is None:
            return

        row.status = WorldStatus.FAILED.value

        try:
            self._s.flush()
        except StaleDataError as e:
            raise _conflict() from e


class SqlWorldPolicyRepository(WorldPolicyRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, data: NewPolicy) -> PolicyRead:
        row = WorldPolicy(
            world_id=data.world_id,
            income_tax_rate=data.income_tax_rate,
            welfare_amount=data.welfare_amount,
            effective_tick=data.effective_tick,
            version=data.version,
        )
        
        self._s.add(row)
        
        try:
            self._s.flush()
        except IntegrityError as e:
            raise _conflict() from e
        
        return PolicyRead.model_validate(row, from_attributes=True)

    def _first(self, *where, order) -> PolicyRead | None:
        row = self._s.scalars(select(WorldPolicy).where(*where).order_by(order).limit(1)).first()
        return PolicyRead.model_validate(row, from_attributes=True) if row else None

    def latest(self, world_id: UUID) -> PolicyRead | None:
        return self._first(WorldPolicy.world_id == world_id, order=WorldPolicy.version.desc())

    def current(self, world_id: UUID, tick: int) -> PolicyRead | None:
        # Spec: latest version whose effective_tick <= tick.
        return self._first(
            WorldPolicy.world_id == world_id,
            WorldPolicy.effective_tick <= tick,
            order=WorldPolicy.version.desc(),
        )


    def all(self, world_id: UUID) -> list[PolicyRead]:
        rows = self._s.scalars(
            select(WorldPolicy).where(WorldPolicy.world_id == world_id).order_by(WorldPolicy.version)
        )
        return [PolicyRead.model_validate(r, from_attributes=True) for r in rows]

    def upsert_pending(self, data: NewPolicy) -> PolicyRead:
        row = self._s.scalars(
            select(WorldPolicy).where(
                WorldPolicy.world_id == data.world_id,
                WorldPolicy.effective_tick == data.effective_tick,
            )
        ).first()

        if row is None:
            return self.add(data)

        row.income_tax_rate = data.income_tax_rate
        row.welfare_amount = data.welfare_amount
        row.version = data.version

        try:
            self._s.flush()
        except IntegrityError as e:
            raise _conflict() from e

        return PolicyRead.model_validate(row, from_attributes=True)


class SqlWorldSnapshotRepository(WorldSnapshotRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def latest(self, world_id: UUID) -> SnapshotRecord | None:
        row = self._s.scalars(
            select(WorldSnapshot)
            .where(WorldSnapshot.world_id == world_id)
            .order_by(WorldSnapshot.tick.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        return SnapshotRecord(row.tick, row.last_event_sequence, row.state_data)


SNAPSHOT_KEEP_INTERVAL = 720


class SqlSimulationPersistence(SimulationPersistence):
    def __init__(self, session: Session, snapshot_keep_latest: int = 3) -> None:
        self._s = session
        self._keep_latest = snapshot_keep_latest

    def _upsert(self, model, rows: list[dict]) -> None:
        if not rows:
            return
        table = model.__table__  # core table: column keys (e.g. "metadata"), not ORM attribute names
        stmt = pg_insert(table)
        skip = {"id", "created_at"}
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                **{c.name: stmt.excluded[c.name] for c in table.c if c.name not in skip and c.name in rows[0]},
                "updated_at": func.now(),
            },
        )
        self._s.execute(stmt, rows)

    def _insert(self, model, rows: list[dict]) -> None:
        if rows:
            self._s.execute(pg_insert(model.__table__), rows)

    def _save(self, world_id: UUID, batch: EngineBatch, policies: list) -> None:
        r = entity_rows(world_id, batch.raw, policies)
        # FK order: buildings -> households/companies -> citizens -> employments/accounts.
        for model, key in (
            (Building, "buildings"),
            (Household, "households"),
            (Company, "companies"),
            (Citizen, "citizens"),
        ):
            self._upsert(model, r[key])
        # uq_employments_world_citizen_active is checked per row: write terminated rows first so a
        # re-hire of the same citizen in one batch cannot hit the unique index.
        emps = r["employments"]
        self._upsert(Employment, [e for e in emps if e["terminated_tick"] is not None])
        self._upsert(Employment, [e for e in emps if e["terminated_tick"] is None])
        self._upsert(Account, r["accounts"])
        self._upsert(WorldPolicy, r["world_policies"])
        for model, key in (
            (Transaction, "transactions"),
            (LedgerEntry, "ledger_entries"),
            (WorldEvent, "world_events"),
            (WorldMetric, "world_metrics"),
            (WorldSnapshot, "world_snapshots"),
        ):
            self._insert(model, r[key])
        self._s.flush()

    def save_generation(self, world_id: UUID, batch: EngineBatch) -> None:
        raw = batch.raw
        try:
            self._save(world_id, batch, list(raw.state.policies.values()))
        except IntegrityError as e:
            raise ConflictError("CONCURRENT_UPDATE", "Concurrent update detected") from e

    def save_advance(self, world_id: UUID, batch: EngineBatch) -> None:
        try:
            self._save_advance(world_id, batch)
            self._prune_snapshots(world_id)
        except IntegrityError as e:
            raise ConflictError("CONCURRENT_UPDATE", "Concurrent update detected") from e

    def _prune_snapshots(self, world_id: UUID) -> None:
        newest = (
            select(WorldSnapshot.tick)
            .where(WorldSnapshot.world_id == world_id)
            .order_by(WorldSnapshot.tick.desc())
            .limit(self._keep_latest)
        )
        self._s.execute(
            delete(WorldSnapshot).where(
                WorldSnapshot.world_id == world_id,
                WorldSnapshot.tick % SNAPSHOT_KEEP_INTERVAL != 0,
                WorldSnapshot.tick.not_in(newest),
            )
        )

    def _save_advance(self, world_id: UUID, batch: EngineBatch) -> None:
        raw = batch.raw
        # Backend pending rows (random ids/versions) are replaced by the engine's rows for the
        # same effective_tick. Delete all first so engine-assigned versions cannot collide.
        if raw.new_policies:
            self._s.execute(
                delete(WorldPolicy).where(
                    WorldPolicy.world_id == world_id,
                    WorldPolicy.effective_tick.in_([p.effective_tick for p in raw.new_policies]),
                )
            )
        self._save(world_id, batch, raw.new_policies)


class SqlWorldEventRepository(WorldEventRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def max_sequence(self, world_id: UUID) -> int:
        return self._s.scalar(
            select(func.coalesce(func.max(WorldEvent.sequence), 0)).where(
                WorldEvent.world_id == world_id
            )
        )


class SqlMapChunkRepository(MapChunkRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def save_all(self, world_id: UUID, chunks: list[ChunkData]) -> None:
        self._s.execute(
            pg_insert(MapChunk),
            [
                {
                    "world_id": world_id,
                    "chunk_x": c.chunk_x,
                    "chunk_y": c.chunk_y,
                    "chunk_size": CHUNK_SIZE,
                    "terrain_tiles": c.terrain_tiles,
                    "road_tiles": c.road_tiles,
                    "schema_version": TILE_SCHEMA_VERSION,
                    "revision": 1,
                }
                for c in chunks
            ],
        )

    def count(self, world_id: UUID) -> int:
        return self._s.scalar(select(func.count()).select_from(MapChunk).where(MapChunk.world_id == world_id))

    def list(self, world_id: UUID, query: ChunkRangeQuery) -> list[ChunkRead]:
        stmt = select(MapChunk).where(MapChunk.world_id == world_id)
        
        if query.x_min is not None:
            stmt = stmt.where(MapChunk.chunk_x >= query.x_min)
        
        if query.x_max is not None:
            stmt = stmt.where(MapChunk.chunk_x <= query.x_max)
        
        if query.y_min is not None:
            stmt = stmt.where(MapChunk.chunk_y >= query.y_min)
        
        if query.y_max is not None:
            stmt = stmt.where(MapChunk.chunk_y <= query.y_max)
        
        rows = self._s.scalars(stmt.order_by(MapChunk.chunk_y, MapChunk.chunk_x))
        return [ChunkRead.model_validate(r, from_attributes=True) for r in rows]


class SqlBuildingRepository(BuildingRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def list(self, world_id: UUID, query: BuildingRangeQuery) -> list[BuildingRead]:
        stmt = select(Building).where(Building.world_id == world_id)

        # rectangle overlap: [tile, tile + size - 1] intersects [min, max]
        if query.x_min is not None:
            stmt = stmt.where(Building.tile_x + Building.width - 1 >= query.x_min)

        if query.x_max is not None:
            stmt = stmt.where(Building.tile_x <= query.x_max)

        if query.y_min is not None:
            stmt = stmt.where(Building.tile_y + Building.height - 1 >= query.y_min)

        if query.y_max is not None:
            stmt = stmt.where(Building.tile_y <= query.y_max)

        return [
            BuildingRead.model_validate(r, from_attributes=True)
            for r in self._s.scalars(stmt.order_by(Building.id))
        ]

    def get(self, world_id: UUID, building_id: UUID) -> BuildingRead | None:
        row = self._s.scalars(
            select(Building).where(Building.id == building_id, Building.world_id == world_id)
        ).first()
        return BuildingRead.model_validate(row, from_attributes=True) if row else None

    def company_ids(self, world_id: UUID, building_id: UUID) -> list[UUID]:
        return list(
            self._s.scalars(
                select(Company.id)
                .where(Company.world_id == world_id, Company.building_id == building_id)
                .order_by(Company.id)
            )
        )

    def household_count(self, world_id: UUID, building_id: UUID) -> int:
        return self._s.scalar(
            select(func.count()).where(
                Household.world_id == world_id, Household.residence_building_id == building_id
            )
        )


def _page(s: Session, stmt, order, limit: int | None, offset: int):
    total = s.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    stmt = stmt.order_by(order).offset(offset)

    if limit is not None:
        stmt = stmt.limit(limit)

    return list(s.scalars(stmt)), total


class SqlCitizenRepository(CitizenRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, world_id: UUID, citizen_id: UUID) -> CitizenRead | None:
        row = self._s.scalars(
            select(Citizen).where(Citizen.id == citizen_id, Citizen.world_id == world_id)
        ).first()
        return CitizenRead.model_validate(row, from_attributes=True) if row else None

    def list(
        self, world_id: UUID, flt: CitizenFilter, limit: int | None, offset: int
    ) -> tuple[list[CitizenRead], int]:
        stmt = select(Citizen).where(Citizen.world_id == world_id)

        if flt.employment_status is not None:
            stmt = stmt.where(Citizen.employment_status == flt.employment_status)

        if flt.current_activity is not None:
            stmt = stmt.where(Citizen.current_activity == flt.current_activity)

        if flt.building_id is not None:
            stmt = stmt.where(Citizen.current_building_id == flt.building_id)

        if flt.company_id is not None:
            stmt = stmt.where(
                Citizen.id.in_(
                    select(Employment.citizen_id).where(
                        Employment.world_id == world_id,
                        Employment.company_id == flt.company_id,
                        Employment.terminated_tick.is_(None),
                    )
                )
            )

        rows, total = _page(self._s, stmt, Citizen.id, limit, offset)
        return [CitizenRead.model_validate(r, from_attributes=True) for r in rows], total

    def movements(self, world_id: UUID, citizen_ids: list[UUID]) -> dict[UUID, MovementRead]:
        if not citizen_ids:
            return {}

        cid = WorldEvent.payload["citizen_id"].astext
        # shortcut: scans this world's movement events newest-first; add a tick lower bound or an
        # index on (world_id, type, payload->>'citizen_id') if the event table grows large.
        rows = self._s.execute(
            select(cid, WorldEvent.payload)
            .where(
                WorldEvent.world_id == world_id,
                WorldEvent.type == "citizen.movement.started",
                cid.in_([str(c) for c in citizen_ids]),
            )
            .distinct(cid)
            .order_by(cid, WorldEvent.sequence.desc())
        )
        return {
            UUID(k): MovementRead(
                from_building_id=p["from_building_id"],
                to_building_id=p["to_building_id"],
                start_tick=p["start_tick"],
                arrival_tick=p["arrival_tick"],
            )
            for k, p in rows
        }

    def employments(self, world_id: UUID, citizen_ids: list[UUID]) -> dict[UUID, EmploymentRead]:
        if not citizen_ids:
            return {}

        rows = self._s.execute(
            select(Employment.citizen_id, Employment.company_id, Employment.salary, Employment.hired_tick)
            .where(
                Employment.world_id == world_id,
                Employment.terminated_tick.is_(None),
                Employment.citizen_id.in_(citizen_ids),
            )
        )
        return {
            r.citizen_id: EmploymentRead(
                company_id=r.company_id, salary=r.salary, hired_tick=r.hired_tick
            )
            for r in rows
        }

    def count(self, world_id: UUID) -> int:
        return self._s.scalar(select(func.count()).where(Citizen.world_id == world_id))

    def count_employed(self, world_id: UUID) -> int:
        return self._s.scalar(
            select(func.count()).where(
                Employment.world_id == world_id, Employment.terminated_tick.is_(None)
            )
        )


class SqlCompanyRepository(CompanyRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, world_id: UUID, company_id: UUID) -> CompanyRead | None:
        row = self._s.scalars(
            select(Company).where(Company.id == company_id, Company.world_id == world_id)
        ).first()
        return CompanyRead.model_validate(row, from_attributes=True) if row else None

    def list(
        self,
        world_id: UUID,
        status: str | None,
        industry: str | None,
        limit: int | None,
        offset: int,
    ) -> tuple[list[CompanyRead], int]:
        stmt = select(Company).where(Company.world_id == world_id)

        if status is not None:
            stmt = stmt.where(Company.status == status)

        if industry is not None:
            stmt = stmt.where(Company.industry == industry)

        rows, total = _page(self._s, stmt, Company.id, limit, offset)
        return [CompanyRead.model_validate(r, from_attributes=True) for r in rows], total

    def active_employees(self, world_id: UUID, company_id: UUID) -> int:
        return self._s.scalar(
            select(func.count()).where(
                Employment.world_id == world_id,
                Employment.company_id == company_id,
                Employment.terminated_tick.is_(None),
            )
        )

    def count_by_status(self, world_id: UUID) -> dict[str, int]:
        rows = self._s.execute(
            select(Company.status, func.count()).where(Company.world_id == world_id).group_by(Company.status)
        )
        return {k: v for k, v in rows}


_OWNER_COLUMN = {
    AccountOwnerType.CITIZEN: Account.citizen_id,
    AccountOwnerType.HOUSEHOLD: Account.household_id,
    AccountOwnerType.COMPANY: Account.company_id,
}


class SqlAccountRepository(AccountRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def cash_balance(
        self, world_id: UUID, owner_type: AccountOwnerType, owner_id: UUID
    ) -> int | None:
        col = _OWNER_COLUMN.get(owner_type)
        
        if col is None:  # GOVERNMENT/SYSTEM accounts have no owner id
            return None
        
        return self._s.scalar(
            select(Account.balance).where(
                Account.world_id == world_id,
                Account.owner_type == owner_type.value,
                col == owner_id,
                Account.account_type == "CASH",
                Account.currency == "KRW",
            )
        )

    def cash_balances(
        self, world_id: UUID, owner_type: AccountOwnerType, owner_ids: list[UUID]
    ) -> dict[UUID, int]:
        col = _OWNER_COLUMN[owner_type]

        if not owner_ids:
            return {}

        rows = self._s.execute(
            select(col, Account.balance).where(
                Account.world_id == world_id,
                Account.owner_type == owner_type.value,
                col.in_(owner_ids),
                Account.account_type == "CASH",
                Account.currency == "KRW",
            )
        )
        return {k: v for k, v in rows}

    def government_treasury(self, world_id: UUID) -> int:
        return self._s.scalar(
            select(func.coalesce(func.sum(Account.balance), 0)).where(
                Account.world_id == world_id,
                Account.owner_type == AccountOwnerType.GOVERNMENT.value,
                Account.account_type == "TREASURY",
                Account.currency == "KRW",
            )
        )

    def city_internal_money(self, world_id: UUID) -> int:
        return self._s.scalar(
            select(func.coalesce(func.sum(Account.balance), 0)).where(
                Account.world_id == world_id,
                Account.owner_type.in_(
                    [
                        AccountOwnerType.CITIZEN.value,
                        AccountOwnerType.HOUSEHOLD.value,
                        AccountOwnerType.COMPANY.value,
                        AccountOwnerType.GOVERNMENT.value,
                    ]
                ),
            )
        )


class SqlWorldMetricRepository(WorldMetricRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def list(self, world_id: UUID, query: MetricQuery) -> list[MetricRead]:
        stmt = select(WorldMetric).where(WorldMetric.world_id == world_id)
        
        if query.metric_code is not None:
            stmt = stmt.where(WorldMetric.metric_code == query.metric_code.value)
        
        if query.period is not None:
            stmt = stmt.where(WorldMetric.period == query.period.value)
        
        if query.from_tick is not None:
            stmt = stmt.where(WorldMetric.tick >= query.from_tick)
        
        if query.to_tick is not None:
            stmt = stmt.where(WorldMetric.tick <= query.to_tick)
        
        rows = self._s.scalars(stmt.order_by(WorldMetric.tick))
        return [MetricRead.model_validate(r, from_attributes=True) for r in rows]

    def latest_monthly(self, world_id: UUID) -> list[MetricRead]:
        monthly = (WorldMetric.world_id == world_id, WorldMetric.period == "MONTHLY")
        latest = select(func.max(WorldMetric.tick)).where(*monthly).scalar_subquery()
        rows = self._s.scalars(
            select(WorldMetric)
            .where(*monthly, WorldMetric.tick == latest)
            .order_by(WorldMetric.metric_code)
        )
        return [MetricRead.model_validate(r, from_attributes=True) for r in rows]


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session, snapshot_keep_latest: int = 3) -> None:
        self.session = session
        self.worlds = SqlWorldRepository(session)
        self.policies = SqlWorldPolicyRepository(session)
        self.events = SqlWorldEventRepository(session)
        self.chunks = SqlMapChunkRepository(session)
        self.buildings = SqlBuildingRepository(session)
        self.citizens = SqlCitizenRepository(session)
        self.companies = SqlCompanyRepository(session)
        self.accounts = SqlAccountRepository(session)
        self.metrics = SqlWorldMetricRepository(session)
        self.snapshots = SqlWorldSnapshotRepository(session)
        self.simulation = SqlSimulationPersistence(session, snapshot_keep_latest)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def begin_consistent_read(self) -> None:
        # Must run before the session's first statement (isolation is fixed per transaction).
        self.session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
