"""Run the preregistered market-entry/session-VWAP screen."""
from __future__ import annotations

import os
from dataclasses import replace

import numpy as np
import pandas as pd

from parity_engine import START, prep_symbol
from retest_engine import Cell, TRIO, filt_ok, resolve, run_cell
from walkforward_dsr import real_cost_per_side

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "derivM15_spreadgated")
CONTROL = Cell("W2 pending-limit control", filt="W2", entry="limit", offset=0.6, sl=1.0, tp=3.0, hold=8)
MARKET_VWAP = Cell("W2 market+VWAP", filt="W2", entry="market", sl=1.0, tp=3.0, hold=8)


def vwap_arrays(raw: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    dt = pd.to_datetime(raw["time"])
    day = dt.dt.floor("D")
    typical = (raw["high"].astype(float) + raw["low"].astype(float) + raw["close"].astype(float)) / 3.0
    volume = raw["volume"].astype(float).where(lambda x: np.isfinite(x) & (x > 0), 0.0)
    pv = (typical * volume).groupby(day).cumsum()
    vv = volume.groupby(day).cumsum().replace(0.0, np.nan)
    return (pv / vv).to_numpy(float), day.groupby(day).cumcount().to_numpy(int) + 1


def market_vwap_cell(s, vwap: np.ndarray, session_pos: np.ndarray, cell: Cell):
    out = []
    i = START
    while i < len(s.c) - 1:
        if not filt_ok(s, i, cell.filt) or session_pos[i] < 8:
            i += 1
            continue
        side = int(s.side[i])
        value = vwap[i]
        if not np.isfinite(value) or (side > 0 and s.c[i] > value) or (side < 0 and s.c[i] < value):
            i += 1
            continue
        entry_bar = i + 1
        exit_bar, r = resolve(s, entry_bar, side, s.o[entry_bar], s.atr[i], cell)
        out.append((int(s.ep[i]), float(r)))
        i = exit_bar + 1
    return out


def stats(rows, s):
    if not rows:
        return {"n": 0, "exp": float("nan"), "win": float("nan"), "oos_n": 0, "oos_exp": float("nan"), "oos_win": float("nan")}
    cut = int(len(s.c) * 0.7)
    cut_epoch = int(s.ep[cut])
    all_r = np.asarray([r for _, r in rows], float)
    oos_r = np.asarray([r for ep, r in rows if ep >= cut_epoch], float)
    return {
        "n": int(len(all_r)), "exp": float(all_r.mean()), "win": float((all_r > 0).mean()),
        "oos_n": int(len(oos_r)), "oos_exp": float(oos_r.mean()) if len(oos_r) else float("nan"),
        "oos_win": float((oos_r > 0).mean()) if len(oos_r) else float("nan"),
    }


def main() -> None:
    for label, cell in (("CONTROL_PENDING", CONTROL), ("MARKET_VWAP", MARKET_VWAP)):
        for stress in (False, True):
            per = []
            pooled_rows = []
            for symbol in TRIO:
                subdir = "derivM15_spreadgated"
                path = os.path.join(HERE, "data", subdir, symbol + ".csv")
                raw = pd.read_csv(path)
                cost = real_cost_per_side(raw)
                s = prep_symbol(raw, cost * (2.0 if stress else 1.0), symbol)
                if label == "CONTROL_PENDING":
                    rows = run_cell(s, cell)
                else:
                    vwap, session_pos = vwap_arrays(raw)
                    rows = market_vwap_cell(s, vwap, session_pos, cell)
                per.append((symbol, stats(rows, s)))
                pooled_rows.extend((symbol, ep, r) for ep, r in rows)
            cut_epochs = []
            for symbol in TRIO:
                subdir = "derivM15_spreadgated"
                raw = pd.read_csv(os.path.join(HERE, "data", subdir, symbol + ".csv"))
                dt = pd.to_datetime(raw["time"])
                cut_epochs.append(int(((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()[int(len(raw) * 0.7)]))
            symbol_to_cut = dict(zip(TRIO, cut_epochs))
            pooled_r = np.asarray([r for _, _, r in pooled_rows], float)
            pooled_oos_r = np.asarray([r for symbol, ep, r in pooled_rows if ep >= symbol_to_cut[symbol]], float)
            all_rows = [v for _, v in per]
            # Pool from per-symbol aggregate moments, preserving exact trade counts.
            pooled_n = sum(v["n"] for v in all_rows)
            pooled_oos_n = sum(v["oos_n"] for v in all_rows)
            print(label, "STRESS" if stress else "MEASURED", "per_symbol", per)
            print(label, "STRESS" if stress else "MEASURED", "pooled", {
                "n": pooled_n, "exp": float(pooled_r.mean()) if len(pooled_r) else float("nan"),
                "win": float((pooled_r > 0).mean()) if len(pooled_r) else float("nan"),
                "oos_n": pooled_oos_n, "oos_exp": float(pooled_oos_r.mean()) if len(pooled_oos_r) else float("nan"),
                "oos_win": float((pooled_oos_r > 0).mean()) if len(pooled_oos_r) else float("nan"),
            })


if __name__ == "__main__":
    main()
