"""Shared evaluation gate for the model arena.

Evaluates candidate strategy configs against the reigning champion on the
spread-gated Deriv M15 universe with real per-instrument cost, calendar-quarter
walk-forward, DSR deflation, 2× cost stress, and paired/permutation tests.

Used by model_arena.py to run model-vs-model tournaments and champion challenges.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from experiment import EMC, n_eff_symbols, nppf, perm_test, psr, stt
from scalper_confluence import CParams, simulate_symbol_c
from walkforward_dsr import (
    DATA_DIR,
    load_spreadgated,
    quarter_signs_from_trades,
    quarter_walkforward,
    real_cost_per_side,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ARENA_DIR = os.path.join(HERE, "arena")
CHAMPION_PATH = os.path.join(ARENA_DIR, "champion.json")
OFF = 99.0  # lock/trail disabled (pure bracket)


# ---------------------------------------------------------------------------
# Champion / submission I/O
# ---------------------------------------------------------------------------
def default_champion_params() -> dict[str, Any]:
    """v1.23 pure-bracket config (matches live EA defaults)."""
    return dict(
        direction="cont",
        entry_style="limit",
        entry_offset_atr=0.6,
        pending_expiry_bars=3,
        stop_atr=1.0,
        tp_atr=3.0,
        lock_trigger_atr=OFF,
        trail_atr=OFF,
        max_hold_bars=8,
        momentum_bars=6,
        momentum_atr=2.0,
        atr_period=14,
    )


def load_champion(path: str | None = None) -> dict[str, Any]:
    p = path or CHAMPION_PATH
    if not os.path.isfile(p):
        return dict(
            version="1.23",
            label="Pure bracket pullback 0.6 / TP 3 / hold 8",
            model_id="baseline",
            promoted_at=None,
            n_cumulative_trials=68,
            params=default_champion_params(),
        )
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_champion(champion: dict[str, Any], path: str | None = None) -> None:
    p = path or CHAMPION_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(champion, f, indent=2)
        f.write("\n")


def mk_params(base: dict[str, Any], cost: float, block: bool = True) -> CParams:
    d = dict(base)
    d["cost_atr_frac"] = cost
    d["block_overlap"] = block
    return CParams(**d)


def collect_trades(
    data: dict[str, pd.DataFrame],
    costs: dict[str, float],
    params: dict[str, Any],
    block: bool = True,
    cost_mult: float = 1.0,
) -> pd.DataFrame:
    recs = []
    for sym, df in data.items():
        c = costs.get(sym, float("nan"))
        if not np.isfinite(c):
            continue
        p = mk_params(params, c * cost_mult, block)
        tr, _ = simulate_symbol_c(df, p, 0, len(df))
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in tr:
            recs.append((tt[t["i"]], sym, t["i"], float(t["r"])))
    if not recs:
        return pd.DataFrame(columns=["time", "sym", "sig_i", "r"])
    return pd.DataFrame(recs, columns=["time", "sym", "sig_i", "r"]).sort_values("time").reset_index(drop=True)


def q_split(trades: pd.DataFrame, is_frac: float = 0.70):
    t = trades.copy()
    t["q"] = pd.PeriodIndex(pd.to_datetime(t["time"]), freq="Q")
    qs = sorted(t["q"].unique())
    n_is = max(1, int(len(qs) * is_frac))
    is_qs, oos_qs = set(qs[:n_is]), qs[n_is:]
    return t[t["q"].isin(is_qs)], t[t["q"].isin(oos_qs)], oos_qs


def dsr_hurdle(n_trials: int, n_obs: int) -> float:
    var_null = 1.0 / max(2, n_obs - 1)
    N = max(2, n_trials)
    z1 = nppf(1 - 1.0 / N)
    z2 = nppf(1 - 1.0 / N * math.exp(-1))
    return math.sqrt(var_null) * ((1 - EMC) * z1 + EMC * z2)


@dataclass
class EvalResult:
    submission_id: str
    model_id: str
    label: str
    kind: str
    params: dict[str, Any]
    n_oos: int = 0
    oos_exp: float = 0.0
    oos_t: float = 0.0
    d_exp: float = 0.0
    wfe: float = float("nan")
    pair_t: float = float("nan")
    perm_p: float = float("nan")
    exp_2x: float = 0.0
    dsr: float = 0.0
    qpos: int = 0
    qn: int = 0
    sym_pos: int = 0
    sym_tot: int = 0
    gates: dict[str, bool] = field(default_factory=dict)
    verdict: str = "NO-SHIP"
    qualifies: bool = False
    beats_champion: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "model_id": self.model_id,
            "label": self.label,
            "kind": self.kind,
            "params": self.params,
            "n_oos": self.n_oos,
            "oos_exp": self.oos_exp,
            "oos_t": self.oos_t,
            "d_exp": self.d_exp,
            "wfe": self.wfe,
            "pair_t": self.pair_t,
            "perm_p": self.perm_p,
            "exp_2x": self.exp_2x,
            "dsr": self.dsr,
            "qpos": self.qpos,
            "qn": self.qn,
            "sym_pos": self.sym_pos,
            "sym_tot": self.sym_tot,
            "gates": self.gates,
            "verdict": self.verdict,
            "qualifies": self.qualifies,
            "beats_champion": self.beats_champion,
        }


def evaluate_submission(
    submission: dict[str, Any],
    data: dict[str, pd.DataFrame],
    costs: dict[str, float],
    champion_params: dict[str, Any],
    champion_oos_exp: float,
    champion_oos_tot: float,
    champion_oos_nb: np.ndarray,
    champion_prd_oos: pd.Series,
    n_trials: int,
    is_frac: float = 0.70,
) -> EvalResult:
    """Evaluate one arena submission vs the champion baseline."""
    kind = submission.get("kind", "geom")
    params = {**champion_params, **submission.get("params", {})}
    sub_id = submission.get("candidate_id") or submission.get("submission_id", "unknown")
    model_id = submission.get("model_id", "unknown")
    label = submission.get("label", sub_id)

    blk = collect_trades(data, costs, params, block=True)
    c_is, c_oos, _ = q_split(blk, is_frac)
    so = stt(c_oos["r"].to_numpy())
    si = stt(c_is["r"].to_numpy())
    d_exp = so["exp"] - champion_oos_exp
    wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else float("nan")

    # Filter: permutation vs random subset of champion trades
    if kind == "filter":
        kept_nb = q_split(collect_trades(data, costs, params, block=False), is_frac)[1]["r"].to_numpy()
        perm_p = perm_test(champion_oos_nb, kept_nb)
        pair_t = float("nan")
    else:
        perm_p = float("nan")
        prd = q_split(collect_trades(data, costs, params, block=False), is_frac)[1]
        prd_oos = prd.set_index(["sym", "sig_i"])["r"]
        joined = pd.concat([champion_prd_oos.rename("b"), prd_oos.rename("c")], axis=1).dropna()
        d = (joined["c"] - joined["b"]).to_numpy()
        pair_t = (
            d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
            if len(d) > 5 and d.std(ddof=1) > 0
            else float("nan")
        )

    oos2 = q_split(collect_trades(data, costs, params, block=True, cost_mult=2.0), is_frac)[1]
    exp_2x = stt(oos2["r"].to_numpy())["exp"]

    qg = c_oos.groupby(pd.PeriodIndex(pd.to_datetime(c_oos["time"]), freq="Q"))["r"].mean()
    qpos, qn = int((qg > 0).sum()), len(qg)
    sg = c_oos.groupby("sym")["r"].agg(["mean", "count"])
    sym_pos = int(((sg["mean"] > 0) & (sg["count"] >= 10)).sum())
    sym_tot = int((sg["count"] >= 10).sum())

    sr0 = dsr_hurdle(n_trials, so["n"])
    dsr = psr(c_oos["r"].to_numpy(), sr0)

    pr, _ = n_eff_symbols(data)
    n_eff_tr = so["n"] * (pr / len(data))
    mde = 1.3 * (1.96 + 0.84) / math.sqrt(max(1, n_eff_tr))

    d_tot = so["tot"] - champion_oos_tot
    if kind == "filter":
        gate2 = np.isfinite(perm_p) and perm_p < 0.05
    elif kind == "exit":
        gate2 = np.isfinite(pair_t) and pair_t > 1.96
    else:
        gate2 = d_exp > 0 and d_tot > 0

    gates = {
        "marginal OOS dExp > 0": d_exp > 0,
        "selection test (perm_p<0.05 or pair_t>1.96)": gate2,
        "WFE >= 0.30": np.isfinite(wfe) and wfe >= 0.3,
        "DSR >= 0.95": np.isfinite(dsr) and dsr >= 0.95,
        "powered (N>=250, exp>MDE)": so["n"] >= 250 and so["exp"] > mde,
        "2× cost stress OOS exp > 0": exp_2x > 0,
        "OOS quarters >= 60% positive": qn > 0 and qpos >= math.ceil(qn * 0.6),
        "breadth >= 60% symbols positive": sym_tot > 0 and sym_pos >= math.ceil(sym_tot * 0.6),
    }

    verdict = "SHIP" if all(gates.values()) else ("watch" if (d_exp > 0 and so["exp"] > 0) else "NO-SHIP")
    qualifies = d_exp > 0 and exp_2x > 0 and so["exp"] > 0
    beats_champion = verdict == "SHIP" and d_exp > 0

    return EvalResult(
        submission_id=sub_id,
        model_id=model_id,
        label=label,
        kind=kind,
        params=params,
        n_oos=so["n"],
        oos_exp=so["exp"],
        oos_t=so["t"],
        d_exp=d_exp,
        wfe=wfe,
        pair_t=pair_t,
        perm_p=perm_p,
        exp_2x=exp_2x,
        dsr=dsr if np.isfinite(dsr) else 0.0,
        qpos=qpos,
        qn=qn,
        sym_pos=sym_pos,
        sym_tot=sym_tot,
        gates=gates,
        verdict=verdict,
        qualifies=qualifies,
        beats_champion=beats_champion,
    )


def load_submissions(submissions_dir: str | None = None) -> list[dict[str, Any]]:
    root = submissions_dir or os.path.join(ARENA_DIR, "submissions")
    out = []
    if not os.path.isdir(root):
        return out
    for model_dir in sorted(os.listdir(root)):
        mpath = os.path.join(root, model_dir)
        if not os.path.isdir(mpath):
            continue
        for fn in sorted(os.listdir(mpath)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(mpath, fn), encoding="utf-8") as f:
                sub = json.load(f)
            sub.setdefault("model_id", model_dir)
            sub.setdefault("candidate_id", os.path.splitext(fn)[0])
            out.append(sub)
    return out


def best_per_model(results: list[EvalResult]) -> list[EvalResult]:
    """Keep each model's highest dExp submission for the round-robin."""
    by_model: dict[str, EvalResult] = {}
    for r in results:
        prev = by_model.get(r.model_id)
        if prev is None or r.d_exp > prev.d_exp:
            by_model[r.model_id] = r
    return sorted(by_model.values(), key=lambda x: (-x.d_exp, -x.dsr, -x.oos_exp))


