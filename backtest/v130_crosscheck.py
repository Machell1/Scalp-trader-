"""Independent v1.30 scale-out cross-check.

The production target is so50@1R with a TP2 remainder.  This runner implements
that resolver independently, compares every enumerated trade with
retest_engine.resolve/run_cell, exercises adversarial synthetic bars, and then
recomputes the venue-correct asymmetric bid-bar fill column documented in
docs/RETEST_SPEC_2026-07-12.md.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from nearmiss_decisions import challenge_mc, daylist
from parity_engine import START, prep_symbol
from retest_engine import Cell, SPREAD_DIR, TRIO, resolve as reference_resolve
from retest_engine import run_cell as reference_run_cell
from walkforward_dsr import real_cost_per_side


WINDOW = 4
HOLD = 8
STOP_ATR = 1.0
TP_ATR = 2.0
SO_AT_R = 1.0
SO_FRACTION = 0.50
REFERENCE_CELL = Cell(
    "v1.30 so50@1R TP2.0",
    filt="W2",
    sl=STOP_ATR,
    tp=TP_ATR,
    hold=HOLD,
    so_frac=SO_FRACTION,
    so_at=SO_AT_R,
)


@dataclass
class Resolution:
    exit_bar: int
    r: float
    partial_done: bool


def resolve_v130(s, entry_bar: int, side: int, entry: float, signal_atr: float) -> Resolution:
    """Independent transcription of the v1.30 exit accounting."""
    risk = STOP_ATR * signal_atr
    stop = entry - side * risk
    target = entry + side * TP_ATR * signal_atr
    partial = entry + side * SO_AT_R * risk
    banked = 0.0
    remainder = 1.0
    partial_done = False
    exit_bar = None
    exit_price = None

    for bar in range(entry_bar, min(entry_bar + HOLD, len(s.c))):
        high = s.h[bar]
        low = s.l[bar]
        if side > 0:
            if low <= stop:  # pessimistic stop first
                exit_bar, exit_price = bar, stop
                break
            if not partial_done and high >= partial:
                banked += SO_FRACTION * (partial - entry) * side / risk
                remainder -= SO_FRACTION
                partial_done = True
            if high >= target:
                exit_bar, exit_price = bar, target
                break
        else:
            if high >= stop:
                exit_bar, exit_price = bar, stop
                break
            if not partial_done and low <= partial:
                banked += SO_FRACTION * (partial - entry) * side / risk
                remainder -= SO_FRACTION
                partial_done = True
            if low <= target:
                exit_bar, exit_price = bar, target
                break

    if exit_bar is None:
        exit_bar = min(entry_bar + HOLD - 1, len(s.c) - 1)
        exit_price = s.c[exit_bar]

    cost_r = 2.0 * s.cost * signal_atr / risk
    result = banked + remainder * (exit_price - entry) * side / risk - cost_r
    return Resolution(int(exit_bar), float(result), partial_done)


def enumerate_v130(s):
    """Independent W2/window-4 live enumeration with paired resolver checks."""
    tape = []
    i = START
    while i < len(s.c) - 1:
        side = int(s.side[i])
        if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30:
            i += 1
            continue
        atr = s.atr[i]
        entry = s.c[i] - 0.6 * atr * side
        fill = -1
        for bar in range(i + 1, min(i + 1 + WINDOW, len(s.c))):
            if (side > 0 and s.l[bar] <= entry) or (side < 0 and s.h[bar] >= entry):
                fill = bar
                break
        if fill < 0:
            i += WINDOW
            continue

        own = resolve_v130(s, fill, side, entry, atr)
        ref_bar, ref_r = reference_resolve(s, fill, side, entry, atr, REFERENCE_CELL)
        if own.exit_bar != ref_bar or abs(own.r - ref_r) > 1e-12:
            raise AssertionError(
                f"resolver mismatch {s.name} signal={i}: "
                f"own=({own.exit_bar},{own.r:.16f}) ref=({ref_bar},{ref_r:.16f})"
            )
        tape.append((int(s.ep[i]), own.r))
        i = own.exit_bar + 1
    return tape


def resolve_asymmetric(s, spread, entry_bar, side, entry, signal_atr, fixed_spread=None):
    """Bid-bar venue rule: buy-side limits require full-spread trade-through."""
    risk = STOP_ATR * signal_atr
    stop = entry - side * risk
    target = entry + side * TP_ATR * signal_atr
    partial = entry + side * SO_AT_R * risk
    banked = 0.0
    remainder = 1.0
    partial_done = False
    exit_bar = None
    exit_price = None

    for bar in range(entry_bar, min(entry_bar + HOLD, len(s.c))):
        high = s.h[bar]
        low = s.l[bar]
        bar_spread = spread[bar] if fixed_spread is None else fixed_spread
        if side > 0:
            if low <= stop:
                exit_bar, exit_price = bar, stop
                break
            if not partial_done and high >= partial:  # sell limit at bid
                banked += SO_FRACTION
                remainder -= SO_FRACTION
                partial_done = True
            if high >= target:  # sell limit at bid
                exit_bar, exit_price = bar, target
                break
        else:
            if high >= stop:
                exit_bar, exit_price = bar, stop
                break
            if not partial_done and low + bar_spread <= partial:  # buy limit at ask
                banked += SO_FRACTION
                remainder -= SO_FRACTION
                partial_done = True
            if low + bar_spread <= target:  # buy limit at ask
                exit_bar, exit_price = bar, target
                break

    if exit_bar is None:
        exit_bar = min(entry_bar + HOLD - 1, len(s.c) - 1)
        exit_price = s.c[exit_bar]
    cost_r = 2.0 * s.cost * signal_atr / risk
    r = banked + remainder * (exit_price - entry) * side / risk - cost_r
    return int(exit_bar), float(r)


def enumerate_asymmetric(s, spread, spread_mode):
    tape = []
    i = START
    while i < len(s.c) - 1:
        side = int(s.side[i])
        if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30:
            i += 1
            continue
        atr = s.atr[i]
        entry = s.c[i] - 0.6 * atr * side
        if spread_mode == "per_bar":
            fill_spread = None
        elif spread_mode == "signal_scaled_median_model":
            fill_spread = 2.0 * s.cost * atr
        elif spread_mode == "constant_raw_median":
            fill_spread = float(np.nanmedian(spread))
        else:
            raise ValueError(spread_mode)
        fill = -1
        for bar in range(i + 1, min(i + 1 + WINDOW, len(s.c))):
            # Long entry buys at ask; short entry sells at bid.
            bar_spread = spread[bar] if fill_spread is None else fill_spread
            touched = (s.l[bar] + bar_spread <= entry) if side > 0 else (s.h[bar] >= entry)
            if touched:
                fill = bar
                break
        if fill < 0:
            i += WINDOW
            continue
        exit_bar, r = resolve_asymmetric(
            s, spread, fill, side, entry, atr, fixed_spread=fill_spread
        )
        tape.append((int(s.ep[i]), r))
        i = exit_bar + 1
    return tape


class Synthetic:
    def __init__(self, highs, lows, closes, cost=0.0):
        self.h = np.asarray(highs, dtype=float)
        self.l = np.asarray(lows, dtype=float)
        self.c = np.asarray(closes, dtype=float)
        self.cost = float(cost)


def synthetic_checks():
    cases = [
        ("stop_precedes_partial", Synthetic([111], [89], [100]), -1.0, False),
        ("partial_then_tp_same_bar", Synthetic([121], [99], [120]), 1.5, True),
        ("partial_then_stop", Synthetic([111, 105], [99, 89], [105, 90]), 0.0, True),
        ("short_partial_then_tp", Synthetic([101], [79], [80]), 1.5, True),
    ]
    for name, s, expected_r, expected_partial in cases:
        side = -1 if name.startswith("short") else 1
        got = resolve_v130(s, 0, side, 100.0, 10.0)
        if abs(got.r - expected_r) > 1e-12 or got.partial_done != expected_partial:
            raise AssertionError(f"synthetic {name}: got {got}, expected r={expected_r}")
    return len(cases)


def summarize(tape):
    rs = np.asarray([r for _, r in tape], dtype=float)
    both, bust, med = challenge_mc(daylist(sorted(tape)))
    return len(rs), float(rs.mean()), float((rs > 0).mean()), both, bust, med


def main():
    synthetic_n = synthetic_checks()
    touch_all = []
    asymmetric = {
        "per_bar": [],
        "signal_scaled_median_model": [],
        "constant_raw_median": [],
    }
    max_tape_delta = 0.0

    print("V130_CROSSCHECK")
    print(f"synthetic_cases={synthetic_n} status=PASS")
    for name in TRIO:
        path = os.path.join(SPREAD_DIR, name + ".csv")
        raw = pd.read_csv(path)
        s = prep_symbol(raw, real_cost_per_side(raw), name)
        own = enumerate_v130(s)
        ref = reference_run_cell(s, REFERENCE_CELL)
        if len(own) != len(ref):
            raise AssertionError(f"{name}: tape length own={len(own)} ref={len(ref)}")
        if own:
            epochs_equal = all(a[0] == b[0] for a, b in zip(own, ref))
            delta = max(abs(a[1] - b[1]) for a, b in zip(own, ref))
        else:
            epochs_equal, delta = True, 0.0
        if not epochs_equal or delta > 1e-12:
            raise AssertionError(f"{name}: tape mismatch epochs={epochs_equal} max_delta={delta}")
        max_tape_delta = max(max_tape_delta, delta)
        spread = raw["spread_price"].to_numpy(float)
        asym_by_mode = {
            mode: enumerate_asymmetric(s, spread, mode) for mode in asymmetric
        }
        touch_all.extend(own)
        for mode, tape in asym_by_mode.items():
            asymmetric[mode].extend(tape)
        print(
            f"symbol={name} reference_n={len(ref)} independent_n={len(own)} "
            f"max_abs_r_delta={delta:.16f} "
            + " ".join(f"{mode}_n={len(tape)}" for mode, tape in asym_by_mode.items())
        )

    touch = summarize(touch_all)
    asym_stats = {mode: summarize(tape) for mode, tape in asymmetric.items()}
    print(f"trade_tape_identity=True max_abs_r_delta={max_tape_delta:.16f}")
    print(
        "touch_fill "
        f"n={touch[0]} exp={touch[1]:+.10f} win={touch[2]:.10f} "
        f"both={touch[3]:.10f} bust={touch[4]:.10f} med_days={touch[5]}"
    )
    for mode, values in asym_stats.items():
        print(
            f"venue_asymmetric mode={mode} "
            f"n={values[0]} exp={values[1]:+.10f} win={values[2]:.10f} "
            f"both={values[3]:.10f} bust={values[4]:.10f} med_days={values[5]}"
        )
    asym = asym_stats["signal_scaled_median_model"]
    matches = (
        round(asym[1], 4) == 0.0270
        and round(asym[3] * 100, 1) == 66.1
        and round(asym[4] * 100, 1) == 17.6
    )
    print(f"handoff_asymmetric_rounding_match={matches}")
    if not matches:
        raise SystemExit("venue-asymmetric result differs from the handoff; report discrepancy")


if __name__ == "__main__":
    main()
