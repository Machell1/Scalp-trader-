"""Model-authored strategy tournament for DerivScalperEA.

Each model submits one or more candidate parameter sets in JSON. This runner
evaluates them against the current main strategy on real Deriv M15 spread-gated
data and promotes only a candidate that clears the existing anti-overfit gate.

This is an orchestrator, not a shortcut around HANDOFF.md:
  * real Deriv M15 spread-gated data is required for replacement decisions
  * pullback entry, no-AVWAP default, TP>=3, and spread-gated universe are hard
    promotion guardrails
  * candidates using simulator-only features can win research ranking, but they
    are not eligible to replace the EA until the EA implements the feature

Usage:
  python model_tournament.py --candidates model_candidates.json
  python model_tournament.py --candidates model_candidates.example.json --list
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LOCK_TRAIL_OFF = 99.0
DATA_DIR = str(HERE / "data" / "derivM15_spreadgated")

SPREAD_GATED = [
    "BTCUSD", "ETHUSD", "XRPUSD", "SOLUSD",
    "US Tech 100", "US SP 500", "Wall Street 30", "US Small Cap 2000",
    "Germany 40", "UK 100", "Japan 225", "France 40",
]

SHIPPED = {
    "direction": "cont",
    "entry_style": "limit",
    "entry_offset_atr": 0.6,
    "pending_expiry_bars": 3,
    "stop_atr": 1.0,
    "tp_atr": 3.0,
    "lock_trigger_atr": 0.25,
    "trail_atr": 0.5,
    "max_hold_bars": 8,
    "momentum_bars": 6,
    "momentum_atr": 2.0,
    "atr_period": 14,
}

CPARAMS_DEFAULTS = {
    "momentum_bars": 6,
    "momentum_atr": 2.0,
    "atr_period": 14,
    "direction": "cont",
    "entry_style": "stop",
    "entry_offset_atr": 0.05,
    "pending_expiry_bars": 2,
    "stop_atr": 1.0,
    "tp_atr": 1.5,
    "lock_trigger_atr": 0.25,
    "trail_atr": 0.5,
    "max_hold_bars": 8,
    "cost_atr_frac": 0.0,
    "trend_ema": 0,
    "long_only": False,
    "short_only": False,
    "vwap_window": 0,
    "vwap_min_bars": 8,
    "stop_mode": "atr",
    "adx_min": 0.0,
    "adx_period": 14,
    "require_di_agree": True,
    "htf_minutes": 0,
    "htf_ema": 50,
    "er_min": 0.0,
    "body_frac_min": 0.0,
    "persist_min": 0,
    "rv_pct_lo": 0.0,
    "rv_pct_hi": 1.0,
    "rv_win": 24,
    "rv_rank_win": 2000,
    "sess_start_hm": -1,
    "sess_end_hm": -1,
    "sess_tz": "America/New_York",
    "vol_gate_k": 0.0,
    "vol_sma": 20,
    "cancel_beyond_atr": 0.0,
    "hold_ext_bars": 0,
    "hold_ext_min_r": 0.0,
    "block_overlap": True,
}

np = None
pd = None
CParams = None
simulate_symbol_c = None
EMC = None
nppf = None
perm_test = None
psr = None
stt = None
load_spreadgated = None
real_cost_per_side = None


def load_backtest_backend() -> None:
    """Import heavy backtest dependencies only for full evaluation.

    This keeps `--list` useful on fresh cloud images before pandas/numpy are
    installed, while preserving the source-of-truth simulator for tournaments.
    """
    global np, pd, CParams, simulate_symbol_c, EMC, nppf, perm_test, psr, stt
    global load_spreadgated, real_cost_per_side

    if np is not None:
        return

    try:
        import numpy as _np
        import pandas as _pd
        from scalper_confluence import CParams as _CParams, simulate_symbol_c as _simulate_symbol_c
        from experiment import EMC as _EMC, nppf as _nppf, perm_test as _perm_test, psr as _psr, stt as _stt
        from walkforward_dsr import load_spreadgated as _load_spreadgated, real_cost_per_side as _real_cost_per_side
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing backtest dependency. Run `pip install -r backtest/requirements.txt` "
            "or at least install numpy and pandas before running a full tournament."
        ) from exc

    np = _np
    pd = _pd
    CParams = _CParams
    simulate_symbol_c = _simulate_symbol_c
    EMC = _EMC
    nppf = _nppf
    perm_test = _perm_test
    psr = _psr
    stt = _stt
    load_spreadgated = _load_spreadgated
    real_cost_per_side = _real_cost_per_side

# v1.24 EA default: v1.23 pure bracket exits plus v1.24 spread-cap hygiene.
MAIN_STRATEGY = {
    **SHIPPED,
    "lock_trigger_atr": LOCK_TRAIL_OFF,
    "trail_atr": LOCK_TRAIL_OFF,
}

# Simulator fields that map directly to the current EA's public inputs/defaults.
EA_SUPPORTED_FIELDS = {
    "momentum_bars",
    "momentum_atr",
    "atr_period",
    "direction",
    "entry_style",
    "entry_offset_atr",
    "pending_expiry_bars",
    "stop_atr",
    "tp_atr",
    "lock_trigger_atr",
    "trail_atr",
    "max_hold_bars",
}

# Promotion guardrails from HANDOFF.md. Models may explore outside these in their
# own branches, but such candidates cannot replace the main strategy.
HARD_GUARDRAIL_EXPECTED = {
    "direction": "cont",
    "entry_style": "limit",
    "vwap_window": 0,
}

# Cumulative prior research trials from the handoff-era studies. Add the number
# of model submissions on each run so DSR gets stricter as the tournament grows.
N_PRIOR_RESEARCH_TRIALS = 62


def cparams_fields() -> set[str]:
    return set(CPARAMS_DEFAULTS)


def load_candidate_file(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    candidates = raw.get("candidates") if isinstance(raw, dict) else raw
    if not isinstance(candidates, list):
        raise ValueError("candidate file must be a list or an object with a 'candidates' list")
    return candidates


def candidate_label(candidate: dict[str, Any]) -> str:
    model = str(candidate.get("model", "unknown-model")).strip()
    name = str(candidate.get("name", "unnamed")).strip()
    return f"{model}: {name}"


def normalize_params(candidate: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    raw_params = candidate.get("params", {})
    if not isinstance(raw_params, dict):
        raise ValueError(f"{candidate_label(candidate)} params must be an object")

    allowed = cparams_fields()
    unknown = sorted(set(raw_params) - allowed)
    if unknown:
        raise ValueError(f"{candidate_label(candidate)} has unknown CParams fields: {', '.join(unknown)}")

    params = dict(MAIN_STRATEGY)
    params.update(raw_params)

    guardrail_notes = []
    for key, expected in HARD_GUARDRAIL_EXPECTED.items():
        actual = params.get(key, CPARAMS_DEFAULTS[key])
        if actual != expected:
            guardrail_notes.append(f"{key}={actual!r} violates required {expected!r}")
    if float(params.get("tp_atr", 0.0)) < 3.0:
        guardrail_notes.append("tp_atr below 3.0 violates validated TP guardrail")

    unsupported = sorted(k for k, v in raw_params.items() if k not in EA_SUPPORTED_FIELDS and v != CPARAMS_DEFAULTS[k])
    return params, guardrail_notes, unsupported


def load_required_data(data_dir: Path, min_instruments: int) -> dict[str, pd.DataFrame]:
    data = load_spreadgated(str(data_dir))
    if len(data) < min_instruments:
        missing = [s for s in SPREAD_GATED if s not in data]
        msg = [
            f"Need at least {min_instruments} spread-gated CSVs in {data_dir} ({len(data)}/{len(SPREAD_GATED)} found).",
            "Run `python fetch_spreadgated.py` with MT5 open and logged in, then rerun this tournament.",
        ]
        if missing:
            msg.append(f"Missing: {', '.join(missing)}")
        raise FileNotFoundError("\n".join(msg))
    return data


def costs_for(data: dict[str, pd.DataFrame]) -> dict[str, float]:
    return {sym: real_cost_per_side(df) for sym, df in data.items()}


def collect(
    data: dict[str, pd.DataFrame],
    costs: dict[str, float],
    params: dict[str, Any],
    *,
    block: bool,
    cost_mult: float = 1.0,
) -> pd.DataFrame:
    recs = []
    for sym, df in data.items():
        cost = costs.get(sym, float("nan"))
        if not np.isfinite(cost):
            continue
        p = CParams(**{**params, "cost_atr_frac": cost * cost_mult, "block_overlap": block})
        trades, _ = simulate_symbol_c(df, p, 0, len(df))
        times = pd.to_datetime(df["time"]).to_numpy()
        for trade in trades:
            recs.append((times[trade["i"]], sym, int(trade["i"]), float(trade["r"])))
    if not recs:
        return pd.DataFrame(columns=["time", "sym", "sig_i", "r"])
    return pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time").reset_index(drop=True)


def quarter_split(trades: pd.DataFrame, is_frac: float) -> tuple[pd.DataFrame, pd.DataFrame, list[pd.Period]]:
    if trades.empty:
        return trades.copy(), trades.copy(), []
    t = trades.copy()
    t["q"] = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    quarters = sorted(t["q"].unique())
    n_is = max(1, int(len(quarters) * is_frac))
    is_qs = set(quarters[:n_is])
    oos_qs = quarters[n_is:]
    return t.loc[t["q"].isin(is_qs)], t.loc[t["q"].isin(oos_qs)], oos_qs


def walkforward_efficiency(trades: pd.DataFrame, oos_qs: list[pd.Period]) -> float:
    if trades.empty or not oos_qs:
        return float("nan")
    t = trades.copy()
    t["q"] = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    vals = []
    for q in oos_qs:
        q_start = t.loc[t["q"] == q, "time"].min()
        is_r = t.loc[t["time"] < q_start, "r"].to_numpy(float)
        oos_r = t.loc[t["q"] == q, "r"].to_numpy(float)
        if is_r.size < 30 or oos_r.size < 3:
            continue
        is_exp = float(is_r.mean())
        if is_exp > 0:
            vals.append(float(oos_r.mean()) / is_exp)
    return float(np.mean(vals)) if vals else float("nan")


def dsr_hurdle(n_trials: int, n_obs: int) -> float:
    var_sr = 1.0 / max(2, n_obs - 1)
    z1 = nppf(1 - 1.0 / max(2, n_trials))
    z2 = nppf(1 - 1.0 / max(2, n_trials) * math.exp(-1))
    return math.sqrt(var_sr) * ((1 - EMC) * z1 + EMC * z2)


def paired_t(base_oos_nb: pd.DataFrame, cand_oos_nb: pd.DataFrame) -> float:
    base = base_oos_nb.set_index(["sym", "sig_i"])["r"]
    cand = cand_oos_nb.set_index(["sym", "sig_i"])["r"]
    joined = pd.concat([base.rename("base"), cand.rename("cand")], axis=1).dropna()
    diff = (joined["cand"] - joined["base"]).to_numpy(float)
    if diff.size < 6:
        return float("nan")
    sd = diff.std(ddof=1)
    return float(diff.mean() / (sd / math.sqrt(diff.size))) if sd > 0 else float("nan")


def evaluate_candidate(
    candidate: dict[str, Any],
    params: dict[str, Any],
    guardrail_notes: list[str],
    unsupported: list[str],
    data: dict[str, pd.DataFrame],
    costs: dict[str, float],
    baseline: dict[str, Any],
    n_trials: int,
    is_frac: float,
) -> dict[str, Any]:
    trades = collect(data, costs, params, block=True)
    is_trades, oos_trades, oos_qs = quarter_split(trades, is_frac)
    oos_r = oos_trades["r"].to_numpy(float)
    is_r = is_trades["r"].to_numpy(float)
    so, si = stt(oos_r), stt(is_r)

    trades2x = collect(data, costs, params, block=True, cost_mult=2.0)
    _, oos2, _ = quarter_split(trades2x, is_frac)
    so2 = stt(oos2["r"].to_numpy(float))

    nb_trades = collect(data, costs, params, block=False)
    _, nb_oos, _ = quarter_split(nb_trades, is_frac)

    p_perm = float("nan")
    p_t = paired_t(baseline["nb_oos"], nb_oos)
    if len(nb_oos) < len(baseline["nb_oos"]) * 0.98:
        p_perm = perm_test(baseline["nb_oos"]["r"].to_numpy(float), nb_oos["r"].to_numpy(float))

    q_group = oos_trades.groupby("q")["r"].mean() if "q" in oos_trades else pd.Series(dtype=float)
    qpos, qn = int((q_group > 0).sum()), int(len(q_group))

    sym_group = oos_trades.groupby("sym")["r"].agg(["mean", "count"]) if not oos_trades.empty else pd.DataFrame()
    sym_eligible = sym_group[sym_group["count"] >= 10] if not sym_group.empty else sym_group
    sym_pos, sym_tot = int((sym_eligible["mean"] > 0).sum()), int(len(sym_eligible))

    sr0 = dsr_hurdle(n_trials, max(so["n"], 2))
    dsr = psr(oos_r, sr0)
    wfe = walkforward_efficiency(trades, oos_qs)
    dexp = so["exp"] - baseline["oos_stats"]["exp"]
    dtot = so["tot"] - baseline["oos_stats"]["tot"]

    transform_gate = np.isfinite(p_t) and p_t > 1.96
    select_gate = not np.isfinite(p_perm) or p_perm < 0.05
    gates = {
        "hard guardrails": not guardrail_notes,
        "EA-supported replacement": not unsupported,
        "marginal OOS expectancy > main": dexp > 0,
        "marginal total R > main": dtot > 0,
        "paired/selectivity edge": transform_gate or select_gate,
        "WFE >= 0.30": np.isfinite(wfe) and wfe >= 0.30,
        "DSR >= 0.95": np.isfinite(dsr) and dsr >= 0.95,
        "2x cost OOS exp > 0": so2["exp"] > 0,
        "OOS quarters >= 60% positive": qn > 0 and qpos >= math.ceil(qn * 0.6),
        "symbols >= 60% positive": sym_tot > 0 and sym_pos >= math.ceil(sym_tot * 0.6),
        "powered sample N>=250": so["n"] >= 250,
    }
    verdict = "REPLACE" if all(gates.values()) else ("RESEARCH-WIN" if so["exp"] > 0 and dexp > 0 else "NO-SHIP")

    return {
        "label": candidate_label(candidate),
        "model": candidate.get("model", "unknown-model"),
        "name": candidate.get("name", "unnamed"),
        "rationale": candidate.get("rationale", ""),
        "params": params,
        "raw_params": candidate.get("params", {}),
        "unsupported": unsupported,
        "guardrail_notes": guardrail_notes,
        "stats": so,
        "dexp": dexp,
        "dtot": dtot,
        "paired_t": p_t,
        "perm_p": p_perm,
        "wfe": wfe,
        "dsr": float(dsr) if np.isfinite(dsr) else 0.0,
        "exp2x": so2["exp"],
        "qpos": qpos,
        "qn": qn,
        "sym_pos": sym_pos,
        "sym_tot": sym_tot,
        "gates": gates,
        "verdict": verdict,
    }


def rank_key(row: dict[str, Any]) -> tuple[int, int, float, float, float]:
    return (
        1 if row["verdict"] == "REPLACE" else 0,
        1 if row["verdict"] == "RESEARCH-WIN" else 0,
        float(row["dexp"]),
        float(row["stats"]["exp"]),
        float(row["dsr"]),
    )


def render_report(results: list[dict[str, Any]], baseline: dict[str, Any], data_dir: Path) -> str:
    b = baseline["oos_stats"]
    lines = [
        "# Model Strategy Tournament Report",
        "",
        f"Data: `{data_dir}`",
        f"Main strategy OOS: N={b['n']} exp={b['exp']:+.4f}R t={b['t']:+.2f} total={b['tot']:+.1f}R",
        "",
        "| Rank | Verdict | Candidate | N | Exp | dExp | paired_t | perm_p | WFE | DSR | 2x Exp | Q+ | Sym+ | Notes |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(sorted(results, key=rank_key, reverse=True), start=1):
        st = row["stats"]
        perm = f"{row['perm_p']:.3f}" if np.isfinite(row["perm_p"]) else "--"
        notes = []
        if row["guardrail_notes"]:
            notes.append("guardrail: " + "; ".join(row["guardrail_notes"]))
        if row["unsupported"]:
            notes.append("EA unsupported: " + ", ".join(row["unsupported"]))
        note = "<br>".join(notes) if notes else ""
        lines.append(
            f"| {rank} | {row['verdict']} | {row['label']} | {st['n']} | {st['exp']:+.4f} | "
            f"{row['dexp']:+.4f} | {row['paired_t']:+.2f} | {perm} | {row['wfe']:.2f} | "
            f"{row['dsr']:.2f} | {row['exp2x']:+.4f} | {row['qpos']}/{row['qn']} | "
            f"{row['sym_pos']}/{row['sym_tot']} | {note} |"
        )
    return "\n".join(lines) + "\n"


def write_champion(path: Path, winner: dict[str, Any], baseline: dict[str, Any]) -> None:
    payload = {
        "champion": {
            "model": winner["model"],
            "name": winner["name"],
            "verdict": winner["verdict"],
            "params": winner["params"],
            "raw_params": winner["raw_params"],
            "stats": winner["stats"],
            "dexp_vs_previous_main": winner["dexp"],
            "previous_main_stats": baseline["oos_stats"],
        }
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate model-authored EA candidates against the current main strategy")
    ap.add_argument("--candidates", default=str(HERE / "model_candidates.json"), help="JSON file with candidate submissions")
    ap.add_argument("--data", default=DATA_DIR, help="Directory with spread-gated Deriv M15 CSVs")
    ap.add_argument("--is-frac", type=float, default=0.70, help="Fraction of calendar quarters treated as in-sample")
    ap.add_argument("--min-instruments", type=int, default=8, help="Minimum spread-gated instruments required")
    ap.add_argument("--report", default=str(HERE / "model_tournament_report.md"), help="Markdown report path")
    ap.add_argument("--champion", default=str(HERE / "champion_strategy.json"), help="Champion JSON path written only on REPLACE")
    ap.add_argument("--list", action="store_true", help="Validate and list candidate submissions without loading data")
    args = ap.parse_args()

    cand_path = Path(args.candidates)
    if not cand_path.is_file():
        print(f"Candidate file not found: {cand_path}", file=sys.stderr)
        print("Copy backtest/model_candidates.example.json to backtest/model_candidates.json and have each model add a proposal.", file=sys.stderr)
        return 2

    try:
        raw_candidates = load_candidate_file(cand_path)
        normalized = [(c, *normalize_params(c)) for c in raw_candidates]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid candidate file: {exc}", file=sys.stderr)
        return 2

    if args.list:
        for candidate, params, guardrails, unsupported in normalized:
            status = "promotion-eligible" if not guardrails and not unsupported else "research-only"
            print(f"{candidate_label(candidate)}  [{status}]")
            if guardrails:
                print(f"  guardrails: {'; '.join(guardrails)}")
            if unsupported:
                print(f"  EA unsupported: {', '.join(unsupported)}")
            changed = {k: v for k, v in candidate.get("params", {}).items()}
            print(f"  params: {json.dumps(changed, sort_keys=True)}")
        return 0

    try:
        load_backtest_backend()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    data_dir = Path(args.data)
    try:
        data = load_required_data(data_dir, args.min_instruments)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    costs = costs_for(data)
    invalid_costs = [sym for sym, cost in costs.items() if not np.isfinite(cost)]
    if invalid_costs:
        print(f"Missing spread/ATR cost for: {', '.join(invalid_costs)}", file=sys.stderr)
        return 1

    baseline_trades = collect(data, costs, MAIN_STRATEGY, block=True)
    _, baseline_oos, baseline_qs = quarter_split(baseline_trades, args.is_frac)
    baseline_nb = collect(data, costs, MAIN_STRATEGY, block=False)
    _, baseline_nb_oos, _ = quarter_split(baseline_nb, args.is_frac)
    baseline = {
        "oos_stats": stt(baseline_oos["r"].to_numpy(float)),
        "oos_qs": baseline_qs,
        "nb_oos": baseline_nb_oos,
    }
    if baseline["oos_stats"]["n"] < 250:
        print(f"Main strategy produced only {baseline['oos_stats']['n']} OOS trades; need more data.", file=sys.stderr)
        return 1

    n_trials = N_PRIOR_RESEARCH_TRIALS + len(normalized)
    results = [
        evaluate_candidate(candidate, params, guardrails, unsupported, data, costs, baseline, n_trials, args.is_frac)
        for candidate, params, guardrails, unsupported in normalized
    ]

    report = render_report(results, baseline, data_dir)
    Path(args.report).write_text(report, encoding="utf-8")
    print(report)

    winners = [r for r in results if r["verdict"] == "REPLACE"]
    if winners:
        winner = sorted(winners, key=rank_key, reverse=True)[0]
        write_champion(Path(args.champion), winner, baseline)
        print(f"Champion written to {args.champion}: {winner['label']}")
        return 0

    print("No candidate earned replacement. Main strategy remains champion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
