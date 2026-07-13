"""Exact path-0 gate for the preregistered H1 account tape."""
from __future__ import annotations

from build_h1_ftmo_tape import build_h1_tape
from v130_coupled import load_ftmo_split
from v130_pass_policy import BootstrapSpec, CompactRun, EquityMode, POLICIES, SimulationConfig, run_monte_carlo
from v130_pass_policy_csharp import run_csharp_monte_carlo
from v130_pass_adapter import compile_cost_tape
from v130_cost_ledger import run_cost_coupled


def metas():
    inputs = load_ftmo_split("mined")
    compiled = compile_cost_tape(inputs, run_cost_coupled(inputs, "E1_MEASURED"))
    return compiled.to_policy_inputs()[1]


for mode, stress in (("E1_MEASURED", False), ("E2_STRESS", True)):
    tape, counts = build_h1_tape(stress=stress)
    policy_metas = metas()
    reference = run_monte_carlo(tape, policy_metas, POLICIES, paths=1, bootstrap=BootstrapSpec(seed=13020260711, block_length=20), config=SimulationConfig(equity_mode=EquityMode.TWO_STOP), path_start=0)
    actual = run_csharp_monte_carlo(tape, policy_metas, POLICIES, paths=1, bootstrap=BootstrapSpec(seed=13020260711, block_length=20), path_start=0)
    print(mode, counts)
    for policy in POLICIES:
        same = reference[policy.name].rows.tobytes() == actual[policy.name].rows.tobytes()
        print(policy.name, "exact_path0", same)
        if not same:
            raise SystemExit(1)
