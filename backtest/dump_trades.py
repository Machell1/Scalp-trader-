"""Dump the DEPLOYED EA config's dated trade list (t_epoch, symbol, r) for the
prop-challenge Monte Carlo. Validated config, realistic cost."""
import sys, csv
import pandas as pd
from scalper_backtest import Params, load_dataset, simulate_symbol

tf = "derivM15_spreadgated"
cost = float(sys.argv[1]) if len(sys.argv) > 1 else 0.03
p = Params(momentum_bars=6, momentum_atr=2.0, atr_period=14, direction="cont",
           entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3,
           stop_atr=1.0, tp_atr=3.0, lock_trigger_atr=999.0, trail_atr=0.0,
           max_hold_bars=8, cost_atr_frac=cost)
data = load_dataset(tf)
rows = []
for sym, df in data.items():
    tr = []
    simulate_symbol(df, p, 0, len(df), trades_out=tr)
    for t_raw, r in tr:
        t_epoch = int(pd.Timestamp(t_raw).timestamp())
        rows.append((t_epoch, sym, r))
rows.sort()
out = f"ea_trades_cost{cost}.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["t", "symbol", "r"]); w.writerows(rows)
import datetime as dt
t0 = dt.datetime.utcfromtimestamp(rows[0][0]); t1 = dt.datetime.utcfromtimestamp(rows[-1][0])
days = (rows[-1][0] - rows[0][0]) / 86400
print(f"{len(rows)} trades, {t0:%Y-%m-%d}..{t1:%Y-%m-%d} ({days:.0f}d), {len(rows)/days:.1f} trades/day -> {out}")
