"""월말 채용·해고.

채용: ACTIVE 기업, 지난달 잉여>0, 정원 여유 -> 월 1명. 월말 시작 시점의 실직자 풀(id 순)에서
rng("hire", tick, company_id)로 선택하며 풀에서 제거한다. 같은 달 해고·파산으로 풀린 시민은 이번 달 풀에 없다.
해고: DISTRESSED 기업은 월 1명, max(hired_tick, id)인 고용을 종료한다.
"""

from simulation_engine.entities import CompanyStatus, Employment
from simulation_engine.policies.employment import active_by_company, last_month_surplus


def run(ctx) -> None:
    state = ctx.state
    pool = [c.id for c in state.ordered("citizens") if c.employment_status == "UNEMPLOYED"]
    by_company = active_by_company(state)
    for co in state.ordered("companies"):
        if co.status == CompanyStatus.DISTRESSED.value:
            emps = by_company.get(co.id, [])
            if not emps:
                continue
            e = max(emps, key=lambda x: (x.hired_tick, x.id))
            e.status = "TERMINATED"
            e.terminated_tick = ctx.tick
            c = state.citizens[e.citizen_id]
            c.employment_status = "UNEMPLOYED"
            c.employer_id = None
            co.employee_count -= 1
            ctx.emit("citizen.employment.changed", {"citizen_id": str(c.id), "company_id": str(co.id),
                                                    "employment_status": "UNEMPLOYED", "reason": "fired"})
        elif (co.status == CompanyStatus.ACTIVE.value and pool and co.employee_count < co.employee_capacity
              and last_month_surplus(state.month_accumulators, co.id) > 0):
            cid = ctx.rng("hire", ctx.tick, co.id).choice(pool)
            pool.remove(cid)
            e = Employment(id=state.new_id("employment"), citizen_id=cid, company_id=co.id, salary=co.base_wage,
                           hired_tick=ctx.tick, status="ACTIVE")
            state.employments[e.id] = e
            c = state.citizens[cid]
            c.employment_status = "EMPLOYED"
            c.employer_id = co.id
            co.employee_count += 1
            ctx.emit("citizen.employment.changed", {"citizen_id": str(cid), "company_id": str(co.id),
                                                    "employment_status": "EMPLOYED", "reason": "hired"})
