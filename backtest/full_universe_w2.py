"""Full-universe W2 sweep: every FTMO symbol + every cached Deriv dataset.

Pre-registered: docs/UNIVERSE_FULL_SPEC_2026-07-11.md
  (SHA256 ae269d1b221a1fb14b74aeb91b037f2fb9bbef99bda1d2720b8baa54ac058245)
Exploratory screen; only cross-frame hits advance to the ledger-charged
portfolio battery (Part D). FTMO side is ~9 months = directional only.
"""
import glob
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr, Params, simulate_symbol
from walkforward_dsr import real_cost_per_side
from prop_mc_scalper import challenge

W2 = 0.30
COST_CEIL = 0.075
LIVE = {"US30.cash", "US100.cash", "JP225.cash"}
PARAMS = dict(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
              entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
              stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
              max_hold_bars=8)


def norm(df):
    n = {c.lower(): c for c in df.columns}
    return df.rename(columns={n[k]: k for k in ("time", "open", "high", "low", "close") if k in n})


def w2_trades(df, cost):
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    up = h - np.maximum(o, c); dn = np.minimum(o, c) - l
    sigs = []
    simulate_symbol(df, Params(**PARAMS, cost_atr_frac=cost), 0, len(df), signals_out=sigs)
    dt = pd.to_datetime(df["time"])
    ep = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()
    out = []
    for (i, eb, side, r) in sigs:
        if np.isfinite(atr[i]) and atr[i] > 0 and ((up[i] if side > 0 else dn[i]) / atr[i]) >= W2:
            out.append((int(ep[i]), i, float(r)))
    return out


def ftmo_sweep():
    import MetaTrader5 as mt5
    assert mt5.initialize(path=r"C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe")
    syms = mt5.symbols_get()
    print(f"PART A/B: {len(syms)} FTMO symbols; cost ceiling {COST_CEIL}/side (W2 economics)")
    rows = []
    for s in syms:
        name, path = s.name, s.path.lower()
        try:
            mt5.symbol_select(name, True)
            r = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_M15, 0, 20000)
            info = mt5.symbol_info(name)
            if r is None or len(r) < 3000 or info is None or info.point <= 0:
                rows.append(dict(symbol=name, status="data-starved")); continue
            df = pd.DataFrame({"time": r["time"], "open": r["open"], "high": r["high"],
                               "low": r["low"], "close": r["close"]})
            sp = r["spread"].astype(float) * info.point
            atr = wilder_atr(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(), 14)
            med_atr = float(np.nanmedian(atr))
            m = sp > 0
            if m.sum() < 200 or med_atr <= 0:
                rows.append(dict(symbol=name, status="data-starved")); continue
            cost = 0.5 * float(np.median(sp[m])) / med_atr
            med_px = float(np.median(df.close))
            if "crypto" in path:
                cost += (0.000325 * med_px) / med_atr           # measured 3.25 bps/side ($20.8/lot/side on live BTC fills 2026-07-10)
            elif "cash" not in path and info.trade_tick_value > 0 and info.trade_tick_size > 0:
                cost += (2.5 / (info.trade_tick_value / info.trade_tick_size)) / med_atr
            if cost > COST_CEIL:
                rows.append(dict(symbol=name, status="cost-dead", cost=round(cost, 4))); continue
            tr = w2_trades(df, cost)
            rs = np.array([x[2] for x in tr], float)
            hit = len(rs) >= 100 and rs.mean() > 0
            rows.append(dict(symbol=name, status="SCREEN-HIT" if hit else "no-edge",
                             cost=round(cost, 4), n=len(rs),
                             exp=round(float(rs.mean()), 4) if len(rs) else None,
                             trades=tr if hit else None))
        except Exception as e:
            rows.append(dict(symbol=name, status=f"error:{e}"))
        finally:
            if name not in LIVE and name not in ("BTCUSD", "EURUSD", "GBPUSD", "USDCHF", "USDJPY"):
                try:
                    mt5.symbol_select(name, False)
                except Exception:
                    pass
    mt5.shutdown()
    return rows


def deriv_frame():
    """Gate-grade Deriv confirmation for every cached dataset."""
    out = {}
    seen = set()
    for sub, flat in (("derivM15_spreadgated", None), ("derivM15_diverse", 0.03)):
        for f in sorted(glob.glob(os.path.join(HERE, "data", sub, "*.csv"))):
            key = os.path.basename(f).replace(".csv", "").replace("_M15", "")
            if key in seen:
                continue
            seen.add(key)
            raw = pd.read_csv(f)
            df = norm(raw)
            cost = real_cost_per_side(raw) if flat is None else flat
            if not np.isfinite(cost):
                cost = 0.03
            tr = w2_trades(df, cost)
            tr2 = w2_trades(df, cost * 2)
            dt = pd.to_datetime(df["time"])
            q = pd.PeriodIndex(dt, freq="Q")
            qs = sorted(q.unique())
            oos_qs = set(qs[int(len(qs) * 0.7):])
            oos = np.array([r for (t, i, r) in tr if q[i] in oos_qs], float)
            oos2 = np.array([r for (t, i, r) in tr2 if q[i] in oos_qs], float)
            ok = len(oos) >= 60 and oos.mean() > 0 and len(oos2) > 0 and oos2.mean() > 0
            out[key] = dict(ok=ok, n=len(oos), exp=float(oos.mean()) if len(oos) else None,
                            exp2=float(oos2.mean()) if len(oos2) else None)
    return out


