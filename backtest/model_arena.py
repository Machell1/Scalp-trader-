#!/usr/bin/env python3
"""Model Arena — competitive strategy improvement tournament.

Each AI model develops EA improvements independently, submits them as JSON
candidates, and they compete in a round-robin. The top qualifier faces the
reigning champion (main strategy). If the challenger clears all SHIP gates and
beats the champion on marginal OOS expectancy, it replaces the champion.

Workflow
--------
1. Each model writes a submission JSON to arena/submissions/<model_id>/<name>.json
2. Run the tournament:  python model_arena.py run
3. Optionally promote:   python model_arena.py run --promote

Nothing reaches the live EA until a challenger wins the champion gate AND a
human (or director agent) applies the param diff to DerivScalperEA.mq5.

See arena/README.md for the submission schema and rules.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from arena_gate import (
    ARENA_DIR,
    CHAMPION_PATH,
    EvalResult,
    best_per_model,
    load_champion,
    load_submissions,
    run_evaluation,
    save_champion,
)

RESULTS_DIR = os.path.join(ARENA_DIR, "results")
HISTORY_DIR = os.path.join(ARENA_DIR, "history")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def print_result_row(r: EvalResult, rank: int | None = None) -> None:
    prefix = f"#{rank} " if rank is not None else "    "
    wfe = f"{r.wfe:.2f}" if r.wfe == r.wfe else " nan"
    pt = f"{r.pair_t:+.2f}" if r.pair_t == r.pair_t else "  --"
    print(
        f"{prefix}{r.model_id:18s} {r.label:32s} "
        f"N={r.n_oos:5d} exp={r.oos_exp:+.4f} dExp={r.d_exp:+.4f} "
        f"pair_t={pt} WFE={wfe} DSR={r.dsr:.2f}  {r.verdict}"
    )


def cmd_status(_args) -> int:
    champion = load_champion()
    subs = load_submissions()
    models = sorted({s.get("model_id", "?") for s in subs})

    print("=" * 72)
    print("MODEL ARENA — STATUS")
    print("=" * 72)
    print(f"Champion: {champion.get('label', '?')}  (v{champion.get('version', '?')})")
    print(f"  Held by: {champion.get('model_id', 'baseline')}")
    print(f"  Promoted: {champion.get('promoted_at') or 'initial (validated baseline)'}")
    print(f"  Cumulative trials (DSR): {champion.get('n_cumulative_trials', 68)}")
    print(f"\nPending submissions: {len(subs)} from {len(models)} model(s)")
    for s in subs:
        print(f"  [{s.get('model_id')}] {s.get('label', s.get('candidate_id'))}  ({s.get('kind', 'geom')})")
    if not subs:
        print("  (none — add JSON files under arena/submissions/<model_id>/)")
    return 0


def cmd_run(args) -> int:
    try:
        champion, champ_eval, results = run_evaluation(is_frac=args.is_frac)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    finalists = best_per_model(results)
    qualified = [r for r in finalists if r.qualifies]

    print("=" * 72)
    print("MODEL ARENA — TOURNAMENT")
    print("=" * 72)
    print(f"Champion: {champion.get('label')}  exp={champ_eval.oos_exp:+.4f}  N={champ_eval.n_oos}")
    print(f"Submissions evaluated: {len(results)}\n")

    print("--- Round 1: Model vs Model (best submission per model, ranked by dExp) ---")
    if not finalists:
        print("  No submissions found.")
    for i, r in enumerate(finalists, 1):
        print_result_row(r, i)

    print("\n--- Round 2: Champion Challenge ---")
    if not qualified:
        print("  No qualifier cleared the minimum bar (dExp>0, exp>0, 2× cost>0).")
        winner = None
    else:
        winner = qualified[0]
        print(f"  Qualifier: [{winner.model_id}] {winner.label}")
        print(f"  vs Champion exp={champ_eval.oos_exp:+.4f}  →  dExp={winner.d_exp:+.4f}")
        print("\n  Gate results:")
        for name, passed in winner.gates.items():
            mark = "PASS" if passed else "FAIL"
            print(f"    [{mark}] {name}")
        if winner.beats_champion:
            print(f"\n  >>> CHALLENGER WINS — {winner.verdict} with positive marginal edge")
        elif winner.verdict == "watch":
            print("\n  >>> CHALLENGER LEADS on dExp but did not clear all SHIP gates (watch)")
        else:
            print("\n  >>> CHAMPION HOLDS — challenger did not beat the gate")

    # Persist results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "run_at": _utcnow(),
        "champion": {
            "label": champion.get("label"),
            "version": champion.get("version"),
            "model_id": champion.get("model_id"),
            "oos_exp": champ_eval.oos_exp,
            "n_oos": champ_eval.n_oos,
        },
        "round1": [r.to_dict() for r in finalists],
        "all_submissions": [r.to_dict() for r in results],
        "qualifier": winner.to_dict() if winner else None,
        "champion_retained": not (winner and winner.beats_champion),
    }
    out_path = os.path.join(RESULTS_DIR, f"tournament_{ts}.json")
    latest_path = os.path.join(RESULTS_DIR, "latest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"\nResults saved: {out_path}")

    if args.promote and winner and winner.beats_champion:
        return cmd_promote(winner, champion, args)
    return 0


def cmd_promote(winner: EvalResult, champion: dict, args) -> int:
    """Replace champion with the winning challenger."""
    old_version = champion.get("version", "1.23")
    try:
        major, minor = old_version.split(".")
        new_version = f"{major}.{int(minor) + 1}"
    except ValueError:
        new_version = old_version + "-arena"

    new_champion = {
        "version": new_version,
        "label": winner.label,
        "model_id": winner.model_id,
        "promoted_at": _utcnow(),
        "promoted_from": {
            "version": old_version,
            "label": champion.get("label"),
            "model_id": champion.get("model_id"),
        },
        "n_cumulative_trials": int(champion.get("n_cumulative_trials", 68)) + 1,
        "params": winner.params,
        "arena_result": winner.to_dict(),
    }
    save_champion(new_champion)

    os.makedirs(HISTORY_DIR, exist_ok=True)
    hist_path = os.path.join(HISTORY_DIR, "promotions.jsonl")
    with open(hist_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": _utcnow(), "new": new_champion}) + "\n")

    print("\n" + "=" * 72)
    print("PROMOTION")
    print("=" * 72)
    print(f"Champion updated: {old_version} → {new_version}")
    print(f"New holder: [{winner.model_id}] {winner.label}")
    print(f"Saved to: {CHAMPION_PATH}")
    print("\nNext steps (manual):")
    print("  1. Diff winner.params against EA inputs in mql5/DerivScalperEA.mq5")
    print("  2. Compile in MetaEditor, demo forward-test, then redeploy")
    print("  3. Update HANDOFF.md and RESULTS.md with promotion evidence")
    return 0


def cmd_template(_args) -> int:
    tpl = {
        "model_id": "your-model-name",
        "candidate_id": "short-slug",
        "label": "Human-readable hypothesis name",
        "kind": "geom",
        "hypothesis": "One paragraph: why this should improve OOS expectancy without breaking validated facts.",
        "params": {
            "entry_offset_atr": 0.6,
            "tp_atr": 3.0,
            "max_hold_bars": 8
        },
        "created_at": _utcnow(),
    }
    print(json.dumps(tpl, indent=2))
    return 0


def cmd_init(_args) -> int:
    """Write champion.json if missing."""
    if os.path.isfile(CHAMPION_PATH):
        print(f"Champion already exists: {CHAMPION_PATH}")
        return 0
    from arena_gate import default_champion_params, save_champion as sc
    sc({
        "version": "1.23",
        "label": "Pure bracket pullback 0.6 / TP 3 / hold 8",
        "model_id": "baseline",
        "promoted_at": None,
        "n_cumulative_trials": 68,
        "params": default_champion_params(),
    })
    print(f"Initialized champion: {CHAMPION_PATH}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Model Arena — competitive EA improvement tournament")
    sub = ap.add_subparsers(dest="cmd")

    p_status = sub.add_parser("status", help="Show champion and pending submissions")
    p_status.set_defaults(func=cmd_status)

    p_run = sub.add_parser("run", help="Run tournament and optional champion challenge")
    p_run.add_argument("--promote", action="store_true", help="Promote winner if it beats champion")
    p_run.add_argument("--is-frac", type=float, default=0.70, help="IS fraction for quarter split")
    p_run.set_defaults(func=cmd_run)

    p_tpl = sub.add_parser("template", help="Print a submission JSON template")
    p_tpl.set_defaults(func=cmd_template)

    p_init = sub.add_parser("init", help="Initialize champion.json from validated baseline")
    p_init.set_defaults(func=cmd_init)

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
