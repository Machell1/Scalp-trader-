"""Would the DerivScalperEA pass an FTMO-style prop challenge?

Day-block bootstrap from the real validated dated trade list (ea_trades_cost*.csv).
Each simulated day = a random historical trading day, its trades applied in entry
order at a fixed % risk of INITIAL balance. Models the EA's own 3% daily-loss halt
(stops trading that day at -3%, keeping it under the firm's -5%).

Firm rules (2-step): Phase1 +10% target, Phase2 +5%; fail at -10% total or -5% in a
single day. Time caps: 30d, 60d, unlimited(=365d). 10k sims/cell.

Caveats (make the numbers mildly OPTIMISTIC, stated honestly):
 - realized daily P&L only, no intraday floating drawdown (the firm's -5% is on equity).
 - the backtest allows up to 12 concurrent (1/symbol); live caps at 3 -> real daily
   swings are smaller than modeled. --maxtrades caps trades/day to approximate this.
"""
import argparse, csv
import numpy as np
import pandas as pd

HERE = r'C:/Users/Sanique Richards/Documents/Homework Heroes/Pokemon/Scalp-trader/backtest'

def load_days(path, maxtrades):
    rows = list(csv.reader(open(path)))[1:]
    t = np.array([int(r[0]) for r in rows])
    r = np.array([float(r[2]) for r in rows])
    day = t // 86400
    days = {}
    for d, rr in zip(day, r):
        days.setdefault(int(d), []).append(rr)
    daylist = list(days.values())
    if maxtrades > 0:
        daylist = [d[:maxtrades] for d in daylist]
    return daylist

def challenge(daylist, rng, risk, target, cap_days, ea_halt=3.0, firm_daily=5.0, firm_total=10.0):
    eq = 0.0
    for _ in range(cap_days):
        d = daylist[rng.integers(0, len(daylist))]
        day_pnl = 0.0
        for rr in d:
            pnl = rr * risk
            eq += pnl; day_pnl += pnl
            if day_pnl <= -firm_daily or eq <= -firm_total:
                return 0, _ + 1              # bust
            if eq >= target:
                return 1, _ + 1              # pass
            if day_pnl <= -ea_halt:
                break                        # EA halts for the day (protective)
    return -1, cap_days                      # timeout

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cost', default='0.03')
    ap.add_argument('--maxtrades', type=int, default=0)
    ap.add_argument('--nsim', type=int, default=10000)
    a = ap.parse_args()
    daylist = load_days(f'{HERE}/ea_trades_cost{a.cost}.csv', a.maxtrades)
    tpd = np.mean([len(d) for d in daylist])
    print(f'trading days={len(daylist)}, avg trades/day={tpd:.1f}, cost={a.cost}, maxtrades/day={a.maxtrades or "uncapped"}')
    rng = np.random.default_rng(42)
    print(f'{"risk":>5} {"cap":>6} | {"P1 pass":>8} {"P1 bust":>8} {"med days":>9} | {"P2 pass":>8} | {"BOTH":>6}')
    for risk in (0.25, 0.5, 1.0, 1.5, 2.0):
        for cap, capname in ((30, '30d'), (60, '60d'), (365, 'unlim')):
            res = np.array([challenge(daylist, rng, risk, 10.0, cap) for _ in range(a.nsim)])
            p1 = np.mean(res[:, 0] == 1); bust = np.mean(res[:, 0] == 0)
            passdays = res[res[:, 0] == 1, 1]
            med = int(np.median(passdays)) if len(passdays) else 0
            res2 = np.array([challenge(daylist, rng, risk, 5.0, cap) for _ in range(a.nsim // 2)])
            p2 = np.mean(res2[:, 0] == 1)
            print(f'{risk:>4}% {capname:>6} | {p1:>7.1%} {bust:>7.1%} {med:>7}d  | {p2:>7.1%} | {p1*p2:>5.1%}')

if __name__ == '__main__':
    main()
