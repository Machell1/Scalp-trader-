"""Chart: OOS vs IS expectancy (R/trade) vs cost for the key configs, real Deriv M15."""
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scalper_backtest import Params, load_dataset, simulate_symbol

data = load_dataset("derivM15")
CFG = {
    "OLD tp1.5":            dict(direction="cont", stop_atr=1.0, tp_atr=1.5),
    "NEW tp3.0":            dict(direction="cont", stop_atr=1.0, tp_atr=3.0),
    "SHIPPED tp3.0+AVWAP":  dict(direction="cont", stop_atr=1.0, tp_atr=3.0, vwap_window=1, vwap_min_bars=8),
    "ROBUST stop2/tp3":     dict(direction="cont", stop_atr=2.0, tp_atr=3.0),
}
costs = np.linspace(0, 0.05, 11)

def pooled_R(base, split):
    p = Params(entry_style="stop", cost_atr_frac=0.0, **base)
    out=[]
    for sym, df in data.items():
        n=len(df); lo,hi=(0,int(n*0.7)) if split=="is" else (int(n*0.7),n)
        out.extend(simulate_symbol(df, p, lo, hi))
    return np.asarray(out,float)

fig, axes = plt.subplots(1,2, figsize=(12,5.2), sharey=True)
for ax, split, title in [(axes[0],"is","IN-SAMPLE (first 70%)"),(axes[1],"oos","OUT-OF-SAMPLE (last 30%) — the honest test")]:
    for name, base in CFG.items():
        R = pooled_R(base, split); stop_atr = base["stop_atr"]
        exp = [ (R - 2*c/stop_atr).mean() for c in costs ]
        ax.plot(costs*100, np.array(exp), marker="o", ms=3, lw=1.5, label=f"{name} (N={R.size})")
    ax.axhline(0, color="#000", lw=0.9)
    ax.axvspan(2,4, color="#fdd", alpha=0.5, label="realistic Deriv cost")
    ax.set_title(title, fontsize=10); ax.set_xlabel("cost per side (% of ATR)"); ax.grid(alpha=0.25)
axes[0].set_ylabel("expectancy (R / trade)")
axes[1].legend(fontsize=8, loc="upper right")
fig.suptitle("DerivScalper updated config on REAL Deriv M15 (5 US indices, 2024–2026): expectancy vs cost", fontsize=11)
fig.tight_layout(); fig.savefig("deriv_recheck.png", dpi=130)
print("saved deriv_recheck.png")
