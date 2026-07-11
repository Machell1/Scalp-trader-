"""Independent Phase B recomputation of the pre-registered W2 claim.

This script is derived from docs/CANDLE_INVERSE_SPEC_2026-07-10.md and the
feature definition in docs/CANDLE_SPEC_2026-07-10.md.  It deliberately does
not import either candle-study implementation.  The audited simulator and
walk-forward cost/frame helpers remain shared infrastructure, as required by
the replication assignment.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import scalper_backtest as B
import walkforward_dsr as W


W2_MIN_ADVERSE_WICK_ATR = 0.30
IS_FRACTION = 0.70


def deployed_params(cost_atr_frac: float) -> B.Params:
    """Return the pure-bracket deployed configuration locked by the spec."""
    return B.Params(
        momentum_bars=6,
        momentum_atr=2.0,
        atr_period=14,
        direction="cont",
        entry_style="limit",
        entry_offset_atr=0.6,
        pending_expiry_bars=3,
        stop_atr=1.0,
        tp_atr=3.0,
        lock_trigger_atr=99.0,
        trail_atr=99.0,
        max_hold_bars=8,
        cost_atr_frac=cost_atr_frac,
    )


def adverse_wick_atr(
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    atr: float,
    side: int,
) -> float:
    """Compute the side-adjusted adverse wick from the specification text."""
    if not np.isfinite(atr) or atr <= 0.0:
        raise ValueError(f"signal-bar ATR must be finite and positive, got {atr!r}")
    if side > 0:
        wick = high_price - max(open_price, close_price)
    elif side < 0:
        wick = min(open_price, close_price) - low_price
    else:
        raise ValueError(f"trade side must be +1 or -1, got {side!r}")
    return float(wick / atr)


def symbol_trade_tape(sym: str, df: pd.DataFrame, cost: float) -> pd.DataFrame:
    """Run one symbol and attach the independently computed W2 feature."""
    signals: list[tuple[int, int, int, float]] = []
    returned = B.simulate_symbol(
        df,
        deployed_params(cost),
        0,
        len(df),
        signals_out=signals,
    )
    if len(returned) != len(signals):
        raise RuntimeError(
            f"{sym}: simulator returned {len(returned)} R values but "
            f"signals_out returned {len(signals)} records"
        )

    open_values = df["open"].to_numpy(float)
    high_values = df["high"].to_numpy(float)
    low_values = df["low"].to_numpy(float)
    close_values = df["close"].to_numpy(float)
    time_values = pd.to_datetime(df["time"], errors="raise").to_numpy()
    atr_values = B.wilder_atr(
        high_values,
        low_values,
        close_values,
        deployed_params(cost).atr_period,
    )

    records = []
    for signal_bar, entry_bar, side, r_multiple in signals:
        feature = adverse_wick_atr(
            open_values[signal_bar],
            high_values[signal_bar],
            low_values[signal_bar],
            close_values[signal_bar],
            atr_values[signal_bar],
            side,
        )
        records.append(
            {
                "time": time_values[entry_bar],
                "sym": sym,
                "signal_bar": int(signal_bar),
                "entry_bar": int(entry_bar),
                "side": int(side),
                "r": float(r_multiple),
                "adv_wick_atr": feature,
                "keep_w2": feature >= W2_MIN_ADVERSE_WICK_ATR,
            }
        )

    return pd.DataFrame.from_records(
        records,
        columns=[
            "time",
            "sym",
            "signal_bar",
            "entry_bar",
            "side",
            "r",
            "adv_wick_atr",
            "keep_w2",
        ],
    )


def expectancy(frame: pd.DataFrame) -> float:
    if frame.empty:
        return float("nan")
    return float(frame["r"].to_numpy(float).mean())


def format_number(value: float) -> str:
    return f"{value:.10f}" if np.isfinite(value) else "nan"


def main() -> None:
    data = W.load_spreadgated()
    missing = [sym for sym in W.SPREAD_GATED if sym not in data]
    if missing or len(data) != len(W.SPREAD_GATED):
        raise RuntimeError(
            "canonical spread-gated universe is incomplete: "
            f"loaded={len(data)} missing={missing}"
        )

    costs = {sym: W.real_cost_per_side(df) for sym, df in data.items()}
    invalid_costs = {
        sym: cost
        for sym, cost in costs.items()
        if not np.isfinite(cost) or cost <= 0.0
    }
    if invalid_costs:
        raise RuntimeError(f"invalid real per-side costs: {invalid_costs}")

    tapes = [symbol_trade_tape(sym, data[sym], costs[sym]) for sym in W.SPREAD_GATED]
    baseline = pd.concat(tapes, ignore_index=True)
    if baseline.empty:
        raise RuntimeError("audited simulator produced no baseline trades")
    baseline = baseline.sort_values(
        ["time", "sym", "signal_bar", "entry_bar"], kind="mergesort"
    ).reset_index(drop=True)

    # Derive the stitched OOS calendar-quarter set from the complete baseline
    # tape once, then apply that identical paired frame to baseline and W2.
    walkforward = W.quarter_walkforward(
        baseline.loc[:, ["time", "sym", "r"]], is_frac=IS_FRACTION
    )
    if "oos_qs" not in walkforward or not walkforward["oos_qs"]:
        raise RuntimeError("walk-forward machinery produced no OOS quarters")
    oos_quarters = tuple(walkforward["oos_qs"])

    baseline["q"] = pd.PeriodIndex(baseline["time"], freq="Q")
    baseline_oos = baseline.loc[baseline["q"].isin(oos_quarters)].copy()
    w2_oos = baseline_oos.loc[baseline_oos["keep_w2"]].copy()

    print("PHASE_B_INDEPENDENT_W2")
    print("formula=buy:(high-max(open,close))/ATR;sell:(min(open,close)-low)/ATR")
    print(f"w2_keep=adv_wick_atr>={W2_MIN_ADVERSE_WICK_ATR:.2f}")
    print("oos_quarters=" + ",".join(str(q) for q in oos_quarters))
    print("symbol,baseline_n,baseline_exp_r,w2_n,w2_exp_r,delta_r")

    for sym in W.SPREAD_GATED:
        base_sym = baseline_oos.loc[baseline_oos["sym"] == sym]
        w2_sym = w2_oos.loc[w2_oos["sym"] == sym]
        base_exp = expectancy(base_sym)
        w2_exp = expectancy(w2_sym)
        delta = w2_exp - base_exp
        print(
            f"{sym},{len(base_sym)},{format_number(base_exp)},"
            f"{len(w2_sym)},{format_number(w2_exp)},{format_number(delta)}"
        )

    pooled_base_exp = expectancy(baseline_oos)
    pooled_w2_exp = expectancy(w2_oos)
    print(
        f"POOLED,{len(baseline_oos)},{format_number(pooled_base_exp)},"
        f"{len(w2_oos)},{format_number(pooled_w2_exp)},"
        f"{format_number(pooled_w2_exp - pooled_base_exp)}"
    )


if __name__ == "__main__":
    main()
