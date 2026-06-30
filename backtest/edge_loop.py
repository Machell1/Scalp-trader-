"""Pre-registered edge-discovery loop for the Deriv scalper.

The runner tries a small set of strategy families that were planned before the
run, evaluates only out-of-sample performance for selection, and labels an idea
as SHIP only if it survives breadth, cost-stress, quarter-stability, WFE, and
deflated-Sharpe gates.

Data is intentionally not fetched here. Export CSVs from TradingView or fetch
Deriv data with fetch_diverse.py, then place them under backtest/data/<tf>/ with
columns: time, open, high, low, close, volume.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

import scalper_backtest as B
from experiment import EMC, nppf, psr, stt
from scalper_confluence import CParams, rs_of, simulate_symbol_c

COST_REAL = 0.02
COST_STRESS = 0.04

CLASS = {
    **{s: "FX" for s in ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY"]},
    **{s: "METAL" for s in ["XAUUSD", "XAGUSD", "XPTUSD", "XCUUSD"]},
    **{s: "ENERGY" for s in ["US_Oil", "UK_Brent_Oil", "NGAS"]},
    **{s: "CRYPTO" for s in ["BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD", "SOLUSD", "BCHUSD"]},
    **{s: "INDEX" for s in ["Germany_40", "UK_100", "Japan_225", "France_40", "Australia_200", "Hong_Kong_50"]},
}
EDGE_CLASSES = {"CRYPTO", "INDEX"}


@dataclass(frozen=True)
class Idea:
    label: str
    overrides: dict
    universe: str = "all"


def planned_ideas() -> list[Idea]:
    """Small, inspectable search space: geometry first, filters only as add-ons."""
    ideas = [
        Idea("baseline chase stop tp3", {}),
        Idea("shipped pullback 0.6", dict(entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3)),
        Idea("edge-pocket pullback 0.6", dict(entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3), "edge-pocket"),
    ]

    for off in (0.4, 0.6, 0.8):
        for expiry in (2, 3, 4):
            ideas.append(Idea(f"pullback off{off:.1f} exp{expiry}", dict(entry_style="limit", entry_offset_atr=off, pending_expiry_bars=expiry)))
            ideas.append(Idea(f"edge-pocket off{off:.1f} exp{expiry}", dict(entry_style="limit", entry_offset_atr=off, pending_expiry_bars=expiry), "edge-pocket"))

    add_on_filters = [
        ("adx20", dict(adx_min=20.0)),
        ("ema50 slope", dict(trend_ema=50)),
        ("er03", dict(er_min=0.3)),
        ("body05", dict(body_frac_min=0.5)),
        ("rv20-80", dict(rv_pct_lo=0.2, rv_pct_hi=0.8)),
    ]
    for name, ov in add_on_filters:
        ideas.append(
            Idea(
                f"edge-pocket pull0.6 + {name}",
                dict(entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3, **ov),
                "edge-pocket",
            )
        )
    return ideas


def mk_params(overrides: dict, cost: float) -> CParams:
    return CParams(**{**dict(tp_atr=3.0), **overrides, "cost_atr_frac": cost})


def select_universe(data: dict[str, pd.DataFrame], universe: str) -> dict[str, pd.DataFrame]:
    if universe == "all":
        return data
    if universe == "edge-pocket":
        selected = {sym: df for sym, df in data.items() if CLASS.get(sym) in EDGE_CLASSES}
        return selected or data
    raise ValueError(f"unknown universe: {universe}")


def n_eff_symbols(data: dict[str, pd.DataFrame]) -> tuple[float, float]:
    if len(data) < 2:
        return float(len(data)), 0.0
    rets = {}
    for sym, df in data.items():
        rets[sym] = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["time"])).pct_change()
    matrix = pd.concat(rets, axis=1, sort=True).dropna()
    if matrix.shape[1] < 2 or len(matrix) < 10:
        return float(matrix.shape[1]), 0.0
    corr = matrix.corr().to_numpy()
    ev = np.linalg.eigvalsh(corr)
    ev = ev[ev > 0]
    if ev.size == 0:
        return 1.0, 0.0
    participation = float((ev.sum() ** 2) / np.square(ev).sum())
    mean_r = float((corr.sum() - len(corr)) / (len(corr) * (len(corr) - 1)))
    return participation, mean_r


def split_bounds(df: pd.DataFrame, split: str) -> tuple[int, int]:
    n = len(df)
    cut = int(n * 0.7)
    if split == "is":
        return 0, cut
    if split == "oos":
        return cut, n
    if split == "all":
        return 0, n
    raise ValueError(f"unknown split: {split}")


def run_idea(data: dict[str, pd.DataFrame], idea: Idea, cost: float, split: str):
    params = mk_params(idea.overrides, cost)
    scoped = select_universe(data, idea.universe)
    per_symbol = {}
    records = []
    counters = dict(signals=0, passed=0, nonfill=0)
    for sym, df in scoped.items():
        lo, hi = split_bounds(df, split)
        trades, cnt = simulate_symbol_c(df, params, lo, hi)
        per_symbol[sym] = np.array(rs_of(trades), float)
        times = pd.to_datetime(df["time"]).to_numpy()
        for trade in trades:
            records.append((times[trade["i"]], sym, trade["r"]))
        for key in counters:
            counters[key] += cnt[key]
    pool = np.concatenate([a for a in per_symbol.values() if a.size]) if any(a.size for a in per_symbol.values()) else np.array([])
    return pool, per_symbol, records, counters


def quarter_signs(records: Iterable[tuple]) -> tuple[int, int]:
    rows = list(records)
    if not rows:
        return 0, 0
    df = pd.DataFrame(rows, columns=["time", "symbol", "r"])
    df["q"] = pd.PeriodIndex(pd.to_datetime(df["time"]), freq="Q")
    by_q = df.groupby("q")["r"].mean()
    return int((by_q > 0).sum()), int(len(by_q))


def dsr_hurdle(sharpes: list[float]) -> float:
    sr = np.array([s for s in sharpes if np.isfinite(s)], float)
    if sr.size < 2:
        return 0.0
    var_sr = float(np.var(sr, ddof=1))
    if var_sr <= 0:
        return 0.0
    n = len(sr)
    z1 = nppf(1 - 1.0 / n)
    z2 = nppf(1 - 1.0 / n * math.exp(-1))
    return math.sqrt(var_sr) * ((1 - EMC) * z1 + EMC * z2)


def verdict(row: dict, sr0: float) -> tuple[str, float]:
    dsr = psr(row["pool"], sr0)
    dsr = float(dsr) if np.isfinite(dsr) else 0.0
    gates = [
        row["n_symbols"] >= 3,
        row["so"]["n"] >= 250,
        row["so"]["exp"] > 0,
        row["exp_stress"] > 0,
        row["wfe"] >= 0.30,
        row["t_haircut"] >= 1.96,
        dsr >= 0.95,
        row["q_total"] > 0 and row["q_pos"] >= math.ceil(row["q_total"] * 0.60),
        row["n_eff_trades"] >= 250 and row["so"]["exp"] > row["mde"],
    ]
    if all(gates):
        return "SHIP", dsr
    if row["so"]["exp"] > 0 and row["exp_stress"] >= 0 and row["wfe"] >= 0.30:
        return "WATCH", dsr
    return "NO-SHIP", dsr


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tf", default="derivM15_diverse", help="dataset folder under backtest/data/")
    args = ap.parse_args()

    data = B.load_dataset(args.tf)
    if not data:
        print(f"No data found in backtest/data/{args.tf}.")
        print("Export CSVs from TradingView or run fetch_diverse.py, then rerun:")
        print(f"  python3 backtest/edge_loop.py --tf {args.tf}")
        return 2

    ideas = planned_ideas()
    rows = []
    trial_sharpes = []
    for idea in ideas:
        scoped = select_universe(data, idea.universe)
        n_eff, mean_r = n_eff_symbols(scoped)
        haircut = math.sqrt(n_eff / len(scoped)) if scoped else 0.0

        oos, per, recs, cnt = run_idea(data, idea, COST_REAL, "oos")
        oos0, _, _, _ = run_idea(data, idea, 0.0, "oos")
        oos_stress, _, _, _ = run_idea(data, idea, COST_STRESS, "oos")
        insample, _, _, _ = run_idea(data, idea, COST_REAL, "is")
        so = stt(oos)
        si = stt(insample)
        wfe = (so["exp"] / si["exp"]) if si["exp"] > 0 else float("nan")
        q_pos, q_total = quarter_signs(recs)
        n_eff_trades = so["n"] * (n_eff / len(scoped)) if scoped else 0.0
        mde = 1.3 * (1.96 + 0.84) / math.sqrt(max(1.0, n_eff_trades))
        pos_symbols = sum(1 for a in per.values() if a.size >= 20 and a.mean() > 0)
        trial_sharpes.append(so["sr"])
        rows.append(
            dict(
                idea=idea,
                pool=oos,
                so=so,
                exp0=float(oos0.mean()) if oos0.size else 0.0,
                exp_stress=float(oos_stress.mean()) if oos_stress.size else 0.0,
                wfe=wfe,
                q_pos=q_pos,
                q_total=q_total,
                n_eff=n_eff,
                mean_r=mean_r,
                t_haircut=so["t"] * haircut,
                n_eff_trades=n_eff_trades,
                mde=mde,
                n_symbols=len(scoped),
                pos_symbols=pos_symbols,
                counters=cnt,
            )
        )

    sr0 = dsr_hurdle(trial_sharpes)
    print(f"EDGE LOOP dataset={args.tf} ideas={len(rows)} DSR_hurdle={sr0:.4f}")
    print("Selection uses OOS only; SHIP requires positive 2x-cost stress and robustness gates.\n")
    header = (
        f"{'idea':34s}{'univ':12s}{'N':>6s}{'exp0':>8s}{'exp.02':>8s}{'exp.04':>8s}"
        f"{'t_hc':>7s}{'WFE':>7s}{'+sym':>7s}{'Q+':>7s}{'DSR':>6s}  verdict"
    )
    print(header)
    print("-" * len(header))
    for row in sorted(rows, key=lambda r: (verdict(r, sr0)[0] != "SHIP", -r["so"]["exp"])):
        label = row["idea"].label
        ds_verdict, dsr = verdict(row, sr0)
        wfe = f"{row['wfe']:+.2f}" if np.isfinite(row["wfe"]) else "  nan"
        print(
            f"{label:34.34s}{row['idea'].universe:12s}{row['so']['n']:6d}"
            f"{row['exp0']:+8.4f}{row['so']['exp']:+8.4f}{row['exp_stress']:+8.4f}"
            f"{row['t_haircut']:+7.2f}{wfe:>7s}{row['pos_symbols']:4d}/{row['n_symbols']:<2d}"
            f"{row['q_pos']:4d}/{row['q_total']:<2d}{dsr:6.2f}  {ds_verdict}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
