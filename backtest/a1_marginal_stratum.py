"""Stage-0 marginal-stratum census for the A1 sleeve study.

Pre-registered: docs/A1_MARGINAL_SLEEVE_SPEC_2026-07-20.md
  (SHA256 8f454013227c4175e37a16c24013fd1d43d95b980617e72c69c3bfffafe64ccb)

Builds the audited C1 and A1 tapes with the EXACT head-to-head kwargs
(stress=True E2, partial 0.75 @ +1R, target 1.5 ATR, reference_same_bar_partial),
extracts per-trade net R from tape events, recomputes per-trade impulse from
the signal bar embedded in trade_id, and reports the marginal stratum
(impulse in [2.0, 3.0) inside the C1 enumeration). Read-only census.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_h1_universe_tape import (build_h1_universe_tape, load_symbol,
                                    META_PATH, MB)
from parity_engine import prep_symbol
from v130_pass_policy import AccountEventKind

SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
KW = dict(stress=True, partial_fraction=0.75, target_atr=1.5,
          reference_same_bar_partial=True)


def symbol_context():
    snapshot = json.loads(META_PATH.read_text(encoding="utf-8"))
    ctx = {}
    for source in SOURCES:
        loaded = load_symbol(source, snapshot)
        h1 = loaded.h1
        prepared = prep_symbol(h1, loaded.cost_e1, source)
        n = len(prepared.c)
        move = np.full(n, np.nan)
        move[MB - 1:] = prepared.c[:n - (MB - 1)] - prepared.c[MB - 1:]
        with np.errstate(invalid="ignore", divide="ignore"):
            imp = np.abs(move / prepared.atr)
        dt = pd.to_datetime(h1["time"])
        q = pd.PeriodIndex(dt, freq="Q")
        qs = sorted(q.unique())
        oos_qs = set(qs[int(len(qs) * 0.7):])
        ctx[loaded.ftmo_symbol] = dict(
            impulse=imp,
            oos=np.array([qq in oos_qs for qq in q]),
            cost_e2=float(loaded.cost_e1) * 2.0,
        )
    return ctx


def trades_from_tape(tape):
    """Per-trade: symbol, signal bar, net R (E2 costs), filled flag."""
    recs = {}
    for ev in tape.events:
        k = ev.normalized_kind()
        rec = recs.setdefault(ev.trade_id, dict(symbol=ev.symbol, entry=None,
                                                side=ev.side, stop=None,
                                                banked=0.0, remaining=1.0,
                                                final_px=None))
        if k == AccountEventKind.ENTRY:
            rec["entry"] = ev.price
            rec["stop"] = ev.stop_distance
        elif k == AccountEventKind.PARTIAL:
            frac = rec["remaining"] - ev.remaining_fraction
            rec["banked"] += frac * (ev.price - rec["entry"]) * rec["side"] / rec["stop"]
            rec["remaining"] = ev.remaining_fraction
        elif k == AccountEventKind.FINAL:
            rec["final_px"] = ev.price
            rec["final_remaining"] = ev.remaining_fraction if ev.remaining_fraction else rec["remaining"]
    return recs


def main():
    print("building C1 (2.0) and A1 (3.0) tapes with audited kwargs...")
    c1, c1_counts = build_h1_universe_tape(SOURCES, momentum_atr_mult=2.0, **KW)
    a1, a1_counts = build_h1_universe_tape(SOURCES, momentum_atr_mult=3.0, **KW)
    print(f"  C1 events={len(c1.events)} counts={c1_counts}")
    print(f"  A1 events={len(a1.events)} counts={a1_counts}")

    ctx = symbol_context()
    rows = []
    for tid, rec in trades_from_tape(c1).items():
        if rec["entry"] is None or rec["final_px"] is None:
            continue
        sym = rec["symbol"]
        bar = int(tid.rsplit(":", 1)[1])
        r_gross = rec["banked"] + rec["remaining"] * (
            (rec["final_px"] - rec["entry"]) * rec["side"] / rec["stop"])
        r_net = r_gross - 2.0 * ctx[sym]["cost_e2"]
        imp = float(ctx[sym]["impulse"][bar])
        rows.append((sym, bar, imp, r_net, bool(ctx[sym]["oos"][bar]), imp >= 3.0))
    df = pd.DataFrame(rows, columns=["sym", "bar", "impulse", "r", "oos", "aplus"])
    print(f"  C1 filled trades reconstructed: {len(df)}")

    def stats(d, label):
        if len(d) == 0:
            print(f"  {label}: empty")
            return
        o = d[d.oos]
        wins = d[d.r > 0]
        print(f"  {label}: n={len(d):4d} exp={d.r.mean():+.4f} win={(d.r > 0).mean():.1%} "
              f"avgWin={wins.r.mean() if len(wins) else float('nan'):+.3f} "
              f"| OOS n={len(o):3d} exp={(o.r.mean() if len(o) else float('nan')):+.4f}")

    print("\n=== C1-enumeration strata (E2 double-cost currency) ===")
    stats(df[df.aplus], "A+ stratum (imp>=3.0)")
    stats(df[~df.aplus], "MARGINAL (2.0<=imp<3.0)")
    print("\nper-symbol marginal stratum:")
    for sym, g in df[~df.aplus].groupby("sym"):
        stats(g, f"  {sym}")
    print("\nimpulse-band check on marginals:")
    m = df[~df.aplus].copy()
    m["band"] = pd.cut(m.impulse, [2.0, 2.25, 2.5, 2.75, 3.0])
    for band, g in m.groupby("band", observed=True):
        print(f"  {str(band):14s}: n={len(g):4d} exp={g.r.mean():+.4f} win={(g.r > 0).mean():.1%}")


if __name__ == "__main__":
    main()
