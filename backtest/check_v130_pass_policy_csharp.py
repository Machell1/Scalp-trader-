"""Field-level equivalence gate for the C# pass-policy kernel."""
from __future__ import annotations

import argparse
from pathlib import Path
import time

import numpy as np

from v130_coupled import load_ftmo_split
from v130_cost_ledger import run_cost_coupled
from v130_pass_adapter import compile_cost_tape
from v130_pass_policy import BootstrapSpec, CompactRun, EquityMode, POLICIES, SimulationConfig, run_monte_carlo
from v130_pass_policy_csharp import run_csharp_monte_carlo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("E1_MEASURED", "E2_STRESS"), required=True)
    parser.add_argument("--path-id", type=int, action="append", required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    print("STAGE inputs_start", flush=True)
    inputs = load_ftmo_split("mined")
    compiled = compile_cost_tape(inputs, run_cost_coupled(inputs, args.mode))
    tape, metas = compiled.to_policy_inputs()
    print(f"STAGE tape_done elapsed={time.perf_counter() - started:.3f}", flush=True)
    bootstrap = BootstrapSpec(seed=13020260711, block_length=20)
    config = SimulationConfig(equity_mode=EquityMode.TWO_STOP)
    for path_id in args.path_id:
        checkpoint = Path(__file__).with_name(f"v130_numba_reference_{args.mode}_{path_id:06d}.npz")
        if checkpoint.exists():
            with np.load(checkpoint, allow_pickle=False) as saved:
                reference = {p.name: CompactRun(p, saved[p.name]) for p in POLICIES}
            print(f"STAGE reference_reused path={path_id}", flush=True)
        else:
            print(f"STAGE reference_start path={path_id}", flush=True)
            reference = run_monte_carlo(
                tape, metas, POLICIES, paths=1, path_start=path_id,
                bootstrap=bootstrap, config=config,
            )
            np.savez_compressed(checkpoint, **{name: run.rows for name, run in reference.items()})
            print(f"STAGE reference_done path={path_id}", flush=True)
        print(f"STAGE csharp_start path={path_id}", flush=True)
        actual = run_csharp_monte_carlo(
            tape, metas, POLICIES, paths=1, path_start=path_id, bootstrap=bootstrap,
        )
        print(f"STAGE csharp_done path={path_id} elapsed={time.perf_counter() - started:.3f}", flush=True)
        for policy in POLICIES:
            left, right = reference[policy.name].rows, actual[policy.name].rows
            mismatches = [
                name for name in left.dtype.names or ()
                if left[name].tobytes() != right[name].tobytes()
            ]
            if mismatches:
                for name in mismatches:
                    print(
                        f"MISMATCH mode={args.mode} path={path_id} policy={policy.name} "
                        f"field={name} reference={left[name][0]!r} csharp={right[name][0]!r}"
                    )
                raise SystemExit(1)
            print(f"PASS exact mode={args.mode} path={path_id} policy={policy.name}")


if __name__ == "__main__":
    main()
