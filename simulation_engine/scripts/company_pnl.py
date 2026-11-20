"""기업별 월 손익표 + 구조적 월 수지 분석 (금액 단위 만원).
사용: PYTHONPATH=src python scripts/company_pnl.py [seed ...]"""

import sys
import uuid
from collections import defaultdict

from simulation_engine.clock import TICKS_PER_MONTH
from simulation_engine.economy import AccountOwnerType as OT
from simulation_engine.economy import TransactionType as TT
from simulation_engine.engine import SimulationEngine
from simulation_engine.metrics.calculator import city_internal_money
from simulation_engine.world.config import SimulationConfig
from simulation_engine.world.generator import generate_world

INDS = ("RETAIL", "RESTAURANT", "WHOLESALE", "BUSINESS_SERVICE")
M = 10_000
COLS = ("cons", "b2b_in", "proc", "export", "salary", "ox_b2b", "ox_gov", "ox_ext")


def simulate(cfg: SimulationConfig, seed: int, months: int = 12, mutate=None):
    """returns (state, rows, series). rows[m][company_id] = dict(COLS..., net, cash, emp, status).
    series[m] = 월말 도시 지표 dict(treasury, internal, ext, avg_cash, shop_rate, employed, bankrupt, distressed)"""
    state = generate_world(seed, cfg).state
    if mutate:
        mutate(state)
    eng = SimulationEngine(state, cfg)
    rows, series = [], []
    for _ in range(months):
        purchases = tax = welfare = 0
        d = defaultdict(lambda: dict.fromkeys(COLS, 0))
        for _ in range(TICKS_PER_MONTH):
            r = eng.step()
            amt = {l.transaction_id: l.amount for l in r.ledger_entries if l.amount > 0}
            for t in r.transactions:
                a, md, tt = amt[t.id], t.metadata, t.transaction_type
                if tt == TT.PURCHASE:
                    purchases += 1
                    d[uuid.UUID(md["company_id"])]["cons"] += a
                elif tt == TT.INCOME_TAX:
                    tax += a
                elif tt == TT.WELFARE:
                    welfare += a
                elif tt == TT.EXPORT:
                    d[uuid.UUID(md["company_id"])]["export"] += a
                elif tt == TT.PUBLIC_PROCUREMENT:
                    d[uuid.UUID(md["company_id"])]["proc"] += a
                elif tt == TT.SALARY:
                    d[uuid.UUID(md["company_id"])]["salary"] += a
                elif tt == TT.OPERATING_EXPENSE:
                    cat = md["expense_category"]
                    key = {"b2b": "ox_b2b", "government": "ox_gov", "external": "ox_ext"}[cat]
                    d[uuid.UUID(md["company_id"])][key] += a
                    if cat == "b2b":
                        d[uuid.UUID(md["supplier_company_id"])]["b2b_in"] += a
        month = {}
        for co in state.ordered("companies"):
            x = dict(d[co.id]) if co.id in d else dict.fromkeys(COLS, 0)
            x["ox_gov"] = x.get("ox_gov", 0)
            x["net"] = x["cons"] + x["b2b_in"] + x["proc"] + x["export"] - x["salary"] - x["ox_b2b"] - x["ox_gov"] - x["ox_ext"]
            x["cash"] = state.account_of(OT.COMPANY, co.id).balance
            x["emp"] = co.employee_count
            x["status"] = co.status
            x["ind"] = co.industry
            x["name"] = co.name
            month[co.id] = x
        rows.append(month)
        cash = [a.balance for a in state.accounts.values() if a.owner_type == OT.CITIZEN]
        sts = [c.status for c in state.companies.values()]
        series.append(dict(
            treasury=state.account_of(OT.GOVERNMENT, None, "TREASURY").balance,
            internal=city_internal_money(state),
            ext=state.account_of(OT.SYSTEM, None, "CASH").balance,
            avg_cash=sum(cash) // len(cash),
            shop_rate=purchases / len(state.citizens) / 30,
            tax=tax, welfare=welfare,
            employed=sum(1 for c in state.citizens.values() if c.employment_status == "EMPLOYED"),
            bankrupt=sts.count("BANKRUPT"), distressed=sts.count("DISTRESSED"),
        ))
    return state, rows, series


