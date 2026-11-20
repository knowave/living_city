## 핸드오프: team-plan → team-exec (engine-integration)

- **결정**: 스펙 `backend/.omc/specs/deep-interview-engine-integration.md`(가정 1–9 승인)를 아래 계약으로 구현한다. 작업 순서: docs(W1) → 계약(W2) → [영속화(W3) ∥ 서비스·API(W4)] → 통합 테스트(W5).
- **거절**: 엔진 수정(동결), 테이블 변경, Tick마다 커밋, 엔진 id를 그대로 저장.
- **위험**: 정책 대기 행 교체 시 version 불일치(허용: effective_tick 기준으로 교체), PG upsert 순서와 복합 FK, Decimal 반올림.
- **남은 것**: Runner, 배속·일시정지 REST, SSE (다음 Phase).

# 공유 계약 (모든 작업자가 이 이름·시그니처를 그대로 쓴다)

## 1. 의존성
- `uv add --editable ../simulation_engine` (backend `pyproject.toml`에 `simulation-engine` path 의존성). `requirements.txt`에는 `-e ../simulation_engine` 한 줄 추가.

## 2. 예외 (`app/core/exceptions.py`에 추가 없음, 기존 클래스 + 새 코드 문자열)
- `InvalidStateError("WORLD_NOT_RUNNABLE")` → 409 : FAILED/ARCHIVED 세계의 Tick 진행
- `ConflictError("SIMULATION_FAILED")` → 409 : 엔진 예외 (세계는 FAILED로 바뀜)
- `ConflictError("SNAPSHOT_MISMATCH")` → 409 : 최신 snapshot.tick != worlds.current_tick, 또는 snapshot 없음
- `ConflictError("CONCURRENT_UPDATE")` → 409 : world.version 불일치 (기존)
- 새 예외 클래스 `SimulationEngineError(Exception)`는 `app/simulation/interfaces.py`에 둔다 (adapter가 엔진 예외를 감싸 던짐; DomainError 아님).

## 3. 엔진 port — `app/simulation/interfaces.py` (simulation_engine import 금지)
```python
@dataclass(frozen=True)
class PolicyCommandInput:      # DB 정책 행에서 만든 명령 입력
    income_tax_rate: int
    welfare_amount: int
    effective_tick: int
    version: int

@dataclass
class EngineBatch:             # 엔진 실행 결과. service에는 불투명(opaque)
    from_tick: int             # 생성이면 0
    to_tick: int               # 실행 후 WorldState.tick (생성이면 0)
    event_count: int
    transaction_count: int
    last_event_sequence: int   # snapshot.last_event_sequence
    snapshot_tick: int
    snapshot_state_data: dict
    raw: object                # 엔진 원본(GenerationResult 또는 list[TickResult] + WorldState). mapper만 해석

class SimulationEngineError(Exception): ...

class SimulationEnginePort(ABC):
    @abstractmethod
    def generate(self, seed: int, name: str) -> EngineBatch: ...
    @abstractmethod
    def advance(self, snapshot_state_data: dict, policies: list[PolicyCommandInput], count: int) -> EngineBatch:
        """snapshot에서 WorldState 복원 → policies 중 snapshot 정책에 effective_tick이 없는 것만
        version 순으로 PolicyChangeCommand로 바꿔 첫 Tick에 적용 → run(count).
        엔진 예외는 SimulationEngineError로 감싼다."""
```
- 구현: `app/simulation/engine_adapter.py`의 `SimulationEngineAdapter(SimulationEnginePort)`. `SimulationConfig()` 기본값 사용. raw에는 최종 `WorldState`와 생성 결과/TickResult 목록을 담는다.

## 4. Repository 추가 — `app/repositories/interfaces.py`
```python
@dataclass(frozen=True)
class SnapshotRecord:
    tick: int
    last_event_sequence: int
    state_data: dict

class WorldRepository:  # 기존에 추가
    def advance_tick(self, world_id, new_tick: int, expected_version: int) -> WorldRead
        # version 불일치 → ConflictError("CONCURRENT_UPDATE")
    def mark_failed(self, world_id) -> None   # status=FAILED (version 증가)

class WorldPolicyRepository:  # 기존에 추가
    def all(self, world_id) -> list[PolicyRead]          # version 오름차순
    def upsert_pending(self, data: NewPolicy) -> PolicyRead
        # (world_id, effective_tick) 행이 있으면 값 덮어쓰고 version=data.version, 없으면 insert

class WorldSnapshotRepository(ABC):
    def latest(self, world_id) -> SnapshotRecord | None

class SimulationPersistence(ABC):
    def save_generation(self, world_id, batch: EngineBatch) -> None
    def save_advance(self, world_id, batch: EngineBatch) -> None
        # 둘 다: 엔티티 7종 upsert, 거래·원장·이벤트·지표 insert, snapshot insert,
        # (advance) 같은 effective_tick의 backend 대기 정책 행을 엔진 정책 행으로 교체. flush만, commit 안 함.

class UnitOfWork:  # 속성 추가
    snapshots: WorldSnapshotRepository
    simulation: SimulationPersistence
```
- `PolicyRead`에 `version` 필드가 없으면 추가한다(스키마).

