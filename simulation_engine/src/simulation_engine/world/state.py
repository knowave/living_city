"""월드 상태 컨테이너. 엔티티 dict(UUID 키)와 엔진 내부 보조 필드, Snapshot 변환을 담는다."""

import enum
import hashlib
import uuid
import typing
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any

from simulation_engine.economy import Account, AccountOwnerType, AccountType
from simulation_engine.entities import Building, Citizen, Company, Employment, Household, World, WorldPolicy
from simulation_engine.world.snapshot import WorldSnapshot

FORMAT_VERSION = 1
# snapshot 키 -> 엔티티 클래스. 순서가 직렬화 순서이다.
_ENTITY_CLASSES = {
    "policies": WorldPolicy,
    "buildings": Building,
    "citizens": Citizen,
    "households": Household,
    "companies": Company,
    "employments": Employment,
    "accounts": Account,
}


def _to_plain(obj: Any) -> dict[str, Any]:
    out = {}
    for f in fields(obj):
        v = getattr(obj, f.name)
        out[f.name] = str(v) if isinstance(v, uuid.UUID) else v.value if isinstance(v, enum.Enum) else v
    return out


def _from_plain(cls: type, data: dict[str, Any]) -> Any:
    hints = typing.get_type_hints(cls)
    kwargs = {}
    for name, v in data.items():
        types = (hints[name], *typing.get_args(hints[name]))
        if v is not None and uuid.UUID in types:
            v = uuid.UUID(v)
        else:
            for t in types:
                if isinstance(t, type) and issubclass(t, enum.Enum):
                    v = t(v)
        kwargs[name] = v
    return cls(**kwargs)


def _uuid_key_dict(d: dict[uuid.UUID, int]) -> dict[str, int]:
    return {str(k): v for k, v in d.items()}