def print_seed(seed: int, cfg: SimulationConfig) -> None:
    state, rows, _ = simulate(cfg, seed)
    ids = [c.id for c in state.ordered("companies")]
    print(f"\n=== seed {seed} 기업별 월 손익 (만원) ===")
    print("기업 | 월 | 상태 | 인원 | 소비 | B2B유입 | 조달 | 수출 | 급여 | 운영비B2B | 운영비정부 | 운영비외부 | 순흐름 | 월말현금")
    for cid in ids:
        for m, month in enumerate(rows, 1):
            x = month[cid]
            print(f"{x['name']:<20} | {m:2d} | {x['status'][:4]} | {x['emp']:2d} | {x['cons'] // M:5d} | {x['b2b_in'] // M:5d} | {x['proc'] // M:5d} | {x['export'] // M:5d} | "
                  f"{x['salary'] // M:5d} | {x['ox_b2b'] // M:4d} | {x['ox_gov'] // M:4d} | {x['ox_ext'] // M:4d} | {x['net'] // M:6d} | {x['cash'] // M:6d}")
    print(f"--- seed {seed} 업종별 소계 (월별 합: 매출소비/B2B/조달 급여 운영비 순흐름 기말현금) ---")
    for ind in INDS:
        for m, month in enumerate(rows, 1):
            xs = [x for x in month.values() if x["ind"] == ind]
            s = lambda k: sum(x[k] for x in xs) // M
            ox = s("ox_b2b") + s("ox_gov") + s("ox_ext")
            print(f"{ind:<16} | {m:2d} | 소비{s('cons'):5d} B2B{s('b2b_in'):5d} 조달{s('proc'):5d} 수출{s('export'):5d} | 급여{s('salary'):5d} 운영비{ox:5d} | 순{s('net'):6d} | 현금{s('cash'):6d} | 인원{sum(x['emp'] for x in xs):3d}")


def structural(seeds, cfg) -> None:
    """파산 전 정상 월(1~3개월) 평균 구조적 수지."""
    print("\n=== 구조적 월 수지: 1~3개월 평균 (시드 평균, 업종 합계, 만원) ===")
    acc = defaultdict(lambda: defaultdict(float))
    for seed in seeds:
        _, rows, _ = simulate(cfg, seed, 3)
        for month in rows:
            for x in month.values():
                for k in (*COLS, "net"):
                    acc[x["ind"]][k] += x[k] / (3 * len(seeds))
    print("업종 | 소비 | B2B유입 | 조달 | 매출계 | 급여 | 운영비(전체) | 수지")
    for ind in INDS:
        a = acc[ind]
        rev = a["cons"] + a["b2b_in"] + a["proc"] + a["export"]
        ox = a["ox_b2b"] + a["ox_gov"] + a["ox_ext"]
        print(f"{ind:<16} | {a['cons'] / M:7.0f} | {a['b2b_in'] / M:7.0f} | {a['proc'] / M:7.0f} | {rev / M:7.0f} | {a['salary'] / M:6.0f} | {ox / M:6.0f} | {a['net'] / M:7.0f}")
    b2b_in = acc["WHOLESALE"]["b2b_in"] + acc["BUSINESS_SERVICE"]["b2b_in"]
    wages = acc["WHOLESALE"]["salary"] + acc["BUSINESS_SERVICE"]["salary"]
    proc = acc["WHOLESALE"]["proc"] + acc["BUSINESS_SERVICE"]["proc"]
    print(f"B2B 4개사: 급여 {wages / M:.0f} + 운영비 {cfg.operating_cost * 4 / M:.0f} = 유출 {(wages + cfg.operating_cost * 4) / M:.0f} / "
          f"유입 B2B {b2b_in / M:.0f} + 조달 {proc / M:.0f} = {(b2b_in + proc) / M:.0f}")
    print("B2B 유입 총량 = 전 기업 운영비의 70% = 10사 x 500 x 0.7 =", 10 * cfg.operating_cost * 7000 // 10_000 // M)


if __name__ == "__main__":
    seeds = [int(a) for a in sys.argv[1:]] or [42, 1, 7]
    cfg = SimulationConfig()
    for s in seeds:
        print_seed(s, cfg)
    structural(seeds, cfg)