## 5. Mapper — `app/repositories/sqlalchemy/engine_mapper.py` (simulation_engine import 허용)
- `db_id(world_id: UUID, engine_id) -> UUID = uuid.uuid5(world_id, str(engine_id))`.
- 엔진이 만든 모든 행(정책, 건물, 가구, 기업, 시민, 고용, 계좌, 거래, 원장, 이벤트, 지표, snapshot)의 id와 그 안의 참조 id를 db_id로 바꾸고 `world_id`를 넣는다.
- 이벤트 payload: 키가 `_id`로 끝나고 값이 UUID 문자열이면 `str(db_id(...))`로 교체.
- `idempotency_key`, snapshot `state_data`는 그대로 둔다.
- `risk_tolerance`, `consumption_preference` = bps / 10000 (float). 지표 Decimal → `quantize(Decimal("0.000001"))`.
- enum → `.value`, Transaction `metadata` → ORM `metadata_`.
- worlds 행은 mapper가 만들지 않는다. 엔진 World는 current_tick만 의미가 있으며 service가 `advance_tick`으로 반영.
- upsert: `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(index_elements=["id"], set_=...)`. 순서: buildings → households → companies → citizens → employments → accounts → policies, 그 뒤 transactions → ledger_entries → world_events → world_metrics → world_snapshots(insert).

## 6. Use case / service / API
- `WorldUseCase.advance_ticks(world_id: UUID, data: TickAdvanceRequest) -> TickAdvanceRead` 추가.
- 스키마(`app/schemas/world.py`): `TickAdvanceRequest(count: int = Field(ge=1, le=720))`, `TickAdvanceRead(from_tick, to_tick, event_count, last_event_sequence, transaction_count)`.
- `WorldService(uow, engine: SimulationEnginePort, engine_version_default)`:
  - `create_world`: seed 결정(없으면 63비트 랜덤) → `uow.worlds.add` → `engine.generate(seed, name)` → `uow.simulation.save_generation` → commit. backend 정책 v1 생성 코드는 제거(엔진 정책 사용). engine_version은 엔진 `__version__`이 아니라 기존 설정값 유지.
  - `advance_ticks`: world 조회(없으면 404) → FAILED/ARCHIVED면 `WORLD_NOT_RUNNABLE` → `uow.snapshots.latest`가 없거나 tick != current_tick이면 `SNAPSHOT_MISMATCH` → `uow.policies.all`을 `PolicyCommandInput`으로 → `engine.advance` → `uow.simulation.save_advance` → `uow.worlds.advance_tick(new_tick=batch.to_tick, expected_version=world.version)` → commit → `TickAdvanceRead`.
    - `SimulationEngineError` → `uow.rollback()` → `uow.worlds.mark_failed` → commit → `ConflictError("SIMULATION_FAILED")`.
    - 저장 중 다른 예외 → rollback 후 그대로 전파(UoW `__exit__`가 이미 처리).
  - `change_policy`: 지금과 같은 검증. effective_tick = current_tick + 1. 같은 effective_tick 대기 행이 있으면 `upsert_pending`(version = latest+1). docstring을 "다음 Tick부터 적용, 다음 진행 때 엔진 명령으로 반영"으로 고친다.
- 라우트: `POST /worlds/{world_id}/ticks` → `return use_case.advance_ticks(world_id, data)` 한 줄.
- `deps.py`: `get_simulation_engine() -> SimulationEnginePort` (adapter 싱글턴) 추가, `WorldService(uow, engine, settings.ENGINE_VERSION)`.

## 7. 테스트
- 단위(DB 없음): `tests/services/fakes.py`에 FakeSnapshotRepository, FakeSimulationPersistence, FakeEnginePort 추가. advance/create/change_policy 흐름 테스트.
- mapper 단위: 실제 `generate_world(42)` 결과로 ORM 객체 변환 검사(id 재매핑, payload 재매핑, Float 변환).
- architecture 테스트: `simulation_engine` import는 `app/simulation/engine_adapter.py`, `app/repositories/sqlalchemy/engine_mapper.py`만 허용. `app/services`, `app/usecases`, `app/simulation/interfaces.py`는 금지.
- 통합(`tests/integration/`, marker `integration`): 세션 fixture가 `lc_it_<pid>` DB를 만들고 `create_all`, 끝나면 drop. 연결 불가면 skip. AC3–AC11.
- 기존 76개 유지.
