"""Synthetic, data-independent checks for the v1.36 signal-detection surface.

Run: ``python backtest/test_v136_signal_detection.py``.
No manifest market-data file is read by these tests.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

import build_h1_universe_tape as builder
import run_v136_signal_detection as runner
from build_h1_universe_tape import (
    Z_TIE_EPSILON,
    _audited_impulse_atr,
    _drive_feature,
    _ordered_claimants,
    _struct_breakout,
)


def test_audited_impulse_indexing() -> None:
    closes = np.arange(40, dtype=float) ** 1.2
    atr = np.linspace(1.0, 2.0, len(closes))
    prepared = SimpleNamespace(c=closes, atr=atr)
    observed = _audited_impulse_atr(prepared)
    assert np.isnan(observed[:5]).all()
    expected = np.abs((closes[:-5] - closes[5:]) / atr[5:])
    assert np.array_equal(observed[5:], expected)


def test_struct_is_strict_prior_only_and_causal() -> None:
    closes = np.arange(30, dtype=float)
    closes[25:] = [-10.0, 200.0, 300.0, 400.0, 500.0]
    full = _struct_breakout(closes, 24, 1)
    truncated = _struct_breakout(closes[:25], 24, 1)
    assert full == truncated == (True, 23.0)

    equal = closes.copy()
    equal[24] = 23.0
    assert _struct_breakout(equal, 24, 1) == (False, 23.0)
    assert _struct_breakout(closes, 19, 1) == (False, None)

    short = np.arange(30, 0, -1, dtype=float)
    assert _struct_breakout(short, 24, -1) == (True, 7.0)


def test_drive_exact_four_constituents_and_causality() -> None:
    start = pd.Timestamp("2026-07-18 10:00:00")
    rows = {
        start + pd.Timedelta(minutes=15 * offset): (1, 100.0, close)
        for offset, close in enumerate((101.0, 103.0, 102.0, 99.0))
    }
    # A huge next-hour body is an explicit poison pill: it may not be accessed.
    rows[start + pd.Timedelta(hours=1)] = (1, 100.0, 1000.0)
    full = _drive_feature(rows, start, 1)
    visible_at_close = {
        timestamp: row for timestamp, row in rows.items()
        if timestamp <= start + pd.Timedelta(minutes=45)
    }
    truncated = _drive_feature(visible_at_close, start, 1)
    assert full == truncated
    decision, k_star, complete, timestamps = full
    assert decision is True and k_star == 1 and complete is True
    assert timestamps == tuple(
        str(start + pd.Timedelta(minutes=15 * offset)) for offset in range(4)
    )
    assert str(start + pd.Timedelta(hours=1)) not in timestamps

    # Earliest index wins exact body ties.
    tied = {
        start + pd.Timedelta(minutes=15 * offset): (1, 100.0, close)
        for offset, close in enumerate((104.0, 101.0, 104.0, 99.0))
    }
    assert _drive_feature(tied, start, 1)[:3] == (True, 0, True)

    missing = tied.copy()
    del missing[start + pd.Timedelta(minutes=30)]
    assert _drive_feature(missing, start, 1)[:3] == (False, None, False)

    duplicate = tied.copy()
    duplicate[start] = (2, 100.0, 104.0)
    assert _drive_feature(duplicate, start, 1)[:3] == (False, None, False)


def _claim(priority: int, trade_id: str, z: float) -> tuple:
    return (1000, priority, trade_id, f"S{priority}", f"C{priority}", 2000, z)


def test_seat_ordering_and_tie_deadband() -> None:
    rows = [_claim(0, "a", 3.1), _claim(1, "b", 4.0), _claim(2, "c", 3.5)]
    assert [row[2] for row in _ordered_claimants(rows, "fixed", None)] == ["a", "b", "c"]
    assert [row[2] for row in _ordered_claimants(rows, "max_z", None)] == ["b", "c", "a"]
    assert [row[2] for row in _ordered_claimants(rows, "min_z", None)] == ["a", "c", "b"]

    tied = [
        _claim(0, "priority", 4.0 - 0.5 * Z_TIE_EPSILON),
        _claim(1, "extreme", 4.0),
    ]
    assert _ordered_claimants(tied, "max_z", None)[0][2] == "priority"

    first = _ordered_claimants(rows, "random", np.random.default_rng(20260711))
    second = _ordered_claimants(rows, "random", np.random.default_rng(20260711))
    assert [row[2] for row in first] == [row[2] for row in second]


def _synthetic_h1() -> pd.DataFrame:
    n = 120
    close = np.full(n, 100.0)
    price = 100.0
    large = {24, 48, 72, 96}
    marginal = {36, 60, 84, 108}
    for bar in range(n):
        if bar in large:
            price += 10.0 if (bar // 24) % 2 else -10.0
        if bar in marginal:
            price += 4.0 if (bar // 12) % 2 else -4.0
        close[bar] = price
    open_ = close.copy()
    for bar in range(1, n):
        if close[bar] > close[bar - 1]:
            open_[bar] = close[bar] - 1.0
        elif close[bar] < close[bar - 1]:
            open_[bar] = close[bar] + 1.0
    return pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": open_,
        "high": np.maximum(open_, close) + 0.6,
        "low": np.minimum(open_, close) - 0.6,
        "close": close,
        "volume": np.ones(n),
        "spread_price": np.full(n, 0.01),
    })


def test_synthetic_builder_candidate_surface() -> None:
    """Exercise all additive paths without reading a manifest market frame."""
    h1 = _synthetic_h1()
    originals = builder.load_symbol, builder._m15_component_lookup

    def fake_load(source, snapshot):
        return SimpleNamespace(
            source=source,
            ftmo_symbol=builder.SOURCE_TO_FTMO[source],
            h1=h1.copy(),
            cost_e1=0.01,
            cost_parts={},
        )

    def fake_m15(_source):
        lookup = {}
        for signal_time in h1["time"]:
            for offset, body in enumerate((4.0, 3.0, 2.0, 1.0)):
                timestamp = pd.Timestamp(signal_time) + pd.Timedelta(minutes=15 * offset)
                lookup[timestamp] = (1, 100.0, 100.0 + body)
        return lookup

    sources = ("Wall_Street_30", "US_Tech_100", "Japan_225")
    common = dict(
        stress=True,
        partial_fraction=0.75,
        target_atr=1.5,
        reference_same_bar_partial=True,
        momentum_atr_mult=3.0,
        return_diagnostics=True,
    )
    try:
        builder.load_symbol = fake_load
        builder._m15_component_lookup = fake_m15
        a1, a1_counts, a1_diag = builder.build_h1_universe_tape(sources, **common)
        assert a1.events and a1_diag["raw_signals"]

        empty_mask, empty_counts, empty_diag = builder.build_h1_universe_tape(
            sources,
            signal_detection="mask",
            marginal_admit={source: set() for source in sources},
            **common,
        )
        assert empty_mask.events == a1.events
        assert empty_counts == a1_counts
        assert empty_diag["filled_trade_ids"] == a1_diag["filled_trade_ids"]

        all_marginal = {
            source: {
                row["bar_index"] for row in a1_diag["raw_signals"]
                if row["source"] == source and row["quality"] == "marginal"
            }
            for source in sources
        }
        expanded, _, expanded_diag = builder.build_h1_universe_tape(
            sources,
            signal_detection="mask",
            marginal_admit=all_marginal,
            **common,
        )
        assert len(expanded.events) >= len(a1.events)
        assert any(
            row["quality"] == "marginal" and row["signal_admitted"]
            for row in expanded_diag["raw_signals"]
        )

        _, _, drive_diag = builder.build_h1_universe_tape(
            sources, signal_detection="r_drive", **common
        )
        assert drive_diag["missing_m15_constituents"] == 0
        drive_rows = [
            row for row in drive_diag["raw_signals"] if row["quality"] == "marginal"
        ]
        assert drive_rows and all(
            len(row["feature_value"]["m15_timestamps"]) == 4 for row in drive_rows
        )

        _, _, seat_diag = builder.build_h1_universe_tape(
            sources, seat_policy="max_z", **common
        )
        assert seat_diag["seat_policy"] == "max_z"
        assert seat_diag["contention_epochs"] > 0

        try:
            builder.build_h1_universe_tape(
                sources, signal_detection="r_struct", seat_policy="max_z", **common
            )
        except ValueError as exc:
            assert "cannot combine" in str(exc)
        else:
            raise AssertionError("forbidden combined cell was accepted")
    finally:
        builder.load_symbol, builder._m15_component_lookup = originals


def _diag_row(
    source: str, symbol: str, bar: int, side: int, quarter_start: str,
    *, feature: bool, quality: str = "marginal", k_star=None,
) -> dict:
    return {
        "source": source, "symbol": symbol, "bar_index": bar,
        "oos_start": 10, "signal_time": str(pd.Timestamp(quarter_start) + pd.Timedelta(hours=bar)),
        "side": side, "quality": quality, "w2_pass": True,
        "feature_decision": feature, "k_star": k_star,
        "trade_id": f"H1U:{symbol}:{bar}",
    }


def test_runner_placebo_strata_and_negative_controls() -> None:
    source, symbol = "Wall_Street_30", "US30.cash"
    rows = [
        _diag_row(source, symbol, 10 + index, 1, "2025-01-01", feature=index < 2)
        for index in range(5)
    ]
    # Preserve one observed IS member while randomizing only the OOS stratum.
    rows.append(_diag_row(source, symbol, 1, 1, "2024-10-01", feature=True))
    diagnostics = {"raw_signals": rows}
    masks, matching = runner.matched_masks(diagnostics)
    assert len(masks) == runner.PLACEBOS == 200
    assert matching["strata"][0]["pool"] == 5
    assert matching["strata"][0]["selected"] == 2
    for mask in masks:
        assert 1 in mask[source]
        assert len({bar for bar in mask[source] if bar >= 10}) == 2

    controls = {"raw_signals": [
        _diag_row(source, symbol, 20, 1, "2025-01-01", feature=False, k_star=3),
        _diag_row(source, symbol, 21, 1, "2025-01-01", feature=False, k_star=None),
        _diag_row(source, symbol, 22, 1, "2025-01-01", feature=True, k_star=1),
    ]}
    assert runner.negative_readmission_keys("R_STRUCT", controls) == {
        (source, 20), (source, 21)
    }
    assert runner.negative_readmission_keys("R_DRIVE", controls) == {(source, 20)}


def test_runner_retention_and_gate_boundaries() -> None:
    source, symbol = "Wall_Street_30", "US30.cash"
    raw = [
        _diag_row(source, symbol, 20, 1, "2025-01-01", feature=False, quality="a1"),
        _diag_row(source, symbol, 21, -1, "2025-01-01", feature=False, quality="a1"),
    ]
    base = {
        "raw_signals": raw,
        "accepted_trade_ids": [row["trade_id"] for row in raw],
        "filled_trade_ids": [row["trade_id"] for row in raw],
    }
    candidate = {
        "raw_signals": raw,
        "accepted_trade_ids": [raw[0]["trade_id"]],
        "filled_trade_ids": [raw[0]["trade_id"]],
    }
    retained = runner.retention(candidate, base)
    assert retained["admitted_fraction"] == retained["filled_fraction"] == 0.5
    assert len(retained["by_symbol_side"]) == 2

    summary = {"oos_expectancy": 0.01, "dsr": 0.95}
    breadth = {"symbol_nonnegative": 3, "quarter_nonnegative_fraction": 0.60}
    retain = {"admitted_fraction": 0.70, "filled_fraction": 0.70}
    placebo = {"available": True, "p95": 0.005, "empirical_one_sided_p": runner.P_LIMIT}
    passed, failures = runner.discovery_gate(
        "R_STRUCT", summary, {}, breadth, retain, 0.01, placebo, 0.0,
    )
    assert passed and not failures
    empty = runner.placebo_statistics([None] * runner.PLACEBOS, None)
    assert empty["available"] is False and empty["p95"] is None
    passed, failures = runner.discovery_gate(
        "R_STRUCT", summary, {}, breadth, retain, None, empty, None,
    )
    assert not passed and "PLACEBO_DISTRIBUTION_UNAVAILABLE" in failures

    control = {"timeout_probability": 0.10, "median_total_days_success": 100.0}
    account = {
        "hard_probability": 0.003700, "timeout_probability": 0.105,
        "median_total_days_success": 110.0,
    }
    comparison = {"lower": 1e-12, "mcnemar_exact_one_sided_p_value": runner.P_LIMIT}
    assert runner.account_gate(account, control, comparison) == (True, [])
    account["hard_probability"] = 0.0037000001
    assert "HARD_GT_0_003700" in runner.account_gate(account, control, comparison)[1]


def test_runner_cache_binding_and_path_offsets() -> None:
    tape = SimpleNamespace(events=[])
    policy = runner.RiskPolicy("TEST", 0.001, 0.001)
    boot = runner.BootstrapSpec(seed=1, block_length=20, eligible_block_starts=(0, 1))
    first = runner.mc_cache_fingerprint(tape, policy, boot, 100, 0, "bundle-a")
    assert first != runner.mc_cache_fingerprint(tape, policy, boot, 100, 0, "bundle-b")
    assert first != runner.mc_cache_fingerprint(tape, policy, boot, 100, 20_000, "bundle-a")
    assert runner.mc_checkpoint("CONFIRMATION:A1", 100_000, 20_000).name.endswith(
        "_20000_120000.npz"
    )


def main() -> None:
    test_audited_impulse_indexing()
    test_struct_is_strict_prior_only_and_causal()
    test_drive_exact_four_constituents_and_causality()
    test_seat_ordering_and_tie_deadband()
    test_synthetic_builder_candidate_surface()
    test_runner_placebo_strata_and_negative_controls()
    test_runner_retention_and_gate_boundaries()
    test_runner_cache_binding_and_path_offsets()
    print("v1.36 signal-detection synthetic checks: 8 passed")


if __name__ == "__main__":
    main()
