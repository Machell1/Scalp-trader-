"""Run the preregistered causal H1 timeframe screen."""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from parity_engine import prep_symbol, START
from session_study import resolve_v130, TRIO
from walkforward_dsr import real_cost_per_side

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "derivM15_spreadgated")


def aggregate_h1(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    dt = pd.to_datetime(df["time"])
    df["_dt"] = dt
    df["_hour"] = dt.dt.floor("h")
    rows = []
    for hour, g in df.groupby("_hour", sort=True):
        g = g.sort_values("_dt")
        expected = [hour + pd.Timedelta(minutes=15 * k) for k in range(4)]
        if len(g) != 4 or list(g["_dt"]) != expected:
            continue
        rows.append({
            "time": hour,
            "open": float(g.iloc[0]["open"]),
            "high": float(g["high"].max()),
            "low": float(g["low"].min()),
            "close": float(g.iloc[-1]["close"]),
            "volume": float(g["volume"].sum()),
            "spread_price": float(g["spread_price"].max()),
        })
    return pd.DataFrame(rows)


def run_cell(s, market: bool = False):
    out = []
    i = START
    while i < len(s.c) - 1:
        side = int(s.side[i])
        if side == 0 or not np.isfinite(s.watr[i]) or s.watr[i] < 0.30:
            i += 1
            continue
        if market:
            j = i + 1
            entry = s.o[j]
        else:
            entry = s.c[i] - 0.6 * s.atr[i] * side
            j = -1
            for b in range(i + 1, min(i + 4, len(s.c))):
                if (side > 0 and s.l[b] <= entry) or (side < 0 and s.h[b] >= entry):
                    j = b
                    break
            if j < 0:
                i += 4
                continue
        xb, r = resolve_v130(s, j, side, entry, s.atr[i])
        out.append((int(s.ep[i]), float(r), bool(s.oos[i])))
        i = xb + 1
    return out


def summary(rows):
    r = np.asarray([x[1] for x in rows], float)
    oos = np.asarray([x[1] for x in rows if x[2]], float)
    return {"n": len(r), "exp": float(r.mean()) if len(r) else float("nan"),
            "win": float((r > 0).mean()) if len(r) else float("nan"),
            "oos_n": len(oos), "oos_exp": float(oos.mean()) if len(oos) else float("nan"),
            "oos_win": float((oos > 0).mean()) if len(oos) else float("nan")}


def main():
    for stress in (False, True):
        pooled = []
        per = []
        for symbol in TRIO:
            raw = pd.read_csv(os.path.join(DATA, symbol + ".csv"))
            h1 = aggregate_h1(raw)
            cost = real_cost_per_side(h1)
            s = prep_symbol(h1, cost * (2.0 if stress else 1.0), symbol)
            s.oos = np.arange(len(h1)) >= int(len(h1) * 0.7)
            rows = run_cell(s, market=False)
            per.append((symbol, len(h1), summary(rows)))
            pooled.extend(rows)
        print("STRESS" if stress else "MEASURED", "per_symbol", per)
        print("STRESS" if stress else "MEASURED", "pooled", summary(pooled))


if __name__ == "__main__":
    main()
