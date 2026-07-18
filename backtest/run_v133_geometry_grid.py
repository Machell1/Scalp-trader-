"""Pre-registered v1.33 reset grid — 2026-07-18 (owner-authorized reset of the failed E3 challenger).

Background: the E3 challenger (bank 67% @ +1R, TP 1.5 ATR) beat v1.31 head-to-head
(+9.91pp pass, paired LB +8.94pp) on the owner's corrected-fidelity harness but FAILED
the absolute hard-halt gate (0.435% > 0.370%). This pre-declared, fully-reported mini
grid searches 4 reset levers for a cell that clears the halt gate AND stays a paired
winner vs v1.31. Ledger charge: 4 candidate cells (+1 control, +1 E3 replication).

Cells (ALL results reported regardless of outcome):
  V131 : bank 0.50 @ +1.0R, TP 2.0, trio 0.300%   (control = incumbent v1.31 portfolio)
  E3   : bank 0.67 @ +1.0R, TP 1.5, trio 0.300%   (failed challenger; replication cell)
  C1   : bank 0.75 @ +1.0R, TP 1.5, trio 0.300%   (bank more)
  C2   : bank 0.67 @ +0.8R, TP 1.5, trio 0.300%   (bank earlier)
  C3   : bank 0.67 @ +1.0R, TP 1.5, trio 0.275%   (risk trim)
  C4   : bank 0.75 @ +0.9R, TP 1.5, trio 0.300%   (combo)

Pre-declared gates (all four required):
  G1 hard_probability <= 0.0037 (the absolute halt gate the challenger missed)
  G2 paired both-delta lower bound vs V131 control > 0 (remains a head-to-head winner)
  G3 hard_probability < E3 hard_probability (improves the failed metric)
  G4 timeout_probability <= V131 timeout (not worse than the incumbent)

House standard: 20,000 paired paths, seed 13020260711, 20-day blocks, E2_STRESS,
exact Python/C# path-0 parity gate per tape before any path is consumed.
Caveat (recorded): this repo harness is the OPTIMISTIC bar-resolution generation
(the owner's corrected harness scored E3 at 86.660% vs 87.965% here). Absolute
numbers are expected to run high; the paired deltas are the pre-screen signal.
Decision-grade confirmation MUST be re-run on the owner's corrected harness.
"""
from __future__ import annotations

from dataclasses import asdict
import gc
import json
from pathlib import Path

import numpy as np

from build_h1_universe_tape import build_h1_universe_tape, ftmo_metas
from run_h1_universe_account import BASE_SOURCES, configure_symbols
import v130_pass_policy_csharp as csharp_engine
from v130_pass_policy import (
    BootstrapSpec,
    CompactRun,
    EquityMode,
    RiskPolicy,
    SimulationConfig,
    run_monte_carlo,
)

HERE = Path(__file__).resolve().parent
RESULT = HERE / "v133_geometry_grid_results.json"
CHUNK_DIR = HERE / "v133_chunks"
SOURCES = BASE_SOURCES + ("USDJPY",)
BOOT_SEED = 13020260711
BLOCK = 20
PATHS = 20_000
CHUNK = 500
HALT_GATE = 0.0037

# name -> (tp_mult, partial_r, bank_frac, trio_risk)
CELLS = {
    "V131": (2.0, 1.0, 0.50, 0.0030),
    "E3":   (1.5, 1.0, 0.67, 0.0030),
    "C1":   (1.5, 1.0, 0.75, 0.0030),
    "C2":   (1.5, 0.8, 0.67, 0.0030),
    "C3":   (1.5, 1.0, 0.67, 0.00275),
    "C4":   (1.5, 0.9, 0.75, 0.0030),
}
# geometry -> cells sharing one tape build
TAPES = {
    "V131": (2.0, 1.0, 0.50),
    "E3":   (1.5, 1.0, 0.67),
    "C1":   (1.5, 1.0, 0.75),
    "C2":   (1.5, 0.8, 0.67),
    "C4":   (1.5, 0.9, 0.75),
}
CELL_TAPE = {"V131": "V131", "E3": "E3", "C1": "C1", "C2": "C2", "C3": "E3", "C4": "C4"}


def policy_for(name: str, trio_risk: float, symbols) -> RiskPolicy:
    mapping = {s: (0.0005 if s == "USDJPY" else trio_risk) for s in symbols}
    return RiskPolicy(name, mapping, mapping)


def exact_path0(tape, metas, policies, boot) -> None:
    reference = run_monte_carlo(
        tape, metas, policies, paths=1, path_start=0, bootstrap=boot,
        config=SimulationConfig(equity_mode=EquityMode.TWO_STOP),
    )
    actual = csharp_engine.run_csharp_monte_carlo(
        tape, metas, policies, paths=1, path_start=0, bootstrap=boot
    )
    for policy in policies:
        if reference[policy.name].rows.tobytes() != actual[policy.name].rows.tobytes():
            raise RuntimeError(f"Python/C# path-0 mismatch: {policy.name}")
    print(f"PATH0_OK {[p.name for p in policies]}", flush=True)


