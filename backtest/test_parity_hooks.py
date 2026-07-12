"""Synthetic fidelity checks for parity_engine's default-off hook surface.

This test deliberately uses no repository market-data file.  In particular it
must remain safe while the FTMO confirmation and holdout frames are sealed.
"""
import numpy as np

from parity_engine import (
    BAR_SEC,
    START,
    ExecutionPlan,
    LifecycleMark,
    SymData,
    find_fill,
    resolve_bracket,
    run_live,
    trade_r,
)


def synthetic(name="SYN", *, wick=0.50, touched=True):
    n = START + 14
    ep = 1_700_000_000 + np.arange(n, dtype=np.int64) * BAR_SEC
    o = np.full(n, 100.0)
    h = np.full(n, 100.1)
    l = np.full(n, 99.9)
    c = np.full(n, 100.0)
    atr = np.ones(n)
    side = np.zeros(n, dtype=np.int8)
    watr = np.full(n, np.nan)
    side[START] = 1
    watr[START] = wick
    if touched:
        l[START + 1] = 99.0       # 99.4 buy limit fills
        h[START + 2] = 102.5      # legacy TP3 at 102.4
    return SymData(name, ep, o, h, l, c, atr, side, watr, 0.0, 0)


class LegacyExecution:
    """The historical run_live resolver expressed through the custom hook."""

    @staticmethod
    def find_fill(s, side, entry, w_start, w_end):
        return find_fill(s, side, entry, w_start, w_end)

    @staticmethod
    def resolve(s, sig_i, entry_bar, side, entry, atr_sig):
        exit_bar, exit_price, reason = resolve_bracket(
            s, entry_bar, side, entry, atr_sig
        )
        total_r = trade_r(s, side, entry, exit_price, atr_sig)
        if reason == "TIME" and exit_bar + 1 < len(s.c):
            free_epoch = int(s.ep[exit_bar + 1])
        else:
            free_epoch = int(s.ep[exit_bar]) + BAR_SEC
        return ExecutionPlan(
            exit_bar, exit_price, reason, total_r, free_epoch
        )


class PartialExecution:
    @staticmethod
    def find_fill(s, side, entry, w_start, w_end):
        return w_start

    @staticmethod
    def resolve(s, sig_i, entry_bar, side, entry, atr_sig):
        partial_bar = entry_bar
        exit_bar = entry_bar + 1
        mark = LifecycleMark(
            "partial_fill",
            partial_bar,
            int(s.ep[partial_bar]) + BAR_SEC - 1,
            entry + side * atr_sig,
            0.50,
            "+1R half",
        )
        return ExecutionPlan(
            exit_bar,
            entry + side * 2.0 * atr_sig,
            "TP",
            1.40,
            int(s.ep[exit_bar]) + BAR_SEC,
            entry_r_component=-0.10,
            marks=(mark,),
        )


class NeverFillExecution:
    @staticmethod
    def find_fill(s, side, entry, w_start, w_end):
        return -1

    @staticmethod
    def resolve(*args):
        raise AssertionError("resolve must not run for an unfilled pending")


class SequenceExecution:
    def __init__(self, outcomes, loss_classifications=None):
        self.outcomes = outcomes
        self.loss_classifications = loss_classifications or {}

    @staticmethod
    def find_fill(s, side, entry, w_start, w_end):
        return w_start

    def resolve(self, s, sig_i, entry_bar, side, entry, atr_sig):
        total_r = self.outcomes[sig_i]
        return ExecutionPlan(
            entry_bar,
            entry,
            "SL" if total_r < 0 else "FLAT" if total_r == 0 else "TP",
            total_r,
            int(s.ep[entry_bar]) + BAR_SEC,
            loss_classification_r=self.loss_classifications.get(sig_i),
        )


def assert_default_and_sink_are_side_effect_free():
    s = synthetic()
    trades_plain, census_plain = run_live([s], thr={s.name: 0.30}, window=4)
    events = []
    trades_sink, census_sink = run_live(
        [s], thr={s.name: 0.30}, window=4, event_sink=events.append
    )
    assert trades_sink == trades_plain
    assert census_sink == census_plain
    assert len(trades_plain) == 1
    assert [e["kind"] for e in events] == [
        "pending_placement", "entry_fill", "final_exit"
    ]
    assert [e["sequence"] for e in events] == [1, 2, 3]
    assert events[0]["trade_key"] == f"{s.name}:{int(s.ep[START])}:1"


