"""AC19 성능 측정. 사용: PYTHONPATH=src python scripts/perf.py [citizens:ticks ...]  (기본 100:720 1000:720 10000:48)"""

import dataclasses
import resource
import math
import statistics
import sys
import time

from simulation_engine.clock import TICKS_PER_MONTH, is_month_end
from simulation_engine.engine import SimulationEngine
from simulation_engine.world.config import IndustryConfig, SimulationConfig
from simulation_engine.world.generator import generate_world


def scaled(n: int) -> SimulationConfig:
    base, k = SimulationConfig(), n / 100
    return dataclasses.replace(
        base,
        citizen_count=n,
        residential_buildings=math.ceil(n / base.residential_capacity),
        commercial_buildings=round(base.commercial_buildings * k),
        office_buildings=round(base.office_buildings * k),
        map_size=math.ceil(base.map_size * math.sqrt(k)),  # 건물 밀도 유지
        industries=tuple(dataclasses.replace(i, count=round(i.count * k)) for i in base.industries),
        initial_employed=round(base.initial_employed * k),
        government_opening_balance=round(base.government_opening_balance * k),
    )


def measure(n: int, ticks: int) -> None:
    cfg = scaled(n)
    t0 = time.perf_counter()
    state = generate_world(42, cfg).state
    gen = time.perf_counter() - t0
    eng = SimulationEngine(state, cfg)
    normal, month_end = [], []
    for _ in range(ticks):
        end = is_month_end(state.tick)
        t0 = time.perf_counter()
        eng.step()
        (month_end if end else normal).append((time.perf_counter() - t0) * 1000)
    # ru_maxrss: macOS는 bytes, Linux는 KB. 프로세스 단위 peak이므로 규모를 올리는 순서(오름차순)로 측정해야 의미가 있다.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1e6 if sys.platform == 'darwin' else 1e3)
    p95 = statistics.quantiles(normal, n=20)[-1] if len(normal) >= 20 else max(normal)
    me = f"{statistics.mean(month_end):.1f}" if month_end else "-"
    print(f"{n:>6} | {ticks:>5} | {gen:7.2f} | {statistics.mean(normal):8.2f} | {p95:8.2f} | {me:>9} | {peak:8.1f}")


if __name__ == "__main__":
    plan = [tuple(map(int, a.split(":"))) for a in sys.argv[1:]] or [(100, 720), (1000, 720), (10000, 48)]
    print("시민수 | ticks | 생성(s) | 평균ms/tick | p95 ms | 월말tick ms | 피크RSS MB(누적 peak)")
    for n, t in plan:
        measure(n, t)
