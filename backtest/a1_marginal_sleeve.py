"""A1 marginal-signal reduced-risk sleeve — Stage-1 20k paired screen.

Pre-registered: docs/A1_MARGINAL_SLEEVE_SPEC_2026-07-20.md
  (SHA256 8f454013227c4175e37a16c24013fd1d43d95b980617e72c69c3bfffafe64ccb)

Candidate = the audited C1 joint enumeration with per-trade tiering via symbol
relabeling: marginal trades (impulse < 3.0 at the signal bar) -> "SYM#M" at
sleeve risk s; A+ trades at base risk. Control = the deployed A1 tape at base
risk. Paired on common flat bootstrap blocks (era seed/block), era gates
verbatim + this study's speed claim. 3 cells: s in {0.05%, 0.10%, 0.15%}.
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_h1_universe_tape import (build_h1_universe_tape, ftmo_metas,
                                    load_symbol, META_PATH, MB)
from run_h1_universe_account import common_bootstrap, configure_symbols
from parity_engine import prep_symbol
import v130_pass_policy_csharp as csharp_engine
from v130_pass_policy import CompactRun, PassTape, RiskPolicy

SOURCES = ("Wall_Street_30", "US_Tech_100", "Japan_225", "USDJPY")
KW = dict(stress=True, partial_fraction=0.75, target_atr=1.5,
          reference_same_bar_partial=True)
BASE_RISK = {"US30.cash": 0.0030, "US100.cash": 0.0030, "JP225.cash": 0.0030,
             "USDJPY": 0.0005}
SLEEVES = (0.0005, 0.0010, 0.0015)
PATHS = 20_000
CHUNK = 500
GATE_HARD = 0.003700


def marginal_ids(c1_tape):
    snapshot = json.loads(META_PATH.read_text(encoding="utf-8"))
    imps = {}
    for source in SOURCES:
        loaded = load_symbol(source, snapshot)
        prepared = prep_symbol(loaded.h1, loaded.cost_e1, source)
        n = len(prepared.c)
        move = np.full(n, np.nan)
        move[MB - 1:] = prepared.c[:n - (MB - 1)] - prepared.c[MB - 1:]
        with np.errstate(invalid="ignore", divide="ignore"):
            imps[loaded.ftmo_symbol] = np.abs(move / prepared.atr)
    ids = set()
    for ev in c1_tape.events:
        bar = int(ev.trade_id.rsplit(":", 1)[1])
        if imps[ev.symbol][bar] < 3.0:
            ids.add(ev.trade_id)
    return ids


def relabel(c1_tape, ids):
    events = tuple(
        replace(ev, symbol=ev.symbol + "#M") if ev.trade_id in ids else ev
        for ev in c1_tape.events)
    return PassTape.from_events(events, first_day=c1_tape.first_day,
                                last_day=c1_tape.last_day)


def run_chunks(tape, metas, policy, boot, paths, label):
    rows = []
    for start in range(0, paths, CHUNK):
        count = min(CHUNK, paths - start)
        part = csharp_engine.run_csharp_monte_carlo(
            tape, metas, (policy,), paths=count, path_start=start,
            bootstrap=boot)[policy.name]
        rows.append(part.rows)
        done = start + count
        if done % 5_000 == 0 or done == paths:
            print(f"MC_PROGRESS {label} {done}/{paths}", flush=True)
    return CompactRun(policy, np.concatenate(rows))


def main():
    print("building tapes...")
    c1, _ = build_h1_universe_tape(SOURCES, momentum_atr_mult=2.0, **KW)
    a1, _ = build_h1_universe_tape(SOURCES, momentum_atr_mult=3.0, **KW)
    ids = marginal_ids(c1)
    n_marg_events = sum(1 for ev in c1.events if ev.trade_id in ids)
    print(f"marginal trade_ids={len(ids)} covering {n_marg_events} events")

    base_metas = ftmo_metas(SOURCES)
    metas = dict(base_metas)
    for sym, m in base_metas.items():
        metas[sym + "#M"] = replace(m, symbol=sym + "#M")
    symbols = tuple(metas)
    configure_symbols(symbols)

    cand_tape = relabel(c1, ids)
    boot = common_bootstrap(a1, cand_tape)
    print(f"common eligible blocks: {len(boot.eligible_block_starts)}")

    # The A1 control tape contains no #M events, so these keys are never read;
    # epsilon entries exist only to satisfy the full-coverage invariant.
    ctrl_risk = dict(BASE_RISK)
    ctrl_risk.update({k + "#M": 1e-9 for k in BASE_RISK})
    ctrl_policy = RiskPolicy("A1_CONTROL", ctrl_risk, ctrl_risk)
    control = run_chunks(a1, metas, ctrl_policy, boot, PATHS, "control:A1")
    cs = control.summary()
    print(f"CONTROL A1: both={cs.both_probability:.4%} hard={cs.hard_probability:.4%} "
          f"timeout={cs.timeout_probability:.4%} medDays={cs.median_total_days_success:.0f}")

    for s in SLEEVES:
        risk = dict(BASE_RISK)
        risk.update({k + "#M": s for k in BASE_RISK})
        policy = RiskPolicy(f"A1_SLEEVE_{int(s * 10000)}bp", risk, risk)
        cand = run_chunks(cand_tape, metas, policy, boot, PATHS, f"sleeve:{s:.4%}")
        ks = cand.summary()
        lower, n10, n01, _, _ = cand.paired_delta_lower(control)
        discordant = n10 + n01
        p = (float(binomtest(n10, discordant, 0.5, alternative="greater").pvalue)
             if discordant else 1.0)
        gates = {
            "hard<=0.37%": ks.hard_probability <= GATE_HARD,
            "paired_lower>0": lower > 0,
            "timeout<=ctrl": ks.timeout_probability <= cs.timeout_probability,
            "medDays<ctrl": ks.median_total_days_success < cs.median_total_days_success,
        }
        verdict = "PASS" if all(gates.values()) else "no"
        print(f"\nSLEEVE {s:.4%}: both={ks.both_probability:.4%} "
              f"hard={ks.hard_probability:.4%} timeout={ks.timeout_probability:.4%} "
              f"medDays={ks.median_total_days_success:.0f}")
        print(f"  paired: lower={lower:+.6f} n10={n10} n01={n01} McNemar p={p:.3g}")
        print(f"  gates: " + " ".join(f"{k}={'Y' if v else 'N'}" for k, v in gates.items())
              + f" -> {verdict}", flush=True)

    print("\nScreen only; any PASS advances to 100k confirmation per spec.")


if __name__ == "__main__":
    main()
