CANDIDATE = dict(
    name="patient pullback, unhurried exit",
    model="claude-opus-4-8-thinking-high",
    kind="mixed",
    description=(
        "One thesis, two minimal knobs: the v1.23 champion abandons the validated "
        "pullback-continuation trade too early on BOTH ends. (1) ENTRY: the resting "
        "pullback LIMIT is cancelled after only 3 bars, yet a genuine retrace to 0.6 ATR "
        "back often needs a bar or two longer; giving it one more bar (pending_expiry 3->4) "
        "captures ~130 additional real fills of the single feature the repo validated as THE "
        "edge (HANDOFF #1), and does so consistently on BOTH datasets and net of 2x cost. "
        "(2) EXIT: the 8-bar time stop truncates the right tail (RESULTS.md §7 -- every exit "
        "loosening improved OOS expectancy); a modest extension to 12 bars lets those trades "
        "reach the unchanged 3-ATR target. The entry price, 0.6-ATR offset, 1.0-ATR stop and "
        "3.0-ATR target are all unchanged -- this is not a new signal, filter, or geometry, "
        "just refusing to abandon the setup prematurely. Both knobs were chosen at robust "
        "INTERIOR behaviour, not parameter boundaries: entry patience gives real new fills at "
        "4 (gains past 4 are only trade-path reshuffling, so 4 is the honest value), and hold "
        "shows a broad interior optimum at 10-12 that decays by 16 with the two datasets "
        "agreeing across 10-12 -- a plateau, not a knife-edge. Cost-fragility improves because "
        "the extra R comes from better fills and surviving winners, not from higher turnover."
    ),
    overrides=dict(
        entry_style="limit",
        entry_offset_atr=0.6,
        pending_expiry_bars=4,
        stop_atr=1.0,
        tp_atr=3.0,
        max_hold_bars=12,
        lock_trigger_atr=1e6,
        trail_atr=0.0,
    ),
)
