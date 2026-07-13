"""Run the preregistered H1 sequential FTMO account MC."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from build_h1_ftmo_tape import build_h1_tape
from v130_coupled import load_ftmo_split
from v130_cost_ledger import run_cost_coupled
from v130_pass_adapter import compile_cost_tape
from v130_pass_policy import POLICIES, CompactRun, BootstrapSpec
from v130_pass_policy_csharp import run_csharp_monte_carlo

HERE = Path(__file__).resolve().parent
PATHS = 100_000
CHUNK = 500
BOOT = BootstrapSpec(seed=13020260711, block_length=20)
RESULT = HERE / "h1_ftmo_account_results.json"
NPZ = HERE / "h1_ftmo_account_paths.npz"


def metas():
    inputs = load_ftmo_split("mined")
    cost = run_cost_coupled(inputs, "E1_MEASURED")
    return compile_cost_tape(inputs, cost).to_policy_inputs()[1]


def run_mode(mode: str, stress: bool, policy_metas):
    tape, counts = build_h1_tape(stress=stress)
    chunks = {}
    for start in range(0, PATHS, CHUNK):
        count = min(CHUNK, PATHS - start)
        path = HERE / f"h1_ftmo_chunk_{mode}_{start:06d}.npz"
        if path.exists():
            with np.load(path, allow_pickle=False) as saved:
                rows = {p.name: saved[p.name] for p in POLICIES}
            expected = np.arange(start, start + count)
            if any(not np.array_equal(rows[p.name]["path_id"], expected) for p in POLICIES):
                raise RuntimeError(f"invalid checkpoint {path}")
            print(f"CHUNK_REUSED {mode} {start}", flush=True)
        else:
            runs = run_csharp_monte_carlo(tape, policy_metas, POLICIES, paths=count, path_start=start, bootstrap=BOOT)
            rows = {name: run.rows for name, run in runs.items()}
            np.savez_compressed(path, **rows)
            print(f"CHUNK_DONE {mode} {start} {count}", flush=True)
        chunks[start] = rows
    runs = {}
    for p in POLICIES:
        rows = np.concatenate([chunks[start][p.name] for start in range(0, PATHS, CHUNK)])
        runs[p.name] = CompactRun(p, rows)
    return tape, counts, runs


def main():
    policy_metas = metas()
    output = {"paths": PATHS, "seed": BOOT.seed, "block_length": BOOT.block_length, "modes": {}}
    arrays = {}
    for mode, stress in (("E1_MEASURED", False), ("E2_STRESS", True)):
        print(f"MC_START {mode} {PATHS}", flush=True)
        tape, counts, runs = run_mode(mode, stress, policy_metas)
        output["modes"][mode] = {"counts": counts, "summaries": {}, "paired": {}}
        for p in POLICIES:
            run = runs[p.name]
            summary = asdict(run.summary())
            summary["outcome_sha256"] = run.sha256()
            output["modes"][mode]["summaries"][p.name] = summary
            arrays[f"{mode}__{p.name}"] = run.rows
        output["modes"][mode]["paired"] = {
            control: {"lower": runs["P1"].paired_delta_lower(runs[control])[0],
                      "n10": runs["P1"].paired_delta_lower(runs[control])[1],
                      "n01": runs["P1"].paired_delta_lower(runs[control])[2]}
            for control in ("C0", "C1")
        }
        print(f"MC_DONE {mode}", flush=True)
    np.savez_compressed(NPZ, **arrays)
    output["npz_sha256"] = hashlib.sha256(NPZ.read_bytes()).hexdigest()
    RESULT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RESULT_FILE={RESULT}")


if __name__ == "__main__":
    main()
