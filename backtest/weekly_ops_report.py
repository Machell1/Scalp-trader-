"""Weekly operations report — single entrypoint for HANDOFF backlog #0 + #3.

Runs (in order, MT5 terminal must be open):
  1. fill_realism.py  — pullback-limit fill reconciliation (backlog #3)
  2. live_trade_report.py acceptance section — v1.21+ bar-close engine check (backlog #0)

Optional:
  --logs <dir>     pass through to fill_realism for SIGNAL-line reconciliation
  --accept-from    restrict acceptance check to trades opened after this time
  --atr-parity     also run atr_parity.py (P4 hygiene measurement)

Usage (weekly, with MT5 open):
  python weekly_ops_report.py
  python weekly_ops_report.py --logs /path/to/MQL5/Logs --atr-parity
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_script(name: str, extra: list[str] | None = None) -> int:
    cmd = [sys.executable, str(HERE / name)] + (extra or [])
    print(f"\n{'=' * 72}\n>>> {name}\n{'=' * 72}")
    return subprocess.call(cmd, cwd=str(HERE))


def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly fill realism + acceptance report")
    ap.add_argument("--logs", default=None, help="EA Experts log file/dir for fill_realism")
    ap.add_argument("--accept-from", default=None, metavar="YYYY-MM-DD HH:MM",
                    help="acceptance check: trades opened at/after this server time")
    ap.add_argument("--frm", default=None, metavar="YYYY-MM-DD",
                    help="history start for fill_realism (default in fill_realism.py)")
    ap.add_argument("--atr-parity", action="store_true",
                    help="also run atr_parity.py and print Wilder-vs-iATR delta")
    ap.add_argument("--atr-bars", type=int, default=5000,
                    help="M15 bars per symbol for atr_parity (default 5000)")
    args = ap.parse_args()

    print(f"WEEKLY OPS REPORT — {datetime.now():%Y-%m-%d %H:%M}")
    print("Requires MT5 terminal open and logged into the Deriv account.\n")

    fill_args = []
    if args.logs:
        fill_args += ["--logs", args.logs]
    if args.frm:
        fill_args += ["--frm", args.frm]

    rc = run_script("fill_realism.py", fill_args)
    if rc != 0:
        print(f"\nfill_realism.py exited {rc} — continuing to acceptance check anyway.")

    accept_args = []
    if args.accept_from:
        accept_args += ["--accept-from", args.accept_from]
    rc2 = run_script("live_trade_report.py", accept_args)

    rc3 = 0
    if args.atr_parity:
        rc3 = run_script("atr_parity.py", ["--bars", str(args.atr_bars)])

    print("\n" + "=" * 72)
    print("WEEKLY OPS SUMMARY")
    print("=" * 72)
    print(f"  fill_realism:        {'OK' if rc == 0 else f'exit {rc}'}")
    print(f"  acceptance check:    {'OK' if rc2 == 0 else f'exit {rc2}'}")
    if args.atr_parity:
        print(f"  atr_parity:          {'OK' if rc3 == 0 else f'exit {rc3}'}")
    print("\nReview fill_realism confusion matrix and acceptance VERDICT above.")
    print("HANDOFF #3 accept: harness fill model conservative; edge sign unchanged under pessimistic fill.")
    print("HANDOFF #0 accept: zero moved-stop exits with zero elapsed M15 bar-closes.")

    return max(rc, rc2, rc3)


if __name__ == "__main__":
    sys.exit(main())
