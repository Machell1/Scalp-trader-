# Model Arena — AI-vs-AI strategy improvement tournament

Multiple AI models each develop **one candidate improvement** to the
DerivScalper strategy. Candidates compete head-to-head on a hidden holdout;
the winner plays a **title match** against the reigning champion
(`champion.json` — the live v1.23 pure-bracket config). If the challenger
clears every gate, it **replaces the champion**.

> **Honesty note (read `HANDOFF.md`):** the arena runs on Yahoo proxy data
> (no MT5 in this environment), which the repo classifies as *screening only*.
> A promoted arena champion is a **staged** config — it must still clear the
> real-Deriv M15 walk-forward + DSR gate (`backtest/walkforward_dsr.py`)
> before anyone changes `mql5/DerivScalperEA.mq5` defaults or live settings.

## How it works

1. **Develop** — each model writes one file in `arena/candidates/` and may
   iterate using only the DEV split (first 70% of bars):
   `python backtest/arena.py --dev --candidate arena/candidates/<file>.py`
2. **Tournament** — all candidates are ranked on the hidden HOLDOUT split
   (last 30%): `python backtest/arena.py --tournament`
3. **Title match** — the tournament winner faces the champion with stricter
   gates: `python backtest/arena.py --title-match [--promote]`
4. **Promotion** — on a win with `--promote`, `champion.json` is updated and
   the old champion is archived in its `history`.

Every candidate is executed by the **same trusted simulator**
(`backtest/scalper_confluence.py`), so a candidate cannot cheat with custom
simulation code — it is purely a declarative parameter set.

## Candidate contract

One Python file in `arena/candidates/`, exposing a single dict:

```python
CANDIDATE = dict(
    name="my improvement",
    model="<model-slug>",            # who authored it
    kind="exit",                     # 'filter' | 'geom' | 'exit' | 'mixed'
    description="one-paragraph thesis: WHY this should beat the champion",
    overrides=dict(                  # CParams overrides vs dataclass defaults
        entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
        tp_atr=3.0, lock_trigger_atr=1e6, trail_atr=0.0, max_hold_bars=8,
        # ... your changes here ...
    ),
)
```

Start from the champion's overrides (above) and change what your thesis needs.
`kind="filter"` candidates additionally face a permutation test in the title
match (they must *select* good trades, not just randomly prune).

## Guardrails (mechanically enforced — see `ALLOWED` in `backtest/arena.py`)

- `entry_style` must stay `"limit"` (pullback entry IS the edge — HANDOFF #1).
- `tp_atr >= 3.0` (HANDOFF #2). No AVWAP (`vwap_window` is not settable —
  HANDOFF #3). Continuation only (`direction` not settable).
- Costs are runner-controlled: 0.02 ATR/side real, 0.04 stress.
- All numeric knobs are bounded to sane ranges; out-of-bounds ⇒ rejected at load.

## Title-match gates (challenger must pass ALL)

1. Marginal holdout expectancy > champion (combined datasets, real cost).
2. No 2×-cost regression (the strategy is cost-fragile by construction).
3. Consistency: not worse than champion by >0.005 R on either dataset
   (yahooM15 and yahooH1).
4. Sample floor: N ≥ max(150, 50 % of champion's N) — no decimating the sample.
5. Monthly sign stability on H1 holdout (≥ 50 % months positive).
6. (`filter` kind only) permutation p < 0.10.

## Files

- `champion.json` — reigning champion params + promotion history.
- `candidates/*.py` — one per model.
- `tournament_results.json` — machine-readable leaderboard of the last run.
- `../backtest/arena.py` — the runner (dev / tournament / title-match modes).
