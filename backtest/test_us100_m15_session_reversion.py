"""Synthetic tests for the preregistered US100 M15 session-reversion runner."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import run_us100_m15_session_reversion as R


def prepared_fixture(*, down: bool = False, date: str = "2025-03-10") -> tuple[R.Prepared, dict[str, int]]:
    clocks = list(R.REQUIRED_CLOCKS)
    start_local = pd.Timestamp(f"{date} 09:15", tz=R.NY_TZ)
    utc = pd.date_range(start_local.tz_convert("UTC"), periods=19, freq="15min")
    epochs = np.asarray([int(value.timestamp()) for value in utc], dtype=np.int64)
    n = len(clocks)
    o = np.full(n, 106.0)
    h = np.full(n, 106.5)
    l = np.full(n, 105.5)
    c = np.full(n, 106.0)
    volume = np.full(n, 50.0)
    spread = np.full(n, 1.0)
    atr = np.full(n, 10.0)
    bars = {clock: i for i, clock in enumerate(clocks)}

    if not down:
        values = {
            "09:15": (100, 105, 95, 100, 50),
            "09:30": (100, 111, 100, 110, 100),
            "09:45": (110, 112, 108, 109, 60),
            "10:00": (109, 111, 107, 108, 50),
            "10:15": (108, 110, 106, 107, 40),
            "10:30": (107, 108, 103, 104, 50),
            "10:45": (106, 106.5, 105.5, 106, 50),
        }
    else:
        o[:] = 93.0
        h[:] = 93.5
        l[:] = 92.5
        c[:] = 93.0
        values = {
            "09:15": (100, 105, 95, 100, 50),
            "09:30": (100, 100, 89, 90, 100),
            "09:45": (90, 92, 88, 91, 60),
            "10:00": (91, 93, 89, 92, 50),
            "10:15": (92, 94, 90, 93, 40),
            "10:30": (93, 97, 92, 96, 50),
            "10:45": (93, 93.5, 92.5, 93, 50),
        }
    for clock, vals in values.items():
        i = bars[clock]
        o[i], h[i], l[i], c[i], volume[i] = vals
    local = utc.tz_convert(R.NY_TZ)
    data = R.Prepared(
        raw=pd.DataFrame(),
        epochs=epochs,
        local_date=np.asarray(local.strftime("%Y-%m-%d"), dtype=str),
        local_clock=np.asarray(local.strftime("%H:%M"), dtype=str),
        o=o,
        h=h,
        l=l,
        c=c,
        volume=volume,
        spread=spread,
        atr=atr,
    )
    return data, bars


def resolved(data: R.Prepared, bars: dict[str, int]) -> tuple[R.Setup, R.Trade, R.Trade]:
    setup, stage = R.detect_setup(data, data.local_date[0], bars)
    assert stage == "trade"
    assert setup is not None
    return setup, R.resolve_trade(data, setup, "MR3"), R.resolve_trade(data, setup, "C1")


def test_protocol_and_calendar_hashes() -> None:
    R.verify_protocol_hash()
    exclusions = R.load_exclusions()
    assert "2025-01-09" in exclusions
    assert "2025-07-03" in exclusions
    assert "2026-07-03" in exclusions


@pytest.mark.parametrize(
    ("utc_start", "date"),
    [("2025-03-07 14:15Z", "2025-03-07"), ("2025-03-10 13:15Z", "2025-03-10")],
)
def test_dst_session_mapping_and_completeness(utc_start: str, date: str) -> None:
    data, _ = prepared_fixture(date=date)
    utc = pd.date_range(pd.Timestamp(utc_start), periods=19, freq="15min")
    local = utc.tz_convert(R.NY_TZ)
    assert local[0].strftime("%H:%M") == "09:15"
    assert local[-1].strftime("%H:%M") == "13:45"
    data = replace(
        data,
        epochs=np.asarray([int(value.timestamp()) for value in utc], dtype=np.int64),
        local_date=np.asarray(local.strftime("%Y-%m-%d"), dtype=str),
        local_clock=np.asarray(local.strftime("%H:%M"), dtype=str),
    )
    found = R.session_index(data, date)
    assert found is not None
    assert found["09:15"] == 0
    assert found["13:45"] == 18


def test_missing_required_bar_rejects_session() -> None:
    data, _ = prepared_fixture()
    keep = np.arange(19) != 10
    short = replace(
        data,
        epochs=data.epochs[keep],
        local_date=data.local_date[keep],
        local_clock=data.local_clock[keep],
        o=data.o[keep], h=data.h[keep], l=data.l[keep], c=data.c[keep],
        volume=data.volume[keep], spread=data.spread[keep], atr=data.atr[keep],
    )
    assert R.session_index(short, "2025-03-10") is None


def test_bar_opens_must_be_exact_quarter_hours() -> None:
    exact = pd.Series(pd.to_datetime(["2025-03-10 13:15:00Z", "2025-03-10 13:30:00Z"], utc=True))
    R.validate_exact_m15_opens(exact)
    shifted = pd.Series(pd.to_datetime(["2025-03-10 13:15:30Z", "2025-03-10 13:30:30Z"], utc=True))
    with pytest.raises(RuntimeError, match="exact M15 open"):
        R.validate_exact_m15_opens(shifted)


def test_up_and_down_setups_match_exact_geometry() -> None:
    up, bars = prepared_fixture()
    setup, stage = R.detect_setup(up, "2025-03-10", bars)
    assert stage == "trade" and setup is not None
    assert setup.side == -1
    assert setup.trigger_clock == "10:30"
    assert setup.entry_bid == 106
    assert setup.reward_distance == 6
    assert setup.risk_distance == 2
    side, entry, target, stop = R._execution_geometry(up, setup, "MR3")
    assert (side, entry, target, stop) == (-1, 106, 100, 108)
    side, entry, target, stop = R._execution_geometry(up, setup, "C1")
    assert (side, entry, target, stop) == (1, 107, 113, 105)

    down, bars = prepared_fixture(down=True)
    setup, stage = R.detect_setup(down, "2025-03-10", bars)
    assert stage == "trade" and setup is not None
    assert setup.side == 1
    assert setup.reward_distance == 6
    assert setup.risk_distance == 2
    assert R._execution_geometry(down, setup, "MR3") == (1, 94, 100, 92)
    assert R._execution_geometry(down, setup, "C1") == (-1, 93, 87, 95)


def test_strict_signal_boundaries_and_late_trigger() -> None:
    data, bars = prepared_fixture()
    weak = data.c.copy()
    weak[bars["09:30"]] = 109.999
    setup, stage = R.detect_setup(replace(data, c=weak), "2025-03-10", bars)
    assert setup is None and stage == "impulse"

    equal_anchor = data.c.copy()
    equal_anchor[bars["10:15"]] = 100
    setup, stage = R.detect_setup(replace(data, c=equal_anchor), "2025-03-10", bars)
    assert setup is None and stage == "box"

    no_fade = data.volume.copy()
    no_fade[bars["09:30"]] = 50
    setup, stage = R.detect_setup(replace(data, volume=no_fade), "2025-03-10", bars)
    assert setup is None and stage == "volume"

    late = data.c.copy()
    late[bars["10:30"]] = 106  # equals box low: not strict
    late[bars["10:45"]] = 104
    late_open = data.o.copy()
    late_open[bars["11:00"]] = 105
    setup, stage = R.detect_setup(replace(data, c=late, o=late_open), "2025-03-10", bars)
    assert stage == "trade" and setup is not None
    assert setup.trigger_clock == "10:45"
    assert setup.entry_index == bars["11:00"]


def test_future_bars_cannot_change_signal_and_nonpositive_reward_cancels() -> None:
    data, bars = prepared_fixture()
    original, stage = R.detect_setup(data, "2025-03-10", bars)
    assert stage == "trade" and original is not None
    future_h, future_l, future_c, future_v = (
        data.h.copy(), data.l.copy(), data.c.copy(), data.volume.copy()
    )
    for clock in ("11:15", "11:30", "12:00", "13:45"):
        i = bars[clock]
        future_h[i], future_l[i], future_c[i], future_v[i] = 1_000, 1, 777, 999_999
    changed, stage = R.detect_setup(
        replace(data, h=future_h, l=future_l, c=future_c, volume=future_v),
        "2025-03-10",
        bars,
    )
    assert stage == "trade" and changed == original

    entry_open = data.o.copy()
    entry_open[bars["10:45"]] = 100
    cancelled, stage = R.detect_setup(replace(data, o=entry_open), "2025-03-10", bars)
    assert cancelled is None and stage == "reward"


@pytest.mark.parametrize("down", [False, True])
def test_target_and_stop_first_resolution(down: bool) -> None:
    data, bars = prepared_fixture(down=down)
    i = bars["11:00"]
    o, h, l, c = (x.copy() for x in (data.o, data.h, data.l, data.c))
    if down:
        o[i], h[i], l[i], c[i] = 94, 101, 93, 100
    else:
        o[i], h[i], l[i], c[i] = 105.5, 106, 98, 99
    target_data = replace(data, o=o, h=h, l=l, c=c)
    _, mr, control = resolved(target_data, bars)
    assert mr.exit_reason == "TARGET" and mr.r0 == pytest.approx(3)
    assert control.exit_reason == "STOP" and control.r0 == pytest.approx(-1)
    assert R.trade_r(mr, "E1_MEASURED") == pytest.approx(2.98)
    assert R.trade_r(mr, "E2_STRESS") == pytest.approx(2.96)

    both_h, both_l = data.h.copy(), data.l.copy()
    if down:
        both_h[i], both_l[i] = 101, 91
    else:
        both_h[i], both_l[i] = 108, 98
    _, mr_both, _ = resolved(replace(data, h=both_h, l=both_l), bars)
    assert mr_both.exit_reason == "STOP"
    assert mr_both.r0 == pytest.approx(-1)


@pytest.mark.parametrize("down", [False, True])
def test_adverse_stop_gap_books_worse_open(down: bool) -> None:
    data, bars = prepared_fixture(down=down)
    i = bars["11:00"]
    o, h, l, c = (x.copy() for x in (data.o, data.h, data.l, data.c))
    if down:
        o[i], h[i], l[i], c[i] = 90, 91, 89, 90
    else:
        o[i], h[i], l[i], c[i] = 109, 110, 109, 109
    _, mr, _ = resolved(replace(data, o=o, h=h, l=l, c=c), bars)
    assert mr.exit_reason == "STOP"
    assert mr.r0 == pytest.approx(-2)


def test_favorable_target_gap_receives_no_price_improvement() -> None:
    data, bars = prepared_fixture()
    i = bars["11:00"]
    o, h, l, c = (x.copy() for x in (data.o, data.h, data.l, data.c))
    o[i], h[i], l[i], c[i] = 97, 98, 96, 97
    _, mr, control = resolved(replace(data, o=o, h=h, l=l, c=c), bars)
    assert mr.exit_reason == "TARGET"
    assert mr.exit_exec == 100
    assert mr.r0 == pytest.approx(3)
    assert control.exit_reason == "STOP"
    assert control.r0 == pytest.approx(-5)


def test_time_exit_uses_executable_side() -> None:
    up, bars = prepared_fixture()
    _, mr, control = resolved(up, bars)
    assert mr.exit_reason == "TIME" and control.exit_reason == "TIME"
    assert mr.r0 == pytest.approx(-0.5)
    assert control.r0 == pytest.approx(-0.5)
    assert R.trade_r(mr, "E2_STRESS") == pytest.approx(-0.54)

    down, bars = prepared_fixture(down=True)
    _, mr, control = resolved(down, bars)
    assert mr.r0 == pytest.approx(-0.5)
    assert control.r0 == pytest.approx(-0.5)


@pytest.mark.parametrize("down", [False, True])
def test_spread_wider_than_risk_is_immediate_stop_not_filter(down: bool) -> None:
    data, bars = prepared_fixture(down=down)
    entry_i = bars["10:45"]
    o, h, l, c = (x.copy() for x in (data.o, data.h, data.l, data.c))
    if down:
        o[entry_i] = h[entry_i] = l[entry_i] = c[entry_i] = 97.5
    else:
        o[entry_i] = h[entry_i] = l[entry_i] = c[entry_i] = 101.5
    trapped = replace(data, o=o, h=h, l=l, c=c)
    setup, stage = R.detect_setup(trapped, "2025-03-10", bars)
    assert stage == "trade" and setup is not None
    assert setup.risk_distance == pytest.approx(0.5)
    mr = R.resolve_trade(trapped, setup, "MR3")
    c1 = R.resolve_trade(trapped, setup, "C1")
    assert mr.exit_index == entry_i and c1.exit_index == entry_i
    assert mr.r0 == pytest.approx(-2) and c1.r0 == pytest.approx(-2)


def test_short_target_uses_each_bars_contemporaneous_spread() -> None:
    data, bars = prepared_fixture()
    setup, stage = R.detect_setup(data, "2025-03-10", bars)
    assert stage == "trade" and setup is not None
    h, l, spread = data.h.copy(), data.l.copy(), data.spread.copy()
    for clock, low, spr in (("11:00", 99.5, 1.0), ("11:15", 99.8, 0.25), ("11:30", 99.7, 0.25)):
        i = bars[clock]
        h[i] = 106
        l[i] = low
        spread[i] = spr
    trade = R.resolve_trade(replace(data, h=h, l=l, spread=spread), setup, "MR3")
    assert trade.exit_index == bars["11:30"]
    assert trade.exit_reason == "TARGET"
    assert trade.r0 == pytest.approx(3)


def test_stats_exact_oracle() -> None:
    e0 = R.stats([3, -1, -2, 1])
    e1 = R.stats([2.98, -1.02, -2.02, 0.98])
    e2 = R.stats([2.96, -1.04, -2.04, 0.96])
    assert e0["expectancy"] == pytest.approx(0.25)
    assert e1["expectancy"] == pytest.approx(0.23)
    assert e2["expectancy"] == pytest.approx(0.21)
    assert e0["profit_factor"] == pytest.approx(4 / 3)
    assert e1["profit_factor"] == pytest.approx(3.96 / 3.04)
    assert e2["profit_factor"] == pytest.approx(3.92 / 3.08)
    assert (e0["max_drawdown_r"], e1["max_drawdown_r"], e2["max_drawdown_r"]) == pytest.approx((3, 3.04, 3.08))
    assert e0["longest_loss_streak"] == 2


def test_frame_boundaries_and_floor_70_30_split() -> None:
    dates = [f"2025-06-{21+i:02d}" for i in range(10)]
    frames = R.frame_dates(dates)
    assert dates[6] in frames["DIAGNOSTIC_70"]
    assert dates[7] in frames["DIAGNOSTIC_30"]
    assert "2025-06-30" in frames["DEVELOPMENT"]
    assert "2025-07-01" not in frames["DEVELOPMENT"]

    boundary = R.frame_dates(["2025-06-30", "2025-07-01", "2026-06-30", "2026-07-01"])
    assert boundary["BINDING_OOS"] == {"2025-07-01", "2026-06-30"}
    assert boundary["POST_OOS_PARTIAL"] == {"2026-07-01"}


def test_bootstrap_and_sign_flip_are_repeatable() -> None:
    primary = np.asarray([3, -1, 3, -1, 3, -1, 3, -1], dtype=float)
    delta = np.asarray([4, -2, 4, -2, 4, -2, 4, -2], dtype=float)
    first = R.bootstrap_lower_bounds(primary, delta)
    second = R.bootstrap_lower_bounds(primary, delta)
    assert first == second
    assert R.sign_flip_pvalue(delta) == R.sign_flip_pvalue(delta)
