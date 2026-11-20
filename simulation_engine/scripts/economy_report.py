"""월별 도시 경제 리포트 (금액 단위: 만원).
사용: PYTHONPATH=src:scripts python scripts/economy_report.py [개월수] [seed ...] [P0|P1|C1..] (기본 12개월, 시드 42 1 7, P0)"""

import sys

from calibrate import PRESETS
from company_pnl import INDS, M, simulate
from simulation_engine.world.config import SimulationConfig


def report(cfg: SimulationConfig, seed: int, months: int) -> None:
    state, rows, series = simulate(cfg, seed, months)
    print(f"\n=== seed {seed}, {months}개월 (만원) ===")
    print("월 | RET/RST/WHL/BSV 파산·위험(B/D) | 취업 | 소비 | B2B | 조달 | 수출 | 세금 | 복지 | 국고 | 도시내부 | 외부잔액 | 시민평균현금 | 일소비율")
    for m, (month, s) in enumerate(zip(rows, series), 1):
        sub = {i: [x for x in month.values() if x["ind"] == i] for i in INDS}
        t = lambda k: sum(x[k] for x in month.values()) // M
        cells = "/".join(f"{sum(x['status'] == 'BANKRUPT' for x in sub[i])}·{sum(x['status'] == 'DISTRESSED' for x in sub[i])}" for i in INDS)
        print(f"{m:2d} | {cells} | {s['employed']} | {t('cons')} | {t('b2b_in')} | {t('proc')} | {t('export')} | {s['tax'] // M} | {s['welfare'] // M}"
              f" | {s['treasury'] // M} | {s['internal'] // M} | {s['ext'] // M} | {s['avg_cash'] // M} | {s['shop_rate']:.2f}")


if __name__ == "__main__":
    preset = next((a for a in sys.argv[1:] if not a.isdigit()), "P0")
    cfg = next(c for n, c in PRESETS.items() if n.startswith(preset + " "))
    args = [int(a) for a in sys.argv[1:] if a.isdigit()]
    months, seeds = (args[0], args[1:] or [42, 1, 7]) if args else (12, [42, 1, 7])
    for seed in seeds:
        report(cfg, seed, months)
