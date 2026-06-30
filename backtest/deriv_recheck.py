"""Re-test the UPDATED DerivScalperEA on REAL Deriv MT5 M15 data only.

Uses the user's own faithful harness (scalper_backtest.simulate_symbol), exactly as
shipped, against the 5 real Deriv M15 index series. No Yahoo, no synthetic data.

Cost is a pure end-of-trade subtraction in the harness (net = gross - 2*cost), and
cost-in-R is a per-config constant (= 2*cost_frac/stop_atr) because risk = stop_atr*ATR.
So we simulate ONCE per (config, split) at cost 0 and apply the cost sweep analytically
-- exact, and avoids re-simulating.
"""
from __future__ import annotations
import numpy as np
from scalper_backtest import Params, load_dataset, simulate_symbol, compute_stats

DATA_TF = "derivM15"

CONFIGS = {
    "OLD  cont stop1.0/tp1.5 (pre-change)":        dict(direction="cont", stop_atr=1.0, tp_atr=1.5),
    "NEW  cont stop1.0/tp3.0 (no AVWAP)":          dict(direction="cont", stop_atr=1.0, tp_atr=3.0),
    "SHIPPED cont stop1.0/tp3.0 +AVWAP cal8":      dict(direction="cont", stop_atr=1.0, tp_atr=3.0, vwap_window=1, vwap_min_bars=8),
    "ROBUST cont stop2.0/tp3.0":                   dict(direction="cont", stop_atr=2.0, tp_atr=3.0),
    "ROBUST cont stop2.0/tp3.0 +AVWAP cal8":       dict(direction="cont", stop_atr=2.0, tp_atr=3.0, vwap_window=1, vwap_min_bars=8),
    "FADE stop1.0/tp3.0 +AVWAP (buy dip/sell rip)":dict(direction="fade", stop_atr=1.0, tp_atr=3.0, vwap_window=1, vwap_min_bars=8),
}
COSTS = [0.00, 0.02, 0.03, 0.05]
SPLITS = [("IS  (first70%)", "is"), ("OOS (last30%)", "oos"), ("ALL", "all")]

def split_bounds(n, split):
    if split == "is":  return 0, int(n*0.7)
    if split == "oos": return int(n*0.7), n
    return 0, n

def sim_gross(data, base):
    """Return {sym: np.array(gross R at cost0)} and stop_atr."""
    p = Params(entry_style="stop", cost_atr_frac=0.0, **base)
    return p

def pooled_stats(rs):
    return compute_stats(list(rs))

def main():
    data = load_dataset(DATA_TF)
    print(f"REAL DERIV M15 — {len(data)} symbols: {', '.join(data)}\n")
    for name, base in CONFIGS.items():
        stop_atr = base.get("stop_atr", 1.0)
        print(f"################ {name} ################")
        for slabel, split in SPLITS:
            # one sim per symbol at cost 0
            p = Params(entry_style="stop", cost_atr_frac=0.0, **base)
            per_sym = {}
            for sym, df in data.items():
                lo, hi = split_bounds(len(df), split)
                per_sym[sym] = np.asarray(simulate_symbol(df, p, lo, hi), float)
            pooled0 = np.concatenate([a for a in per_sym.values() if a.size]) if any(a.size for a in per_sym.values()) else np.array([])
            line = []
            for cost in COSTS:
                shift = 2*cost/stop_atr            # cost in R, constant per config
                pr = pooled0 - shift
                s = compute_stats(list(pr))
                pos = sum(1 for a in per_sym.values() if a.size>=20 and (a-shift).mean()>0)
                tot = sum(1 for a in per_sym.values() if a.size>=20)
                line.append(f"c{cost:.2f}: exp{s.expectancy:+.3f}R t{s.tstat:+.1f} PF{s.profit_factor:.2f} +{pos}/{tot}")
            n = pooled0.size; wr = (pooled0>0).mean()*100 if n else 0
            print(f"  {slabel:16s} N={n:5d} win{wr:5.1f}%  " + "   ".join(line))
        print()

if __name__ == "__main__":
    main()
