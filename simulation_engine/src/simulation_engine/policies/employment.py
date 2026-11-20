"""고용 정책을 담는다."""

import uuid
from collections import defaultdict

from simulation_engine.entities import CompanyStatus, Employment

OPERATING = (CompanyStatus.ACTIVE.value, CompanyStatus.DISTRESSED.value)


def active_by_company(state) -> dict[uuid.UUID, list[Employment]]:
    """company_id -> ACTIVE 고용 목록(id 순)."""
    out: dict[uuid.UUID, list[Employment]] = defaultdict(list)
    for e in state.ordered("employments"):
        if e.status == "ACTIVE":
            out[e.company_id].append(e)
    return out


def last_month_surplus(acc: dict[str, int], company_id: uuid.UUID) -> int:
    """방금 마감한 회계월(월말 Tick, clear 전 누적값)의 잉여 = 매출(소비+B2B+조달) - 급여 - 지급 운영비.
    조달은 evaluate_status보다 먼저 실행되므로 조달 수입이 당월 상태 평가와 채용 판단에 반영된다."""
    g = lambda name: acc.get(f"{name}:{company_id}", 0)
    return g("revenue_consumer") + g("revenue_b2b") + g("revenue_procurement") + g("revenue_export") - g("payroll") - g("opex_paid")
