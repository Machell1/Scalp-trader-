"""Sliding-anchor MTF entry screen (pre-registered: docs/MTF_ANCHOR_SPEC_2026-07-13.md).

Question: does evaluating the UNCHANGED H1-scale W2 momentum-pullback signal on a
sliding lower-timeframe clock (every M15/M5 close, trailing anchor aggregation)
preserve the H1 edge while adding phase-offset entries and finer execution?

Cells (per symbol, real per-symbol cost, E1 measured + E2 double-cost stress):
  A    phase-0 H1 aggregation, H1-grain resolution.  GOLDEN CONTROL: delegates to
       the registered run_h1_timeframe_screen functions verbatim; must reproduce
       the recorded H1 screen numbers on the manifest data before anything else
       is interpreted.
  B_p  phase-p H1 aggregation (p = 1..factor-1 bar offsets), H1-grain resolution.
       Alignment-robustness control: the H1 edge must not be an artifact of
       hour-aligned bar construction.
  C1   phase-0 signals only, fine-grain (working-TF) execution + fine re-arm.
       Isolates the execution-granularity package.
  C2   sliding anchor: all phases evaluated chronologically on the working-TF
       clock with shared single-seat occupancy.  THE CANDIDATE.  Cohort columns:
       hour-aligned (phase 0) vs off-phase signals.

Geometry is frozen throughout (H1_TIMEFRAME_SPEC values): momentum 6 anchor bars
>= 2.0 ATR with candle-direction alignment, Wilder ATR(14) on the anchor series,
W2 adverse wick >= 0.30 anchor-ATR, limit at signal close -/+ 0.6 anchor-ATR,
pending window 3 anchor bars, SL 1.0 anchor-ATR, bank 50% at +1R, TP 2.0
anchor-ATR, 8 anchor-bar hold, stop-first pessimistic intrabar ordering, cost
charged once on full size in anchor-ATR units.

No parameter is swept.  Usage:
  python backtest/run_mtf_anchor_screen.py                 # trio, M15 data, factor 4
  python backtest/run_mtf_anchor_screen.py --universe holdout
  python backtest/run_mtf_anchor_screen.py --data data/derivM5_spreadgated --factor 12
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from parity_engine import prep_symbol, START  # noqa: E402
from walkforward_dsr import real_cost_per_side  # noqa: E402
import run_h1_timeframe_screen as h1screen  # noqa: E402

THR = 0.30          # W2 adverse-wick threshold (anchor-ATR units)
OFFSET = 0.6        # pullback limit offset (anchor-ATR)
EXPIRY_ANCHOR = 3   # pending window in anchor bars (registered H1 screen value)
HOLD_ANCHOR = 8     # max hold in anchor bars
SO_FRAC, SO_AT_R, TP_ATR, SL_ATR = 0.5, 1.0, 2.0, 1.0

TRIO = ["Wall_Street_30", "US_Tech_100", "Japan_225"]
HOLDOUT = [
    ("Germany_40", "derivM15_spreadgated"), ("US_SP_500", "derivM15_spreadgated"),
    ("UK_100", "derivM15_spreadgated"), ("France_40", "derivM15_spreadgated"),
    ("US_Small_Cap_2000", "derivM15_spreadgated"), ("Australia_200", "derivM15_diverse"),
    ("Hong_Kong_50", "derivM15_diverse"), ("EURUSD", "derivM15_diverse"),
    ("XAUUSD", "derivM15_diverse"), ("XAGUSD", "derivM15_diverse"),
]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def infer_bar_minutes(dt: pd.Series) -> int:
    d = dt.diff().dropna()
    return int(d.median() / pd.Timedelta(minutes=1))


def aggregate_phase(raw: pd.DataFrame, factor: int, phase: int) -> pd.DataFrame:
    """Anchor bars of `factor` contiguous working bars, offset by `phase` bars.

    phase 0 with factor 4 on M15 data reproduces run_h1_timeframe_screen.aggregate_h1
    exactly (asserted by test_mtf_anchor_screen.py).  Returned columns add
    `end_idx`: the integer index (into `raw`) of the last working bar of each
    complete anchor window -- the sliding evaluation clock.
    """
    df = raw.reset_index(drop=True).copy()
    dt = pd.to_datetime(df["time"])
    bar_min = infer_bar_minutes(dt)
    step = pd.Timedelta(minutes=bar_min)
    span = pd.Timedelta(minutes=bar_min * factor)
    df["_dt"] = dt
    df["_key"] = (dt - phase * step).dt.floor(span)
    df["_idx"] = np.arange(len(df))
    rows = []
    for key, g in df.groupby("_key", sort=True):
        g = g.sort_values("_dt")
        start = key + phase * step
        expected = [start + k * step for k in range(factor)]
        if len(g) != factor or list(g["_dt"]) != expected:
            continue
        rows.append({
            "time": start,
            "open": float(g.iloc[0]["open"]),
            "high": float(g["high"].max()),
            "low": float(g["low"].min()),
            "close": float(g.iloc[-1]["close"]),
            "volume": float(g["volume"].sum()) if "volume" in g else 0.0,
            "spread_price": float(g["spread_price"].max()) if "spread_price" in g else 0.0,
            "end_idx": int(g.iloc[-1]["_idx"]),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Fine-grain v1.30 resolution (bank 50% @ +1R, TP2, SL1, hold in working bars).
# Same math as session_study.resolve_v130, executed on the working-TF arrays.
# ---------------------------------------------------------------------------

def resolve_fine(o, h, l, c, cost, j, sd, entry, atr_sig, hold_bars):
    """Returns (exit_bar, r).  Stop-first pessimistic per working bar; the +1R
    bank and TP/SL levels all derive from the frozen anchor ATR."""
    risk = SL_ATR * atr_sig
    sl = entry - risk * sd
    tp = entry + TP_ATR * atr_sig * sd
    so = entry + SO_AT_R * risk * sd
    so_done = False
    banked, frac = 0.0, 1.0
    cost_r = 2.0 * cost * atr_sig / risk
    n = len(c)
    for k in range(j, min(j + hold_bars, n)):
        if sd > 0:
            if l[k] <= sl:
                return k, banked + frac * (sl - entry) / risk - cost_r
            if not so_done and h[k] >= so:
                banked += SO_FRAC
                frac -= SO_FRAC
                so_done = True
            if h[k] >= tp:
                return k, banked + frac * (tp - entry) / risk - cost_r
        else:
            if h[k] >= sl:
                return k, banked + frac * (entry - sl) / risk - cost_r
            if not so_done and l[k] <= so:
                banked += SO_FRAC
                frac -= SO_FRAC
                so_done = True
            if l[k] <= tp:
                return k, banked + frac * (entry - tp) / risk - cost_r
    k = min(j + hold_bars - 1, n - 1)
    return k, banked + frac * (c[k] - entry) * sd / risk - cost_r


# ---------------------------------------------------------------------------
# Enumeration on the working-TF clock
# ---------------------------------------------------------------------------

def build_phase_signals(raw: pd.DataFrame, cost: float, factor: int, phases):
    """(events, phase_data): events maps working-bar signal index -> (phase, anchor
    index); phase_data[p] = (SymData on the phase-p anchor series, end_idx)."""
    events: dict[int, tuple[int, int]] = {}
    phase_data = {}
    for p in phases:
        agg = aggregate_phase(raw, factor, p)
        if len(agg) <= START + 1:
            continue
        s = prep_symbol(agg[["time", "open", "high", "low", "close"]], cost, f"p{p}")
        end_idx = agg["end_idx"].to_numpy(int)
        phase_data[p] = (s, end_idx)
        for a in range(START, len(end_idx)):
            m = int(end_idx[a])
            if m in events:
                raise AssertionError("two phases share a signal bar (broken contiguity)")
            events[m] = (p, a)
    return events, phase_data


def run_fine(raw: pd.DataFrame, cost: float, factor: int, phases, cost_mult: float = 1.0,
             window_bars: int | None = None):
    """Sequential single-seat enumeration at working-TF granularity.

    At the open of working bar sig+1 the just-completed anchor window ending at
    `sig` is evaluated (occupancy and cooldown checked first, then W2 pre-entry,
    matching the live EA's manage-then-scan heartbeat).  A pending rests over
    working bars sig+1..sig+window; unfilled -> seat free again for signal bars
    >= sig+window+1.  After an exit at working bar x, signal bars <= x are
    cooldown-blocked (live g_noSignalUpTo semantics).
    """
    nmap = {col.lower(): col for col in raw.columns}
    df = raw.rename(columns={nmap[k]: k for k in ("open", "high", "low", "close") if k in nmap})
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    dt = pd.to_datetime(raw[nmap["time"]])
    ep = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy().astype(np.int64)
    n = len(c)
    window = window_bars if window_bars is not None else EXPIRY_ANCHOR * factor
    hold = HOLD_ANCHOR * factor

    events, phase_data = build_phase_signals(raw, cost, factor, phases)

    trades = []
    occupied_upto = -1   # working bars <= this cannot start a new signal (pending/position seat)
    cooldown_upto = -1   # signal bars <= this are exit-cooldown blocked
    for sig in sorted(events):
        if sig + 1 >= n:
            break
        if sig <= occupied_upto or sig <= cooldown_upto:
            continue
        p, a = events[sig]
        s, _ = phase_data[p]
        sd = int(s.side[a])
        if sd == 0 or not (np.isfinite(s.watr[a]) and s.watr[a] >= THR):
            continue
        atr_sig = float(s.atr[a])
        entry = float(s.c[a]) - OFFSET * atr_sig * sd
        j = -1
        for b in range(sig + 1, min(sig + window + 1, n)):
            if (sd > 0 and l[b] <= entry) or (sd < 0 and h[b] >= entry):
                j = b
                break
        if j < 0:
            occupied_upto = sig + window   # first eligible signal bar = sig+window+1
            continue
        xb, r = resolve_fine(o, h, l, c, cost * cost_mult, j, sd, entry, atr_sig, hold)
        trades.append({
            "sig_bar": int(sig), "entry_bar": int(j), "exit_bar": int(xb),
            "side": sd, "r": float(r), "phase": int(p), "ep_sig": int(ep[sig]),
        })
        occupied_upto = xb
        cooldown_upto = xb
    return trades


def run_anchor_grain(raw: pd.DataFrame, cost: float, factor: int, phase: int,
                     cost_mult: float = 1.0):
    """Cells A/B: phase-`phase` aggregation resolved on the anchor grain via the
    registered H1 screen's run_cell (verbatim), with OOS flags from the anchor
    series index (the H1 screen's own convention)."""
    agg = aggregate_phase(raw, factor, phase)
    s = prep_symbol(agg[["time", "open", "high", "low", "close"]], cost * cost_mult, f"p{phase}")
    s.oos = np.arange(len(agg)) >= int(len(agg) * 0.7)
    rows = h1screen.run_cell(s, market=False)
    return [{"ep_sig": int(t[0]), "r": float(t[1]), "oos": bool(t[2]), "phase": phase}
            for t in rows], len(agg)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def summarize(trades, oos_mask):
    r = np.asarray([t["r"] for t in trades], float)
    ro = np.asarray([t["r"] for t, m in zip(trades, oos_mask) if m], float)
    return {
        "n": int(len(r)), "exp": _m(r), "win": _w(r), "tot_r": float(r.sum()) if len(r) else 0.0,
        "oos_n": int(len(ro)), "oos_exp": _m(ro), "oos_win": _w(ro),
        "oos_tot_r": float(ro.sum()) if len(ro) else 0.0,
    }


def _m(x):
    return float(np.mean(x)) if len(x) else float("nan")


def _w(x):
    return float((x > 0).mean()) if len(x) else float("nan")


def oos_quarters(trades, oos_mask):
    rows = [(t["ep_sig"], t["r"]) for t, m in zip(trades, oos_mask) if m]
    if not rows:
        return []
    df = pd.DataFrame(rows, columns=["ep", "r"])
    q = pd.PeriodIndex(pd.to_datetime(df["ep"], unit="s"), freq="Q")
    out = []
    for qq, g in df.groupby(q):
        out.append({"quarter": str(qq), "n": int(len(g)), "exp": float(g["r"].mean())})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join("data", "derivM15_spreadgated"))
    ap.add_argument("--factor", type=int, default=4)
    ap.add_argument("--universe", choices=["trio", "holdout"], default="trio")
    ap.add_argument("--live-window", action="store_true",
                    help="sensitivity: model the live Bars() off-by-one (window 3F+1)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.universe == "trio":
        syms = [(k, args.data) for k in TRIO]
    else:
        syms = [(k, os.path.join("data", d)) for k, d in HOLDOUT]

    factor = args.factor
    window = EXPIRY_ANCHOR * factor + (1 if args.live_window else 0)
    results = {"factor": factor, "window_bars": window, "universe": args.universe,
               "symbols": {}, "pooled": {}}
    pooled: dict[str, list] = {}

    for key, sub in syms:
        path = os.path.join(HERE, sub) if not os.path.isabs(sub) else sub
        raw = pd.read_csv(os.path.join(path, key + ".csv"))
        h1_phase0 = aggregate_phase(raw, factor, 0)
        cost = real_cost_per_side(h1_phase0)
        if not np.isfinite(cost) or cost <= 0.0:
            cost = 0.03   # flat fallback for sources without a spread column (session_study convention)
        n_work = len(raw)
        oos_start_work = int(n_work * 0.7)
        sym_out = {"cost_per_side_atr": float(cost), "cells": {}}

        for stress, mult in (("E1", 1.0), ("E2", 2.0)):
            cells = {}
            # A: golden control (registered H1 screen path, phase 0)
            tr, n_anchor = run_anchor_grain(raw, cost, factor, 0, mult)
            cells["A_phase0_anchor"] = {
                **summarize(tr, [t["oos"] for t in tr]),
                "oos_quarters": oos_quarters(tr, [t["oos"] for t in tr]),
            }
            # B: phase-offset controls on the anchor grain
            for p in range(1, factor):
                trp, _ = run_anchor_grain(raw, cost, factor, p, mult)
                cells[f"B_phase{p}_anchor"] = summarize(trp, [t["oos"] for t in trp])
            # C1: phase-0 signals, fine execution
            t1 = run_fine(raw, cost, factor, phases=[0], cost_mult=mult, window_bars=window)
            m1 = [t["sig_bar"] >= oos_start_work for t in t1]
            cells["C1_phase0_fine"] = {**summarize(t1, m1),
                                       "oos_quarters": oos_quarters(t1, m1)}
            # C2: sliding anchor, all phases, shared seat
            t2 = run_fine(raw, cost, factor, phases=list(range(factor)),
                          cost_mult=mult, window_bars=window)
            m2 = [t["sig_bar"] >= oos_start_work for t in t2]
            aligned = [(t, m) for t, m in zip(t2, m2) if t["phase"] == 0]
            off = [(t, m) for t, m in zip(t2, m2) if t["phase"] != 0]
            cells["C2_sliding_fine"] = {
                **summarize(t2, m2),
                "oos_quarters": oos_quarters(t2, m2),
                "cohort_aligned": summarize([t for t, _ in aligned], [m for _, m in aligned]),
                "cohort_offphase": summarize([t for t, _ in off], [m for _, m in off]),
            }
            sym_out["cells"][stress] = cells
            for cname, cval in cells.items():
                pooled.setdefault((stress, cname), []).append(cval)
        results["symbols"][key] = sym_out
        print(f"== {key} cost/side={cost:.4f} ATR ==")
        for stress in ("E1", "E2"):
            for cname, cval in sym_out["cells"][stress].items():
                print(f"  {stress} {cname:18s} n={cval['n']:5d} exp={cval['exp']:+.4f} "
                      f"oos_n={cval['oos_n']:4d} oos_exp={cval['oos_exp']:+.4f} "
                      f"oos_totR={cval['oos_tot_r']:+.1f}")

    # trade-weighted pooled expectancies
    for (stress, cname), vals in pooled.items():
        n = sum(v["n"] for v in vals)
        on = sum(v["oos_n"] for v in vals)
        results["pooled"].setdefault(stress, {})[cname] = {
            "n": n,
            "exp": float(sum(v["exp"] * v["n"] for v in vals if v["n"]) / n) if n else float("nan"),
            "oos_n": on,
            "oos_exp": float(sum(v["oos_exp"] * v["oos_n"] for v in vals if v["oos_n"]) / on)
                       if on else float("nan"),
            "oos_tot_r": float(sum(v["oos_tot_r"] for v in vals)),
        }
    print("\n== POOLED ==")
    for stress in ("E1", "E2"):
        for cname, v in results["pooled"].get(stress, {}).items():
            print(f"  {stress} {cname:18s} n={v['n']:6d} exp={v['exp']:+.4f} "
                  f"oos_n={v['oos_n']:5d} oos_exp={v['oos_exp']:+.4f} oos_totR={v['oos_tot_r']:+.1f}")

    out = args.out or os.path.join(HERE, "mtf_anchor_screen_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
