"""Synthetic fidelity checks for the C1 M15 universe builder."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from parity_engine import SymData, run_live
from v130_pass_policy import PassTape
from c1_universe_m15 import (
    C1M15Execution,
    CAPS_SOURCE,
    HOLD_H1_BARS,
    PENDING_M15_BARS,
    SplitBounds,
    SymbolContext,
    _calendar_bounds,
    _full_horizon_available,
    _signal_mask,
    _to_policy_events,
)


def _synthetic(
    symbol: str,
    cluster: int,
    *,
    hours: int = 12,
    spread: float = 0.20,
    weekend_gap: bool = False,
) -> tuple[SymData, SymbolContext]:
    pieces = []
    start = pd.Timestamp("2026-01-05T00:00:00Z")
    for hour in range(hours):
        wall_hour = hour + (72 if weekend_gap and hour >= 4 else 0)
        for quarter in range(4):
            pieces.append(start + pd.Timedelta(hours=wall_hour, minutes=15 * quarter))
    n = len(pieces)
    ep = np.asarray([int(value.timestamp()) for value in pieces], dtype=np.int64)
    o = np.full(n, 10.0)
    h = np.full(n, 10.2)
    low = np.full(n, 9.8)
    c = np.full(n, 10.0)
    atr = np.full(n, np.nan)
    side = np.zeros(n, dtype=np.int8)
    watr = np.full(n, np.nan)
    data = SymData(symbol, ep, o, h, low, c, atr, side, watr, 0.01, cluster)
    raw = pd.DataFrame({
        "time": pieces, "open": o, "high": h, "low": low, "close": c,
    })
    hour_codes = np.repeat(np.arange(hours, dtype=np.int64), 4)
    last = {hour: hour * 4 + 3 for hour in range(hours)}
    context = SymbolContext(
        source=symbol,
        symbol=symbol,
        cluster_name=f"C{cluster}",
        cluster_id=cluster,
        raw=raw,
        h1=pd.DataFrame(),
        h1_prepared=data,
        end_idx=np.arange(3, n, 4, dtype=np.int64),
        raw_prepared=data,
        h1_index_by_raw={index: pos for pos, index in enumerate(range(3, n, 4))},
        hour_ordinal_by_raw=hour_codes,
        last_raw_by_hour_ordinal=last,
        source_spread=np.full(n, spread),
        snapshot_full_spread=spread,
        fallback_per_side_atr=None,
        cost_e1_per_side_atr=0.01,
        cost_parts={},
    )
    return data, context


def _check(name: str, condition: bool, passed: list[str]) -> None:
    if not condition:
        raise AssertionError(name)
    passed.append(name)


def self_test() -> dict:
    passed: list[str] = []

    long_data, long_context = _synthetic("LONG", 0)
    long_data.atr[3] = 1.0
    execution = C1M15Execution({"LONG": long_context}, 2.0)
    long_data.l[4] = 9.90
    long_data.l[5] = 9.80
    fill = execution.find_fill(long_data, 1, 10.0, 4, 8)
    _check("long_entry_requires_ask_trade_through", fill == 5, passed)

    short_data, short_context = _synthetic("SHORT", 0)
    short_data.atr[3] = 1.0
    short_data.h[4] = 9.9
    short_data.h[5] = 10.0
    short_exec = C1M15Execution({"SHORT": short_context}, 2.0)
    _check(
        "short_entry_uses_bid_touch",
        short_exec.find_fill(short_data, -1, 10.0, 4, 8) == 5,
        passed,
    )

    stop_data, stop_context = _synthetic("STOP", 0)
    stop_data.atr[3] = 1.0
    stop_data.l[4] = 8.9
    stop_data.h[4] = 12.0
    stop_plan = C1M15Execution({"STOP": stop_context}, 2.0).resolve(
        stop_data, 3, 4, 1, 10.0, 1.0
    )
    _check("same_m15_stop_first", stop_plan.reason == "SL", passed)
    _check("same_m15_stop_price", stop_plan.exit_price == 9.0, passed)
    _check("same_m15_stop_emits_no_partial", stop_plan.marks == (), passed)
    _check(
        "same_m15_stop_exact_r",
        math.isclose(stop_plan.total_r, -1.04, abs_tol=1e-12),
        passed,
    )

    win_data, win_context = _synthetic("WIN", 0)
    win_data.atr[3] = 1.0
    win_data.l[4] = 9.5
    win_data.h[4] = 11.5
    win_plan = C1M15Execution({"WIN": win_context}, 2.0).resolve(
        win_data, 3, 4, 1, 10.0, 1.0
    )
    expected = 0.75 + 0.25 * 1.5 - 0.04
    _check("partial_precedes_target", win_plan.reason == "TP", passed)
    _check(
        "bank75_target_r",
        math.isclose(win_plan.total_r, expected, abs_tol=1e-12),
        passed,
    )
    _check(
        "one_partial_only",
        sum(mark.kind == "partial_fill" for mark in win_plan.marks) == 1,
        passed,
    )

    ask_stop_data, ask_stop_context = _synthetic("ASKSTOP", 0)
    ask_stop_data.atr[3] = 1.0
    ask_stop_data.h[4] = 10.85
    ask_stop_data.l[4] = 10.5
    ask_stop_plan = C1M15Execution({"ASKSTOP": ask_stop_context}, 2.0).resolve(
        ask_stop_data, 3, 4, -1, 10.0, 1.0
    )
    _check("short_stop_uses_ask", ask_stop_plan.reason == "SL", passed)

    short_win_data, short_win_context = _synthetic("SHORTWIN", 0)
    short_win_data.atr[3] = 1.0
    short_win_data.l[4] = 8.9  # bid touches +1R, ask low 9.1 does not
    short_win_data.l[5] = 8.8  # ask low 9.0: exact +1R partial
    short_win_data.l[6] = 8.4  # bid touches target, ask low 8.6 does not
    short_win_data.l[7] = 8.3  # ask low 8.5: exact target
    short_win_plan = C1M15Execution({"SHORTWIN": short_win_context}, 2.0).resolve(
        short_win_data, 3, 4, -1, 10.0, 1.0
    )
    _check("short_partial_uses_ask_low", short_win_plan.marks[0].bar == 4, passed)
    partial_marks = [mark for mark in short_win_plan.marks if mark.kind == "partial_fill"]
    _check(
        "short_partial_exact_ask_touch",
        len(partial_marks) == 1 and partial_marks[0].bar == 5,
        passed,
    )
    _check(
        "short_target_exact_ask_touch",
        short_win_plan.reason == "TP" and short_win_plan.exit_bar == 7,
        passed,
    )
    _check(
        "short_partial_target_exact_r",
        math.isclose(short_win_plan.total_r, 1.085, abs_tol=1e-12),
        passed,
    )

    time_data, time_context = _synthetic("TIME", 0, hours=12)
    time_data.atr[3] = 1.0
    time_plan = C1M15Execution({"TIME": time_context}, 2.0).resolve(
        time_data, 3, 4, 1, 10.0, 1.0
    )
    expected_hour = int(time_context.hour_ordinal_by_raw[4]) + HOLD_H1_BARS - 1
    _check(
        "eighth_h1_time_exit",
        time_plan.exit_bar == time_context.last_raw_by_hour_ordinal[expected_hour],
        passed,
    )

    short_time_data, short_time_context = _synthetic("SHORTTIME", 0, hours=12)
    short_time_data.atr[3] = 1.0
    short_time_plan = C1M15Execution({"SHORTTIME": short_time_context}, 2.0).resolve(
        short_time_data, 3, 4, -1, 10.0, 1.0
    )
    # C1-era parity fix (spec 3166c4f, registered sha 796f2450): the short TIME
    # exit stays at the structural bid close; no spread folded into the price.
    _check(
        "short_time_exit_stays_structural_bid_close",
        short_time_plan.reason == "TIME"
        and math.isclose(short_time_plan.exit_price, 10.0, abs_tol=1e-12),
        passed,
    )

    gap_data, gap_context = _synthetic("GAP", 0, hours=12, weekend_gap=True)
    gap_data.atr[3] = 1.0
    gap_plan = C1M15Execution({"GAP": gap_context}, 2.0).resolve(
        gap_data, 3, 4, 1, 10.0, 1.0
    )
    _check(
        "session_gap_counts_broker_h1_bars",
        gap_plan.exit_bar == gap_context.last_raw_by_hour_ordinal[8],
        passed,
    )

    pending_data, pending_context = _synthetic("PENDING", 0, hours=12)
    pending_data.side[23] = 1
    pending_data.atr[23] = 1.0
    pending_data.watr[23] = 0.5
    pending_data.l[:] = 10.0
    events: list[dict] = []
    run_live(
        [pending_data],
        thr={"PENDING": 0.30},
        caps=CAPS_SOURCE,
        window=PENDING_M15_BARS,
        execution=C1M15Execution({"PENDING": pending_context}, 2.0),
        event_sink=events.append,
    )
    cancel = next(row for row in events if row["kind"] == "pending_cancellation")
    _check("pending_expiry_twelve_m15", cancel["bar"] == 36, passed)

    scheduled = []
    contexts = {}
    for index, symbol in enumerate(("US30", "US100", "JP225", "USDJPY", "CAND")):
        cluster = 0 if symbol in {"US30", "US100"} else index
        data, context = _synthetic(symbol, cluster, hours=16)
        data.side[23] = 1
        data.atr[23] = 1.0
        data.watr[23] = 0.5
        data.l[24] = 8.0
        scheduled.append(data)
        contexts[symbol] = context
    priority_events: list[dict] = []
    run_live(
        scheduled,
        thr={data.name: 0.30 for data in scheduled},
        caps=CAPS_SOURCE,
        window=PENDING_M15_BARS,
        execution=C1M15Execution(contexts, 2.0),
        event_sink=priority_events.append,
    )
    placements = [
        row["symbol"] for row in priority_events if row["kind"] == "pending_placement"
    ]
    _check("candidate_appended_after_current_four", placements[:2] == ["US30", "JP225"], passed)
    attempts = [
        row for row in priority_events
        if row["kind"] in {"pending_placement", "signal_rejection"}
    ]
    _check(
        "candidate_does_not_reorder_usdjpy",
        [row["symbol"] for row in attempts[:5]]
        == ["US30", "US100", "JP225", "USDJPY", "CAND"],
        passed,
    )
    _check(
        "candidate_loses_same_epoch_global_contention",
        attempts[4]["kind"] == "signal_rejection"
        and attempts[4]["reason"] == "global_cap",
        passed,
    )

    asia_jp, asia_jp_context = _synthetic("JP", 1, hours=16)
    asia_au, asia_au_context = _synthetic("AU", 1, hours=16)
    for data in (asia_jp, asia_au):
        data.side[23] = 1
        data.atr[23] = 1.0
        data.watr[23] = 0.5
        data.l[24] = 8.0
    cluster_events: list[dict] = []
    run_live(
        [asia_jp, asia_au],
        thr={"JP": 0.30, "AU": 0.30},
        caps=CAPS_SOURCE,
        window=PENDING_M15_BARS,
        execution=C1M15Execution(
            {"JP": asia_jp_context, "AU": asia_au_context}, 2.0
        ),
        event_sink=cluster_events.append,
    )
    _check(
        "asia_cluster_one_seat",
        [row["symbol"] for row in cluster_events if row["kind"] == "pending_placement"]
        == ["JP"],
        passed,
    )
    asia_rejection = next(
        row for row in cluster_events
        if row["symbol"] == "AU" and row["kind"] == "signal_rejection"
    )
    _check("asia_loser_rejected_by_cluster", asia_rejection["reason"] == "cluster_cap", passed)

    # Adding an inert fifth symbol must leave every event generated by the
    # current four byte-for-byte equivalent.  This catches any future sort or
    # scheduler refactor that changes the control merely by extending the
    # configured universe.
    inert_candidate, inert_context = _synthetic("INERT", 4, hours=16)
    control_events: list[dict] = []
    extended_events: list[dict] = []
    run_live(
        scheduled[:4],
        thr={data.name: 0.30 for data in scheduled[:4]},
        caps=CAPS_SOURCE,
        window=PENDING_M15_BARS,
        execution=C1M15Execution(
            {symbol: contexts[symbol] for symbol in ("US30", "US100", "JP225", "USDJPY")},
            2.0,
        ),
        event_sink=control_events.append,
    )
    run_live(
        scheduled[:4] + [inert_candidate],
        thr={data.name: 0.30 for data in scheduled[:4] + [inert_candidate]},
        caps=CAPS_SOURCE,
        window=PENDING_M15_BARS,
        execution=C1M15Execution(
            {
                **{symbol: contexts[symbol] for symbol in ("US30", "US100", "JP225", "USDJPY")},
                "INERT": inert_context,
            },
            2.0,
        ),
        event_sink=extended_events.append,
    )
    _check("no_candidate_order", control_events == extended_events, passed)

    flow_data, flow_context = _synthetic("FLOW", 0, hours=16)
    flow_data.side[23] = 1
    flow_data.atr[23] = 1.0
    flow_data.watr[23] = 0.5
    flow_data.l[24] = 9.0
    flow_data.h[24] = 10.5
    flow_data.l[25] = 9.5
    flow_data.h[25] = 11.0
    flow_events: dict[float, list[dict]] = {}
    flow_trades = {}
    for cost_mult in (1.0, 2.0):
        events: list[dict] = []
        trades, _ = run_live(
            [flow_data],
            thr={"FLOW": 0.30},
            caps=CAPS_SOURCE,
            window=PENDING_M15_BARS,
            execution=C1M15Execution({"FLOW": flow_context}, cost_mult),
            event_sink=events.append,
        )
        flow_events[cost_mult] = events
        flow_trades[cost_mult] = trades

    def structural(rows: list[dict]) -> list[dict]:
        return [
            {
                key: value for key, value in row.items()
                if key not in {"r_component", "total_r"}
            }
            for row in rows
        ]

    _check(
        "e1_e2_structural_parity",
        structural(flow_events[1.0]) == structural(flow_events[2.0]),
        passed,
    )
    e1_entry = next(row for row in flow_events[1.0] if row["kind"] == "entry_fill")
    e2_entry = next(row for row in flow_events[2.0] if row["kind"] == "entry_fill")
    _check(
        "e1_e2_only_registered_cost_delta",
        math.isclose(e1_entry["r_component"], -0.02, abs_tol=1e-12)
        and math.isclose(e2_entry["r_component"], -0.04, abs_tol=1e-12)
        and math.isclose(
            flow_trades[1.0][0].r - flow_trades[2.0][0].r,
            0.02,
            abs_tol=1e-12,
        ),
        passed,
    )

    policy_events = _to_policy_events(
        flow_events[2.0], {"FLOW": flow_data}, {"FLOW": "TEST_CLUSTER"}
    )
    policy_tape = PassTape.from_events(
        policy_events, first_day="2026-01-05", last_day="2026-01-05"
    )
    entry_event = next(row for row in policy_events if str(row.kind) == "entry")
    partial_event = next(row for row in policy_events if str(row.kind) == "partial")
    final_event = next(row for row in policy_events if str(row.kind) == "final")
    mark_roles = {row.mark_role for row in policy_events if str(row.kind) == "mark"}
    _check(
        "source_to_policy_lifecycle_reconciles",
        len(policy_tape.trades) == 1
        and len(policy_tape.events) == len(flow_events[2.0]),
        passed,
    )
    _check(
        "policy_entry_cost_and_frozen_stop",
        math.isclose(entry_event.fixed_slippage_r, 0.04, abs_tol=1e-12)
        and math.isclose(entry_event.stop_distance, 1.0, abs_tol=1e-12),
        passed,
    )
    _check(
        "policy_partial_and_final_fractions",
        math.isclose(partial_event.remaining_fraction, 0.25, abs_tol=1e-12)
        and final_event.remaining_fraction == 0.0,
        passed,
    )
    _check(
        "policy_mark_roles_and_order",
        mark_roles == {"favorable", "adverse"}
        and [row.sequence for row in policy_events]
        == sorted(row.sequence for row in policy_events),
        passed,
    )

    censor_data, censor_context = _synthetic("CENSOR", 0, hours=12)
    censor_data.side[3] = 1
    censor_data.atr[3] = 1.0
    censor_data.watr[3] = 0.5
    censor_data.side[35] = 1
    censor_data.atr[35] = 1.0
    censor_data.watr[35] = 0.5
    censor_bounds = SplitBounds(
        int(censor_data.ep[0]), int(censor_data.ep[24]), int(censor_data.ep[-1]) + 900
    )
    masked, censored, missing_next = _signal_mask(
        censor_context, censor_bounds, "full", 2.0
    )
    _check(
        "right_censored_signal_excluded",
        masked.side[3] == 1
        and masked.side[35] == 0
        and censored == 1
        and missing_next == 0,
        passed,
    )

    non_w2_data, non_w2_context = _synthetic("NONW2", 0, hours=12)
    non_w2_data.side[35] = 1
    non_w2_data.atr[35] = 1.0
    non_w2_data.watr[35] = 0.20
    non_w2_masked, non_w2_censored, non_w2_missing = _signal_mask(
        non_w2_context, censor_bounds, "full", 2.0
    )
    non_w2_events: list[dict] = []
    run_live(
        [non_w2_masked],
        thr={"NONW2": 0.30},
        caps=CAPS_SOURCE,
        window=PENDING_M15_BARS,
        execution=C1M15Execution({"NONW2": non_w2_context}, 2.0),
        event_sink=non_w2_events.append,
    )
    _check(
        "near_end_non_w2_remains_predicate_rejection",
        non_w2_censored == 0
        and non_w2_missing == 0
        and non_w2_masked.side[35] == 1
        and len(non_w2_events) == 1
        and non_w2_events[0]["kind"] == "signal_rejection"
        and non_w2_events[0]["reason"] == "pre_entry_predicate",
        passed,
    )

    placement_data, placement_context = _synthetic("PLACEMENT", 0, hours=16)
    placement_data.side[3] = 1
    placement_data.atr[3] = 1.0
    placement_data.watr[3] = 0.50
    placement_data.ep[4:] += 72 * 3600
    placement_bounds = SplitBounds(
        int(placement_data.ep[0]),
        int(placement_data.ep[0]) + 24 * 3600,
        int(placement_data.ep[-1]) + 900,
    )
    discovery_mask, _, _ = _signal_mask(
        placement_context, placement_bounds, "discovery", 2.0
    )
    validation_mask, _, _ = _signal_mask(
        placement_context, placement_bounds, "validation", 2.0
    )
    _check(
        "segment_uses_actual_next_observed_open",
        discovery_mask.side[3] == 0 and validation_mask.side[3] == 1,
        passed,
    )

    missing_data, missing_context = _synthetic("MISSINGOPEN", 0, hours=16)
    missing_data.side[-1] = 1
    missing_data.atr[-1] = 1.0
    missing_data.watr[-1] = 0.50
    missing_bounds = SplitBounds(
        int(missing_data.ep[0]),
        int(missing_data.ep[20]),
        int(missing_data.ep[-1]) + 900,
    )
    missing_mask, missing_censored, missing_count = _signal_mask(
        missing_context, missing_bounds, "full", 2.0
    )
    _check(
        "missing_next_open_is_explicitly_excluded",
        missing_mask.side[-1] == 0
        and missing_censored == 0
        and missing_count == 1,
        passed,
    )

    gap_end_data, gap_end_context = _synthetic("GAPEND", 0, hours=12)
    common_end = int(gap_end_data.ep[43]) + 900
    gap_end_data.ep[44:] += 72 * 3600
    gap_end_bounds = SplitBounds(
        int(gap_end_data.ep[0]), int(gap_end_data.ep[20]), common_end
    )
    _check(
        "right_censor_uses_actual_next_open_after_gap",
        not _full_horizon_available(gap_end_context, 3, gap_end_bounds),
        passed,
    )

    midnight_bounds = SplitBounds(
        int(pd.Timestamp("2026-01-05T00:00:00Z").timestamp()),
        int(pd.Timestamp("2026-01-05T12:00:00Z").timestamp()),
        int(pd.Timestamp("2026-01-05T23:00:00Z").timestamp()),
    )
    first_day, last_day = _calendar_bounds(midnight_bounds, "full")
    _check(
        "calendar_end_is_half_open_for_owner_days",
        str(first_day) == "2026-01-05" and str(last_day) == "2026-01-05",
        passed,
    )

    return {"passed": len(passed), "checks": passed}


if __name__ == "__main__":
    result = self_test()
    print(f"C1_UNIVERSE_SYNTHETIC passed={result['passed']}")
    for name in result["checks"]:
        print("PASS", name)