def run_evaluation(
    submissions: list[dict[str, Any]] | None = None,
    data_dir: str | None = None,
    is_frac: float = 0.70,
) -> tuple[dict[str, Any], EvalResult, list[EvalResult]]:
    """Run full arena evaluation. Returns (champion_meta, champion_eval, all_results)."""
    champion = load_champion()
    champ_params = champion.get("params", default_champion_params())
    n_trials = int(champion.get("n_cumulative_trials", 68))

    data = load_spreadgated(data_dir or DATA_DIR)
    if len(data) < 8:
        raise FileNotFoundError(
            f"Need spread-gated CSVs in {data_dir or DATA_DIR}/ "
            f"({len(data)} found). Run: python fetch_spreadgated.py"
        )

    costs = {s: real_cost_per_side(df) for s, df in data.items()}

    # Champion baseline metrics
    champ_blk = collect_trades(data, costs, champ_params, block=True)
    _, champ_oos, _ = q_split(champ_blk, is_frac)
    champ_so = stt(champ_oos["r"].to_numpy())
    champ_nb = q_split(collect_trades(data, costs, champ_params, block=False), is_frac)[1]["r"].to_numpy()
    champ_prd = q_split(collect_trades(data, costs, champ_params, block=False), is_frac)[1]
    champ_prd_oos = champ_prd.set_index(["sym", "sig_i"])["r"]
    champ_oos_tot = champ_so["tot"]

    champ_eval = EvalResult(
        submission_id="champion",
        model_id=champion.get("model_id", "baseline"),
        label=champion.get("label", "Champion"),
        kind="champion",
        params=champ_params,
        n_oos=champ_so["n"],
        oos_exp=champ_so["exp"],
        oos_t=champ_so["t"],
        d_exp=0.0,
        verdict="CHAMPION",
        qualifies=True,
    )

    subs = submissions if submissions is not None else load_submissions()
    results = []
    for sub in subs:
        results.append(
            evaluate_submission(
                sub, data, costs, champ_params,
                champ_so["exp"], champ_oos_tot, champ_nb, champ_prd_oos,
                n_trials + len(subs), is_frac,
            )
        )

    return champion, champ_eval, results
