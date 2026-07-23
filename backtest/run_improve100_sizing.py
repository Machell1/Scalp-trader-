"""IMPROVE-100 family S screen (docs/IMPROVE100_SPEC_2026-07-15.md, hash 562bbffa...).

Runnable cells: S01, S02, S16 (pure RiskPolicy phase mappings on the deployed
tape). All other S RUN cells are FORFEIT(harness): the registered C# kernel
hardcodes concurrency caps and has no rule hooks for budgets/locks/ramps —
testing them would require engine surgery plus its own parity re-validation,
out of scope for this screen. Mirrors run_h1_xauusd_risk.py.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from build_h1_universe_tape import build_h1_universe_tape, ftmo_metas
from run_h1_universe_account import BASE_SOURCES, common_bootstrap, configure_symbols
import v130_pass_policy_csharp as csharp_engine
from v130_pass_policy import BootstrapSpec, CompactRun, EquityMode, RiskPolicy, SimulationConfig, run_monte_carlo

HERE = Path(__file__).resolve().parent
RESULT = HERE / "improve100_sizing_results.json"
SPEC = HERE.parent / "docs" / "IMPROVE100_SPEC_2026-07-15.md"
SOURCES = BASE_SOURCES + ("USDJPY",)
BOOT_SEED = 13020260711
SCREEN_PATHS = 20_000
CONFIRM_PATHS = 100_000
CHUNK = 500
ABSOLUTE_GATE = 0.78887

IDX = ("US30.cash", "US100.cash", "JP225.cash")

FORFEITS = {
    "S04": "worst-case day budget needs an entry-blocking rule hook absent from the C# kernel",
    "S06": "daily profit lock needs a day-P&L entry hook absent from the kernel",
    "S08": "cushion glide needs phase-progress-conditional risk absent from the kernel",
    "S09": "ramp-in needs trading-day-indexed risk absent from the kernel",
    "S12": "global cap hardcoded in C# kernel; config not exposed",
    "S13": "global cap hardcoded in C# kernel; config not exposed",
    "S14": "phase-conditional cap not exposed",
    "S15": "conditional cluster cap not exposed",
    "S17": "directional yen-cluster rule not expressible in the cluster map",
    "S19": "harness ends phases at target-hit (min-days window not modeled) - vacuous per spec",
    "S20": "per-day position-count rule hook absent from the kernel",
}


def policy(name, idx_p1, idx_p2, symbols=None, per_symbol=None):
    m1, m2 = {}, {}
    for s in symbols:
        if s == "USDJPY":
            m1[s] = m2[s] = 0.0005
        else:
            m1[s] = idx_p1
            m2[s] = idx_p2
    if per_symbol:
        for s, r in per_symbol.items():
            m1[s] = m2[s] = r
    return RiskPolicy(name, m1, m2)


def exact_path0(tape, metas, policies, boot):
    ref = run_monte_carlo(tape, metas, policies, paths=1, path_start=0, bootstrap=boot,
                          config=SimulationConfig(equity_mode=EquityMode.TWO_STOP))
    act = csharp_engine.run_csharp_monte_carlo(tape, metas, policies, paths=1, path_start=0, bootstrap=boot)
    for p in policies:
        if ref[p.name].rows.tobytes() != act[p.name].rows.tobytes():
            raise RuntimeError(f"path-0 mismatch: {p.name}")
    return True


def run_chunks(tape, metas, policies, boot, paths, label):
    rows = {p.name: [] for p in policies}
    for start in range(0, paths, CHUNK):
        count = min(CHUNK, paths - start)
        chunk = csharp_engine.run_csharp_monte_carlo(tape, metas, policies, paths=count,
                                                     path_start=start, bootstrap=boot)
        for p in policies:
            rows[p.name].append(chunk[p.name].rows)
        done = start + count
        if done % 5_000 == 0 or done == paths:
            print(f"MC_PROGRESS {label} {done}/{paths}", flush=True)
    return {p.name: CompactRun(p, np.concatenate(rows[p.name])) for p in policies}


def gates(summary, comparison, control):
    fails = []
    if summary["both_probability"] < ABSOLUTE_GATE:
        fails.append("BOTH_POINT_LT_78_887PCT")
    if summary["both_wilson_lower"] < ABSOLUTE_GATE:
        fails.append("BOTH_WILSON_LOWER_LT_78_887PCT")
    if comparison["lower"] <= 0:
        fails.append("PAIRED_LOWER_NOT_POSITIVE")
    if summary["hard_probability"] > 0.01:
        fails.append("HARD_HALT_GT_1PCT")
    if summary["timeout_probability"] > control["timeout_probability"]:
        fails.append("TIMEOUT_WORSE_THAN_CONTROL")
    return not fails, fails


def stage(tape, metas, policies, control_policy, boot, paths, label):
    exact_path0(tape, metas, (control_policy,) + policies, boot)
    runs = run_chunks(tape, metas, (control_policy,) + policies, boot, paths, label)
    control = runs[control_policy.name]
    csum = asdict(control.summary())
    cells = []
    for p in policies:
        run = runs[p.name]
        s = asdict(run.summary())
        lower, n10, n01, est, pval = run.paired_delta_lower(control)
        comp = dict(lower=lower, n10=n10, n01=n01, estimate=est, p_value=pval)
        ok, fails = gates(s, comp, csum)
        cells.append(dict(policy=p.name, summary=s, paired=comp, gates_pass=ok, failures=fails,
                          rows_sha256=run.sha256()))
        print("SIZING_RESULT", p.name, "PASS" if ok else "FAIL",
              f"both={s['both_probability']:.6f}", f"hard={s['hard_probability']:.6f}",
              f"timeout={s['timeout_probability']:.6f}", f"paired_lower={comp['lower']:.6f}",
              ",".join(fails) if fails else "none", flush=True)
    return dict(paths=paths, control_summary=csum, control_rows_sha256=control.sha256(), cells=cells)


def main():
    tape, counts = build_h1_universe_tape(SOURCES, stress=True)
    metas = ftmo_metas(SOURCES)
    configure_symbols(tuple(metas))
    syms = tuple(metas)                      # FTMO names, e.g. US30.cash
    control_policy = policy("CONTROL_V131", 0.0030, 0.0030, symbols=syms)
    cands = (
        policy("S01_P2_STEPDOWN", 0.0030, 0.0025, symbols=syms),
        policy("S02_BARBELL", 0.0035, 0.0025, symbols=syms),
        policy("S16_REWEIGHT", 0.0030, 0.0030, symbols=syms,
               per_symbol={"US100.cash": 0.0025, "JP225.cash": 0.0035}),
    )
    boot = common_bootstrap(tape, tape)
    out = dict(spec=str(SPEC.name), spec_sha256=hashlib.sha256(SPEC.read_bytes()).hexdigest(),
               seed=BOOT_SEED, forfeits=FORFEITS, counts=counts, screen=None,
               confirmation=None, selected=None, verdict="INCOMPLETE")
    RESULT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out["screen"] = stage(tape, metas, cands, control_policy, boot, SCREEN_PATHS, "SCREEN")
    RESULT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passing = [c for c in out["screen"]["cells"] if c["gates_pass"]]
    if not passing:
        out["verdict"] = "NO_ADMISSION"
        RESULT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("FINAL NO_ADMISSION", flush=True)
        return
    best = sorted(passing, key=lambda c: -c["paired"]["lower"])[0]
    out["selected"] = best["policy"]
    sel = next(p for p in cands if p.name == best["policy"])
    out["confirmation"] = stage(tape, metas, (sel,), control_policy, boot, CONFIRM_PATHS, "CONFIRM")
    out["verdict"] = "ADMIT" if out["confirmation"]["cells"][0]["gates_pass"] else "NO_ADMISSION"
    RESULT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("FINAL", out["verdict"], out["selected"], flush=True)


if __name__ == "__main__":
    main()
