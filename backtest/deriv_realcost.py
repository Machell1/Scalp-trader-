"""Settle WATCH-vs-kill on Deriv: measure REAL per-instrument spread cost (in ATR
units) from the live Deriv feed, then run the EXACT Pine config at that real cost.

Pine config (DerivScalperPullback v1.2): continuation, pullback LIMIT 0.6 ATR,
expiry 3, stop 1 ATR, TP 3 ATR, BE-lock 0.25, trail 0.5, hold 8, momentum 2ATR/6, no AVWAP.

Cost model: Deriv crypto/indices are spread-only (no % commission). A round trip
crosses the spread once, so per-side cost = 0.5 * spread_price. We express it in ATR
units (cost_atr_frac, what the harness uses): cost_perside = 0.5*median(spread*point)/median(ATR).
"""
from __future__ import annotations
import numpy as np, pandas as pd
import MetaTrader5 as mt5
from scalper_backtest import wilder_atr, compute_stats
from scalper_confluence import CParams, simulate_symbol_c, rs_of

PINE = dict(direction="cont", entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
            stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=0.25, trail_atr=0.5, max_hold_bars=8,
            momentum_bars=6, momentum_atr=2.0, atr_period=14)

CRYPTO = ["BTCUSD","ETHUSD","LTCUSD","XRPUSD","SOLUSD","BCHUSD"]
INDEX  = ["US Tech 100","US SP 500","Wall Street 30","US Mid Cap 400","US Small Cap 2000",
          "Germany 40","UK 100","Japan 225","France 40","Australia 200","Hong Kong 50"]
COUNT = 70000

def pull(sym):
    if not mt5.symbol_select(sym, True): return None, None
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, COUNT)
    if r is None or len(r) < 2000: return None, None
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    info = mt5.symbol_info(sym)
    point = info.point if info else 0.0
    out = df[["time","open","high","low","close","tick_volume","spread"]].rename(columns={"tick_volume":"volume"})
    return out, point

def main():
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    print(f"connected: {mt5.terminal_info().company}  (Pine config, OOS=last30%)\n")
    rows=[]
    pools={"CRYPTO":{0:[],1:[]}, "INDEX":{0:[],1:[]}}
    for cls, syms in [("CRYPTO",CRYPTO),("INDEX",INDEX)]:
        for sym in syms:
            df, point = pull(sym)
            if df is None:
                print(f"  skip {sym}"); continue
            h=df.high.to_numpy(float); l=df.low.to_numpy(float); c=df.close.to_numpy(float)
            atr = wilder_atr(h,l,c,14)
            med_atr = np.nanmedian(atr)
            spread_price = df["spread"].to_numpy(float) * point
            med_spread = np.median(spread_price[np.isfinite(spread_price)])
            cost_ps = 0.5 * med_spread / med_atr if med_atr>0 else np.nan      # per side, ATR units
            n=len(df); lo,hi=int(n*0.7),n
            # real-cost and frictionless OOS
            tr_r,_ = simulate_symbol_c(df, CParams(**{**PINE,"cost_atr_frac":cost_ps}), lo, hi)
            tr_0,_ = simulate_symbol_c(df, CParams(**{**PINE,"cost_atr_frac":0.0}), lo, hi)
            rr=np.array(rs_of(tr_r)); r0=np.array(rs_of(tr_0))
            pools[cls][1].extend(rr.tolist()); pools[cls][0].extend(r0.tolist())
            rows.append(dict(cls=cls,sym=sym,n=len(rr),cost=cost_ps,exp0=(r0.mean() if r0.size else 0),
                             expR=(rr.mean() if rr.size else 0),rr=rr))
            print(f"  {sym:18s}[{cls[:3]}] spread~{med_spread:.4g} = {cost_ps:.3f} ATR/side | "
                  f"N={len(rr):4d} exp0={r0.mean():+.4f} expREAL={rr.mean():+.4f}")
    mt5.shutdown()

    print("\n================ POOLED (Pine config, OOS, REAL Deriv spread cost) ================")
    for cls in ("CRYPTO","INDEX"):
        a0=np.array(pools[cls][0]); ar=np.array(pools[cls][1])
        s0=compute_stats(a0); sr=compute_stats(ar)
        print(f"  {cls:7s} N={sr.n:5d}  frictionless exp={s0.expectancy:+.4f} (t{s0.tstat:+.2f})  "
              f"REAL-cost exp={sr.expectancy:+.4f} (t{sr.tstat:+.2f})  PF={sr.profit_factor:.2f}")
    both0=np.array(pools["CRYPTO"][0]+pools["INDEX"][0]); bothr=np.array(pools["CRYPTO"][1]+pools["INDEX"][1])
    sb0=compute_stats(both0); sbr=compute_stats(bothr)
    print(f"  CRYPTO+INDEX N={sbr.n}  frictionless {sb0.expectancy:+.4f} (t{sb0.tstat:+.2f})  "
          f"REAL {sbr.expectancy:+.4f} (t{sbr.tstat:+.2f})")
    costs=[r["cost"] for r in rows if np.isfinite(r["cost"])]
    print(f"\n  Real Deriv per-side cost: median {np.median(costs):.3f} ATR  (range {min(costs):.3f}-{max(costs):.3f})")
    print(f"  For reference: Python assumed 0.02; Binance 0.1% taker ~ 0.23 ATR/side on BTC.")

    print("\n================ SPREAD-GATED universe (a-priori cost filter, real cost, OOS) ================")
    for thr in (0.05, 0.03):
        keep=[r for r in rows if np.isfinite(r["cost"]) and r["cost"] <= thr]
        pool=np.concatenate([r["rr"] for r in keep]) if keep else np.array([])
        s=compute_stats(pool)
        names=", ".join(r["sym"] for r in keep)
        print(f"  spread/ATR <= {thr:.2f}/side : {len(keep)} instruments, N={s.n}  "
              f"exp={s.expectancy:+.4f} (t{s.tstat:+.2f}) PF={s.profit_factor:.2f}")
        print(f"      kept: {names}")

if __name__ == "__main__":
    main()
