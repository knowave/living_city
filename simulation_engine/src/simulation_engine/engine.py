"""시뮬레이션 엔진: Tick 실행 순서와 불변식 검사."""

from collections import defaultdict
from dataclasses import dataclass, field

from simulation_engine import clock
from simulation_engine.context import TickContext
from simulation_engine.economy import AccountOwnerType, AccountType, LedgerEntry, Transaction
from simulation_engine.entities import WorldPolicy
from simulation_engine.events import generator as ev
from simulation_engine.events.models import WorldEvent
from simulation_engine.metrics import calculator
from simulation_engine.metrics.models import WorldMetric
from simulation_engine.systems import behavior, business, consumption, employment, external, government, movement, payroll
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.state import WorldState


class InvariantViolation(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PolicyChangeCommand:
    income_tax_rate: int  # bps
    welfare_amount: int
    effective_tick: int


@dataclass(slots=True)
class TickResult:
    tick: int
    events: list[WorldEvent] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)
    ledger_entries: list[LedgerEntry] = field(default_factory=list)
    metrics: list[WorldMetric] = field(default_factory=list)


class SimulationEngine:
    def __init__(self, state: WorldState, config: SimulationConfig) -> None:
        self.state = state
        self.config = config

    def step(self, commands: tuple[PolicyChangeCommand, ...] | list[PolicyChangeCommand] = ()) -> TickResult:
        state = self.state
        ctx = TickContext(state=state, config=self.config, tick=state.tick)
        self._validate_commands(state, commands)
        for command in commands:
            self._apply_command(ctx, command)

        consumption.depart(ctx)
        movement.run(ctx)
        consumption.run(ctx)
        behavior.run(ctx)

        if clock.is_month_end(ctx.tick):
            payroll.run(ctx)
            business.pay_operating_expenses(ctx)
            government.pay_welfare(ctx)
            government.procure(ctx)
            external.pay_exports(ctx)
            business.evaluate_status(ctx)
            employment.run(ctx)
            consumption.set_monthly_budgets(ctx)  # 급여·복지 직후 현금 기준
            ctx.emit(ev.ECONOMY_MONTH_CLOSED, {"month": clock.month_of(ctx.tick)})
            ctx.metrics.extend(calculator.compute_monthly(ctx))
            ctx.emit(ev.METRICS_UPDATED, {"period": "MONTHLY", "count": len(ctx.metrics)})
            state.month_accumulators.clear()

        self._check_invariants(ctx)
        ctx.emit(ev.SIMULATION_TICK, {"tick": ctx.tick})
        state.world.current_tick += 1
        return TickResult(ctx.tick, ctx.events, ctx.transactions, ctx.ledger_entries, ctx.metrics)

    def run(
        self, n: int, commands_by_tick: dict[int, list[PolicyChangeCommand]] | None = None
    ) -> list[TickResult]:
        """n Tick 진행. commands_by_tick[t]는 tick t 시작에 적용된다."""
        by_tick = commands_by_tick or {}
        return [self.step(by_tick.get(self.state.tick, ())) for _ in range(n)]

    @staticmethod
    def _validate_commands(state: WorldState, commands) -> None:
        """하나라도 잘못되면 아무것도 적용하지 않도록 먼저 전부 검증한다 (backend 제약과 동일)."""
        taken = {p.effective_tick for p in state.policies.values()}
        for c in commands:
            if c.effective_tick < state.tick:
                raise ValueError(f"effective_tick {c.effective_tick}는 현재 tick {state.tick}보다 과거일 수 없음")
            if not 0 <= c.income_tax_rate <= 10000:
                raise ValueError(f"income_tax_rate는 0..10000 bps여야 함: {c.income_tax_rate}")
            if c.welfare_amount < 0:
                raise ValueError(f"welfare_amount는 0 이상이어야 함: {c.welfare_amount}")
            if c.effective_tick in taken:
                raise ValueError(f"effective_tick {c.effective_tick}의 정책이 이미 있음")
            taken.add(c.effective_tick)

    def _apply_command(self, ctx: TickContext, command: PolicyChangeCommand) -> None:
        state = ctx.state
        version = max((p.version for p in state.policies.values()), default=0) + 1
        policy = WorldPolicy(
            id=state.new_id("policy"),
            income_tax_rate=command.income_tax_rate,
            welfare_amount=command.welfare_amount,
            effective_tick=command.effective_tick,
            version=version,
        )
        state.policies[policy.id] = policy
        ctx.emit(
            ev.POLICY_UPDATED,
            {
                "policy_id": str(policy.id),
                "version": version,
                "income_tax_rate": policy.income_tax_rate,
                "welfare_amount": policy.welfare_amount,
                "effective_tick": policy.effective_tick,
            },
        )

    def _check_invariants(self, ctx: TickContext) -> None:
        state = ctx.state
        if state.total_balance() != 0:
            raise InvariantViolation(f"전체 잔액 합계가 0이 아님: {state.total_balance()}")
        for acc in state.accounts.values():
            issuance = acc.owner_type == AccountOwnerType.SYSTEM and acc.account_type == AccountType.ISSUANCE
            if acc.balance < 0 and not issuance:
                raise InvariantViolation(f"음수 잔액: {acc.id} {acc.balance}")
        sums: dict = defaultdict(int)
        for entry in ctx.ledger_entries:
            sums[entry.transaction_id] += entry.amount
        for tx_id, total in sums.items():
            if total != 0:
                raise InvariantViolation(f"거래 원장 합계가 0이 아님: {tx_id} {total}")