@dataclass(slots=True)
class WorldState:
    world: World
    policies: dict[uuid.UUID, WorldPolicy] = field(default_factory=dict)
    buildings: dict[uuid.UUID, Building] = field(default_factory=dict)
    citizens: dict[uuid.UUID, Citizen] = field(default_factory=dict)
    households: dict[uuid.UUID, Household] = field(default_factory=dict)
    companies: dict[uuid.UUID, Company] = field(default_factory=dict)
    employments: dict[uuid.UUID, Employment] = field(default_factory=dict)
    accounts: dict[uuid.UUID, Account] = field(default_factory=dict)

    # 엔진 내부 필드 (snapshot "engine"에 저장)
    next_event_sequence: int = 1
    id_counters: dict[str, int] = field(default_factory=dict)
    distressed_months: dict[uuid.UUID, int] = field(default_factory=dict)  # company_id -> 연속 DISTRESSED 월 수
    last_month_income: dict[uuid.UUID, int] = field(default_factory=dict)  # citizen_id -> 지난달 세후 소득
    movement_starts: dict[uuid.UUID, int] = field(default_factory=dict)  # citizen_id -> 이동 출발 tick
    trip_purpose: dict[uuid.UUID, str] = field(default_factory=dict)  # citizen_id -> commute|home|shop (이동 중에만)
    last_shop_day: dict[uuid.UUID, int] = field(default_factory=dict)  # citizen_id -> 마지막 소비 출발 소비일
    monthly_budget: dict[uuid.UUID, int] = field(default_factory=dict)  # citizen_id -> 이번 달 소비 예산
    unpaid_opex: dict[uuid.UUID, int] = field(default_factory=dict)  # company_id -> 이번 달 미납액
    month_accumulators: dict[str, int] = field(default_factory=dict)  # "이름:id" -> 이번 달 누적 (월말 지표 후 엔진이 비움)

    _account_index: dict[tuple, uuid.UUID] = field(default_factory=dict, repr=False, compare=False)

    @property
    def seed(self) -> int:
        return self.world.seed

    @property
    def tick(self) -> int:
        return self.world.current_tick

    def new_id(self, kind: str) -> uuid.UUID:
        n = self.id_counters.get(kind, 0)
        self.id_counters[kind] = n + 1
        digest = hashlib.sha256(f"{self.seed}:{kind}:{n}".encode()).digest()
        return uuid.UUID(bytes=digest[:16], version=4)

    def ordered(self, name: str) -> list:
        """엔티티 컬렉션(name 예: "citizens")을 id 순으로 돌려준다. 순회는 항상 이것을 쓴다."""
        d = getattr(self, name)
        return [d[k] for k in sorted(d)]

    def add_account(self, account: Account) -> Account:
        self.accounts[account.id] = account
        owner = account.citizen_id or account.household_id or account.company_id
        self._account_index[(account.owner_type, owner, account.account_type)] = account.id
        return account

    def account_of(
        self,
        owner_type: AccountOwnerType,
        owner_id: uuid.UUID | None = None,
        account_type: AccountType = AccountType.CASH,
    ) -> Account:
        """소유자 계정. GOVERNMENT는 account_type=TREASURY, SYSTEM은 ISSUANCE/CASH로 부른다."""
        return self.accounts[self._account_index[(owner_type, owner_id, account_type)]]

    def current_policy(self, tick: int) -> WorldPolicy:
        return max((p for p in self.policies.values() if p.effective_tick <= tick), key=lambda p: p.version)

    def total_balance(self) -> int:
        return sum(a.balance for a in self.accounts.values())

    def to_snapshot(self) -> WorldSnapshot:
        data: dict[str, Any] = {
            "format_version": FORMAT_VERSION,
            "engine_version": self.world.engine_version,
            "seed": self.seed,
            "tick": self.tick,
            "world": _to_plain(self.world),
        }
        for key in _ENTITY_CLASSES:
            data[key] = [_to_plain(e) for e in self.ordered(key)]
        data["engine"] = {
            "next_event_sequence": self.next_event_sequence,
            "id_counters": dict(self.id_counters),
            "distressed_months": _uuid_key_dict(self.distressed_months),
            "last_month_income": _uuid_key_dict(self.last_month_income),
            "movement_starts": _uuid_key_dict(self.movement_starts),
            "trip_purpose": _uuid_key_dict(self.trip_purpose),
            "last_shop_day": _uuid_key_dict(self.last_shop_day),
            "monthly_budget": _uuid_key_dict(self.monthly_budget),
            "unpaid_opex": _uuid_key_dict(self.unpaid_opex),
            "month_accumulators": dict(self.month_accumulators),
        }
        digest = hashlib.sha256(f"{self.seed}:snapshot:{self.tick}".encode()).digest()
        return WorldSnapshot(
            id=uuid.UUID(bytes=digest[:16], version=4),
            tick=self.tick,
            last_event_sequence=self.next_event_sequence - 1,
            engine_version=self.world.engine_version,
            state_data=data,
        )

    @classmethod
    def from_snapshot(cls, snapshot: WorldSnapshot) -> "WorldState":
        data = snapshot.state_data
        if data["format_version"] != FORMAT_VERSION:
            raise ValueError(f"지원하지 않는 snapshot format_version: {data['format_version']}")
        state = cls(world=_from_plain(World, data["world"]))
        for key, entity_cls in _ENTITY_CLASSES.items():
            for raw in data[key]:
                e = _from_plain(entity_cls, raw)
                if key == "accounts":
                    state.add_account(e)
                else:
                    getattr(state, key)[e.id] = e
        eng = data["engine"]
        state.next_event_sequence = eng["next_event_sequence"]
        state.id_counters = dict(eng["id_counters"])
        for name in ("distressed_months", "last_month_income", "movement_starts", "trip_purpose", "last_shop_day", "monthly_budget", "unpaid_opex"):
            setattr(state, name, {uuid.UUID(k): v for k, v in eng[name].items()})
        state.month_accumulators = dict(eng["month_accumulators"])
        return state
