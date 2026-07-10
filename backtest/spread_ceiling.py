"""Per-instrument spread ceiling for the edge to survive at a prop firm.

Gate: spread PER SIDE <= 0.05 ATR(M15,14)  =>  quoted (bid-ask) spread <= 0.10 * ATR.
Reports, for each EA instrument: median M15 ATR, the max tolerable QUOTED spread in
price units, and the standard prop-firm name. Check a firm's spec sheet against these
BEFORE paying a challenge fee."""
import numpy as np
from scalper_backtest import load_dataset, wilder_atr

NAME = {  # Deriv name -> standard prop-firm symbol
 "US_Tech_100":"NAS100/US100", "US_SP_500":"SPX500/US500", "Wall_Street_30":"US30/DJI30",
 "US_Small_Cap_2000":"US2000/RUS2000", "Germany_40":"GER40/DAX40", "UK_100":"UK100/FTSE100",
 "France_40":"FRA40/CAC40", "Japan_225":"JP225/JPN225", "BTCUSD":"BTCUSD", "ETHUSD":"ETHUSD",
 "SOLUSD":"SOLUSD", "XRPUSD":"XRPUSD"}

data = load_dataset("derivM15_spreadgated")
print(f"{'instrument':22s} {'prop name':16s} {'med ATR(M15)':>12s} {'max spread':>11s}  {'(= 0.10*ATR)':>12s}")
for sym, df in sorted(data.items()):
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    atr = wilder_atr(h, l, c, 14)
    med = float(np.nanmedian(atr))
    print(f"{sym:22s} {NAME.get(sym,'?'):16s} {med:12.3f} {0.10*med:11.3f}  price units")
print("\nRule: a prop firm's typical QUOTED spread on the instrument must be <= 'max spread'.")
print("Indices are usually quoted in points; crypto in dollars. Compare like-for-like.")