def assert_legacy_hook_matches_default():
    s = synthetic()
    expected = run_live([s], thr={s.name: 0.30}, window=4)
    hooked = run_live(
        [s], thr={s.name: 0.30}, window=4, execution=LegacyExecution()
    )
    assert hooked == expected


def partial_events():
    s = synthetic()
    events = []
    trades, census = run_live(
        [s],
        thr={s.name: 0.30},
        caps={"global": 2, "cluster": 1, "fills_day": 8, "consec": 4},
        window=4,
        execution=PartialExecution(),
        event_sink=events.append,
    )
    assert len(trades) == 1 and trades[0].r == 1.40
    assert census.occupied == 0
    assert [e["kind"] for e in events] == [
        "pending_placement", "entry_fill", "partial_fill", "final_exit"
    ]
    entry = events[1]
    assert entry["r_component"] == -0.10
    partial = events[2]
    assert partial["r_component"] == 0.50
    assert partial["state_before"] == partial["state_after"] == "position"
    assert partial["global_before"] == partial["global_after"] == 1
    assert partial["scheduler_epoch"] == partial["epoch"] + 1
    final = events[3]
    assert final["r_component"] == 1.0 and final["total_r"] == 1.40
    assert final["state_before"] == "position" and final["state_after"] == "free"
    component_sum = (entry["r_component"] + partial["r_component"]
                     + final["r_component"])
    assert abs(component_sum - 1.40) < 1e-12
    return trades, census, events


def assert_cancellation_and_rejection_events():
    s = synthetic(touched=False)
    events = []
    trades, _ = run_live(
        [s], thr={s.name: 0.30}, window=4,
        execution=NeverFillExecution(), event_sink=events.append
    )
    assert not trades
    assert [e["kind"] for e in events] == [
        "pending_placement", "pending_cancellation"
    ]
    assert events[-1]["reason"] == "unfilled_expiry"
    assert events[-1]["state_before"] == "pending"
    assert events[-1]["state_after"] == "free"

    rejected = synthetic(name="REJECT", wick=0.10)
    reject_events = []
    trades, _ = run_live(
        [rejected], thr={rejected.name: 0.30}, window=4,
        event_sink=reject_events.append
    )
    assert not trades
    assert len(reject_events) == 1
    assert reject_events[0]["kind"] == "signal_rejection"
    assert reject_events[0]["reason"] == "pre_entry_predicate"


def assert_custom_account_day_boundary():
    s = synthetic()
    second_signal = START + 3
    s.side[second_signal] = 1
    s.watr[second_signal] = 0.50
    caps = {"global": 2, "cluster": 1, "fills_day": 1, "consec": 4}

    utc_trades, utc_census = run_live(
        [s], thr={s.name: 0.30}, caps=caps, window=4,
        execution=PartialExecution()
    )
    assert len(utc_trades) == 1 and utc_census.day_fills == 1

    observed_epochs = []
    boundary = int(s.ep[second_signal + 1])

    def local_day(epoch):
        observed_epochs.append(epoch)
        return "before" if epoch < boundary else "after"

    local_trades, local_census = run_live(
        [s], thr={s.name: 0.30}, caps=caps, window=4,
        execution=PartialExecution(), day_key=local_day
    )
    assert len(local_trades) == 2 and local_census.day_fills == 0
    # Fill and final-only streak booking both use the supplied day mapping.
    assert int(s.ep[START + 1]) in observed_epochs
    assert int(s.ep[START + 2]) + BAR_SEC - 1 in observed_epochs


