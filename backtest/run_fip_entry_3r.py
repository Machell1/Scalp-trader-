"""Run the preregistered smooth-impulse FIP entry study."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "FIP_ENTRY_3R_SPEC_2026-07-12.md"
PROTOCOL_SHA256 = "f5d20adc0f9d3d8535a8c4b585f4ef2c6fa5a82261b66d5b3073299325d79ad4"
RESULT = HERE / "fip_entry_3r_results.json"
BUFFER = 0.02

sys.path.insert(0, str(HERE))
from fip_entry_3r import fip4of5, self_test
from parity_engine import prep_symbol
from retest_engine import SPREAD_DIR, TRIO
from retest_fillrealism import run
from walkforward_dsr import real_cost_per_side

CONTROL_HASHES = {
    ("Wall_Street_30", 0.00): (1279, "5f3046b10d91c11632391ccad4a88eaf4029dd392303e8457c9c5838900b64d2"),
    ("Wall_Street_30", 0.02): (1256, "63c2dfdef6ed6d839f77ddecf111582de1e54e4ca6774c88f2d4f7a9a0c6ec4b"),
    ("Wall_Street_30", 0.05): (1228, "83cb337253466d36462224f50b5a6fcfea280d47572b60fac83bc5fb5c2b90f1"),
    ("US_Tech_100", 0.00): (1232, "d1ad13795d5b83cdde3db6dd45ec81ca7bf8640756173f6d920f58a5d717c206"),
    ("US_Tech_100", 0.02): (1206, "c8d0c24aa5fd6fc571b1b17937aade8e4553db44f9d0f3cc57b6ff39a48a8346"),
    ("US_Tech_100", 0.05): (1178, "29f854d72945b39c89aae7640715288f4d117fc634d2857799c8de3e44698520"),
    ("Japan_225", 0.00): (1153, "407314b9c2ebe5379ec275c129d82d28b338f2f66b47e5891ca289eb782390f5"),
    ("Japan_225", 0.02): (1131, "a05673b0553894f5abfee74147e2bd06a0063a9503622cb5e83e4c56174d775c"),
    ("Japan_225", 0.05): (1111, "7a0734beb906bdd00b88734ecff54fba46757c8dd7517aac7f98c50098adfe8b"),
}


def protocol_hash():
    raw = subprocess.check_output(
        ["git", "show", f"HEAD:{SPEC.relative_to(ROOT).as_posix()}"], cwd=ROOT
    )
    lines = raw.splitlines(keepends=True)
    end = next(i for i, line in enumerate(lines) if line.startswith(b"**PRE-REGISTRATION ENDS"))
    actual = hashlib.sha256(b"".join(lines[:end + 1])).hexdigest()
    if actual != PROTOCOL_SHA256:
        raise RuntimeError(f"protocol hash mismatch: {actual}")
    return actual


def clean_dependencies():
    paths = (
        "docs/FIP_ENTRY_3R_SPEC_2026-07-12.md",
        "backtest/retest_fillrealism.py",
        "backtest/fip_entry_3r.py",
        "backtest/run_fip_entry_3r.py",
        "backtest/parity_engine.py",
        "backtest/retest_engine.py",
        "backtest/walkforward_dsr.py",
    )
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--", *paths], cwd=ROOT, text=True
    ).strip()
    if status:
        raise RuntimeError(f"dirty registered dependency:\n{status}")
    for path in paths:
        subprocess.check_call(["git", "cat-file", "-e", f"HEAD:{path}"], cwd=ROOT)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def tape_hash(rows):
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def summarize(rows):
    values = np.asarray([row["r"] for row in rows], dtype=float)
    return {
        "n": int(len(values)),
        "win_rate": float(np.mean(values > 0.0)) if len(values) else None,
        "expectancy_r": float(np.mean(values)) if len(values) else None,
        "total_r": float(np.sum(values)),
    }


def main():
    if RESULT.exists():
        raise RuntimeError(f"refusing to overwrite {RESULT}")
    protocol = protocol_hash()
    commit = clean_dependencies()
    print(f"verified FIP-entry protocol SHA256 {protocol}", flush=True)
    subprocess.check_call([sys.executable, str(HERE / "verify_data.py")], cwd=ROOT)
    self_test()

    prepared, oos_quarters, complete_oos = {}, {}, {}
    for symbol in TRIO:
        raw = pd.read_csv(os.path.join(SPREAD_DIR, symbol + ".csv"))
        time_col = next(col for col in raw.columns if col.lower() == "time")
        times = pd.to_datetime(raw[time_col], utc=True)
        quarters = pd.PeriodIndex(times.dt.tz_convert(None), freq="Q")
        ordered = sorted(set(str(q) for q in quarters))
        oos_quarters[symbol] = set(ordered[int(len(ordered) * 0.7):])
        tmin, tmax = times.min().tz_convert(None), times.max().tz_convert(None)
        complete_oos[symbol] = {
            q for q in oos_quarters[symbol]
            if tmin <= pd.Period(q, freq="Q").start_time
            and tmax >= pd.Period(q, freq="Q").end_time.floor("min")
        }
        prepared[symbol] = prep_symbol(raw, real_cost_per_side(raw), symbol)

    regression = {}
    for symbol, s in prepared.items():
        for buf in (0.00, 0.02, 0.05):
            rows = run(s, 3.0, 0.0, 0.0, buf)
            expected_n, expected_hash = CONTROL_HASHES[(symbol, buf)]
            actual_hash = tape_hash(rows)
            passed = len(rows) == expected_n and actual_hash == expected_hash
            regression[f"{symbol}@{buf:.2f}"] = {
                "n": len(rows), "sha256": actual_hash, "passed": passed,
            }
            if not passed:
                raise RuntimeError(f"default regression mismatch: {symbol}@{buf:.2f}")
    print("default-mode regression: 9 identical, 0 failed", flush=True)

    cells = {"C0_PASSIVE_3R": [], "F1_FIP4OF5_3R": []}
    diagnostics = {}
    for symbol, s in prepared.items():
        control = run(s, 3.0, 0.0, 0.0, BUFFER)
        candidate, diag = run(
            s, 3.0, 0.0, 0.0, BUFFER,
            pre_entry=fip4of5, return_diag=True,
        )
        diagnostics[symbol] = diag
        for name, rows in (("C0_PASSIVE_3R", control), ("F1_FIP4OF5_3R", candidate)):
            for epoch, r_value in rows:
                quarter = str(pd.Timestamp(epoch, unit="s", tz="UTC").tz_localize(None).to_period("Q"))
                cells[name].append({
                    "symbol": symbol, "epoch": int(epoch), "quarter": quarter,
                    "r": float(r_value),
                })

    results = {}
    for name, rows in cells.items():
        oos = [row for row in rows if row["quarter"] in oos_quarters[row["symbol"]]]
        results[name] = {
            "all": summarize(rows),
            "stitched_oos": summarize(oos),
            "stitched_oos_by_symbol": {
                symbol: summarize([row for row in oos if row["symbol"] == symbol])
                for symbol in TRIO
            },
            "stitched_oos_by_quarter": {
                q: summarize([row for row in oos if row["quarter"] == q])
                for q in sorted({row["quarter"] for row in oos})
            },
        }

    c0 = results["C0_PASSIVE_3R"]["stitched_oos"]
    f1 = results["F1_FIP4OF5_3R"]["stitched_oos"]
    complete = sorted(set.intersection(*[complete_oos[s] for s in TRIO]))
    gates = {
        "oos_win_rate_lift_at_least_5pp": f1["win_rate"] >= c0["win_rate"] + 0.05,
        "oos_expectancy_positive": f1["expectancy_r"] > 0.0,
        "oos_expectancy_not_below_control": f1["expectancy_r"] >= c0["expectancy_r"],
        "every_symbol_oos_expectancy_positive": all(
            results["F1_FIP4OF5_3R"]["stitched_oos_by_symbol"][s]["expectancy_r"] > 0
            for s in TRIO
        ),
        "every_complete_oos_quarter_positive": all(
            results["F1_FIP4OF5_3R"]["stitched_oos_by_quarter"][q]["expectancy_r"] > 0
            for q in complete
        ),
        "oos_trade_retention_at_least_35pct": f1["n"] >= 0.35 * c0["n"],
        "default_regression_and_synthetic_pass": all(x["passed"] for x in regression.values()),
    }
    diag_total = {key: sum(x[key] for x in diagnostics.values()) for key in next(iter(diagnostics.values()))}
    diag_total["eligibility_rate"] = (
        diag_total["predicate_eligible"] / diag_total["frozen_signals"]
        if diag_total["frozen_signals"] else None
    )
    output = {
        "protocol_sha256": protocol,
        "commit": commit,
        "ledger": {"working_start": 213, "working_end": 214, "charged_cells": 1},
        "regression": regression,
        "complete_pooled_oos_quarters": complete,
        "results": results,
        "fip_diagnostics_all": diag_total,
        "fip_diagnostics_by_symbol_all": diagnostics,
        "candidate_minus_control_oos": {
            "n": f1["n"] - c0["n"],
            "retention": f1["n"] / c0["n"],
            "win_rate": f1["win_rate"] - c0["win_rate"],
            "expectancy_r": f1["expectancy_r"] - c0["expectancy_r"],
            "total_r": f1["total_r"] - c0["total_r"],
        },
        "win_rate_above_80pct_diagnostic": f1["win_rate"] > 0.80,
        "gates": gates,
        "verdict": "ADVANCE" if all(gates.values()) else "DISPOSE",
        "confirmation_accessed": False,
        "blind_holdout_accessed": False,
        "ftmo_mc_paths": 0,
        "terminal_writes": 0,
    }
    RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(output, indent=2, sort_keys=True), flush=True)
    print(f"RESULT_FILE={RESULT}", flush=True)


if __name__ == "__main__":
    main()
