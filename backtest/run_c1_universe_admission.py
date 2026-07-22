"""Execute the preregistered C1 M15-grain universe-admission study."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback
from typing import Any, Iterable

import numpy as np
import pandas as pd
import scipy
from scipy.stats import binomtest

from build_h1_universe_tape import build_h1_universe_tape
from test_c1_universe_admission import self_test as universe_self_test
from c1_universe_m15 import (
    BASE_SOURCES,
    BASE_SYMBOLS,
    CANDIDATES,
    MOMENTUM_C1,
    BuiltTape,
    build_tape,
    event_hash,
    load_contexts,
    metadata_for_sources,
    split_bounds,
)
import v130_pass_adapter
import v130_pass_policy as policy_engine
import v130_pass_policy_csharp as csharp_engine
import v130_risk_policy as risk_engine
from v130_pass_policy import (
    BootstrapSpec,
    CompactRun,
    COUNTER_FIELDS,
    EquityMode,
    RiskPolicy,
    SimulationConfig,
    run_monte_carlo,
)
from v130_risk_policy import exact_paired_delta_lower
from walkforward_dsr import dsr_hurdle, psr


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "C1_UNIVERSE_ADMISSION_SPEC_2026-07-21.md"
SPEC_HASH_FILE = SPEC.with_suffix(".sha256")
RESULT = HERE / "c1_universe_admission_results.json"
FAILURES = HERE / "c1_universe_admission_failures.jsonl"
CHECKPOINTS = ROOT.parent / ".c1_universe_checkpoints"

DATA_OK = "verified 46 OK, 0 missing, 0 mismatched"
# Registered spec identity is pinned in the LF (blob) regime: sha256 of the
# spec bytes exactly as committed at EXPECTED_SPEC_COMMIT (amendment 3166c4f).
EXPECTED_SPEC_SHA = "796f24501c29a468acabca41833a8b61bfa5efa7e489a26a3cb61697aa3aff71"
EXPECTED_META_SHA = "bb0b3489c48e7cad83e5a85c3eea6005db7c5ec0e7ed9098c76814bb049cd3a6"
EXPECTED_MANIFEST_SHA = "ec1fcc26132366ab157b8d298c1cf60d79d63ac16708d1a887a1740ad46de49f"
EXPECTED_LIVE_EA_SHA = "fbb8c5fe4d61a41ca46e0f06aafb98accc584d78347372a6df2d0177ac67c5ce"
EXPECTED_PARENT_COMMIT = "08811c963959ab0efaf92c38508dcf4bf4c48011"
EXPECTED_SPEC_COMMIT = "3166c4fefe98ae70240d0bd8f20f6e5125b47446"
LEGACY_SHA = "3f51b01dfca92bd5d5fd2b01b1579d9e971661bc689ffee219f29dfaf347005f"
C1_SHA = "b294ebe5f4e54a4bc97c2ff010754d58900268d69db12ff0d2cdd9f567ba4187"

BOOT_SEED = 13020260711
BLOCK = 20
CHUNK = 500
SCREEN_PATHS = 20_000
CONFIRM_PATHS = 100_000
CONFIRM_START = 20_000
PLACEBOS = 999
PLACEBO_BASE_SEED = 20260718
DSR_TRIALS = 317
FAMILY_CONFIDENCE = 0.975
FAMILY_P = 0.025
WILSON_CONFIDENCE = 0.95

EXPERIMENT_FILES = (
    SPEC,
    SPEC_HASH_FILE,
    HERE / "run_c1_universe_admission.py",
    HERE / "c1_universe_m15.py",
    HERE / "test_c1_universe_admission.py",
    HERE / "build_h1_universe_tape.py",
    HERE / "parity_engine.py",
    HERE / "run_mtf_anchor_screen.py",
    HERE / "run_h1_universe_screen.py",
    HERE / "h1_universe_broker_meta.json",
    HERE / "snapshot_h1_universe_meta.py",
    HERE / "scalper_backtest.py",
    HERE / "scalper_confluence.py",
    HERE / "experiment.py",
    HERE / "run_h1_timeframe_screen.py",
    HERE / "v130_pass_policy.py",
    HERE / "v130_pass_policy_csharp.py",
    HERE / "v130_pass_policy_kernel.cs",
    HERE / "v130_risk_policy.py",
    HERE / "v130_pass_adapter.py",
    HERE / "walkforward_dsr.py",
    HERE / "verify_data.py",
    HERE / "data" / "MANIFEST.sha256",
    ROOT / "mql5" / "MomentumPullbackEA.mq5",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        text=True, capture_output=True,
    ).stdout.strip()


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True,
    ).stdout.strip()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_result(output: dict) -> None:
    RESULT.write_text(
        json.dumps(json_safe(output), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def refresh_ledger(output: dict) -> None:
    ledger = output["trial_ledger"]
    charged = (
        int(ledger["discovery_cells"])
        + int(ledger["account_screen_cells"])
        + int(ledger["confirmation_cells"])
    )
    ledger["charged_cells"] = charged
    ledger["end"] = int(ledger["start_floor"]) + charged


def append_failure(exc: BaseException) -> None:
    row = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }
    with FAILURES.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def verify_committed_bundle() -> dict:
    commit = git_commit()
    status = git_text("status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeError(f"experiment worktree is not clean at HEAD:\n{status}")
    rows = {}
    for path in EXPERIMENT_FILES:
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=ROOT, text=True, capture_output=True,
        )
        if tracked.returncode:
            raise RuntimeError(f"experiment file is not tracked at HEAD: {relative}")
        head_bytes = subprocess.run(
            ["git", "show", f"HEAD:{relative}"], cwd=ROOT, check=True,
            capture_output=True,
        ).stdout
        work_bytes = path.read_bytes()
        if head_bytes != work_bytes:
            raise RuntimeError(f"experiment file differs from HEAD: {relative}")
        rows[relative] = hashlib.sha256(work_bytes).hexdigest()
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "commit": commit,
        "files": rows,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


@lru_cache(maxsize=1)
def experiment_bundle_sha256() -> str:
    rows = {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
        for path in EXPERIMENT_FILES
    }
    payload = json.dumps(
        {"commit": git_commit(), "files": rows},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@lru_cache(maxsize=1)
def runtime_provenance() -> dict:
    compiler = csharp_engine.CSC
    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "csharp_compiler": str(compiler),
        "csharp_compiler_sha256": sha256_file(compiler),
        "wilson_one_sided_confidence": WILSON_CONFIDENCE,
        "quote_buffer_stress_multiplier": 1.0,
        "swap_model": "NO_EVENTS_AVAILABLE_NO_CREDIT_OR_DEBIT_SYNTHESIZED",
        "aus200_fallback_per_side_atr": 0.03,
    }


def verify_provenance() -> dict:
    actual_spec = sha256_file(SPEC)
    registered = SPEC_HASH_FILE.read_text(encoding="utf-8").split()[0]
    if actual_spec != EXPECTED_SPEC_SHA or registered != EXPECTED_SPEC_SHA:
        raise RuntimeError(
            f"spec hash mismatch: actual={actual_spec} sidecar={registered} "
            f"expected={EXPECTED_SPEC_SHA}"
        )
    actual_meta = sha256_file(HERE / "h1_universe_broker_meta.json")
    if actual_meta != EXPECTED_META_SHA:
        raise RuntimeError(
            f"metadata hash mismatch: {actual_meta} != {EXPECTED_META_SHA}"
        )
    manifest_path = HERE / "data" / "MANIFEST.sha256"
    actual_manifest = sha256_file(manifest_path)
    if actual_manifest != EXPECTED_MANIFEST_SHA:
        raise RuntimeError(
            f"manifest hash mismatch: {actual_manifest} != {EXPECTED_MANIFEST_SHA}"
        )
    live_ea = ROOT / "mql5" / "MomentumPullbackEA.mq5"
    actual_live_ea = sha256_file(live_ea)
    if actual_live_ea != EXPECTED_LIVE_EA_SHA:
        raise RuntimeError(
            f"live EA hash mismatch: {actual_live_ea} != {EXPECTED_LIVE_EA_SHA}"
        )
    relative_spec = str(SPEC.relative_to(ROOT)).replace("\\", "/")
    # Amended-registration lineage (pre-outcome amendment 3166c4f): the spec
    # file was INTRODUCED by the original registration commit (which is also
    # the amendment's parent) and last touched by the amendment commit itself.
    # Any spec edit after EXPECTED_SPEC_COMMIT still fails this gate.
    introduced = git_text(
        "log", "--diff-filter=A", "--format=%H", "--", relative_spec
    ).splitlines()
    if introduced != [EXPECTED_PARENT_COMMIT]:
        raise RuntimeError(f"unexpected spec introduction lineage: {introduced}")
    last_touch = git_text("log", "-1", "--format=%H", "--", relative_spec)
    if last_touch != EXPECTED_SPEC_COMMIT:
        raise RuntimeError(
            f"spec touched after registered amendment: {last_touch}"
        )
    spec_parent = git_text("rev-parse", f"{EXPECTED_SPEC_COMMIT}^")
    if spec_parent != EXPECTED_PARENT_COMMIT:
        raise RuntimeError(
            f"spec parent mismatch: {spec_parent} != {EXPECTED_PARENT_COMMIT}"
        )
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_SPEC_COMMIT, "HEAD"],
        cwd=ROOT,
    )
    if ancestor.returncode:
        raise RuntimeError("registered spec commit is not an ancestor of HEAD")
    committed_spec = subprocess.run(
        ["git", "show", f"{EXPECTED_SPEC_COMMIT}:{relative_spec}"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout
    if committed_spec != SPEC.read_bytes():
        raise RuntimeError("spec bytes changed after the registered spec commit")
    run = subprocess.run(
        [sys.executable, str(HERE / "verify_data.py")], cwd=ROOT,
        text=True, capture_output=True,
    )
    output = (run.stdout + run.stderr).strip()
    print("DATA_VERIFY", output, flush=True)
    if run.returncode or output != DATA_OK:
        raise RuntimeError(f"data verification failed verbatim: {output}")
    return {
        "data_output": output,
        "spec_sha256": actual_spec,
        "metadata_sha256": actual_meta,
        "manifest_sha256": actual_manifest,
        "live_ea_sha256": actual_live_ea,
        "spec_commit": EXPECTED_SPEC_COMMIT,
        "spec_parent": spec_parent,
    }


def _h1_event_hash(tape) -> str:
    payload = json.dumps(
        [asdict(event) for event in tape.events],
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def protected_regressions() -> dict:
    legacy_tape, legacy_counts = build_h1_universe_tape(BASE_SOURCES, stress=True)
    c1_tape, c1_counts = build_h1_universe_tape(
        BASE_SOURCES,
        stress=True,
        partial_fraction=0.75,
        target_atr=1.5,
        reference_same_bar_partial=True,
        momentum_atr_mult=2.0,
    )
    rows = {
        "legacy": {
            "trades": len(legacy_tape.trades), "events": len(legacy_tape.events),
            "sha256": _h1_event_hash(legacy_tape), "counts": legacy_counts,
            "expected": {"trades": 1645, "events": 7317, "sha256": LEGACY_SHA},
        },
        "c1": {
            "trades": len(c1_tape.trades), "events": len(c1_tape.events),
            "sha256": _h1_event_hash(c1_tape), "counts": c1_counts,
            "expected": {"trades": 1684, "events": 7145, "sha256": C1_SHA},
        },
    }
    for name, row in rows.items():
        actual = (row["trades"], row["events"], row["sha256"])
        expected = (
            row["expected"]["trades"], row["expected"]["events"],
            row["expected"]["sha256"],
        )
        if actual != expected:
            raise RuntimeError(f"{name} protected regression failed: {actual} != {expected}")
        print(
            "PROTECTED_REGRESSION", name, "PASS",
            f"trades={row['trades']}", f"events={row['events']}",
            f"sha256={row['sha256']}", flush=True,
        )
    return rows


def synthetic_tests() -> dict:
    universe = universe_self_test()
    configure_symbols(BASE_SYMBOLS)
    pass_policy = policy_engine.self_test()
    risk_policy = risk_engine.synthetic_fidelity_tests()
    adapter = v130_pass_adapter.self_test()
    print(
        "SYNTHETIC_TESTS PASS",
        f"universe={universe['passed']}",
        f"pass_policy={len(pass_policy)}",
        f"risk_policy={len(risk_policy)}",
        f"adapter={adapter['passed']}",
        flush=True,
    )
    return {
        "universe": universe,
        "pass_policy": list(pass_policy),
        "risk_policy": list(risk_policy),
        "adapter": adapter,
    }


def configure_symbols(symbols: tuple[str, ...]) -> None:
    policy_engine.SYMBOLS = tuple(symbols)
    csharp_engine.SYMBOLS = tuple(symbols)


def _quarter(epoch: int) -> str:
    timestamp = pd.Timestamp(epoch, unit="s", tz="UTC").tz_localize(None)
    return str(timestamp.to_period("Q"))


def _payload_sha256(value: Any) -> str:
    payload = json.dumps(
        json_safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def assert_e1_e2_structural_parity(
    e1: BuiltTape, e2: BuiltTape, label: str
) -> dict:
    if (e1.tape.first_day, e1.tape.last_day) != (
        e2.tape.first_day,
        e2.tape.last_day,
    ):
        raise RuntimeError(f"{label}: E1/E2 calendar frames changed")

    trade_e1 = [
        {key: value for key, value in row.items() if key != "r"}
        for row in e1.trades
    ]
    trade_e2 = [
        {key: value for key, value in row.items() if key != "r"}
        for row in e2.trades
    ]
    def source_structure(row: dict) -> dict:
        normalized = dict(row)
        normalized.pop("total_r", None)
        if normalized["kind"] == "entry_fill":
            normalized.pop("r_component", None)
        return normalized

    def policy_structure(event) -> dict:
        normalized = asdict(event)
        kind = normalized["kind"]
        if getattr(kind, "value", str(kind)) == "entry":
            normalized.pop("fixed_slippage_r", None)
        return normalized

    source_e1 = [source_structure(row) for row in e1.source_events]
    source_e2 = [source_structure(row) for row in e2.source_events]
    policy_e1 = [policy_structure(event) for event in e1.tape.events]
    policy_e2 = [policy_structure(event) for event in e2.tape.events]
    mismatches = []
    if trade_e1 != trade_e2:
        mismatches.append("trade_geometry")
    if source_e1 != source_e2:
        mismatches.append("source_lifecycle")
    if policy_e1 != policy_e2:
        mismatches.append("policy_lifecycle")
    if mismatches:
        raise RuntimeError(
            f"{label}: E1/E2 structural parity failed: {mismatches}"
        )
    entry_cost_e1 = np.asarray(
        [
            event.fixed_slippage_r for event in e1.tape.events
            if event.normalized_kind().value == "entry"
        ],
        dtype=float,
    )
    entry_cost_e2 = np.asarray(
        [
            event.fixed_slippage_r for event in e2.tape.events
            if event.normalized_kind().value == "entry"
        ],
        dtype=float,
    )
    if entry_cost_e1.shape != entry_cost_e2.shape or not np.allclose(
        entry_cost_e2, 2.0 * entry_cost_e1, rtol=0.0, atol=1e-15
    ):
        raise RuntimeError(f"{label}: E2 entry cost is not exactly twice E1")
    e1_r = np.asarray([row["r"] for row in e1.trades], dtype=float)
    e2_r = np.asarray([row["r"] for row in e2.trades], dtype=float)
    if not np.isfinite(e1_r).all() or not np.isfinite(e2_r).all():
        raise RuntimeError(f"{label}: non-finite E1/E2 return")
    deltas = e1_r - e2_r
    return {
        "pass": True,
        "trades": len(trade_e1),
        "source_events": len(source_e1),
        "policy_events": len(policy_e1),
        "trade_geometry_sha256": _payload_sha256(trade_e1),
        "source_lifecycle_sha256": _payload_sha256(source_e1),
        "policy_lifecycle_sha256": _payload_sha256(policy_e1),
        "entry_costs_checked": len(entry_cost_e1),
        "e1_minus_e2_r_min": float(deltas.min()) if len(deltas) else None,
        "e1_minus_e2_r_max": float(deltas.max()) if len(deltas) else None,
    }


def trade_stats(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    values = np.asarray([row["r"] for row in rows], dtype=float)
    if not np.isfinite(values).all():
        raise RuntimeError("non-finite trade return in registered cell")
    if any(int(row["side"]) not in {-1, 1} for row in rows):
        raise RuntimeError("invalid trade side in registered cell")
    sides = {}
    for side, label in ((1, "long"), (-1, "short")):
        selected = np.asarray([row["r"] for row in rows if row["side"] == side], float)
        sides[label] = {
            "n": int(len(selected)),
            "expectancy": float(selected.mean()) if len(selected) else None,
            "win_rate": float((selected > 0).mean()) if len(selected) else None,
        }
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[_quarter(int(row["placement_epoch"]))].append(float(row["r"]))
    quarters = {
        quarter: {
            "n": len(group),
            "expectancy": float(np.mean(group)),
            "win_rate": float((np.asarray(group) > 0).mean()),
        }
        for quarter, group in sorted(grouped.items())
    }
    return {
        "n": int(len(values)),
        "expectancy": float(values.mean()) if len(values) else None,
        "win_rate": float((values > 0).mean()) if len(values) else None,
        "sum_r": float(values.sum()) if len(values) else 0.0,
        "sides": sides,
        "quarters": quarters,
    }


def complete_validation_quarters(bounds) -> list[str]:
    start = pd.Timestamp(bounds.cutoff_epoch, unit="s", tz="UTC").tz_localize(None)
    end = pd.Timestamp(bounds.end_epoch, unit="s", tz="UTC").tz_localize(None)
    periods = pd.period_range(start=start.to_period("Q"), end=end.to_period("Q"), freq="Q")
    complete = []
    for period in periods:
        q_start = period.start_time
        q_next = (period + 1).start_time
        if q_start >= start and q_next <= end:
            complete.append(str(period))
    return complete


def matched_placebos(observed: tuple[dict, ...], pool: tuple[dict, ...], seed: int) -> dict:
    observed_values = np.asarray([row["r"] for row in observed], dtype=float)
    pool_values = np.asarray([row["r"] for row in pool], dtype=float)
    if not np.isfinite(observed_values).all() or not np.isfinite(pool_values).all():
        raise RuntimeError("non-finite return in observed or C1 placebo population")
    observed_groups = Counter(
        (int(row["side"]), _quarter(int(row["placement_epoch"]))) for row in observed
    )
    pool_groups: dict[tuple[int, str], list[float]] = defaultdict(list)
    for row in pool:
        pool_groups[(int(row["side"]), _quarter(int(row["placement_epoch"])))].append(
            float(row["r"])
        )
    shortages = {
        f"{side}:{quarter}": {"needed": needed, "available": len(pool_groups[(side, quarter)])}
        for (side, quarter), needed in observed_groups.items()
        if len(pool_groups[(side, quarter)]) < needed
    }
    observed_mean = (
        float(np.mean([row["r"] for row in observed])) if observed else None
    )
    if shortages or observed_mean is None:
        return {
            "available": False,
            "shortages": shortages,
            "observed_mean": observed_mean,
            "placebo_means": [],
            "p97_5": None,
            "empirical_p": None,
        }
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(PLACEBOS):
        selected = []
        for key, needed in sorted(observed_groups.items()):
            population = np.asarray(pool_groups[key], dtype=float)
            indices = rng.choice(len(population), size=needed, replace=False)
            selected.extend(population[indices].tolist())
        means.append(float(np.mean(selected)))
    values = np.asarray(means, dtype=float)
    p_value = (1 + int((values >= observed_mean).sum())) / (PLACEBOS + 1)
    return {
        "available": True,
        "shortages": {},
        "observed_mean": observed_mean,
        "placebo_means": means,
        "p97_5": float(np.quantile(values, 0.975, method="higher")),
        "empirical_p": float(p_value),
    }


def discovery_cell(contexts, bounds, source: str, order_index: int) -> dict:
    cells = {
        "discovery_e1": build_tape(
            contexts, (source,), bounds, segment="discovery", cost_mult=1.0,
            momentum_atr_mult=MOMENTUM_C1,
        ),
        "discovery_e2": build_tape(
            contexts, (source,), bounds, segment="discovery", cost_mult=2.0,
            momentum_atr_mult=MOMENTUM_C1,
        ),
        "validation_e1": build_tape(
            contexts, (source,), bounds, segment="validation", cost_mult=1.0,
            momentum_atr_mult=MOMENTUM_C1,
        ),
        "validation_e2": build_tape(
            contexts, (source,), bounds, segment="validation", cost_mult=2.0,
            momentum_atr_mult=MOMENTUM_C1,
        ),
        # Placebo pool (spec amendment 2, commit 3166c4f): the BASE-UNIVERSE
        # C1 book — matched side x quarter draws from the quartet's validation
        # trades, built by the same M15-grain machinery.  The A1-era candidate
        # C1-opportunity pool is degenerate in the C1 era (observed == pool).
        "validation_base_c1_e2": build_tape(
            contexts,
            BASE_SOURCES,
            bounds,
            segment="validation",
            cost_mult=2.0,
            momentum_atr_mult=MOMENTUM_C1,
        ),
    }
    structural_parity = {
        "discovery": assert_e1_e2_structural_parity(
            cells["discovery_e1"], cells["discovery_e2"],
            f"{source}:discovery",
        ),
        "validation": assert_e1_e2_structural_parity(
            cells["validation_e1"], cells["validation_e2"],
            f"{source}:validation",
        ),
    }
    summaries = {name: trade_stats(cell.trades) for name, cell in cells.items()}
    validation_values = np.asarray(
        [row["r"] for row in cells["validation_e2"].trades], dtype=float
    )
    hurdle = dsr_hurdle(n_trials=DSR_TRIALS, n_obs=len(validation_values))
    dsr = psr(validation_values, hurdle) if len(validation_values) else float("nan")
    placebos = matched_placebos(
        cells["validation_e2"].trades,
        cells["validation_base_c1_e2"].trades,
        PLACEBO_BASE_SEED + order_index,
    )
    complete = complete_validation_quarters(bounds)
    qstats = summaries["validation_e2"]["quarters"]
    complete_rows = {
        quarter: qstats.get(quarter, {"n": 0, "expectancy": None, "win_rate": None})
        for quarter in complete
    }
    positive_complete = sum(
        row["expectancy"] is not None and row["expectancy"] > 0
        for row in complete_rows.values()
    )
    failures = []
    if summaries["discovery_e2"]["n"] < 50:
        failures.append("DISCOVERY_FILLS_LT_50")
    if summaries["validation_e2"]["n"] < 30:
        failures.append("VALIDATION_FILLS_LT_30")
    for side in ("long", "short"):
        if summaries["validation_e2"]["sides"][side]["n"] < 10:
            failures.append(f"VALIDATION_{side.upper()}_FILLS_LT_10")
    for name in ("discovery_e1", "discovery_e2", "validation_e1", "validation_e2"):
        value = summaries[name]["expectancy"]
        if value is None or value <= 0:
            failures.append(f"{name.upper()}_EXPECTANCY_NONPOSITIVE")
    for side in ("long", "short"):
        value = summaries["validation_e2"]["sides"][side]["expectancy"]
        if value is None or value <= 0:
            failures.append(f"VALIDATION_E2_{side.upper()}_EXPECTANCY_NONPOSITIVE")
    if len(complete) < 2:
        failures.append("COMPLETE_VALIDATION_QUARTERS_LT_2")
    elif positive_complete / len(complete) < 0.60:
        failures.append("POSITIVE_COMPLETE_QUARTERS_LT_60PCT")
    if not complete or complete_rows[complete[-1]]["expectancy"] is None or (
        complete_rows[complete[-1]]["expectancy"] <= 0
    ):
        failures.append("LATEST_COMPLETE_QUARTER_NONPOSITIVE")
    if not np.isfinite(dsr) or dsr < 0.95:
        failures.append("DSR_LT_0_95")
    if not placebos["available"]:
        failures.append("PLACEBO_MATCH_UNAVAILABLE")
    else:
        if placebos["observed_mean"] <= placebos["p97_5"]:
            failures.append("OBSERVED_NOT_ABOVE_PLACEBO_P97_5")
        if placebos["empirical_p"] > FAMILY_P:
            failures.append("PLACEBO_EMPIRICAL_P_GT_0_025")
    record = {
        "source": source,
        "symbol": contexts[source].symbol,
        "pass": not failures,
        "failures": failures,
        "complete_validation_quarters": complete_rows,
        "positive_complete_quarters": positive_complete,
        "dsr": {"trials": DSR_TRIALS, "n": len(validation_values), "hurdle": hurdle, "value": dsr},
        "placebo": placebos,
        "e1_e2_structural_parity": structural_parity,
        "summaries": summaries,
        "tapes": {
            name: {
                "diagnostics": cell.diagnostics,
                "trades": list(cell.trades),
                "source_events": list(cell.source_events),
                "event_sha256": event_hash(cell.tape),
            }
            for name, cell in cells.items()
        },
    }
    print(
        "DISCOVERY_RESULT", contexts[source].symbol,
        "PASS" if record["pass"] else "FAIL",
        f"discovery_n={summaries['discovery_e2']['n']}",
        f"validation_n={summaries['validation_e2']['n']}",
        f"validation_e2={summaries['validation_e2']['expectancy']}",
        f"dsr={dsr}",
        f"placebo_p={placebos['empirical_p']}",
        ",".join(failures) if failures else "none",
        flush=True,
    )
    return record


def common_bootstrap(tapes: Iterable) -> BootstrapSpec:
    tapes = tuple(tapes)
    if not tapes:
        raise RuntimeError("no tapes supplied to common bootstrap")
    frames = {(tape.first_day, tape.last_day) for tape in tapes}
    if len(frames) != 1:
        raise RuntimeError(f"account tapes do not share one calendar frame: {frames}")
    sets = [set(tape.eligible_flat_block_starts(BLOCK)) for tape in tapes]
    eligible = tuple(sorted(set.intersection(*sets)))
    if len(eligible) < 20:
        raise RuntimeError(f"common eligible block count below 20: {len(eligible)}")
    return BootstrapSpec(
        seed=BOOT_SEED, block_length=BLOCK, eligible_block_starts=eligible
    )


def policy_for(symbols: tuple[str, ...]) -> RiskPolicy:
    risk_map = {
        symbol: (0.0005 if symbol == "USDJPY" or symbol not in BASE_SYMBOLS else 0.0030)
        for symbol in symbols
    }
    return RiskPolicy("C1_UNIVERSE_005", risk_map, risk_map)


def exact_path0(tape, metas, policy: RiskPolicy, boot: BootstrapSpec) -> dict:
    reference = run_monte_carlo(
        tape, metas, (policy,), paths=1, path_start=0, bootstrap=boot,
        config=SimulationConfig(equity_mode=EquityMode.TWO_STOP),
    )[policy.name]
    actual = csharp_engine.run_csharp_monte_carlo(
        tape, metas, (policy,), paths=1, path_start=0, bootstrap=boot
    )[policy.name]
    mismatches = [
        name for name in (reference.rows.dtype.names or ())
        if reference.rows[name].tobytes() != actual.rows[name].tobytes()
    ]
    if mismatches:
        raise RuntimeError(f"Python/C# path-0 mismatch fields: {mismatches}")
    return {"exact": True, "row_sha256": actual.sha256(), "row": actual.rows[0].tolist()}


def _checkpoint_fingerprint(tape, metas, policy, boot, label, start, count) -> str:
    engine_files = (
        HERE / "v130_pass_policy.py",
        HERE / "v130_pass_policy_csharp.py",
        HERE / "v130_pass_policy_kernel.cs",
        HERE / "v130_risk_policy.py",
    )
    payload = {
        "label": label,
        "start": start,
        "count": count,
        "events": event_hash(tape),
        "first_day": tape.first_day.isoformat(),
        "last_day": tape.last_day.isoformat(),
        "policy": policy.normalized_dict(),
        "seed": boot.seed,
        "block": boot.block_length,
        "eligible": list(boot.eligible_block_starts or ()),
        "metas": {
            symbol: asdict(meta) for symbol, meta in sorted(metas.items())
        },
        "engine_sha256": {
            path.name: sha256_file(path) for path in engine_files
        },
        "experiment_bundle_sha256": experiment_bundle_sha256(),
        "simulation_config": json_safe(asdict(SimulationConfig())),
        "result_dtype": policy_engine.RESULT_DTYPE.descr,
        "runtime_provenance": runtime_provenance(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def run_chunks(
    tape, metas, policy: RiskPolicy, boot: BootstrapSpec, *,
    paths: int, path_start: int, label: str,
) -> CompactRun:
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for offset in range(0, paths, CHUNK):
        start = path_start + offset
        count = min(CHUNK, paths - offset)
        fingerprint = _checkpoint_fingerprint(
            tape, metas, policy, boot, label, start, count
        )
        checkpoint = CHECKPOINTS / f"{label}_{start}_{count}_{fingerprint[:16]}.npz"
        if checkpoint.exists():
            with np.load(checkpoint, allow_pickle=False) as saved:
                if str(saved["fingerprint"].item()) != fingerprint:
                    raise RuntimeError(f"checkpoint fingerprint mismatch: {checkpoint}")
                part_rows = saved["rows"]
        else:
            part = csharp_engine.run_csharp_monte_carlo(
                tape, metas, (policy,), paths=count, path_start=start, bootstrap=boot
            )[policy.name]
            part_rows = part.rows
            temporary = CHECKPOINTS / (
                f".{checkpoint.stem}.{os.getpid()}.tmp.npz"
            )
            try:
                np.savez_compressed(
                    temporary, fingerprint=np.asarray(fingerprint), rows=part_rows
                )
                temporary.replace(checkpoint)
            finally:
                if temporary.exists():
                    temporary.unlink()
        if part_rows.shape != (count,):
            raise RuntimeError(
                f"checkpoint row count mismatch: {checkpoint} {part_rows.shape} != {(count,)}"
            )
        if part_rows.dtype != policy_engine.RESULT_DTYPE:
            raise RuntimeError(
                f"checkpoint dtype mismatch: {checkpoint} "
                f"{part_rows.dtype.descr} != {policy_engine.RESULT_DTYPE.descr}"
            )
        expected_ids = np.arange(start, start + count, dtype=np.int32)
        if not np.array_equal(part_rows["path_id"], expected_ids):
            raise RuntimeError(f"checkpoint path IDs mismatch: {checkpoint}")
        rows.append(part_rows)
        done = offset + count
        if done % 5_000 == 0 or done == paths:
            print(f"MC_PROGRESS {label} {done}/{paths} path_start={path_start}", flush=True)
    return CompactRun(policy, np.concatenate(rows))


def counter_totals(run: CompactRun) -> dict:
    return {
        phase: {
            name: int(run.rows[f"{phase}_{name}"].sum()) for name in COUNTER_FIELDS
        }
        for phase in ("p1", "p2")
    }


def reason_counts(run: CompactRun) -> dict:
    output = {}
    for phase in ("p1", "p2"):
        values, counts = np.unique(run.rows[f"{phase}_reason"], return_counts=True)
        output[phase] = {
            str(int(value)): int(count) for value, count in zip(values, counts)
        }
    return output


def run_record(run: CompactRun) -> dict:
    return {
        "summary": asdict(run.summary()),
        "row_sha256": run.sha256(),
        "counter_totals": counter_totals(run),
        "reason_counts": reason_counts(run),
    }


def paired(candidate: CompactRun, control: CompactRun) -> dict:
    lower, n10, n01, p10_lower, p01_upper = candidate.paired_delta_lower(
        control, confidence=FAMILY_CONFIDENCE
    )
    discordant = n10 + n01
    p_value = (
        float(binomtest(n10, discordant, 0.5, alternative="greater").pvalue)
        if discordant else 1.0
    )
    hard_control = control.rows["hard"].astype(bool).tolist()
    hard_candidate = candidate.rows["hard"].astype(bool).tolist()
    control_minus_candidate_lower, hc10, hc01, _, _ = exact_paired_delta_lower(
        hard_control, hard_candidate, confidence=FAMILY_CONFIDENCE
    )
    return {
        "confidence": FAMILY_CONFIDENCE,
        "lower": lower,
        "n10_candidate_only_pass": n10,
        "n01_control_only_pass": n01,
        "point_delta": (n10 - n01) / len(candidate.rows),
        "p10_lower": p10_lower,
        "p01_upper": p01_upper,
        "mcnemar_exact_one_sided_p": p_value,
        "hard_candidate_minus_control_upper": -control_minus_candidate_lower,
        "hard_candidate_only": hc01,
        "hard_control_only": hc10,
    }


def retention(control: BuiltTape, candidate: BuiltTape) -> dict:
    control_by_symbol: dict[str, set[str]] = defaultdict(set)
    candidate_ids = {row["trade_id"] for row in candidate.trades}
    for row in control.trades:
        control_by_symbol[row["symbol"]].add(row["trade_id"])
    rows = {}
    all_control = set().union(*control_by_symbol.values()) if control_by_symbol else set()
    for symbol, identifiers in sorted(control_by_symbol.items()):
        kept = len(identifiers & candidate_ids)
        rows[symbol] = {
            "control": len(identifiers),
            "retained": kept,
            "fraction": kept / len(identifiers) if identifiers else 1.0,
        }
    retained_all = len(all_control & candidate_ids)
    return {
        "by_symbol": rows,
        "control_fills": len(control.trades),
        "candidate_total_fills": len(candidate.trades),
        "retained_control_fills": retained_all,
        "overall_fraction": retained_all / len(all_control) if all_control else 1.0,
        "net_fills": len(candidate.trades) - len(control.trades),
    }


def account_gate(candidate: dict, control: dict, comparison: dict, keep: dict) -> tuple[bool, list[str]]:
    failures = []
    if comparison["lower"] <= 0:
        failures.append("PAIRED_PASS_LOWER_NOT_POSITIVE")
    if comparison["mcnemar_exact_one_sided_p"] > FAMILY_P:
        failures.append("MCNEMAR_P_GT_0_025")
    if candidate["both_wilson_lower"] < 0.88:
        failures.append("BOTH_WILSON_LOWER_LT_0_88")
    if candidate["hard_probability"] > 0.003700:
        failures.append("HARD_GT_0_370PCT")
    if comparison["hard_candidate_minus_control_upper"] > 0.000500:
        failures.append("PAIRED_HARD_UPPER_GT_0_05PP")
    if candidate["timeout_probability"] > control["timeout_probability"]:
        failures.append("TIMEOUT_WORSE_THAN_CONTROL")
    candidate_median = float(candidate["median_total_days_success"])
    control_median = float(control["median_total_days_success"])
    if not math.isfinite(candidate_median) or not math.isfinite(control_median):
        failures.append("MEDIAN_DAYS_NONFINITE")
    elif candidate_median > control_median:
        failures.append("MEDIAN_DAYS_WORSE_THAN_CONTROL")
    if candidate["firm_probability"] != 0:
        failures.append("FIRM_BREACH_NONZERO")
    if keep["overall_fraction"] < 0.97:
        failures.append("C1_FILL_RETENTION_LT_97PCT")
    if any(row["fraction"] < 0.95 for row in keep["by_symbol"].values()):
        failures.append("SYMBOL_FILL_RETENTION_LT_95PCT")
    if keep["candidate_total_fills"] <= keep["control_fills"]:
        failures.append("TOTAL_FILLS_NOT_INCREASED")
    return not failures, failures


def account_stage(
    builds: dict[str, BuiltTape], sources_by_label: dict[str, tuple[str, ...]], *,
    paths: int, path_start: int, label: str,
) -> dict:
    labels = tuple(builds)
    union_sources = list(BASE_SOURCES)
    for cell in labels:
        for source in sources_by_label[cell]:
            if source not in union_sources:
                union_sources.append(source)
    metas = metadata_for_sources(tuple(union_sources))
    symbols = tuple(metas)
    configure_symbols(symbols)
    policy = policy_for(symbols)
    boot = common_bootstrap([build.tape for build in builds.values()])
    path0 = {
        cell: exact_path0(build.tape, metas, policy, boot) for cell, build in builds.items()
    }
    runs = {
        cell: run_chunks(
            build.tape, metas, policy, boot,
            paths=paths, path_start=path_start, label=f"{label}_{cell}",
        )
        for cell, build in builds.items()
    }
    control_run = runs["C1_CONTROL"]
    control_record = run_record(control_run)
    cells = {}
    for cell in labels:
        if cell == "C1_CONTROL":
            continue
        candidate_record = run_record(runs[cell])
        comparison = paired(runs[cell], control_run)
        keep = retention(builds["C1_CONTROL"], builds[cell])
        passed, failures = account_gate(
            candidate_record["summary"], control_record["summary"], comparison, keep
        )
        # The predeclared minimum-lot gate is a no-worse-than-control counter test.
        control_min = sum(
            control_record["counter_totals"][phase]["min_lot_substitutions"]
            for phase in ("p1", "p2")
        )
        candidate_min = sum(
            candidate_record["counter_totals"][phase]["min_lot_substitutions"]
            for phase in ("p1", "p2")
        )
        if candidate_min > control_min:
            failures.append("MIN_LOT_SUBSTITUTIONS_WORSE_THAN_CONTROL")
            passed = False
        cells[cell] = {
            "pass": passed,
            "failures": failures,
            "record": candidate_record,
            "paired": comparison,
            "retention": keep,
            "min_lot_substitutions": {
                "control": control_min, "candidate": candidate_min,
            },
        }
        print(
            "ACCOUNT_RESULT", label, cell, "PASS" if passed else "FAIL",
            f"control_both={control_record['summary']['both_probability']:.6f}",
            f"candidate_both={candidate_record['summary']['both_probability']:.6f}",
            f"candidate_lower={candidate_record['summary']['both_wilson_lower']:.6f}",
            f"candidate_hard={candidate_record['summary']['hard_probability']:.6f}",
            f"paired_lower={comparison['lower']:.6f}",
            f"paired_p={comparison['mcnemar_exact_one_sided_p']:.6g}",
            ",".join(failures) if failures else "none",
            flush=True,
        )
    return {
        "paths": paths,
        "path_start": path_start,
        "wilson_one_sided_confidence": WILSON_CONFIDENCE,
        "common_eligible_blocks": len(boot.eligible_block_starts or ()),
        "symbols": list(symbols),
        "risk": policy.normalized_dict(),
        "path0_python_csharp": path0,
        "control": control_record,
        "cells": cells,
        "tape_diagnostics": {
            cell: build.diagnostics for cell, build in builds.items()
        },
    }


def choose_winner(screen: dict, symbol_by_cell: dict[str, str]) -> str | None:
    survivors = [cell for cell, row in screen["cells"].items() if row["pass"]]
    if not survivors:
        return None
    survivors.sort(key=lambda cell: (
        -screen["cells"][cell]["paired"]["lower"],
        screen["cells"][cell]["record"]["summary"]["timeout_probability"],
        screen["cells"][cell]["record"]["summary"]["median_total_days_success"],
        symbol_by_cell[cell],
    ))
    return survivors[0]


def main() -> None:
    bundle = verify_committed_bundle()
    provenance = verify_provenance()
    regressions = protected_regressions()
    synthetics = synthetic_tests()
    contexts = load_contexts()
    bounds = split_bounds(contexts)
    print("TIMESTAMP_SPLIT", json.dumps(bounds.as_dict(), sort_keys=True), flush=True)

    control_e1 = build_tape(
        contexts, BASE_SOURCES, bounds, segment="discovery", cost_mult=1.0,
        momentum_atr_mult=MOMENTUM_C1,
    )
    control_first = build_tape(
        contexts, BASE_SOURCES, bounds, segment="discovery", cost_mult=2.0,
        momentum_atr_mult=MOMENTUM_C1,
    )
    control_second = build_tape(
        contexts, BASE_SOURCES, bounds, segment="discovery", cost_mult=2.0,
        momentum_atr_mult=MOMENTUM_C1,
    )
    if event_hash(control_first.tape) != event_hash(control_second.tape):
        raise RuntimeError("M15 C1 control did not reproduce identical event bytes")
    control_structural_parity = assert_e1_e2_structural_parity(
        control_e1, control_first, "C1_CONTROL:discovery"
    )
    print(
        "M15_CONTROL_DETERMINISM PASS",
        f"e1_events_sha256={event_hash(control_e1.tape)}",
        f"events_sha256={event_hash(control_first.tape)}",
        f"fills={len(control_first.trades)}", flush=True,
    )

    if "--preflight" in sys.argv[1:]:
        # Registered pre-flight stop (LF-worktree gate check): provenance,
        # protected regressions, synthetic tests, and the control E1/E2
        # structural-parity assertions have all passed by this point.  Exit
        # cleanly BEFORE any discovery outcome is computed or charged.
        print(
            "PREFLIGHT_COMPLETE control_e1_e2_structural_parity=PASS",
            f"control_fills={len(control_first.trades)}", flush=True,
        )
        return

    output = {
        "verdict": "INCOMPLETE",
        "tested_commit": bundle["commit"],
        "experiment_bundle": bundle,
        "runtime_provenance": runtime_provenance(),
        "provenance": provenance,
        "protected_regressions": regressions,
        "synthetic_tests": synthetics,
        "timestamp_split": bounds.as_dict(),
        "trial_ledger": {
            "start_floor": 315,
            "dsr_trials": DSR_TRIALS,
            "discovery_cells": 0,
            "account_screen_cells": 0,
            "confirmation_cells": 0,
            "maximum_end": 317,
            "charged_cells": 0,
            "end": 315,
        },
        "m15_control_determinism": {
            "e1_event_sha256": event_hash(control_e1.tape),
            "e1_diagnostics": control_e1.diagnostics,
            "e1_e2_structural_parity": control_structural_parity,
            "event_sha256": event_hash(control_first.tape),
            "diagnostics": control_first.diagnostics,
        },
        "discovery": {},
        "account_screen": None,
        "selected_winner": None,
        "confirmation": None,
    }
    write_result(output)

    discovery = {}
    for order_index, source in enumerate(CANDIDATES):
        output["trial_ledger"]["discovery_cells"] = order_index + 1
        refresh_ledger(output)
        write_result(output)
        discovery[source] = discovery_cell(contexts, bounds, source, order_index)
        output["discovery"] = discovery
        write_result(output)

    survivors = [source for source in CANDIDATES if discovery[source]["pass"]]
    if not survivors:
        output["verdict"] = "NO_SYMBOL_SURVIVED_DISCOVERY"
        write_result(output)
        print("FINAL NO_SYMBOL_SURVIVED_DISCOVERY", flush=True)
        print(f"RESULT_FILE {RESULT}", flush=True)
        return

    screen_builds = {"C1_CONTROL": control_first}
    sources_by_label = {"C1_CONTROL": BASE_SOURCES}
    symbol_by_cell = {}
    source_by_cell = {}
    for source in survivors:
        cell = contexts[source].symbol.replace(".", "_")
        screen_builds[cell] = build_tape(
            contexts, BASE_SOURCES + (source,), bounds,
            segment="discovery", cost_mult=2.0,
            momentum_atr_mult=MOMENTUM_C1,
        )
        sources_by_label[cell] = BASE_SOURCES + (source,)
        symbol_by_cell[cell] = contexts[source].symbol
        source_by_cell[cell] = source
    output["trial_ledger"]["account_screen_cells"] = len(survivors)
    refresh_ledger(output)
    write_result(output)
    screen = account_stage(
        screen_builds, sources_by_label,
        paths=SCREEN_PATHS, path_start=0, label="SCREEN",
    )
    output["account_screen"] = screen
    winner_cell = choose_winner(screen, symbol_by_cell)
    output["selected_winner"] = (
        None if winner_cell is None else {
            "cell": winner_cell,
            "source": source_by_cell[winner_cell],
            "symbol": symbol_by_cell[winner_cell],
        }
    )
    write_result(output)
    if winner_cell is None:
        output["verdict"] = "NO_SYMBOL_SURVIVED_ACCOUNT_SCREEN"
        write_result(output)
        print("FINAL NO_SYMBOL_SURVIVED_ACCOUNT_SCREEN", flush=True)
        print(f"RESULT_FILE {RESULT}", flush=True)
        return

    winner_source = source_by_cell[winner_cell]
    confirmation_builds = {
        "C1_CONTROL": build_tape(
            contexts, BASE_SOURCES, bounds, segment="validation", cost_mult=2.0,
            momentum_atr_mult=MOMENTUM_C1,
        ),
        winner_cell: build_tape(
            contexts, BASE_SOURCES + (winner_source,), bounds,
            segment="validation", cost_mult=2.0,
            momentum_atr_mult=MOMENTUM_C1,
        ),
    }
    confirmation_sources = {
        "C1_CONTROL": BASE_SOURCES,
        winner_cell: BASE_SOURCES + (winner_source,),
    }
    output["trial_ledger"]["confirmation_cells"] = 1
    refresh_ledger(output)
    write_result(output)
    confirmation = account_stage(
        confirmation_builds, confirmation_sources,
        paths=CONFIRM_PATHS, path_start=CONFIRM_START, label="CONFIRMATION",
    )
    output["confirmation"] = confirmation
    output["verdict"] = (
        "ONE_SYMBOL_NOMINATED_FOR_DEMO_FORWARD"
        if confirmation["cells"][winner_cell]["pass"]
        else "SYMBOL_CONFIRMATION_REJECTED"
    )
    write_result(output)
    print("FINAL", output["verdict"], flush=True)
    print(f"RESULT_FILE {RESULT}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        append_failure(exc)
        print("FATAL", type(exc).__name__, str(exc), flush=True)
        raise