def run_tape_chunked(tape_name, tape, metas, policies, boot) -> dict[str, CompactRun]:
    CHUNK_DIR.mkdir(exist_ok=True)
    rows = {p.name: [] for p in policies}
    for start in range(0, PATHS, CHUNK):
        count = min(CHUNK, PATHS - start)
        ck = CHUNK_DIR / f"{tape_name}_{start:05d}.npz"
        if ck.exists():
            saved = np.load(ck)
            for p in policies:
                rows[p.name].append(saved[p.name])
            continue
        chunk = csharp_engine.run_csharp_monte_carlo(
            tape, metas, policies, paths=count, path_start=start, bootstrap=boot
        )
        np.savez(ck, **{p.name: chunk[p.name].rows for p in policies})
        for p in policies:
            rows[p.name].append(chunk[p.name].rows)
        print(f"MC_PROGRESS {tape_name} {start + count}/{PATHS}", flush=True)
    return {p.name: CompactRun(p, np.concatenate(rows[p.name])) for p in policies}


def main() -> None:
    metas = ftmo_metas(SOURCES)
    configure_symbols(tuple(metas))
    tapes, counts = {}, {}
    for tname, (tp, pr, bf) in TAPES.items():
        tapes[tname], counts[tname] = build_h1_universe_tape(
            SOURCES, stress=True, tp_mult=tp, partial_r=pr, bank_frac=bf
        )
        print(f"TAPE_OK {tname} {counts[tname]}", flush=True)
        gc.collect()
    eligible = None
    for tape in tapes.values():
        s = set(tape.eligible_flat_block_starts(BLOCK))
        eligible = s if eligible is None else (eligible & s)
    if not eligible:
        raise RuntimeError("no common flat bootstrap blocks across grid tapes")
    boot = BootstrapSpec(seed=BOOT_SEED, block_length=BLOCK,
                         eligible_block_starts=tuple(sorted(eligible)))
    print(f"BOOT_OK common_blocks={len(boot.eligible_block_starts)}", flush=True)

    runs: dict[str, CompactRun] = {}
    for tname, tape in tapes.items():
        policies = tuple(policy_for(c, CELLS[c][3], tuple(metas)) for c in CELLS if CELL_TAPE[c] == tname)
        exact_path0(tape, metas, policies, boot)
        runs.update(run_tape_chunked(tname, tape, metas, policies, boot))
        del tape
        tapes[tname] = None
        gc.collect()

    control = runs["V131"]
    cs = asdict(control.summary())
    e3s = asdict(runs["E3"].summary())
    out = {
        "spec": "PRE-REGISTERED GRID 2026-07-18 (see module docstring)",
        "seed": BOOT_SEED, "block_length": BLOCK, "paths": PATHS, "stress": "E2_STRESS",
        "halt_gate": HALT_GATE, "common_eligible_blocks": len(boot.eligible_block_starts),
        "tape_counts": counts, "cells": [],
    }
    for name, (tp, pr, bf, risk) in CELLS.items():
        run = runs[name]
        s = asdict(run.summary())
        lower, n10, n01, est, pv = run.paired_delta_lower(control)
        gates = {
            "G1_halt_le_037": s["hard_probability"] <= HALT_GATE,
            "G2_paired_lower_pos": lower > 0,
            "G3_halt_lt_E3": s["hard_probability"] < e3s["hard_probability"],
            "G4_timeout_le_V131": s["timeout_probability"] <= cs["timeout_probability"],
        }
        cell = {
            "cell": name, "tp_mult": tp, "partial_r": pr, "bank_frac": bf,
            "trio_risk": risk, "summary": s,
            "paired_vs_V131": {"lower": lower, "n10": n10, "n01": n01,
                               "estimate": est, "p_value": pv},
            "gates": gates, "pass_all": all(gates.values()),
            "rows_sha256": run.sha256(),
        }
        out["cells"].append(cell)
        print(
            "CELL_RESULT", name,
            f"both={s['both_probability']:.6f}", f"hard={s['hard_probability']:.6f}",
            f"timeout={s['timeout_probability']:.6f}",
            f"median_days={s['median_total_days_success']:.1f}",
            f"paired_lower={lower:.6f}",
            "PASS" if cell["pass_all"] else "FAIL",
            flush=True,
        )
        RESULT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    winners = [c["cell"] for c in out["cells"] if c["pass_all"] and c["cell"] != "V131"]
    out["verdict"] = f"RESET_CANDIDATES={winners}" if winners else "NO_CELL_PASSES"
    RESULT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("FINAL", out["verdict"], flush=True)


if __name__ == "__main__":
    main()
