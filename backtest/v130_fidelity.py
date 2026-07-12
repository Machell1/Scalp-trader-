"""Pre-policy fidelity gates for the coupled v1.30 execution hook.

Only the already-contaminated canonical Deriv trio is opened here.  The sealed
FTMO confirmation/holdout directory is neither enumerated nor imported.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from parity_engine import OFFSET, START, prep_symbol, run_live
from retest_engine import SPREAD_DIR, resolve as reference_resolve
from retest_engine import run_cell as reference_run_cell
from v130_crosscheck import (
    REFERENCE_CELL,
    enumerate_asymmetric,
    resolve_asymmetric,
)
from v130_coupled import (
    D0_TOUCH,
    F1_PER_BAR,
    SYMBOLS,
    V130Execution,
)
from walkforward_dsr import real_cost_per_side


CASES = (
    ("Wall_Street_30", "US30.cash"),
    ("US_Tech_100", "US100.cash"),
    ("Japan_225", "JP225.cash"),
)
WINDOW = 4


def _spread_map(name: str, spread: np.ndarray) -> dict[str, np.ndarray]:
    # Only ``name`` is dereferenced, but a complete map makes missing-symbol
    # mistakes fail at construction in the same way as the study runner.
    return {symbol: (spread if symbol == name else np.zeros_like(spread)) for symbol in SYMBOLS}


def touch_reference_details(s):
    """Reference run_cell enumeration with bars retained for the identity gate."""
    out = []
    i = START
    while i < len(s.c) - 1:
        side = int(s.side[i])
        if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30:
            i += 1
            continue
        atr = float(s.atr[i])
        entry = float(s.c[i]) - OFFSET * atr * side
        fill = -1
        for bar in range(i + 1, min(i + 1 + WINDOW, len(s.c))):
            if (side > 0 and s.l[bar] <= entry) or (side < 0 and s.h[bar] >= entry):
                fill = bar
                break
        if fill < 0:
            i += WINDOW
            continue
        exit_bar, r_value = reference_resolve(
            s, fill, side, entry, atr, REFERENCE_CELL
        )
        out.append((int(s.ep[i]), i, fill, int(exit_bar), side, float(r_value)))
        i = int(exit_bar) + 1
    return out


def asymmetric_reference_details(s, spread):
    """v130_crosscheck per-bar enumeration with bars retained."""
    out = []
    i = START
    while i < len(s.c) - 1:
        side = int(s.side[i])
        if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30:
            i += 1
            continue
        atr = float(s.atr[i])
        entry = float(s.c[i]) - OFFSET * atr * side
        fill = -1
        for bar in range(i + 1, min(i + 1 + WINDOW, len(s.c))):
            touched = (
                s.l[bar] + spread[bar] <= entry
                if side > 0
                else s.h[bar] >= entry
            )
            if touched:
                fill = bar
                break
        if fill < 0:
            i += WINDOW
            continue
        exit_bar, r_value = resolve_asymmetric(
            s, spread, fill, side, entry, atr, fixed_spread=None
        )
        out.append((int(s.ep[i]), i, fill, int(exit_bar), side, float(r_value)))
        i = int(exit_bar) + 1
    return out


def _hook_details(s, spread, mode):
    trades, _ = run_live(
        [s],
        thr={s.name: 0.30},
        caps=None,
        queue=False,
        reverse_scan=False,
        window=WINDOW,
        replace_on_signal=False,
        execution=V130Execution(_spread_map(s.name, spread), mode),
    )
    return [
        (
            int(t.ep_sig),
            int(t.sig),
            int(t.entry_bar),
            int(t.exit_bar),
            int(t.side),
            float(t.r),
        )
        for t in trades
    ]


def _compare(label: str, expected, actual) -> tuple[int, float]:
    if len(expected) != len(actual):
        raise AssertionError(f"{label}: count {len(expected)} != {len(actual)}")
    max_delta = 0.0
    for index, (left, right) in enumerate(zip(expected, actual)):
        if left[:5] != right[:5]:
            raise AssertionError(
                f"{label}: lifecycle mismatch at {index}: {left[:5]} != {right[:5]}"
            )
        delta = abs(float(left[5]) - float(right[5]))
        max_delta = max(max_delta, delta)
        if delta > 1e-12:
            raise AssertionError(f"{label}: R delta {delta:.16g} at {index}")
    return len(expected), max_delta


def main() -> None:
    print("V130_FIDELITY")
    total_touch = total_f1 = 0
    max_touch = max_f1 = 0.0
    for file_stem, live_name in CASES:
        raw = pd.read_csv(os.path.join(SPREAD_DIR, file_stem + ".csv"))
        spread = raw["spread_price"].to_numpy(float)
        s = prep_symbol(raw, real_cost_per_side(raw), live_name)

        touch_ref_public = reference_run_cell(s, REFERENCE_CELL)
        touch_ref = touch_reference_details(s)
        if [(row[0], row[5]) for row in touch_ref] != touch_ref_public:
            raise AssertionError(f"{live_name}: detailed touch reference != run_cell")
        touch_hook = _hook_details(s, spread, D0_TOUCH)
        n_touch, d_touch = _compare(f"{live_name}/D0", touch_ref, touch_hook)

        f1_ref_public = enumerate_asymmetric(s, spread, "per_bar")
        f1_ref = asymmetric_reference_details(s, spread)
        if len(f1_ref) != len(f1_ref_public):
            raise AssertionError(f"{live_name}: detailed F1 count != v130_crosscheck")
        for index, (detail, public) in enumerate(zip(f1_ref, f1_ref_public)):
            if detail[0] != public[0] or abs(detail[5] - public[1]) > 1e-12:
                raise AssertionError(
                    f"{live_name}: detailed F1 != v130_crosscheck at {index}"
                )
        f1_hook = _hook_details(s, spread, F1_PER_BAR)
        n_f1, d_f1 = _compare(f"{live_name}/F1", f1_ref, f1_hook)

        total_touch += n_touch
        total_f1 += n_f1
        max_touch = max(max_touch, d_touch)
        max_f1 = max(max_f1, d_f1)
        print(
            f"symbol={live_name} D0_n={n_touch} D0_max_abs_r_delta={d_touch:.16f} "
            f"F1_n={n_f1} F1_max_abs_r_delta={d_f1:.16f}"
        )

    print(
        f"fidelity_pass=True D0_total={total_touch} "
        f"D0_max_abs_r_delta={max_touch:.16f} F1_total={total_f1} "
        f"F1_max_abs_r_delta={max_f1:.16f}"
    )


if __name__ == "__main__":
    main()
