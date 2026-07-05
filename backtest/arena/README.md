# Model Arena — Competitive Strategy Improvement

Each AI model develops EA improvements **independently**, submits them as JSON
candidates, and they **compete** in a tournament. The top qualifier faces the
**champion** (main strategy). If the challenger clears all SHIP gates and beats
the champion on marginal OOS expectancy, it **replaces** the champion.

Nothing auto-deploys to the live EA. Promotion updates `champion.json`; a human
(or director agent) must still apply changes to `mql5/DerivScalperEA.mq5`.

## Quick start

```bash
cd backtest

# 1. Ensure spread-gated data exists (MT5 terminal open)
python fetch_spreadgated.py

# 2. Check arena status
python model_arena.py status

# 3. Each model writes a submission (see template below)
python model_arena.py template > arena/submissions/composer-2.5/my-candidate.json
# edit the file with your hypothesis and param overrides

# 4. Run the tournament
python model_arena.py run

# 5. Promote winner if it beats champion (updates champion.json)
python model_arena.py run --promote
```

## Tournament rules

### Round 1 — Model vs Model

- Each model may submit **multiple** candidates under `arena/submissions/<model_id>/`.
- Only the **best submission per model** (highest marginal OOS dExp vs champion) advances.
- Models are ranked by dExp; ties break on DSR, then raw OOS exp.

### Round 2 — Champion Challenge

The top qualifier must:

1. Beat the champion on **marginal OOS dExp** (dExp > 0)
2. Pass **all SHIP gates** (same bar as `experiment.py` / `exit_ladder_study.py`):
   - Selection test: permutation p < 0.05 (filters) OR dExp>0 & dTotR>0 (geometry) OR paired t > 1.96 (exits)
   - WFE ≥ 0.30
   - DSR ≥ 0.95 (deflated for cumulative research trials)
   - Powered sample (N ≥ 250, exp > MDE)
   - Positive at 2× cost stress
   - ≥ 60% OOS quarters positive
   - ≥ 60% symbols positive

### Promotion

If the challenger **wins**, `python model_arena.py run --promote` updates
`arena/champion.json` and appends to `arena/history/promotions.jsonl`.

The new champion's `params` dict is the source of truth for the next tournament
and for manual EA sync.

## Submission schema

Place one JSON file per candidate at:

```
arena/submissions/<model_id>/<candidate_id>.json
```

Required fields:

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | string | Model identifier (folder name) |
| `candidate_id` | string | Short slug (filename without .json) |
| `label` | string | Human-readable name |
| `kind` | string | `geom`, `filter`, or `exit` |
| `hypothesis` | string | Why this should improve OOS expectancy |
| `params` | object | **Marginal overrides** vs champion (not full config) |
| `created_at` | string | ISO 8601 timestamp |

### `kind` values

- **`geom`** — entry geometry, stop/TP/hold changes (dExp + dTotR gate)
- **`filter`** — confluence filter (permutation test gate)
- **`exit`** — exit-engine changes (paired per-signal t-test gate)

### Allowed `params` keys

Any field from `scalper_confluence.CParams`. Common overrides:

```json
{
  "entry_offset_atr": 0.5,
  "tp_atr": 3.5,
  "max_hold_bars": 16,
  "lock_trigger_atr": 99.0,
  "trail_atr": 99.0,
  "momentum_atr": 2.0,
  "adx_min": 20.0
}
```

Use `lock_trigger_atr: 99.0` and `trail_atr: 99.0` for pure bracket (v1.23 default).

## Hard guardrails (from HANDOFF.md)

Submissions that violate these will fail or should not be proposed:

- Do **not** revert to STOP breakout entry (destroys the edge)
- Do **not** shrink TP below 3.0 ATR without evidence
- Do **not** re-enable AVWAP as default
- Do **not** remove spread/ATR gate or whitelist without re-validation
- Do **not** port to higher timeframes

## Directory layout

```
arena/
  champion.json          # Reigning main strategy config
  README.md              # This file
  submissions/           # Model candidates (one folder per model)
    composer-2.5/
    gpt-5.5/
    claude-opus/
  results/               # Tournament output (auto-generated)
    latest.json
    tournament_YYYYMMDDTHHMMSSZ.json
  history/
    promotions.jsonl     # Promotion audit trail
```

## Example submissions

See `arena/submissions/example-model/` for placeholder candidates that demonstrate
the format. **Do not treat example submissions as real hypotheses** — replace them
with your model's own work.

## Evaluation data

The arena uses the **spread-gated 12-major universe** with **real per-instrument
Deriv spread cost** — the same protocol as `walkforward_dsr.py` and
`exit_ladder_study.py`. Yahoo proxy data is not accepted.

## Director workflow (multi-model orchestration)

Recommended flow when running multiple models in parallel:

1. **Director** (e.g. Fable 5) sets the tournament round and deadline
2. Each **model** independently reads HANDOFF.md, develops a hypothesis, writes submission JSON
3. **Director** runs `python model_arena.py run` after all submissions are in
4. **Director** reviews the qualifier's gate table; if SHIP, runs `--promote`
5. **Implementer** syncs winning params to the EA, compiles, demo-tests, deploys

This keeps model creativity independent while ensuring a single validation gate
decides what replaces the main strategy.
