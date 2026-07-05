CANDIDATE = dict(
    name="pullback patience +1 bar",
    model="composer-2.5",
    kind="geom",
    description=(
        "The champion's 3-bar pending window is tight for a 0.6-ATR pullback limit: "
        "valid setups often need one more bar for price to retrace to the resting order, "
        "especially on slower clocks (H1 proxy) and in live fills (day-1: ~75% fill vs "
        "~59% modeled at 3 bars). Extending pending expiry to 4 keeps the same signal "
        "population and entry geometry — only gives the limit one extra bar to work — "
        "without bolt-on filters or stacking exit changes."
    ),
    overrides=dict(
        entry_style="limit",
        entry_offset_atr=0.6,
        pending_expiry_bars=4,
        stop_atr=1.0,
        tp_atr=3.0,
        max_hold_bars=8,
        lock_trigger_atr=1e6,
        trail_atr=0.0,
    ),
)
