"""Hold-16 promotion gate — live pure-bracket trades vs backtest distribution.

exit_ladder_study validated unconditional hold 8→16 (+0.0774R OOS, avg win 2.24R,
≥+2R 22.4%, 12/12 symbols) but GATED: promote only after ~30–50 live pure-bracket
trades track the backtest distribution.

This helper compares post-v1.23 pure-bracket live round trips against the
pre-registered backtest benchmarks. It does NOT promote automatically — Fable 5
owns the validation gate.

Backtest anchors (RESULTS.md §7, real cost, stitched OOS):
  pure bracket:  exp≈+0.0778R  avgWin≈1.72R  ≥+2R≈16.6%
  hold16:        exp≈+0.0774R  avgWin≈2.24R  ≥+2R≈22.4%

Promotion heuristic (conservative):
  * N >= 30 round trips on pure-bracket config (v1.23+, no lock/trail exits)
  * live exp within ±0.05R of bracket backtest AND sign positive
  * avg win within [1.2R, 2.0R] (bracket band)
  * no bar-close acceptance violations in the cohort

Run:
  python live_trade_report.py && python hold16_promotion_check.py
  python hold16_promotion_check.py --json live_trades.json
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

# v1.23 pure-bracket deploy (see CURSOR_HELPER_BRIEFS_2026-07-02)
DEPLOY_V123 = datetime(2026, 7, 2, 0, 0)
MIN_TRADES = 30
TARGET_TRADES = 50

BRACKET_BENCH = dict(exp=0.0778, avg_win=1.72, pct_ge2r=16.6)
HOLD16_BENCH = dict(exp=0.0774, avg_win=2.24, pct_ge2r=22.4)

EXP_TOL = 0.05
AVG_WIN_LO, AVG_WIN_HI = 1.20, 2.00


def load_trades(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"{path} not found — run live_trade_report.py first (MT5 open).")
    with open(path) as f:
        data = json.load(f)
    return data.get("trades", [])


def filter_pure_bracket(trades: list[dict], since: datetime) -> list[dict]:
    out = []
    for t in trades:
        if t.get("r") is None:
            continue
        opened = datetime.strptime(t["t_open"], "%Y-%m-%d %H:%M:%S")
        if opened < since:
            continue
        if t.get("stop_was_moved"):
            continue
        out.append(t)
    return out


def cohort_metrics(trades: list[dict]) -> dict:
    rs = np.array([t["r"] for t in trades], float)
    w = rs[rs > 0]
    return dict(
        n=len(rs),
        exp=float(rs.mean()) if rs.size else 0.0,
        avg_win=float(w.mean()) if w.size else 0.0,
        pct_ge2r=float((rs >= 2.0).mean() * 100) if rs.size else 0.0,
        win_pct=float((rs > 0).mean() * 100) if rs.size else 0.0,
    )


def evaluate(m: dict) -> tuple[str, list[str]]:
    notes: list[str] = []
    if m["n"] < MIN_TRADES:
        return "GATED (insufficient N)", [
            f"N={m['n']} < {MIN_TRADES} minimum — accumulate more pure-bracket live trades.",
            f"Target band: {MIN_TRADES}–{TARGET_TRADES} before promotion review.",
        ]
    if m["exp"] < 0:
        notes.append(f"live exp {m['exp']:+.3f}R is negative — do NOT promote hold16.")
        return "GATED (live underperforming)", notes
    if abs(m["exp"] - BRACKET_BENCH["exp"]) > EXP_TOL:
        notes.append(
            f"live exp {m['exp']:+.3f}R vs bracket backtest {BRACKET_BENCH['exp']:+.4f}R "
            f"(tolerance ±{EXP_TOL}R).")
    if not (AVG_WIN_LO <= m["avg_win"] <= AVG_WIN_HI):
        notes.append(
            f"avg win {m['avg_win']:.2f}R outside bracket band [{AVG_WIN_LO}, {AVG_WIN_HI}]R "
            f"(backtest {BRACKET_BENCH['avg_win']:.2f}R).")
    if (m["n"] >= TARGET_TRADES and m["exp"] > 0
            and abs(m["exp"] - BRACKET_BENCH["exp"]) <= EXP_TOL
            and AVG_WIN_LO <= m["avg_win"] <= AVG_WIN_HI):
        notes.append(
            "Live distribution tracks bracket backtest — eligible for Fable 5 hold16 re-gate "
            "(not automatic promotion).")
        return "ELIGIBLE FOR REVIEW", notes
    if m["n"] >= MIN_TRADES:
        notes.append(f"N={m['n']} in range but metrics not yet aligned — keep monitoring.")
    return "GATED (tracking)", notes


def main() -> int:
    ap = argparse.ArgumentParser(description="hold16 promotion gate check")
    ap.add_argument("--json", default=str(HERE / "live_trades.json"),
                    help="live_trades.json from live_trade_report.py")
    ap.add_argument("--since", default=None, metavar="YYYY-MM-DD HH:MM",
                    help=f"pure-bracket cohort start (default v1.23 {DEPLOY_V123})")
    ap.add_argument("--refresh", action="store_true",
                    help="run live_trade_report.py first (MT5 must be open)")
    args = ap.parse_args()
    since = (datetime.strptime(args.since, "%Y-%m-%d %H:%M")
             if args.since else DEPLOY_V123)

    if args.refresh:
        rc = subprocess.call([sys.executable, str(HERE / "live_trade_report.py")], cwd=str(HERE))
        if rc != 0:
            return rc

    cohort = filter_pure_bracket(load_trades(Path(args.json)), since)
    m = cohort_metrics(cohort)
    violations = [t for t in cohort if t.get("barclose_violation")]

    print("HOLD-16 PROMOTION GATE CHECK")
    print("=" * 64)
    print(f"Cohort: pure-bracket trades opened >= {since}")
    print(f"Backtest — bracket: exp {BRACKET_BENCH['exp']:+.4f}R  avgWin {BRACKET_BENCH['avg_win']:.2f}R  "
          f"≥+2R {BRACKET_BENCH['pct_ge2r']:.1f}%")
    print(f"           hold16: exp {HOLD16_BENCH['exp']:+.4f}R  avgWin {HOLD16_BENCH['avg_win']:.2f}R  "
          f"≥+2R {HOLD16_BENCH['pct_ge2r']:.1f}%")
    print(f"\nLive: N={m['n']}  exp={m['exp']:+.3f}R  avgWin={m['avg_win']:.2f}R  "
          f"≥+2R {m['pct_ge2r']:.1f}%  win% {m['win_pct']:.0f}%")
    if violations:
        print(f"\n[FAIL] {len(violations)} bar-close violations — halt promotion until engine is clean.")

    verdict, notes = evaluate(m)
    print(f"\n>>> VERDICT: {verdict}")
    for note in notes:
        print(f"    {note}")
    print("\nNecessary not sufficient: Fable 5 must re-run hold16 through the harness gate.")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
