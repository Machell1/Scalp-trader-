"""High-water breakeven lock study — the resident's own input, gated like everyone else's.

Pre-registered: docs/HIGHWATER_SPEC_2026-07-11.md
  (SHA256 36593569647d5a0b0b597a5a6398eedbbf978202ebd3c2ffd03b3bc5ea982dc2)
Cells: BE-lock armed at T in {1.0,1.5,2.0,2.5} R (engine-native lock_trigger_atr,
trail off). Trades pair 1:1 with baseline by signal bar (identical entries).
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

TRIO = [("Wall_Street_30", "Wall_Street_30.csv"), ("US_Tech_100", "US_Tech_100.csv"),
        ("Japan_225", "Japan_225.csv")]
BASE = dict(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
            entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
            stop_atr=1.0, tp_atr=3.0, max_hold_bars=8)
CELLS = [1.0, 1.5, 2.0, 2.5]


def tape(lock_trigger):
    """Per-trade records keyed by (sym, signal bar). lock_trigger=None -> baseline."""
    rows = []
    for sym, fn in TRIO:
        raw = pd.read_csv(os.path.join(HERE, "data", "derivM15_spreadgated", fn))
        n = {c.lower(): c for c in raw.columns}
        df = raw.rename(columns={n[k]: k for k in ("time", "open", "high", "low", "close") if k in n})
        cost = real_cost_per_side(raw)
        o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        atr = wilder_atr(h, l, c, 14)
        up = h - np.maximum(o, c); dn = np.minimum(o, c) - l
        p = Params(**BASE, cost_atr_frac=cost,
                   lock_trigger_atr=(lock_trigger if lock_trigger else 999.0),
                   trail_atr=999.0 if lock_trigger else 0.0)
        sigs = []
        simulate_symbol(df, p, 0, len(df), signals_out=sigs)
        dt = pd.to_datetime(df["time"])
        ep = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()
        q = pd.PeriodIndex(dt, freq="Q")
        qs = sorted(q.unique()); oos_qs = set(qs[int(len(qs) * 0.7):])
        for (i, eb, side, r) in sigs:
            if not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            if ((up[i] if side > 0 else dn[i]) / atr[i]) < 0.30:
                continue
            rows.append((sym, i, int(ep[i]), float(r), str(q[i]), q[i] in oos_qs))
    return pd.DataFrame(rows, columns=["sym", "i", "ep", "r", "quarter", "oos"])


def mc_both(t, nsim=8000):
    days = {}
    for ep, r in zip(t.ep, t.r):
        days.setdefault(ep // 86400, []).append(r)
    dl = list(days.values())
    rng = np.random.default_rng(7)
    r1 = np.array([challenge(dl, rng, 0.3, 10.0, 365) for _ in range(nsim)])
    p1 = float(np.mean(r1[:, 0] == 1)); bust = float(np.mean(r1[:, 0] == 0))
    r2 = np.array([challenge(dl, rng, 0.3, 5.0, 365)[0] for _ in range(nsim // 2)])
    return p1 * float(np.mean(r2 == 1)), bust


def stats(t, label):
    full_stop = float((t.r <= -0.9).mean())
    win = float((t.r > 0).mean())
    tp = float((t.r >= 2.5).mean())
    scratch = float(((t.r > -0.2) & (t.r <= 0.2)).mean())
    return f"{label}: exp={t.r.mean():+.4f} win={win:.1%} TP={tp:.1%} fullStop={full_stop:.1%} scratch={scratch:.1%}"


def main():
    base = tape(None)
    print(f"baseline: {len(base)} trades | {stats(base, 'ALL')}")
    b_both, b_bust = mc_both(base)
    print(f"baseline MC: both={b_both:.1%} bust={b_bust:.1%}\n")
    boos = base[base.oos].set_index(["sym", "i"])

    for T in CELLS:
        cell = tape(T)
        coos = cell[cell.oos].set_index(["sym", "i"])
        j = boos.join(coos, rsuffix="_c", how="inner")
        d = j.r_c - j.r
        se = d.std(ddof=1) / np.sqrt(len(d))
        lo95 = d.mean() - 1.96 * se
        g1 = (d.mean() >= -0.005) and (lo95 > -0.02)
        both, bust = mc_both(cell)
        g2 = both >= b_both and bust <= b_bust
        fs_base = float((j.r <= -0.9).mean()); fs_cell = float((j.r_c <= -0.9).mean())
        g3 = (fs_base - fs_cell) >= 0.02
        qtab = j.assign(dd=d).groupby(j.index.get_level_values(0).map(lambda s: s) if False else j["quarter"]).dd.mean() if "quarter" in j else None
        qtab = j.assign(dd=d.values).groupby("quarter").dd.mean()
        g4a = (qtab >= 0).mean() >= 0.6 if len(qtab) else False
        sym_del = j.assign(dd=d.values).groupby(level=0).dd.mean()
        g4b = (sym_del >= -0.02).all()
        ok = g1 and g2 and g3 and g4a and g4b
        print(f"T={T}: pairedDexp={d.mean():+.4f} (95%lo {lo95:+.4f}) | MC both={both:.1%} bust={bust:.1%} "
              f"| fullStop {fs_base:.1%}->{fs_cell:.1%} | qtrs+ {(qtab>=0).sum()}/{len(qtab)} "
              f"| G1{'Y' if g1 else 'N'} G2{'Y' if g2 else 'N'} G3{'Y' if g3 else 'N'} G4{'Y' if (g4a and g4b) else 'N'} -> {'PASS' if ok else 'no'}")
        print(f"   {stats(coos.reset_index(), 'cell OOS')}")

    print("\nDone. Passing cell -> v1.30 flag-gated (existing EA ladder inputs), shadow-first, sign-off.")


if __name__ == "__main__":
    main()