DERIV_ALIAS = {  # FTMO name -> Deriv dataset key
    "GER40.cash": "Germany_40", "JP225.cash": "Japan_225", "US500.cash": "US_SP_500",
    "US30.cash": "Wall_Street_30", "US100.cash": "US_Tech_100", "UK100.cash": "UK_100",
    "FRA40.cash": "France_40", "AUS200.cash": "Australia_200", "US2000.cash": "US_Small_Cap_2000",
    "XAUUSD": "XAUUSD", "XAGUSD": "XAGUSD", "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD",
    "XRPUSD": "XRPUSD", "SOLUSD": "SOLUSD", "EURUSD": "EURUSD", "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY", "USDCAD": "USDCAD", "USDCHF": "USDCHF", "AUDJPY": "AUDJPY",
    "EURJPY": "EURJPY", "EURGBP": "EURGBP",
}


def main():
    rows = ftmo_sweep()
    hits = [r for r in rows if r["status"] == "SCREEN-HIT"]
    print(f"\nFTMO screen: {len(hits)} hits / {sum(1 for r in rows if r['status']=='cost-dead')} cost-dead / "
          f"{sum(1 for r in rows if r['status']=='no-edge')} no-edge / "
          f"{sum(1 for r in rows if r['status']=='data-starved')} data-starved\n")
    for r in sorted(hits, key=lambda x: -(x["exp"] or 0)):
        print(f"  HIT {r['symbol']:14s} cost={r['cost']:.4f} n={r['n']:4d} exp={r['exp']:+.4f}")

    print("\nPART C: Deriv confirmation frame (41 datasets)")
    dframe = deriv_frame()
    for k, v in sorted(dframe.items(), key=lambda kv: -(kv[1]['exp'] or -9)):
        tag = "GATE-PASS" if v["ok"] else "no"
        print(f"  {k:22s} n={v['n']:5d} oos={v['exp'] if v['exp'] is not None else float('nan'):+.4f} "
              f"2x={v['exp2'] if v['exp2'] is not None else float('nan'):+.4f} -> {tag}")

    print("\nPART D: cross-frame candidates (FTMO hit + Deriv gate-pass, tradable, not live)")
    live_tape = []
    import MetaTrader5  # noqa - already used
    for r in rows:
        if r["symbol"] in LIVE and r.get("trades"):
            live_tape += [(t, rr) for (t, i, rr) in r["trades"]]
    # live trio tape from Deriv frame for MC consistency
    trio = []
    for f, cst in (("derivM15_spreadgated/Wall_Street_30.csv", None),
                   ("derivM15_spreadgated/US_Tech_100.csv", None),
                   ("derivM15_spreadgated/Japan_225.csv", None)):
        raw = pd.read_csv(os.path.join(HERE, "data", f))
        trio += [(t, r) for (t, i, r) in w2_trades(norm(raw), real_cost_per_side(raw))]

    def mc_both(tape, nsim=10000):
        days = {}
        for (t, r) in tape:
            days.setdefault(t // 86400, []).append(r)
        dl = list(days.values())
        rng = np.random.default_rng(7)
        p1 = float(np.mean([challenge(dl, rng, 0.5, 10.0, 365)[0] == 1 for _ in range(nsim)]))
        p2 = float(np.mean([challenge(dl, rng, 0.5, 5.0, 365)[0] == 1 for _ in range(nsim // 2)]))
        return p1 * p2

    base = mc_both(trio)
    print(f"  live-trio MC baseline (no-time-limit both-phases): {base:.1%}")
    any_c = False
    for r in hits:
        sym = r["symbol"]
        if sym in LIVE:
            continue
        dk = DERIV_ALIAS.get(sym)
        if not dk or dk not in dframe or not dframe[dk]["ok"]:
            print(f"  {sym}: FTMO hit but no Deriv gate-pass ({dk}) -> WATCH only")
            continue
        raw_path = None
        for sub in ("derivM15_spreadgated", "derivM15_diverse"):
            p = os.path.join(HERE, "data", sub, dk + ".csv")
            if os.path.isfile(p):
                raw_path = p; break
        raw = pd.read_csv(raw_path)
        cost = real_cost_per_side(raw)
        cand = [(t, rr) for (t, i, rr) in w2_trades(norm(raw), cost if np.isfinite(cost) else 0.03)]
        both = mc_both(trio + cand)
        verdict = "ADD-CANDIDATE" if both > base else "portfolio drag"
        any_c = True
        print(f"  {sym}: cross-frame OK | MC {both:.1%} vs {base:.1%} -> {verdict}")
    if not any_c:
        print("  (no cross-frame candidates beyond the live trio)")


if __name__ == "__main__":
    main()
