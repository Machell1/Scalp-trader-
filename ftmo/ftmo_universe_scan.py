"""Stage 1 (v2) — FTMO universe cost gate, using REPRESENTATIVE historical spreads.

Why v2: a live-tick snapshot taken Friday night is the weekly WIDEST spread and
most markets are closed (only 32/167 symbols even returned a tick). FTMO's per-bar
historical `spread` column was verified REAL (37-99 distinct values/symbol, tracks
live), so we use it — but bars with spread==0 are MISSING DATA, not free trades,
and must be dropped or FX looks costless.

Gate (validated necessary condition):
    median( spread_price / (2*ATR_M15) ) + commission_per_side/ATR  <=  0.05

Commission (FTMO): indices = 0 ("zero commissions on indices"); crypto = 0;
forex/metals/energies = $5/lot treated as ROUND TURN -> $2.50/side (LENIENT: if a
symbol fails even under the lenient assumption, it definitively fails).

Passing is NECESSARY, not sufficient. Stage 2 tests whether the edge exists.
"""
import argparse, csv
import numpy as np
import MetaTrader5 as mt5

FTMO_PATH = r"C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe"

def commission_usd_per_lot(path):
    p = path.lower()
    if "cash" in p or "crypto" in p:      # indices + crypto: spread only
        return 0.0
    return 5.0                            # fx / metals / energies (round turn)

def analyse(sym, path, bars):
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, bars)
    if r is None or len(r) < 200:
        return None
    h, l, c = r['high'].astype(float), r['low'].astype(float), r['close'].astype(float)
    sp_pts = r['spread'].astype(float)
    vol = r['tick_volume'].astype(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    # rolling ATR(14)
    atr = np.convolve(tr, np.ones(14) / 14, mode='valid')
    sp_pts = sp_pts[13:]; vol = vol[13:]
    info = mt5.symbol_info(sym)
    if info is None or info.point <= 0:
        return None
    pt = info.point
    # keep only real, tradable bars: spread recorded AND ticks present
    m = (sp_pts > 0) & (vol > 0) & (atr > 0)
    if m.sum() < 200:
        return None
    sp_price = sp_pts[m] * pt
    a = atr[m]
    cost_side_spread = np.median(sp_price / (2.0 * a))
    comm_lot = commission_usd_per_lot(path)
    # Correct, currency-agnostic conversion of USD commission -> price offset:
    #   value of a 1.0 price move for 1 lot (in account ccy) = tick_value / tick_size
    #   => price offset = usd_per_side / (tick_value/tick_size)
    # (Dividing USD by contract_size is only valid for USD-QUOTED pairs and
    #  understates commission ~160x on e.g. USDJPY.)
    tv, ts = info.trade_tick_value, info.trade_tick_size
    if comm_lot > 0 and tv and ts and tv > 0:
        usd_per_price_unit = tv / ts
        comm_price_side = (comm_lot / 2.0) / usd_per_price_unit
    else:
        comm_price_side = 0.0
    comm_atr_side = comm_price_side / np.median(a)
    total = cost_side_spread + comm_atr_side
    return {
        "symbol": sym, "group": path.split("\\")[0] if "\\" in path else path,
        "bars_used": int(m.sum()),
        "med_spread": round(float(np.median(sp_price)), 6),
        "med_atr": round(float(np.median(a)), 6),
        "spread_atr_side": round(float(cost_side_spread), 4),
        "comm_atr_side": round(float(comm_atr_side), 4),
        "cost_atr_side": round(float(total), 4),
        "pass": bool(total <= 0.05),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=20000)
    a = ap.parse_args()
    if not mt5.initialize(path=FTMO_PATH):
        print("init failed:", mt5.last_error()); return
    ai = mt5.account_info()
    print(f"connected: {ai.company} | {ai.server}\n")
    syms = mt5.symbols_get()
    print(f"universe: {len(syms)} symbols; pulling M15 history (spread>0 & vol>0 bars only)\n")
    rows = []
    for s in syms:
        try:
            mt5.symbol_select(s.name, True)
            r = analyse(s.name, s.path, a.bars)
            if r:
                rows.append(r)
        except Exception:
            pass
    rows.sort(key=lambda r: r["cost_atr_side"])
    with open("ftmo_universe.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    npass = sum(r["pass"] for r in rows)
    print(f"{'symbol':16s} {'group':16s} {'spread/ATR':>10s} {'comm/ATR':>9s} {'TOTAL':>7s}  gate")
    print("-" * 72)
    for r in rows[:30]:
        print(f"{r['symbol']:16s} {r['group'][:16]:16s} {r['spread_atr_side']:10.4f} "
              f"{r['comm_atr_side']:9.4f} {r['cost_atr_side']:7.4f}  {'PASS' if r['pass'] else 'fail'}")
    print(f"\n{npass}/{len(rows)} symbols clear the 0.05 ATR/side cost gate (of {len(syms)} in universe)")
    print("-> ftmo_universe.csv. Cost gate is NECESSARY, not sufficient; stage 2 tests the edge.")
    mt5.shutdown()

if __name__ == "__main__":
    main()
