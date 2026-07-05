CANDIDATE = dict(
    name="moderate bracket hold14",
    model="gpt-5.5-high",
    kind="exit",
    description=(
        "Start from the v1.23 pure bracket and only relax the bar-count time exit "
        "from 8 to 14 bars. The pullback-limit entry, 1 ATR stop, and 3 ATR target "
        "remain unchanged; the trade simply gets a little more time for the validated "
        "right-tail bracket payoff to develop. This expresses the exit-ladder lesson "
        "without adding filters, increasing entry turnover, or depending on fragile "
        "session/volume/regime gates."
    ),
    overrides=dict(
        entry_style="limit",
        entry_offset_atr=0.6,
        pending_expiry_bars=3,
        stop_atr=1.0,
        tp_atr=3.0,
        max_hold_bars=14,
        lock_trigger_atr=1e6,
        trail_atr=0.0,
    ),
)
