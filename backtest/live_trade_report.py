"""Forensic report on DerivScalperEA live trades (magic 770077).

Reconstructs every round trip with full context and dumps:
  * per-trade record: symbol, dir, lots, times, entry vs requested limit (fill quality),
    exit reason (SL/TP/EXPERT=time), P&L, R-multiple (risk from the originating order's SL),
    signal context (impulse ATRs, ATR at entry, spread/ATR at entry bar),
    MAE/MFE in R (M1 path), post-exit shakeout check (did TP print within 8 bars after an SL?)
  * every unfilled (canceled/expired) pending: what the market did next (missed R)
  * aggregate: exit mix, realized cost, fill stats — compared to backtest assumptions.

Writes live_trades.json and prints a readable report.

v2 fixes (P1 from docs/LIVE_TRADE_ANALYSIS_2026-07-01.md, found by the audit of v1):
  * R denominator is now converted to the ACCOUNT currency via mt5.order_calc_profit
    (v1 used raw trade_tick_value, which for DE40/UK100 is quoted in EUR/GBP and
    overstated those R values by ~14%/33%). Conversion uses the current FX rate,
    which for day-scale lookbacks is within a fraction of a percent of trade-time.
  * MAE/MFE exclude the exit-minute M1 bar's extremes and use the exit price as the
    final path point instead, so an intrabar stop can no longer report MAE > 1R
    from wick overshoot past the level we actually exited at.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

from scalper_backtest import wilder_atr

MAGIC = 770077
FRM = datetime(2026, 6, 29)

def bars_m15(sym, t_from, t_to):
    r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M15, t_from, t_to)
    return pd.DataFrame(r) if r is not None and len(r) else pd.DataFrame()

def atr_context(sym, t_open):
    """ATR14 + impulse + spread at the last closed bar before entry."""
    r = mt5.copy_rates_from(sym, mt5.TIMEFRAME_M15, t_open, 60)
    if r is None or len(r) < 25:
        return {}
    df = pd.DataFrame(r)
    h, l, c = df.high.to_numpy(float), df.low.to_numpy(float), df.close.to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    i = len(df) - 2  # last closed bar before/at entry
    info = mt5.symbol_info(sym)
    point = info.point if info else 0.0
    a = float(atr[i]) if np.isfinite(atr[i]) else None
    out = dict(atr=a,
               spread_pts=float(df.spread.iloc[i]),
               spread_price=float(df.spread.iloc[i]) * point,
               close_sig=float(c[i]))
    if a and i >= 5:
        out["impulse_atr"] = float((c[i] - c[i - 5]) / a)
    if a:
        out["spread_atr_perside"] = 0.5 * out["spread_price"] / a
    return out

def risk_in_account_ccy(sym, side, volume, entry, sl):
    """Risk of the entry->SL move in the ACCOUNT currency.

    v2 fix: mt5.order_calc_profit does the quote->account currency conversion that
    raw trade_tick_value arithmetic misses (DE40 is EUR-quoted, UK100 GBP-quoted;
    v1 overstated their R by ~14%/33%)."""
    otype = mt5.ORDER_TYPE_BUY if side > 0 else mt5.ORDER_TYPE_SELL
    p = mt5.order_calc_profit(otype, sym, volume, entry, sl)
    if p is not None and p != 0:
        return abs(p)
    # Fallback (symbol not visible etc.): tick-value arithmetic - correct only for
    # USD-quoted symbols; flag it so the number is never silently trusted.
    info = mt5.symbol_info(sym)
    if info is None or info.trade_tick_size <= 0:
        return None
    print(f"WARN {sym}: order_calc_profit unavailable - R uses raw tick value (no FX conversion)")
    return (abs(entry - sl) / info.trade_tick_size) * info.trade_tick_value * volume

def mae_mfe(sym, t_open, t_close, entry, risk, side, exit_px, t_close_ts):
    r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, t_open, t_close + timedelta(minutes=1))
    if r is None or len(r) == 0 or risk <= 0:
        return None, None
    df = pd.DataFrame(r)
    # v2 fix: drop the exit-minute bar - its wick can overshoot the level we actually
    # exited at (e.g. an intrabar stop showing MAE > 1R) - and terminate the price
    # path at the real exit price instead.
    df = df[df.time < (int(t_close_ts) // 60) * 60]
    lows = list(df.low) + [exit_px]
    highs = list(df.high) + [exit_px]
    if side > 0:
        mae = (entry - min(lows)) / risk
        mfe = (max(highs) - entry) / risk
    else:
        mae = (max(highs) - entry) / risk
        mfe = (entry - min(lows)) / risk
    return float(mae), float(mfe)

def shakeout(sym, t_close, tp, side, nbars=8):
    """After exit: did TP print within nbars M15 bars?"""
    if not tp:
        return None
    r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M15, t_close, t_close + timedelta(minutes=15 * (nbars + 1)))
    if r is None or len(r) == 0:
        return None
    df = pd.DataFrame(r)
    return bool((df.high >= tp).any()) if side > 0 else bool((df.low <= tp).any())

def fwd_move_atr(sym, t_from, side, a, nbars=8):
    r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M15, t_from, t_from + timedelta(minutes=15 * (nbars + 1)))
    if r is None or len(r) == 0 or not a:
        return None
    df = pd.DataFrame(r)
    ref = float(df.open.iloc[0])
    return float(((df.close.iloc[-1] - ref) / a) * (1 if side > 0 else -1))

def main():
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    now = datetime.now() + timedelta(days=1)
    deals = [d for d in (mt5.history_deals_get(FRM, now) or []) if d.magic == MAGIC]
    orders = [o for o in (mt5.history_orders_get(FRM, now) or []) if o.magic == MAGIC]

    ord_by_pos = {}
    for o in orders:
        ord_by_pos.setdefault(o.position_id, []).append(o)

    # ---- round trips ----
    by_pos = {}
    for d in deals:
        by_pos.setdefault(d.position_id, []).append(d)

    REASON = {0: "CLIENT", 1: "MOBILE", 2: "WEB", 3: "EXPERT(time/manual)", 4: "SL", 5: "TP", 6: "SO"}
    trades = []
    for pid, ds in sorted(by_pos.items(), key=lambda kv: min(d.time for d in kv[1])):
        ins = [d for d in ds if d.entry == mt5.DEAL_ENTRY_IN]
        outs = [d for d in ds if d.entry == mt5.DEAL_ENTRY_OUT]
        if not ins or not outs:
            continue
        din, dout = ins[0], outs[-1]
        sym = din.symbol
        side = 1 if din.type == mt5.DEAL_TYPE_BUY else -1
        t_open = datetime.fromtimestamp(din.time)
        t_close = datetime.fromtimestamp(dout.time)
        # originating limit order (filled)
        oorig = None
        for o in ord_by_pos.get(pid, []):
            if o.type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT) and o.state == mt5.ORDER_STATE_FILLED:
                oorig = o
        req = oorig.price_open if oorig else None
        sl0 = oorig.sl if oorig else 0.0
        tp0 = oorig.tp if oorig else 0.0
        risk = abs(din.price - sl0) if sl0 else None
        pnl = dout.profit + dout.swap + dout.commission + din.commission
        r_mult = None
        if risk and risk > 0 and din.volume > 0:
            risk_ccy = risk_in_account_ccy(sym, side, din.volume, din.price, sl0)
            r_mult = pnl / risk_ccy if risk_ccy else None
        ctx = atr_context(sym, t_open)
        mae, mfe = mae_mfe(sym, t_open, t_close, din.price, risk or 0, side,
                           exit_px=dout.price, t_close_ts=dout.time)
        shk = shakeout(sym, t_close, tp0, side) if REASON.get(dout.reason) == "SL" else None
        hold_min = (t_close - t_open).total_seconds() / 60
        trades.append(dict(
            pos=pid, sym=sym, side="LONG" if side > 0 else "SHORT", lots=din.volume,
            t_open=str(t_open), t_close=str(t_close), hold_min=round(hold_min, 1),
            req_limit=req, fill=din.price, slip=(None if req is None else round((din.price - req) * side, 6)),
            sl=sl0, tp=tp0, exit_px=dout.price, exit_reason=REASON.get(dout.reason, dout.reason),
            pnl=round(pnl, 2), r=None if r_mult is None else round(r_mult, 3),
            atr=ctx.get("atr"), impulse_atr=None if ctx.get("impulse_atr") is None else round(ctx["impulse_atr"], 2),
            spread_atr_perside=None if ctx.get("spread_atr_perside") is None else round(ctx["spread_atr_perside"], 4),
            mae_r=None if mae is None else round(mae, 2), mfe_r=None if mfe is None else round(mfe, 2),
            tp_hit_after_sl=shk,
        ))

    # ---- unfilled pendings ----
    misses = []
    for o in orders:
        if o.type not in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT):
            continue
        if o.state not in (mt5.ORDER_STATE_CANCELED, mt5.ORDER_STATE_EXPIRED):
            continue
        side = 1 if o.type == mt5.ORDER_TYPE_BUY_LIMIT else -1
        t0 = datetime.fromtimestamp(o.time_setup)
        ctx = atr_context(o.symbol, t0)
        fwd = fwd_move_atr(o.symbol, t0, side, ctx.get("atr"))
        misses.append(dict(sym=o.symbol, side="LONG" if side > 0 else "SHORT", t=str(t0),
                           state="EXPIRED" if o.state == mt5.ORDER_STATE_EXPIRED else "CANCELED",
                           limit=o.price_open, fwd_8bar_atr=None if fwd is None else round(fwd, 2)))

    mt5.shutdown()

    out = dict(trades=trades, misses=misses)
    with open("live_trades.json", "w") as f:
        json.dump(out, f, indent=1, default=str)

    # ---- print ----
    print(f"ROUND TRIPS: {len(trades)}   UNFILLED PENDINGS: {len(misses)}\n")
    for t in trades:
        print(f"#{t['pos']} {t['sym']:12s} {t['side']:5s} {t['lots']:>5} lots  "
              f"{t['t_open'][5:16]} -> {t['t_close'][5:16]} ({t['hold_min']:.0f}m)")
        print(f"    limit {t['req_limit']} fill {t['fill']} slip {t['slip']}  SL {t['sl']} TP {t['tp']}")
        print(f"    exit {t['exit_px']} [{t['exit_reason']}]  pnl ${t['pnl']}  R {t['r']}  "
              f"MAE {t['mae_r']}R MFE {t['mfe_r']}R" + (f"  TP-after-SL: {t['tp_hit_after_sl']}" if t['tp_hit_after_sl'] is not None else ""))
        print(f"    ctx: ATR {t['atr']}  impulse {t['impulse_atr']} ATR  spread/ATR/side {t['spread_atr_perside']}")
    if misses:
        print("\nUNFILLED:")
        for m in misses:
            print(f"  {m['t'][5:16]} {m['sym']:12s} {m['side']:5s} [{m['state']}] limit {m['limit']}  fwd8bar {m['fwd_8bar_atr']} ATR")

    rs = [t["r"] for t in trades if t["r"] is not None]
    if rs:
        rs = np.array(rs)
        print(f"\nAGG: N={len(rs)}  sumR={rs.sum():+.2f}  exp={rs.mean():+.3f}R  win={(rs>0).mean()*100:.0f}%  "
              f"pnl=${sum(t['pnl'] for t in trades):+.2f}")
        from collections import Counter
        print("exit mix:", dict(Counter(t["exit_reason"] for t in trades)))
        sp = [t["spread_atr_perside"] for t in trades if t["spread_atr_perside"] is not None]
        print(f"spread/ATR per side at entries: median {np.median(sp):.4f}  max {max(sp):.4f}")

if __name__ == "__main__":
    main()
