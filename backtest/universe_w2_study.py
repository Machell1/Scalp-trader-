"""Universe expansion under the live W2 candle filter — per-candidate gates.

Pre-registered: docs/UNIVERSE_W2_SPEC_2026-07-10.md
  (SHA256 488ecb0e2dbf4f0a21c9988c42aaf1f5a2e3d948c59c21fc871907e16110fb4d)
Candidates: GER40.cash, JP225.cash, US500.cash, XAUUSD (XAUAUD/XAUEUR ride only
if XAUUSD passes). Crypto excluded by commission arithmetic (see spec).
Gate 1 Deriv 2.5y W2-OOS>0 (+2x cost) | Gate 2 FTMO ~9mo W2>0 at true cost |
Gate 3 portfolio: MC both-phases (no time limit) must IMPROVE vs the live pair.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr, Params, simulate_symbol
from walkforward_dsr import real_cost_per_side
from prop_mc_scalper import challenge

RNG = np.random.default_rng(20260713)
W2 = 0.30
GOLD_DERIV_COST = 0.03   # diverse CSV has no spread column; conservative flat (pre-registered)

CANDS = [
    # name, deriv_csv, ftmo_symbol, metal(commission)?
    ("GER40", "derivM15_spreadgated/Germany_40.csv", "GER40.cash", False),
    ("JP225", "derivM15_spreadgated/Japan_225.csv", "JP225.cash", False),
    ("US500", "derivM15_spreadgated/US_SP_500.csv", "US500.cash", False),
    ("XAUUSD", "derivM15_diverse/XAUUSD.csv", "XAUUSD", True),
]

PARAMS = dict(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
              entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
              stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
              max_hold_bars=8)


def norm(df):
    ncols = {c.lower(): c for c in df.columns}
    return df.rename(columns={ncols[k]: k for k in ("time", "open", "high", "low", "close") if k in ncols})


def w2_trades(df, cost):
    """Engine trades surviving the live W2 filter: (epoch, signal_bar, r)."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    body_top = np.maximum(o, c); body_bot = np.minimum(o, c)
    up, dn = h - body_top, body_bot - l
    p = Params(**PARAMS, cost_atr_frac=cost)
    sigs = []
    simulate_symbol(df, p, 0, len(df), signals_out=sigs)
    dt = pd.to_datetime(df["time"])
    epoch = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()
    out = []
    for (i, eb, side, r) in sigs:
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        adv = (up[i] if side > 0 else dn[i]) / atr[i]
        if adv >= W2:
            out.append((int(epoch[i]), i, float(r)))
    return out


def stitched_oos(df, trades):
    dt = pd.to_datetime(df["time"])
    q = pd.PeriodIndex(dt, freq="Q")
    quarters = sorted(q.unique())
    oos_qs = set(quarters[int(len(quarters) * 0.7):])
    rs = [r for (t, i, r) in trades if q[i] in oos_qs]
    return np.array(rs, float)


def mc_both(day_trades, nsim=4000):
    """No-time-limit both-phases probability from a (epoch, r) list."""
    days = {}
    for (t, r) in day_trades:
        days.setdefault(t // 86400, []).append(r)
    daylist = list(days.values())
    rng = np.random.default_rng(7)
    r1 = np.array([challenge(daylist, rng, 0.5, 10.0, 365) for _ in range(nsim)])
    p1 = float(np.mean(r1[:, 0] == 1))
    r2 = np.array([challenge(daylist, rng, 0.5, 5.0, 365) for _ in range(nsim // 2)])
    p2 = float(np.mean(r2[:, 0] == 1))
    return p1 * p2, p1, p2


def ftmo_pull(sym, metal):
    import MetaTrader5 as mt5
    assert mt5.initialize(path=r"C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe")
    mt5.symbol_select(sym, True)
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 20000)
    info = mt5.symbol_info(sym)
    mt5.shutdown()
    if r is None or len(r) < 3000 or info is None:
        return None, None
    df = pd.DataFrame({"time": r["time"], "open": r["open"], "high": r["high"],
                       "low": r["low"], "close": r["close"]})
    sp = r["spread"].astype(float) * info.point
    atr = wilder_atr(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(), 14)
    med_atr = float(np.nanmedian(atr))
    m = sp > 0
    cost = 0.5 * float(np.median(sp[m])) / med_atr if m.sum() > 100 else float("nan")
    if metal and info.trade_tick_value > 0 and info.trade_tick_size > 0:
        usd_per_unit = info.trade_tick_value / info.trade_tick_size
        cost += (2.5 / usd_per_unit) / med_atr        # $5/lot round turn -> per side
    return df, cost


def main():
    # live pair W2 tape (Deriv frame) = the MC baseline
    pair = []
    for f in ("Wall_Street_30.csv", "US_Tech_100.csv"):
        df = norm(pd.read_csv(os.path.join(HERE, "data", "derivM15_spreadgated", f)))
        cost = real_cost_per_side(pd.read_csv(os.path.join(HERE, "data", "derivM15_spreadgated", f)))
        pair += [(t, r) for (t, i, r) in w2_trades(df, cost)]
    base_both, bp1, bp2 = mc_both(pair)
    print(f"BASELINE pair (W2): {len(pair)} trades | MC both-phases (unlim) = {base_both:.1%} (P1 {bp1:.1%}, P2 {bp2:.1%})\n")

    for name, deriv_csv, ftmo_sym, metal in CANDS:
        raw = pd.read_csv(os.path.join(HERE, "data", deriv_csv))
        df = norm(raw)
        cost = real_cost_per_side(raw)
        if not np.isfinite(cost):
            cost = GOLD_DERIV_COST
        tr = w2_trades(df, cost)
        oos = stitched_oos(df, tr)
        tr2 = w2_trades(df, cost * 2)
        oos2 = stitched_oos(df, tr2)
        g1 = len(oos) >= 60 and oos.mean() > 0 and len(oos2) > 0 and oos2.mean() > 0
        print(f"{name}: G1 Deriv W2-OOS n={len(oos)} exp={oos.mean() if len(oos) else float('nan'):+.4f} "
              f"| 2x cost {oos2.mean() if len(oos2) else float('nan'):+.4f} -> {'pass' if g1 else 'FAIL'}")

        fdf, fcost = ftmo_pull(ftmo_sym, metal)
        if fdf is None:
            print(f"   G2 FTMO: no data -> FAIL\n"); continue
        ftr = w2_trades(fdf, fcost)
        frs = np.array([r for (t, i, r) in ftr], float)
        g2 = len(frs) >= 30 and frs.mean() > 0
        print(f"   G2 FTMO ({ftmo_sym}, cost {fcost:.4f}/side): n={len(frs)} exp={frs.mean() if len(frs) else float('nan'):+.4f} -> {'pass' if g2 else 'FAIL'}")

        if not (g1 and g2):
            print(f"   VERDICT {name}: NOT added\n"); continue

        aug = pair + [(t, r) for (t, i, r) in tr]
        both, p1, p2 = mc_both(aug)
        g3 = both > base_both
        print(f"   G3 portfolio MC: pair+{name} both-phases {both:.1%} vs {base_both:.1%} baseline -> {'pass' if g3 else 'FAIL'}")
        print(f"   VERDICT {name}: {'ADD (all gates)' if g3 else 'NOT added (portfolio drag)'}\n")


if __name__ == "__main__":
    main()
