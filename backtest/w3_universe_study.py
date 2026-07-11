"""W3 universe expansion: re-audition 10 candidates under the stricter filter,
then greedy portfolio construction toward the owner's five-asset floor.

Pre-registered: docs/W3_UNIVERSE_SPEC_2026-07-12.md
  (SHA256 37853f16231ce1dfb6c212a16d71a461483076c006367b143459caeca7f02b4b)
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scalper_backtest import wilder_atr, Params, simulate_symbol
from walkforward_dsr import real_cost_per_side
from prop_mc_scalper import challenge

W3 = 0.50
COST_CEIL = 0.085
P = dict(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
         entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
         stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
         max_hold_bars=8)
TRIO = [("Wall_Street_30", "derivM15_spreadgated"), ("US_Tech_100", "derivM15_spreadgated"),
        ("Japan_225", "derivM15_spreadgated")]
CANDS = [("Germany_40", "derivM15_spreadgated", "GER40.cash", False),
         ("US_SP_500", "derivM15_spreadgated", "US500.cash", False),
         ("XAUUSD", "derivM15_diverse", "XAUUSD", True),
         ("UK_100", "derivM15_spreadgated", "UK100.cash", False),
         ("France_40", "derivM15_spreadgated", "FRA40.cash", False),
         ("Australia_200", "derivM15_diverse", "AUS200.cash", False),
         ("Hong_Kong_50", "derivM15_diverse", "HK50.cash", False),
         ("US_Small_Cap_2000", "derivM15_spreadgated", "US2000.cash", False),
         ("XAGUSD", "derivM15_diverse", "XAGUSD", True),
         ("EURUSD", "derivM15_diverse", "EURUSD", True)]


def w3_tape(key, sub, costmult=1.0, flat_cost=0.03):
    path = os.path.join(HERE, "data", sub, key + ".csv")
    if not os.path.isfile(path):
        return None, None
    raw = pd.read_csv(path)
    n = {c.lower(): c for c in raw.columns}
    df = raw.rename(columns={n[k]: k for k in ("time", "open", "high", "low", "close") if k in n})
    cost = real_cost_per_side(raw)
    if not np.isfinite(cost):
        cost = flat_cost
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    up = h - np.maximum(o, c); dn = np.minimum(o, c) - l
    sigs = []
    simulate_symbol(df, Params(**P, cost_atr_frac=cost * costmult), 0, len(df), signals_out=sigs)
    dt = pd.to_datetime(df["time"])
    ep = ((dt - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).to_numpy()
    q = pd.PeriodIndex(dt, freq="Q")
    qs = sorted(q.unique()); oos_qs = set(qs[int(len(qs) * 0.7):])
    rows = [(int(ep[i]), float(r), q[i] in oos_qs)
            for (i, eb, side, r) in sigs
            if np.isfinite(atr[i]) and atr[i] > 0 and ((up[i] if side > 0 else dn[i]) / atr[i]) >= W3]
    return rows, cost


def ftmo_check(sym, metal):
    try:
        import MetaTrader5 as mt5
        assert mt5.initialize(path=r"C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe")
        mt5.symbol_select(sym, True)
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 20000)
        info = mt5.symbol_info(sym)
        mt5.shutdown()
        if r is None or len(r) < 3000 or info is None or info.point <= 0:
            return None, None
        df = pd.DataFrame({"time": r["time"], "open": r["open"], "high": r["high"],
                           "low": r["low"], "close": r["close"]})
        sp = r["spread"].astype(float) * info.point
        atr = wilder_atr(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(), 14)
        med_atr = float(np.nanmedian(atr))
        m = sp > 0
        if m.sum() < 100 or med_atr <= 0:
            return None, None
        cost = 0.5 * float(np.median(sp[m])) / med_atr
        if metal and info.trade_tick_value > 0 and info.trade_tick_size > 0:
            cost += (2.5 / (info.trade_tick_value / info.trade_tick_size)) / med_atr
        o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        fatr = wilder_atr(h, l, c, 14)
        up = h - np.maximum(o, c); dn = np.minimum(o, c) - l
        sigs = []
        simulate_symbol(df, Params(**P, cost_atr_frac=cost), 0, len(df), signals_out=sigs)
        rs = [r_ for (i, eb, side, r_) in sigs
              if np.isfinite(fatr[i]) and fatr[i] > 0 and ((up[i] if side > 0 else dn[i]) / fatr[i]) >= W3]
        return cost, (float(np.mean(rs)) if len(rs) >= 20 else None)
    except Exception as e:
        print(f"   FTMO check error for {sym}: {e}")
        return None, None


def mc_both(tape, nsim=8000):
    days = {}
    for (t, r, _) in tape:
        days.setdefault(t // 86400, []).append(r)
    dl = list(days.values())
    rng = np.random.default_rng(7)
    r1 = np.array([challenge(dl, rng, 0.3, 10.0, 365) for _ in range(nsim)])
    p1 = float(np.mean(r1[:, 0] == 1)); bust = float(np.mean(r1[:, 0] == 0))
    r2 = np.array([challenge(dl, rng, 0.3, 5.0, 365)[0] for _ in range(nsim // 2)])
    return p1 * float(np.mean(r2 == 1)), bust


def main():
    trio = []
    for key, sub in TRIO:
        tp, _ = w3_tape(key, sub)
        trio += tp
    base_both, base_bust = mc_both(trio)
    print(f"W3 TRIO baseline: n={len(trio)} | both={base_both:.1%} bust={base_bust:.1%}\n")

    passers = {}
    print(f"{'candidate':20s} {'derivOOS':>9s} {'2x':>8s} {'nOOS':>5s} {'ftmoCost':>9s} {'ftmoExp':>8s}  verdict")
    for key, sub, fsym, metal in CANDS:
        tp, cost = w3_tape(key, sub)
        if tp is None:
            print(f"{key:20s}  no Deriv data -> skip"); continue
        oos = np.array([r for (t, r, o_) in tp if o_])
        tp2, _ = w3_tape(key, sub, costmult=2.0)
        oos2 = np.array([r for (t, r, o_) in tp2 if o_])
        g1 = len(oos) >= 50 and oos.mean() > 0 and len(oos2) > 0 and oos2.mean() > 0
        fcost, fexp = ftmo_check(fsym, metal)
        g2 = fcost is not None and fcost <= COST_CEIL
        g3 = fexp is not None and fexp > 0
        ok = g1 and g2 and g3
        if ok:
            passers[key] = tp
        print(f"{key:20s} {oos.mean() if len(oos) else float('nan'):+9.4f} "
              f"{oos2.mean() if len(oos2) else float('nan'):+8.4f} {len(oos):5d} "
              f"{fcost if fcost is not None else float('nan'):9.4f} "
              f"{fexp if fexp is not None else float('nan'):+8.4f}  {'PASS' if ok else 'no'}", flush=True)

    print(f"\nGreedy portfolio construction from W3 trio (passers: {list(passers)}):")
    port = list(trio); names = ["trio"]
    cur_both, cur_bust = base_both, base_bust
    remaining = dict(passers)
    while remaining:
        best_key, best_both, best_bust = None, cur_both, None
        for key, tp in remaining.items():
            b, bu = mc_both(port + tp, nsim=5000)
            print(f"   try +{key}: both={b:.1%} bust={bu:.1%}")
            if b > best_both and bu <= cur_bust + 0.01:
                best_key, best_both, best_bust = key, b, bu
        if best_key is None:
            break
        port += remaining.pop(best_key)
        names.append(best_key)
        cur_both, cur_bust = best_both, best_bust
        print(f"   ADDED {best_key} -> portfolio {names}: both={cur_both:.1%} bust={cur_bust:.1%}")
    n_assets = 2 + len(names)  # trio=3 symbols; names[0]='trio'
    n_assets = 3 + (len(names) - 1)
    print(f"\nEvidence-optimal portfolio: {names} ({n_assets} assets) both={cur_both:.1%} bust={cur_bust:.1%}")

    if n_assets < 5 and passers:
        print("\nForced-5 analysis (owner floor): best remaining additions to reach 5:")
        rem = {k: v for k, v in passers.items() if k not in names}
        combo_needed = 5 - n_assets
        if len(rem) >= combo_needed:
            import itertools
            best = None
            for combo in itertools.combinations(rem.keys(), combo_needed):
                tape5 = list(port)
                for k in combo:
                    tape5 += rem[k]
                b, bu = mc_both(tape5, nsim=5000)
                print(f"   {names[1:]} + {list(combo)}: both={b:.1%} bust={bu:.1%}")
                if best is None or b > best[1]:
                    best = (combo, b, bu)
            print(f"\nBest forced-5: +{list(best[0])} both={best[1]:.1%} bust={best[2]:.1%} "
                  f"(cost vs optimum: {cur_both - best[1]:+.1%} odds)")
        else:
            print(f"   insufficient passers to reach 5 assets ({len(rem)} remaining) — reported honestly")

    print("\nDone. Owner chooses: evidence-optimal vs five-asset floor, with the odds cost quantified.")


if __name__ == "__main__":
    main()
