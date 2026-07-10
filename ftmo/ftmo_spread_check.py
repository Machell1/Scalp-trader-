"""FTMO spread-transfer check — does the DerivScalperEA edge survive on FTMO's feed?

Gate (validated): quoted spread must be <= 0.10 * ATR(M15,14) per instrument.
This script connects to a RUNNING MT5 terminal (point it at the FTMO demo/trial
terminal), and for each target symbol computes — from FTMO's OWN data — its M15
ATR ceiling and its live spread, then verdicts PASS / FAIL.

USAGE (after you've logged the FTMO MT5 terminal in yourself; I never enter creds):
  python ftmo_spread_check.py                      # auto-connect to the running terminal
  python ftmo_spread_check.py --path "C:/.../terminal64.exe"   # target a specific terminal
  python ftmo_spread_check.py --samples 300        # also sample live spread over N ticks

FTMO tickers use a .cash suffix on indices; the script tries a few name variants.
"""
import argparse, time
import numpy as np
import MetaTrader5 as mt5

# Deriv name -> candidate FTMO tickers (first that resolves is used)
TARGETS = {
    "US30 (Wall St)":   ["US30.cash", "US30", "US30.spot", "DJI30"],
    "NAS100 (US Tech)": ["US100.cash", "USTEC.cash", "NAS100", "US100"],
    "SP500":            ["US500.cash", "US500", "SPX500", "SP500"],
    "US2000":           ["US2000.cash", "US2000", "RUS2000"],
    "GER40 (DAX)":      ["GER40.cash", "DE40.cash", "GER40", "DE40", "DAX40"],
    "UK100 (FTSE)":     ["UK100.cash", "UK100", "FTSE100"],
    "FRA40 (CAC)":      ["FRA40.cash", "FR40.cash", "FRA40", "CAC40"],
    "JP225":            ["JP225.cash", "JPN225.cash", "JP225", "JPN225"],
    "BTCUSD":           ["BTCUSD", "BTC/USD", "BTCUSD.cash"],
    "ETHUSD":           ["ETHUSD", "ETH/USD", "ETHUSD.cash"],
}

def atr_m15(sym, period=14, bars=200):
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, bars)
    if r is None or len(r) < period + 2:
        return None
    h = r['high']; l = r['low']; c = r['close']
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return float(np.mean(tr[-period:]))

def resolve(cands):
    for name in cands:
        info = mt5.symbol_info(name)
        if info is not None:
            mt5.symbol_select(name, True)
            return name
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=None)
    ap.add_argument("--samples", type=int, default=0)
    a = ap.parse_args()
    ok = mt5.initialize(path=a.path) if a.path else mt5.initialize()
    if not ok:
        print("MT5 initialize failed:", mt5.last_error())
        print("-> Open the FTMO MT5 terminal, log in yourself, then re-run.")
        return
    ai = mt5.account_info()
    print(f"connected: {ai.company} | login {ai.login} | {ai.server} | {ai.currency}\n")
    print(f"{'instrument':18s} {'ftmo sym':14s} {'spread':>9s} {'ceiling(0.10xATR)':>18s}  verdict")
    npass = 0; ntot = 0
    for label, cands in TARGETS.items():
        sym = resolve(cands)
        if sym is None:
            print(f"{label:18s} {'-- not found --':14s}")
            continue
        atr = atr_m15(sym)
        tick = mt5.symbol_info_tick(sym)
        if atr is None or tick is None or tick.ask <= 0:
            print(f"{label:18s} {sym:14s}  (no data / market closed)")
            continue
        spread = tick.ask - tick.bid
        # optional: sample live spread over N ticks for a robust median
        if a.samples > 0:
            s = []
            for _ in range(a.samples):
                t = mt5.symbol_info_tick(sym)
                if t and t.ask > 0:
                    s.append(t.ask - t.bid)
                time.sleep(0.02)
            if s:
                spread = float(np.median(s))
        ceiling = 0.10 * atr
        ntot += 1
        verdict = "PASS" if spread <= ceiling else "FAIL"
        if verdict == "PASS":
            npass += 1
        print(f"{label:18s} {sym:14s} {spread:9.3f} {ceiling:18.3f}  {verdict}"
              f"{'' if verdict=='PASS' else '  (edge dies here)'}")
    print(f"\n{npass}/{ntot} instruments clear the spread ceiling on FTMO.")
    print("Only the PASS instruments should be in the EA's FTMO whitelist.")
    mt5.shutdown()

if __name__ == "__main__":
    main()
