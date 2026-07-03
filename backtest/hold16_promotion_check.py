"""Hold16 promotion-trigger helper.

The unconditional hold 8->16 change is validated in backtest but gated: do not promote it
until roughly 30-50 live v1.23 pure-bracket trades track the backtest distribution.

Input is the live_trades.json emitted by live_trade_report.py. This helper does not
promote anything; it prints whether the live sample is large enough and directionally
consistent enough for Fable 5 to review through the harness.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

BACKTEST = {
    "exp": 0.0778,
    "avg_win": 1.72,
    "pct_ge2": 16.6,
    "win_rate": 38.7,
}


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def load_trades(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        return list(data.get("trades", []))
    if isinstance(data, list):
        return data
    raise ValueError(f"unrecognized trade JSON shape in {path}")


def pure_bracket_trade(t: dict) -> bool:
    """Approximate v1.23 pure bracket from live_trade_report fields.

    Pure bracket exits should not involve a moved stop. TP, initial-SL, and time/manual EXPERT
    exits remain eligible. This keeps old lock/trail trades out of the promotion sample.
    """
    if t.get("r") is None:
        return False
    return not bool(t.get("stop_was_moved"))


def summarize(trades: list[dict]) -> dict:
    rs = [float(t["r"]) for t in trades if t.get("r") is not None]
    wins = [r for r in rs if r > 0]
    return {
        "n": len(rs),
        "sum_r": sum(rs),
        "exp": sum(rs) / len(rs) if rs else 0.0,
        "win_rate": len(wins) / len(rs) * 100 if rs else 0.0,
        "avg_win": sum(wins) / len(wins) if wins else 0.0,
        "pct_ge2": sum(1 for r in rs if r >= 2.0) / len(rs) * 100 if rs else 0.0,
    }


def tracking(stats: dict) -> tuple[bool, list[str]]:
    checks = [
        ("expectancy positive", stats["exp"] > 0.0),
        ("avg win >= 75% of backtest", stats["avg_win"] >= BACKTEST["avg_win"] * 0.75),
        (">=+2R share >= 60% of backtest", stats["pct_ge2"] >= BACKTEST["pct_ge2"] * 0.60),
        ("win rate not collapsed", stats["win_rate"] >= BACKTEST["win_rate"] * 0.70),
    ]
    failed = [name for name, ok in checks if not ok]
    return not failed, failed


def main() -> int:
    ap = argparse.ArgumentParser(description="Check hold16 live promotion trigger")
    ap.add_argument("--json", default="live_trades.json", help="live_trade_report.py JSON output")
    ap.add_argument("--since", default=None, metavar="YYYY-MM-DD HH:MM",
                    help="only trades opened at/after this server time count")
    ap.add_argument("--min-trades", type=int, default=30,
                    help="minimum live pure-bracket trades before any review")
    ap.add_argument("--target-trades", type=int, default=50,
                    help="preferred sample for promotion review")
    args = ap.parse_args()

    path = Path(args.json)
    if not path.exists():
        raise SystemExit(f"{path} not found; run live_trade_report.py first")

    trades = load_trades(path)
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d %H:%M")
        trades = [t for t in trades if parse_dt(t["t_open"]) >= since]
    eligible = [t for t in trades if pure_bracket_trade(t)]
    stats = summarize(eligible)
    ok, failed = tracking(stats)

    print("HOLD16 PROMOTION TRIGGER CHECK")
    print(f"sample: {stats['n']} live pure-bracket trades"
          + (f" opened >= {args.since}" if args.since else ""))
    print(f"backtest reference (pure bracket h8): exp {BACKTEST['exp']:+.4f}R, "
          f"avgWin {BACKTEST['avg_win']:.2f}R, >=+2R {BACKTEST['pct_ge2']:.1f}%, "
          f"win {BACKTEST['win_rate']:.1f}%")
    print(f"live sample: sumR {stats['sum_r']:+.2f}, exp {stats['exp']:+.4f}R, "
          f"avgWin {stats['avg_win']:.2f}R, >=+2R {stats['pct_ge2']:.1f}%, "
          f"win {stats['win_rate']:.1f}%")

    if stats["n"] < args.min_trades:
        print(f">>> VERDICT: PENDING - need >= {args.min_trades} live pure-bracket trades.")
        return 0
    if not ok:
        print(">>> VERDICT: HOLD - live sample is not tracking the backtest distribution.")
        print("    Failed checks: " + ", ".join(failed))
        return 2
    if stats["n"] < args.target_trades:
        print(f">>> VERDICT: WATCH - sample tracks so far, but prefer {args.target_trades} trades before review.")
        return 0
    print(">>> VERDICT: READY_FOR_FABLE_REVIEW - sample size and distribution trigger are met.")
    print("    Do not promote automatically; Fable 5 still owns the harness validation gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
