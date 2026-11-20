"""보정 후보 비교 (config 복사본만, 소스 무수정). 시드 42·1·7 x 36개월.
사용: PYTHONPATH=src:scripts python scripts/calibrate.py presets|grid"""

import dataclasses as dc
import itertools
import sys
from multiprocessing import Pool

from company_pnl import simulate
from simulation_engine.world.config import (BUSINESS_SERVICE, RESTAURANT, RETAIL, WHOLESALE, SimulationConfig)

SEEDS = (42, 1, 7)
MONTHS = 36
M = 10_000
BASE = SimulationConfig()


def caps(cfg, wh, bs, rr, init=90, wages=None) -> SimulationConfig:
    c = {WHOLESALE: wh, BUSINESS_SERVICE: bs, RETAIL: rr, RESTAURANT: rr}
    new = tuple(dc.replace(i, employee_capacity=c[i.industry], base_wage=(wages or {}).get(i.industry, i.base_wage)) for i in cfg.industries)
    return dc.replace(cfg, industries=new, initial_employed=init)


def j1(**kw) -> SimulationConfig:
    return dc.replace(caps(BASE, 6, 2, 12, init=88), **kw)


def evaluate(args):
    name, cfg, seed, months = args
    state, rows, series = simulate(cfg, seed, months)
    first_bad, mult = None, 99.0
    for m, month in enumerate(rows, 1):
        for co in state.ordered("companies"):
            x = month[co.id]
            if x["status"] != "ACTIVE" and first_bad is None:
                first_bad = m
            if x["status"] in ("ACTIVE", "DISTRESSED"):
                mult = min(mult, x["cash"] / (x["emp"] * co.base_wage + co.operating_cost))
    s = lambda m, k: series[m - 1][k]
    return dict(name=name, seed=seed, bank={m: s(m, "bankrupt") for m in (12, 24, 36)}, first_bad=first_bad, mult=mult,
                emp={m: s(m, "employed") for m in (12, 24, 36)}, treasury={m: s(m, "treasury") // M for m in (1, 6, 12, 24, 36)},
                internal={m: s(m, "internal") // M for m in (1, 12, 24, 36)}, cash={m: s(m, "avg_cash") // M for m in (1, 12, 24, 36)},
                bank_end=series[-1]["bankrupt"], shop=sum(x["shop_rate"] for x in series[-12:]) / 12, dist36=s(36, "distressed"))


PRESETS = {
    # P0 = 현재 config 기본값(2026-11-19 보정안 C1 적용 후). 아래 C1과 같은 값이다.
    "P0 현재 기본값(C1 적용)": BASE,
    # 구 기본값(보정 전): 정원 10 / 9명 배치 / cash_reserve 4M / extra 2000
    "P00 구 기본값(정원 10, 9명 배치, 4M/2000)": caps(dc.replace(BASE, cash_reserve=4_000_000, extra_spend_bps=2000), 10, 10, 10, init=90),
    "P1 J1 정원+구 소비값(4M/2000)": j1(cash_reserve=4_000_000, extra_spend_bps=2000),
    "C1 J1 + cash_reserve=1000000 extra_spend_bps=3000": j1(cash_reserve=1_000_000, extra_spend_bps=3000),
    "C2 J1 + cash_reserve=2000000 extra_spend_bps=4000": j1(cash_reserve=2_000_000, extra_spend_bps=4000),
    "C3 J1 + cash_reserve=2000000 extra_spend_bps=5000": j1(cash_reserve=2_000_000, extra_spend_bps=5000),
    "C4 J1 + cash_reserve=2500000 extra_spend_bps=6000": j1(cash_reserve=2_500_000, extra_spend_bps=6000),
}


def run(cands, seeds=SEEDS, months=MONTHS):
    with Pool() as p:
        res = p.map(evaluate, [(n, c, s, months) for n, c in cands.items() for s in seeds])
    return res


def show(res, full=True):
    for r in res:
        f = lambda d: "/".join(str(v) for v in d.values())
        print(f"{r['name']} | s{r['seed']} | 파산12/24/36 {f(r['bank'])} | 첫이상 {r['first_bad']} | 배수 {r['mult']:.2f} | 취업12/24/36 {f(r['emp'])} | "
              f"국고1/6/12/24/36 {f(r['treasury'])} | 내부자금1/12/24/36 {f(r['internal'])} | 시민현금1/12/24/36 {f(r['cash'])} | 소비율 {r['shop']:.2f} | 36월DIST {r['dist36']}")


GRID_AXES = dict(
    caps=[(6, 2, 12)],
    reserve=[4_000_000, 3_000_000, 2_500_000, 2_000_000, 1_000_000],
    extra=[2000, 3000, 4000, 5000, 6000],
    export=[5000],
)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "presets"
    if mode == "robust":  # 다른 시드 12개 x 60개월: 파산 수와 최저 배수
        res = run({n: c for n, c in PRESETS.items() if n[:2] in ("C1", "C2", "C3", "C4")}, range(2, 14), 60)
        for n in sorted({r["name"] for r in res}):
            rs = [r for r in res if r["name"] == n]
            print(f"{n} | 36개월 파산 {[r['bank'][36] for r in rs]} | 60개월 파산 {[r['bank_end'] for r in rs]} | 최저배수 {min(r['mult'] for r in rs):.2f} | 시드 중 이상 발생 {sum(r['first_bad'] is not None for r in rs)}/12")
    elif mode == "presets":
        show(run(PRESETS))
    else:
        cands = {}
        for (wh, bs, rr), rv, ex, xp in itertools.product(*GRID_AXES.values()):
            cands[f"G caps{wh}/{bs}/{rr} res{rv // 10000}만 ex{ex} xp{xp}"] = caps(
                dc.replace(BASE, cash_reserve=rv, extra_spend_bps=ex, export_bps=xp), wh, bs, rr, init=min(90, wh * 2 + bs * 2 + rr * 6))
        res = run(cands)
        by = {}
        for r in res:
            by.setdefault(r["name"], []).append(r)
        print("후보 | 파산36(3시드 합) | 최대파산36 | 36월DIST합 | 최저배수 | 취업36 평균 | 국고36 평균 | 내부자금36 평균 | 시민현금36 평균")
        for n, rs in by.items():
            print(f"{n} | {sum(r['bank'][36] for r in rs)} | {max(r['bank'][36] for r in rs)} | {sum(r['dist36'] for r in rs)} | {min(r['mult'] for r in rs):.2f} | "
                  f"{sum(r['emp'][36] for r in rs) / 3:.0f} | {sum(r['treasury'][36] for r in rs) // 3} | {sum(r['internal'][36] for r in rs) // 3} | {sum(r['cash'][36] for r in rs) // 3}")
