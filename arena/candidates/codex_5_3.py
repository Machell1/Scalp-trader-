CANDIDATE = dict(
    name="pure bracket hold10",
    model="gpt-5.3-codex-high",
    kind="exit",
    description=(
        "Minimal, evidence-aligned exit change: keep the champion pullback LIMIT + "
        "pure bracket geometry, but relax the time exit from 8 to 10 bars. The "
        "exit-ladder study showed the prior ladder was truncating the right tail; "
        "this is a small loosening intended to keep more continuation winners while "
        "remaining cost-aware and structurally simple."
    ),
    overrides=dict(
        entry_style="limit",
        entry_offset_atr=0.6,
        pending_expiry_bars=3,
        stop_atr=1.0,
        tp_atr=3.0,
        max_hold_bars=10,
        lock_trigger_atr=1e6,
        trail_atr=0.0,
    ),
)