def assert_intrabar_event_stays_on_fill_day():
    s = synthetic()
    fill_bar = START + 1
    day_start = 100 * 86400
    desired_fill_open = day_start + 23 * 3600 + 45 * 60
    s.ep = desired_fill_open + (np.arange(len(s.ep)) - fill_bar) * BAR_SEC
    second_signal = START + 3
    s.side[second_signal] = 1
    s.watr[second_signal] = 0.50
    events = []
    trades, census = run_live(
        [s],
        thr={s.name: 0.30},
        caps={"global": 2, "cluster": 1, "fills_day": 1, "consec": 4},
        window=4,
        execution=PartialExecution(),
        event_sink=events.append,
    )
    # The first fill belongs to 23:45's account day, leaving the new UTC day's
    # one-fill allowance available for the second signal after midnight.
    assert len(trades) == 2 and census.day_fills == 0
    first_entry = next(e for e in events if e["kind"] == "entry_fill")
    first_partial = next(e for e in events if e["kind"] == "partial_fill")
    assert first_entry["epoch"] == day_start + 86400 - 1
    assert first_partial["epoch"] == day_start + 86400 - 1
    assert first_entry["scheduler_epoch"] == day_start + 86400
    assert first_partial["scheduler_epoch"] == day_start + 86400


def assert_zero_result_does_not_reset_live_streak():
    s = synthetic()
    signal_bars = [START, START + 2, START + 4, START + 6]
    for bar in signal_bars:
        s.side[bar] = 1
        s.watr[bar] = 0.50
    outcomes = {
        signal_bars[0]: -1.0,
        signal_bars[1]: 0.0,
        signal_bars[2]: -1.0,
        signal_bars[3]: 1.0,
    }
    trades, census = run_live(
        [s],
        thr={s.name: 0.30},
        caps={"global": 2, "cluster": 1, "fills_day": 8, "consec": 2},
        window=4,
        execution=SequenceExecution(outcomes),
    )
    assert [trade.r for trade in trades] == [-1.0, 0.0, -1.0]
    assert census.day_consec == 1


def assert_loss_classification_override_is_default_off():
    signal_bars = [START, START + 2, START + 4]
    caps = {"global": 2, "cluster": 1, "fills_day": 8, "consec": 2}

    default = synthetic()
    for bar in signal_bars:
        default.side[bar] = 1
        default.watr[bar] = 0.50
    positive_outcomes = {bar: 1.0 for bar in signal_bars}
    default_trades, default_census = run_live(
        [default],
        thr={default.name: 0.30},
        caps=caps,
        window=4,
        execution=SequenceExecution(positive_outcomes),
    )
    assert [trade.r for trade in default_trades] == [1.0, 1.0, 1.0]
    assert default_census.day_consec == 0

    classified_losses = synthetic()
    for bar in signal_bars:
        classified_losses.side[bar] = 1
        classified_losses.watr[bar] = 0.50
    classified_trades, classified_census = run_live(
        [classified_losses],
        thr={classified_losses.name: 0.30},
        caps=caps,
        window=4,
        execution=SequenceExecution(
            positive_outcomes,
            {signal_bars[0]: -0.25, signal_bars[1]: -0.25},
        ),
    )
    assert [trade.r for trade in classified_trades] == [1.0, 1.0]
    assert classified_census.day_consec == 1

    classified_wins = synthetic()
    for bar in signal_bars:
        classified_wins.side[bar] = 1
        classified_wins.watr[bar] = 0.50
    negative_outcomes = {bar: -1.0 for bar in signal_bars}
    win_classifications = {bar: 0.25 for bar in signal_bars}
    classified_win_trades, classified_win_census = run_live(
        [classified_wins],
        thr={classified_wins.name: 0.30},
        caps=caps,
        window=4,
        execution=SequenceExecution(negative_outcomes, win_classifications),
    )
    assert [trade.r for trade in classified_win_trades] == [-1.0, -1.0, -1.0]
    assert classified_win_census.day_consec == 0


def main():
    assert_default_and_sink_are_side_effect_free()
    assert_legacy_hook_matches_default()
    first = partial_events()
    second = partial_events()
    assert first == second
    assert_cancellation_and_rejection_events()
    assert_custom_account_day_boundary()
    assert_intrabar_event_stays_on_fill_day()
    assert_zero_result_does_not_reset_live_streak()
    assert_loss_classification_override_is_default_off()
    print("parity hook synthetic checks: 9 passed")


if __name__ == "__main__":
    main()
