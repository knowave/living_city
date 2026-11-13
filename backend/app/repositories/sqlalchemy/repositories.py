from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import ConflictError
from app.models import (
    Account,
    Citizen,
    Company,
    MapChunk,
    World,
    WorldEvent,
    WorldMetric,
    WorldPolicy,
)
from app.repositories.interfaces import (
    AccountRepository,
    CitizenRepository,
    CompanyRepository,
    MapChunkRepository,
    NewPolicy,
    NewWorld,
    UnitOfWork,
    WorldEventRepository,
    WorldMetricRepository,
    WorldPolicyRepository,
    WorldRepository,
)
from app.schemas.city import (
    ChunkRangeQuery,
    ChunkRead,
    CitizenRead,
    CompanyRead,
    MetricQuery,
    MetricRead,
)
from app.schemas.enums import AccountOwnerType, WorldStatus
from app.schemas.world import PolicyRead, WorldRead


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


class SqlCitizenRepository(CitizenRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, world_id: UUID, citizen_id: UUID) -> CitizenRead | None:
        row = self._s.scalars(
            select(Citizen).where(Citizen.id == citizen_id, Citizen.world_id == world_id)
        ).first()
        return CitizenRead.model_validate(row, from_attributes=True) if row else None


class SqlCompanyRepository(CompanyRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, world_id: UUID, company_id: UUID) -> CompanyRead | None:
        row = self._s.scalars(
            select(Company).where(Company.id == company_id, Company.world_id == world_id)
        ).first()
        return CompanyRead.model_validate(row, from_attributes=True) if row else None


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


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:
        self.session = session
        self.worlds = SqlWorldRepository(session)
        self.policies = SqlWorldPolicyRepository(session)
        self.events = SqlWorldEventRepository(session)
        self.chunks = SqlMapChunkRepository(session)
        self.citizens = SqlCitizenRepository(session)
        self.companies = SqlCompanyRepository(session)
        self.accounts = SqlAccountRepository(session)
        self.metrics = SqlWorldMetricRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
