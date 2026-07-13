"""Self-tests for run_mtf_anchor_screen (no market data required).

Run: python backtest/test_mtf_anchor_screen.py

1. GOLDEN AGGREGATION: aggregate_phase(factor=4, phase=0) must equal the
   registered run_h1_timeframe_screen.aggregate_h1 column-for-column on
   synthetic M15 data with session gaps.
2. GOLDEN CELL A: the cell-A path (delegating to run_h1_timeframe_screen.run_cell)
   must reproduce the same trades as calling the registered pipeline directly.
3. FINE-GRAIN EQUIVALENCE: with factor=1 (anchor == working bar) and coarse
   accounting, run_fine must reproduce run_cell trade-for-trade (entry
   enumeration parity), with fine resolution differing only through intrabar
   granularity (identical here because factor=1 uses the same bars).
4. C2 INVARIANTS: single-seat occupancy (no overlapping lifecycles), signals
   only at anchor-complete bars, cooldown respected, phase labels correct.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_h1_timeframe_screen as h1screen  # noqa: E402
from parity_engine import prep_symbol, START  # noqa: E402
from run_mtf_anchor_screen import (  # noqa: E402
    aggregate_phase, run_fine, run_anchor_grain, EXPIRY_ANCHOR, HOLD_ANCHOR, THR,
)


def synth_m15(n=12000, seed=7, gap_every=900):
    """Synthetic M15 series with occasional multi-bar session gaps and enough
    drift/vol structure to fire momentum signals."""
    rng = np.random.default_rng(seed)
    t = pd.Timestamp("2024-01-01 00:00:00")
    times, px = [], []
    price = 10000.0
    regime = 0.0
    for i in range(n):
        if gap_every and i % gap_every == gap_every - 1:
            t += pd.Timedelta(minutes=15 * int(rng.integers(1, 9)))  # gap
        else:
            t += pd.Timedelta(minutes=15)
        if i % 250 == 0:
            regime = rng.normal(0, 6.0)
        price += regime + rng.normal(0, 12.0)
        times.append(t)
        px.append(price)
    px = np.asarray(px)
    o = np.r_[px[0], px[:-1]]
    spread = rng.uniform(0.5, 2.0, n)
    h = np.maximum(o, px) + np.abs(rng.normal(0, 6.0, n))
    l = np.minimum(o, px) - np.abs(rng.normal(0, 6.0, n))
    return pd.DataFrame({
        "time": times, "open": o, "high": h, "low": l, "close": px,
        "volume": rng.integers(100, 5000, n).astype(float),
        "spread_price": spread,
    })


def test_golden_aggregation(raw):
    a = h1screen.aggregate_h1(raw).reset_index(drop=True)
    b = aggregate_phase(raw, 4, 0).drop(columns=["end_idx"]).reset_index(drop=True)
    assert len(a) == len(b), f"row count {len(a)} vs {len(b)}"
    for col in ("time", "open", "high", "low", "close", "volume", "spread_price"):
        av, bv = a[col].to_numpy(), b[col].to_numpy()
        if col == "time":
            assert (pd.to_datetime(av) == pd.to_datetime(bv)).all(), "time mismatch"
        else:
            assert np.allclose(av.astype(float), bv.astype(float)), f"{col} mismatch"
    print(f"PASS golden aggregation ({len(a)} anchor bars)")


def test_golden_cell_a(raw, cost=0.02):
    h1 = h1screen.aggregate_h1(raw)
    s = prep_symbol(h1, cost, "syn")
    s.oos = np.arange(len(h1)) >= int(len(h1) * 0.7)
    ref = h1screen.run_cell(s, market=False)
    mine, _ = run_anchor_grain(raw, cost, 4, 0, 1.0)
    assert len(ref) == len(mine), f"trade count {len(ref)} vs {len(mine)}"
    for (ep, r, oos), t in zip(ref, mine):
        assert ep == t["ep_sig"] and abs(r - t["r"]) < 1e-12 and oos == t["oos"]
    print(f"PASS golden cell A ({len(ref)} trades)")


def run_cell_v130_reference(s, window, hold):
    """Reference enumeration mirroring run_h1_timeframe_screen.run_cell but with
    the exit-cooldown convention of run_fine (resume at exit_bar+1 -- identical
    to run_cell) and explicit window/hold, for the factor=1 equivalence test."""
    from session_study import resolve_v130
    out = []
    i = START
    while i < len(s.c) - 1:
        side = int(s.side[i])
        if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < THR:
            i += 1
            continue
        entry = s.c[i] - 0.6 * s.atr[i] * side
        j = -1
        for b in range(i + 1, min(i + window + 1, len(s.c))):
            if (side > 0 and s.l[b] <= entry) or (side < 0 and s.h[b] >= entry):
                j = b
                break
        if j < 0:
            i += window + 1
            continue
        xb, r = resolve_v130(s, j, side, entry, s.atr[i])
        out.append((i, j, xb, float(r)))
        i = xb + 1
    return out


def test_factor1_equivalence(raw, cost=0.02):
    """factor=1: the anchor series IS the working series, so run_fine must
    reproduce the sequential reference enumeration trade-for-trade.
    (session_study.resolve_v130 hard-codes hold 8 == HOLD_ANCHOR * 1.)"""
    s = prep_symbol(raw[["time", "open", "high", "low", "close"]], cost, "syn")
    ref = run_cell_v130_reference(s, EXPIRY_ANCHOR, HOLD_ANCHOR)
    mine = run_fine(raw, cost, 1, phases=[0])
    assert len(ref) == len(mine), f"trade count {len(ref)} vs {len(mine)}"
    for (i, j, xb, r), t in zip(ref, mine):
        assert i == t["sig_bar"] and j == t["entry_bar"] and xb == t["exit_bar"], \
            f"bars mismatch {(i, j, xb)} vs {t}"
        assert abs(r - t["r"]) < 1e-12, f"r mismatch {r} vs {t['r']}"
    print(f"PASS factor=1 fine==reference ({len(ref)} trades)")


def test_c2_invariants(raw, cost=0.02, factor=4):
    trades = run_fine(raw, cost, factor, phases=list(range(factor)))
    assert trades, "no C2 trades on synthetic data (test not powered)"
    window_ends = {}
    for p in range(factor):
        for m in aggregate_phase(raw, factor, p)["end_idx"]:
            window_ends[int(m)] = p
    last_exit = -1
    phases_seen = set()
    for t in trades:
        assert t["sig_bar"] > last_exit, "signal inside a previous lifecycle"
        assert t["entry_bar"] > t["sig_bar"]
        assert t["entry_bar"] <= t["sig_bar"] + EXPIRY_ANCHOR * factor
        assert t["exit_bar"] >= t["entry_bar"]
        assert t["exit_bar"] <= t["entry_bar"] + HOLD_ANCHOR * factor - 1
        # phase label consistency: the signal bar must close a phase-p anchor window
        assert window_ends.get(t["sig_bar"]) == t["phase"], "phase label mismatch"
        phases_seen.add(t["phase"])
        last_exit = t["exit_bar"]
    aligned = [t for t in trades if t["phase"] == 0]
    off = [t for t in trades if t["phase"] != 0]
    assert len(phases_seen) > 1, "sliding mode never used an off-phase signal"
    print(f"PASS C2 invariants ({len(trades)} trades: {len(aligned)} aligned, "
          f"{len(off)} off-phase, phases {sorted(phases_seen)})")


def test_phase_partition(raw, factor=4):
    """Every complete anchor window end-bar belongs to exactly one phase."""
    ends = {}
    for p in range(factor):
        agg = aggregate_phase(raw, factor, p)
        for m in agg["end_idx"]:
            assert m not in ends, f"bar {m} claimed by phases {ends[m]} and {p}"
            ends[m] = p
    frac = len(ends) / len(raw)
    assert frac > 0.9, f"only {frac:.1%} of bars close an anchor window"
    print(f"PASS phase partition ({len(ends)} window-ends over {len(raw)} bars, {frac:.1%})")


def main():
    raw = synth_m15()
    test_golden_aggregation(raw)
    test_golden_cell_a(raw)
    test_factor1_equivalence(raw)
    test_phase_partition(raw)
    test_c2_invariants(raw)
    # a second seed with different gap cadence
    raw2 = synth_m15(seed=99, gap_every=333)
    test_golden_aggregation(raw2)
    test_golden_cell_a(raw2)
    test_factor1_equivalence(raw2)
    test_phase_partition(raw2)
    test_c2_invariants(raw2)
    print("ALL PASS")


if __name__ == "__main__":
    main()
