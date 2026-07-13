"""Run the preregistered exploratory FTMO risk-allocation screen."""
from v130_coupled import load_ftmo_split
from v130_cost_ledger import run_cost_coupled
from v130_pass_adapter import compile_cost_tape
from v130_pass_policy import BootstrapSpec, EquityMode, RiskPolicy, SimulationConfig, run_monte_carlo
from v130_pass_policy_csharp import run_csharp_monte_carlo

POLICIES = (
    RiskPolicy("R4", {"JP225.cash": .004, "US100.cash": .004, "US30.cash": .0001}, {"JP225.cash": .002, "US100.cash": .002, "US30.cash": .00005}),
    RiskPolicy("R3", {"JP225.cash": .003, "US100.cash": .003, "US30.cash": .0001}, {"JP225.cash": .0015, "US100.cash": .0015, "US30.cash": .00005}),
    RiskPolicy("R5", {"JP225.cash": .005, "US100.cash": .005, "US30.cash": .0001}, {"JP225.cash": .0025, "US100.cash": .0025, "US30.cash": .00005}),
)
BOOT = BootstrapSpec(seed=13020260711, block_length=20)
for mode in ("E1_MEASURED", "E2_STRESS"):
    inputs = load_ftmo_split("mined")
    compiled = compile_cost_tape(inputs, run_cost_coupled(inputs, mode))
    tape, metas = compiled.to_policy_inputs()
    actual = run_csharp_monte_carlo(tape, metas, POLICIES, paths=10_000, bootstrap=BOOT)
    reference = run_monte_carlo(tape, metas, POLICIES, paths=1, path_start=0, bootstrap=BOOT, config=SimulationConfig(equity_mode=EquityMode.TWO_STOP))
    print(mode)
    for policy in POLICIES:
        left = reference[policy.name].rows
        right = actual[policy.name].rows[:1]
        print(policy.name, "exact_path0", left.tobytes() == right.tobytes())
        summary = actual[policy.name].summary()
        print({"both": summary.both_probability, "wilson_lower": summary.both_wilson_lower, "hard": summary.hard_probability, "timeout": summary.timeout_probability, "p90": summary.p90_total_days_success})
