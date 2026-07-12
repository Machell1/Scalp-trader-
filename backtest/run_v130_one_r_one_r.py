"""Run the preregistered v1.30 full-position 1R:1R development screen."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "V130_ONE_R_ONE_R_REPAIR_SPEC_2026-07-12.md"
PROTOCOL_SHA256 = "9a32d3f85f9107e175693f40cb5cef2b1eaf779708ff350051cf0a34ce4770f3"
RESULT = HERE / "v130_one_r_one_r_results.json"

sys.path.insert(0, str(HERE))
from parity_engine import prep_symbol
from retest_engine import Cell, SPREAD_DIR, TRIO, run_cell
from walkforward_dsr import real_cost_per_side


def protocol_hash() -> str:
    raw = subprocess.check_output(
        ["git", "show", f"HEAD:{SPEC.relative_to(ROOT).as_posix()}"], cwd=ROOT
    )
    lines = raw.splitlines(keepends=True)
    end = next(i for i, line in enumerate(lines) if line.startswith(b"**PRE-REGISTRATION ENDS"))
    actual = hashlib.sha256(b"".join(lines[: end + 1])).hexdigest()
    if actual != PROTOCOL_SHA256:
        raise RuntimeError(f"protocol hash mismatch: {actual}")
    return actual


def verify_clean_dependencies() -> str:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = (
        "docs/V130_ONE_R_ONE_R_SPEC_2026-07-12.md",
        "docs/V130_ONE_R_ONE_R_REPAIR_SPEC_2026-07-12.md",
        "backtest/run_v130_one_r_one_r.py",
        "backtest/retest_engine.py",
        "backtest/parity_engine.py",
        "backtest/walkforward_dsr.py",
    )
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--", *paths], cwd=ROOT, text=True
    ).strip()
    if status:
        raise RuntimeError(f"dirty registered dependency:\n{status}")
    for path in paths:
        subprocess.check_call(["git", "cat-file", "-e", f"HEAD:{path}"], cwd=ROOT)
    return commit


def summarize(rows: list[dict]) -> dict:
    r = np.asarray([row["r"] for row in rows], dtype=float)
    return {
        "n": int(len(r)),
        "win_rate": float(np.mean(r > 0.0)) if len(r) else None,
        "expectancy_r": float(np.mean(r)) if len(r) else None,
        "total_r": float(np.sum(r)),
    }


def main() -> None:
    if RESULT.exists():
        raise RuntimeError(f"refusing to overwrite {RESULT}")
    protocol = protocol_hash()
    commit = verify_clean_dependencies()
    print(f"verified 1R:1R protocol SHA256 {protocol}")
    subprocess.check_call([sys.executable, str(HERE / "verify_data.py")], cwd=ROOT)

    cells = {
        "CONTROL_V130": Cell(
            "CONTROL_V130", tp=2.0, so_frac=0.50, so_at=1.0
        ),
        "CANDIDATE_FULL_TP1": Cell("CANDIDATE_FULL_TP1", tp=1.0),
    }
    cell_rows: dict[str, list[dict]] = {name: [] for name in cells}
    symbol_oos: dict[str, set[str]] = {}
    complete_oos: dict[str, set[str]] = {}

    for symbol in TRIO:
        path = Path(SPREAD_DIR) / f"{symbol}.csv"
        raw = pd.read_csv(path)
        time_col = next(col for col in raw.columns if col.lower() == "time")
        times = pd.to_datetime(raw[time_col], utc=True)
        quarters = pd.PeriodIndex(times.dt.tz_convert(None), freq="Q")
        ordered = sorted(set(str(q) for q in quarters))
        oos = set(ordered[int(len(ordered) * 0.7):])
        symbol_oos[symbol] = oos
        complete = set()
        tmin, tmax = times.min().tz_convert(None), times.max().tz_convert(None)
        for quarter in oos:
            period = pd.Period(quarter, freq="Q")
            if tmin <= period.start_time and tmax >= period.end_time.floor("min"):
                complete.add(quarter)
        complete_oos[symbol] = complete

        prepared = prep_symbol(raw, real_cost_per_side(raw), symbol)
        for name, cell in cells.items():
            for epoch, r_value in run_cell(prepared, cell):
                quarter = str(pd.Timestamp(epoch, unit="s", tz="UTC").to_period("Q"))
                cell_rows[name].append(
                    {"symbol": symbol, "epoch": int(epoch), "quarter": quarter, "r": float(r_value)}
                )

    results: dict[str, dict] = {}
    for name, rows in cell_rows.items():
        oos_rows = [row for row in rows if row["quarter"] in symbol_oos[row["symbol"]]]
        by_symbol = {
            symbol: summarize([row for row in oos_rows if row["symbol"] == symbol])
            for symbol in TRIO
        }
        quarter_keys = sorted({row["quarter"] for row in oos_rows})
        by_quarter = {
            quarter: summarize([row for row in oos_rows if row["quarter"] == quarter])
            for quarter in quarter_keys
        }
        results[name] = {
            "all": summarize(rows),
            "stitched_oos": summarize(oos_rows),
            "stitched_oos_by_symbol": by_symbol,
            "stitched_oos_by_quarter": by_quarter,
        }

    control = results["CONTROL_V130"]["stitched_oos"]
    candidate = results["CANDIDATE_FULL_TP1"]["stitched_oos"]
    complete_quarters = sorted(set.intersection(*[complete_oos[s] for s in TRIO]))
    gates = {
        "pooled_oos_win_rate_gt_80pct": candidate["win_rate"] > 0.80,
        "pooled_oos_expectancy_positive": candidate["expectancy_r"] > 0.0,
        "pooled_oos_expectancy_not_below_control": candidate["expectancy_r"] >= control["expectancy_r"],
        "every_symbol_oos_expectancy_positive": all(
            results["CANDIDATE_FULL_TP1"]["stitched_oos_by_symbol"][s]["expectancy_r"] > 0.0
            for s in TRIO
        ),
        "every_complete_oos_quarter_positive": all(
            results["CANDIDATE_FULL_TP1"]["stitched_oos_by_quarter"][q]["expectancy_r"] > 0.0
            for q in complete_quarters
        ),
    }
    output = {
        "protocol_sha256": protocol,
        "commit": commit,
        "ledger": {"start": 209, "end": 210, "charged_cells": 1},
        "complete_pooled_oos_quarters": complete_quarters,
        "results": results,
        "candidate_minus_control_oos": {
            "n": candidate["n"] - control["n"],
            "win_rate": candidate["win_rate"] - control["win_rate"],
            "expectancy_r": candidate["expectancy_r"] - control["expectancy_r"],
            "total_r": candidate["total_r"] - control["total_r"],
        },
        "gates": gates,
        "verdict": "ADVANCE" if all(gates.values()) else "DISPOSE",
    }
    RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    print(f"RESULT_FILE={RESULT}")


if __name__ == "__main__":
    main()
