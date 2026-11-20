"""시민 일과: 08시 출근, 18시 귀가, 19시 쇼핑 출발."""

from simulation_engine.clock import hour_of
from simulation_engine.systems.movement import OPERATING, start_move, try_shop


def run(ctx) -> None:
    state, cfg = ctx.state, ctx.config
    hour = hour_of(ctx.tick)
    if hour not in (cfg.work_start_hour, cfg.work_end_hour, cfg.shop_hour):
        return
    for c in state.ordered("citizens"):
        act = c.current_activity
        if act == "MOVING":
            continue
        if hour == cfg.work_start_hour:
            employer = state.companies.get(c.employer_id) if c.employer_id else None
            if act == "AT_HOME" and employer and employer.status in OPERATING and employer.building_id:
                start_move(ctx, c, employer.building_id, "commute")
        elif hour == cfg.work_end_hour:
            if act != "AT_HOME":
                start_move(ctx, c, c.home_building_id, "home")
        elif act == "AT_HOME":
            try_shop(ctx, c)
