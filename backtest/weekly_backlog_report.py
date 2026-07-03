"""Weekly backlog report entrypoint.

Runs the two live-operational checks that should be reviewed together:

  1. live_trade_report.py acceptance section (bar-close exit fidelity)
  2. fill_realism.py pullback-limit fill reconciliation

It also runs the hold16 promotion helper from the live_trade_report output when
available, and can include the ATR parity measurement on demand.

Run on the machine with MT5 open:
  python weekly_backlog_report.py --logs <experts-log-dir> --hold16-since "YYYY-MM-DD HH:MM"
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_section(title: str, cmd: list[str], keep_going: bool) -> int:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)
    print("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=HERE)
    if proc.returncode and not keep_going:
        raise SystemExit(proc.returncode)
    if proc.returncode:
        print(f"[WARN] section exited {proc.returncode}; continuing because --keep-going is set.")
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly live acceptance + fill-realism report")
    ap.add_argument("--accept-from", default=None, metavar="YYYY-MM-DD HH:MM",
                    help="passed through to live_trade_report.py")
    ap.add_argument("--frm", default=None, metavar="YYYY-MM-DD",
                    help="passed through to fill_realism.py")
    ap.add_argument("--logs", default=None, help="EA Experts log file/dir for fill_realism.py")
    ap.add_argument("--hold16-since", default=None, metavar="YYYY-MM-DD HH:MM",
                    help="only live_trades.json trades opened at/after this time count for hold16")
    ap.add_argument("--hold16-min", type=int, default=30, help="minimum live pure-bracket trades")
    ap.add_argument("--hold16-target", type=int, default=50, help="preferred review sample")
    ap.add_argument("--include-atr-parity", action="store_true",
                    help="also run atr_parity.py; requires MT5 history access")
    ap.add_argument("--atr-bars", type=int, default=5000, help="bars per symbol for atr_parity.py")
    ap.add_argument("--keep-going", action="store_true",
                    help="continue later sections if one report fails")
    args = ap.parse_args()

    py = sys.executable
    live = [py, "live_trade_report.py"]
    if args.accept_from:
        live += ["--accept-from", args.accept_from]
    fill = [py, "fill_realism.py"]
    if args.frm:
        fill += ["--frm", args.frm]
    if args.logs:
        fill += ["--logs", args.logs]

    rc = 0
    rc |= run_section("1) LIVE TRADE REPORT + ACCEPTANCE CHECK", live, args.keep_going)
    rc |= run_section("2) FILL REALISM REPORT", fill, args.keep_going)

    hold = [py, "hold16_promotion_check.py", "--json", "live_trades.json",
            "--min-trades", str(args.hold16_min), "--target-trades", str(args.hold16_target)]
    if args.hold16_since:
        hold += ["--since", args.hold16_since]
    rc |= run_section("3) HOLD16 PROMOTION TRIGGER CHECK", hold, args.keep_going)

    if args.include_atr_parity:
        atr = [py, "atr_parity.py", "--bars", str(args.atr_bars)]
        rc |= run_section("4) ATR PARITY DELTA REPORT", atr, args.keep_going)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
