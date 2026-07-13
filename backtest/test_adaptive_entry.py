"""Synthetic checks for the v1.32 scale-invariant entry research mirror."""
import numpy as np
import pandas as pd

from adaptive_entry import adaptive_geometry, adaptive_signal_frame


def frame(periods, freq, *, start="2026-01-01", slope=0.0):
    time = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    close = 100.0 + slope * np.arange(periods)
    return pd.DataFrame(
        {
            "time": time,
            "open": close - np.sign(slope) * 0.02,
            "high": close + 0.10,
            "low": close - 0.10,
            "close": close,
        }
    )


def assert_geometry_preserves_clock():
    assert adaptive_geometry(3600) == adaptive_geometry(3600, 3600)
    assert adaptive_geometry(900) == type(adaptive_geometry(900))(21, 12, 32)
    assert adaptive_geometry(300) == type(adaptive_geometry(300))(61, 36, 96)


def assert_reference_atr_is_causal():
    work = frame(400, "15min", slope=0.03)
    reference = frame(100, "1h", slope=0.12)
    first = adaptive_signal_frame(work, reference, work_seconds=900)

    # A future H1 shock must not alter diagnostics decided before that bar closes.
    changed = reference.copy()
    changed.loc[80:, "high"] += 50.0
    changed.loc[80:, "low"] -= 50.0
    second = adaptive_signal_frame(work, changed, work_seconds=900)
    cutoff = reference.loc[80, "time"]
    early = first["time"] < cutoff
    np.testing.assert_allclose(
        first.loc[early, "signal_atr"],
        second.loc[early, "signal_atr"],
        equal_nan=True,
    )


def assert_local_wick_is_not_divided_by_h1_atr():
    work = frame(400, "15min", slope=0.04)
    reference = frame(100, "1h", slope=0.16)
    # Force a large local adverse upper wick on the final bullish signal bar.
    work.loc[len(work) - 1, "high"] = work.loc[len(work) - 1, "close"] + 0.25
    out = adaptive_signal_frame(
        work,
        reference,
        work_seconds=900,
        momentum_atr=0.1,
        wick_atr=0.30,
    )
    row = out.iloc[-1]
    assert row["local_atr"] < row["signal_atr"]
    assert row["adverse_wick_atr"] >= 0.30
    assert row["side"] == 1


def main():
    assert_geometry_preserves_clock()
    assert_reference_atr_is_causal()
    assert_local_wick_is_not_divided_by_h1_atr()
    print("adaptive entry synthetic checks: 3 passed")


if __name__ == "__main__":
    main()
