"""Pull a DIVERSE basket of real (non-synthetic) Deriv M15 instruments to disk.

Writes data/derivM15_diverse/<sym>.csv with columns time,open,high,low,close,volume
(volume = tick_volume). No data passes through the agent's context.
"""
import os, time as _t
import MetaTrader5 as mt5
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "derivM15_diverse")
os.makedirs(OUT, exist_ok=True)
COUNT = 70000   # request up to ~7y of M15; terminal returns what it has

BASKET = [
    # FX majors
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD",
    # FX crosses
    "EURJPY","GBPJPY","EURGBP","AUDJPY",
    # metals
    "XAUUSD","XAGUSD","XPTUSD","XCUUSD",
    # energy
    "US Oil","UK Brent Oil","NGAS",
    # crypto (genuine volume)
    "BTCUSD","ETHUSD","LTCUSD","XRPUSD","SOLUSD","BCHUSD",
    # global (non-US) indices
    "Germany 40","UK 100","Japan 225","France 40","Australia 200","Hong Kong 50",
]

def main():
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    print(f"connected: {mt5.terminal_info().company}  acct {mt5.account_info().login}\n")
    rows=[]
    for sym in BASKET:
        if not mt5.symbol_select(sym, True):
            print(f"  SKIP {sym:16s} (not selectable)"); continue
        _t.sleep(0.05)
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, COUNT)
        if r is None or len(r) < 2000:
            print(f"  SKIP {sym:16s} (only {0 if r is None else len(r)} bars)"); continue
        df = pd.DataFrame(r)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        out = df[["time","open","high","low","close","tick_volume"]].rename(columns={"tick_volume":"volume"})
        fn = sym.replace(" ", "_") + ".csv"
        out.to_csv(os.path.join(OUT, fn), index=False)
        bpd = out.groupby(pd.to_datetime(out.time).dt.date).size().median()
        rows.append((sym, len(out), str(out.time.iloc[0])[:10], str(out.time.iloc[-1])[:10], bpd))
        print(f"  OK   {sym:16s} {len(out):6d} bars  {rows[-1][2]} -> {rows[-1][3]}  ~{bpd:.0f}/day")
    mt5.shutdown()
    print(f"\nFetched {len(rows)} instruments to {OUT}")

if __name__ == "__main__":
    main()
