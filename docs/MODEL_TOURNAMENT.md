# Model Tournament Loop

This repo now has a reproducible loop for the workflow: independent models propose
EA improvements, the proposals compete on the same real-data gate, and only a
validated winner can replace the current main strategy.

## Roles

1. **Model agents** work independently. Each model submits a JSON candidate with:
   - `model`: model/agent identifier
   - `name`: short strategy name
   - `rationale`: why the change should help
   - `params`: `scalper_confluence.CParams` overrides
2. **Tournament runner** evaluates all submissions against the current main
   strategy (`v1.24` pure-bracket pullback) on real Deriv M15 spread-gated data.
3. **Champion promotion** happens only when a candidate earns `REPLACE`.

## Files

- `backtest/model_tournament.py` - evaluator/orchestrator
- `backtest/model_candidates.example.json` - submission template
- `backtest/model_candidates.json` - local tournament input (not committed unless desired)
- `backtest/model_tournament_report.md` - generated ranking report
- `backtest/champion_strategy.json` - generated only when a candidate replaces main

## Runbook

Fetch the source-of-truth data first:

```bash
cd backtest
python fetch_spreadgated.py
```

Have each model add its own candidate:

```bash
cp model_candidates.example.json model_candidates.json
python model_tournament.py --candidates model_candidates.json --list
```

Then run the tournament:

```bash
python model_tournament.py --candidates model_candidates.json
```

If no candidate earns `REPLACE`, the main strategy remains champion.

## Replacement gate

A candidate must pass all of these to replace the main strategy:

- keep HANDOFF guardrails: continuation pullback, no AVWAP default, TP >= 3.0
- use only parameters supported by the current EA defaults
- improve stitched OOS expectancy and total R vs the main strategy
- show paired/selectivity edge vs the main strategy
- WFE >= 0.30
- DSR >= 0.95, deflated for prior research plus tournament submissions
- positive OOS expectancy at 2x real spread cost
- at least 60% positive OOS quarters
- at least 60% positive eligible symbols
- powered OOS sample (N >= 250)

Simulator-only features can still be useful research winners, but they are marked
`RESEARCH-WIN` instead of `REPLACE` until the EA implements them and they pass the
same gate.

## Agent prompt template

Give each model a prompt like:

> Read `HANDOFF.md`, `docs/MODEL_TOURNAMENT.md`, and the backtest harness. Propose
> one conservative improvement to DerivScalperEA as a JSON candidate for
> `backtest/model_candidates.json`. Do not weaken the pullback entry, spread gate,
> no-AVWAP default, or TP>=3 guardrails. Optimize for out-of-sample robustness, not
> in-sample curve fit.

