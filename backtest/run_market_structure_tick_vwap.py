"""Run the preregistered market-structure/tick/VWAP entry screen."""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from session_study import TRIO, load, resolve_v130
from parity_engine import START

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "derivM15_spreadgated")


def volume_vwap(raw):
    dt = pd.to_datetime(raw["time"])
    day = dt.dt.floor("D")
    tp = (raw["high"].astype(float) + raw["low"].astype(float) + raw["close"].astype(float)) / 3.0
    vol = raw["volume"].astype(float).where(lambda x: np.isfinite(x) & (x > 0), 0.0)
    pv = (tp * vol).groupby(day).cumsum()
    vv = vol.groupby(day).cumsum().replace(0.0, np.nan)
    return (pv / vv).to_numpy(float), day.groupby(day).cumcount().to_numpy(int) + 1


def market_w2(s):
    out = []
    i = START
    while i < len(s.c) - 1:
        if s.side[i] == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30:
            i += 1
            continue
        j = i + 1
        xb, r = resolve_v130(s, j, int(s.side[i]), s.o[j], s.atr[i])
        out.append((int(s.ep[i]), float(r), bool(s.oos[i])))
        i = xb + 1
    return out


def structure_tick_vwap(s, vwap, session_pos, volume):
    out = []
    i = START
    while i < len(s.c) - 1:
        side = int(s.side[i])
        if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30 or session_pos[i] < 8:
            i += 1
            continue
        if not np.isfinite(vwap[i]) or (side > 0 and s.c[i] > vwap[i]) or (side < 0 and s.c[i] < vwap[i]):
            i += 1
            continue
        rng = s.h[i] - s.l[i]
        body = abs(s.c[i] - s.o[i])
        if rng <= 0 or body / rng < 0.60:
            i += 1
            continue
        close_loc = (s.c[i] - s.l[i]) / rng
        if (side > 0 and close_loc < 0.75) or (side < 0 and close_loc > 0.25):
            i += 1
            continue
        prior_lows = s.l[i - 3:i]
        prior_highs = s.h[i - 3:i]
        if side > 0:
            structure_ok = s.l[i] > np.min(prior_lows) and s.c[i] > s.c[i - 1]
        else:
            structure_ok = s.h[i] < np.max(prior_highs) and s.c[i] < s.c[i - 1]
        if not structure_ok:
            i += 1
            continue
        prev = volume[i - 20:i]
        prev = prev[np.isfinite(prev) & (prev > 0)]
        if len(prev) < 20 or not np.isfinite(volume[i]) or volume[i] < 1.20 * np.median(prev):
            i += 1
            continue
        j = i + 1
        xb, r = resolve_v130(s, j, side, s.o[j], s.atr[i])
        out.append((int(s.ep[i]), float(r), bool(s.oos[i])))
        i = xb + 1
    return out


def summary(rows):
    r = np.asarray([x[1] for x in rows], float)
    oos = np.asarray([x[1] for x in rows if x[2]], float)
    return {
        "n": int(len(r)), "exp": float(r.mean()) if len(r) else float("nan"),
        "win": float((r > 0).mean()) if len(r) else float("nan"),
        "oos_n": int(len(oos)), "oos_exp": float(oos.mean()) if len(oos) else float("nan"),
        "oos_win": float((oos > 0).mean()) if len(oos) else float("nan"),
    }


def main():
    for stress in (False, True):
        pooled = {"control": [], "candidate": []}
        per = {"control": [], "candidate": []}
        for symbol in TRIO:
            raw = pd.read_csv(os.path.join(DATA, symbol + ".csv"))
            s = load(symbol)
            vwap, session_pos = volume_vwap(raw)
            volume = raw["volume"].to_numpy(float)
            s.cost *= 2.0 if stress else 1.0
            control = market_w2(s)
            candidate = structure_tick_vwap(s, vwap, session_pos, volume)
            per["control"].append((symbol, summary(control)))
            per["candidate"].append((symbol, summary(candidate)))
            pooled["control"].extend(control)
            pooled["candidate"].extend(candidate)
        print("STRESS" if stress else "MEASURED")
        print("CONTROL", per["control"], summary(pooled["control"]))
        print("CANDIDATE", per["candidate"], summary(pooled["candidate"]))


if __name__ == "__main__":
    main()
