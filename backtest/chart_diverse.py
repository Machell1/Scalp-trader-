"""Chart the diverse-basket confirmation of the pullback entry (efficient: each sim run once)."""
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import scalper_backtest as B
from scalper_confluence import CParams, simulate_symbol_c, rs_of
from validate_diverse import CLASS, BASE

data=B.load_dataset("derivM15_diverse")
PULL=dict(entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3)
COSTS=[0.0,0.02,0.04]

def persym(ov,cost):
    out={}
    for s,df in data.items():
        n=len(df); tr,_=simulate_symbol_c(df, CParams(**{**BASE,**ov,"cost_atr_frac":cost}), int(n*0.7), n)
        out[s]=np.array(rs_of(tr),float)
    return out

# run each config once per cost
pull={c:persym(PULL,c) for c in COSTS}
base={c:persym({},c) for c in COSTS}

def agg(ps, subset=None):
    rs=np.concatenate([a for s,a in ps.items() if (subset is None or CLASS.get(s) in subset) and a.size])
    return rs.mean()

classes=["FX","METAL","ENERGY","CRYPTO","INDEX"]
vals=[np.concatenate([a for s,a in pull[0.02].items() if CLASS.get(s)==c]).mean() for c in classes]

fig,(ax1,ax2)=plt.subplots(1,2,figsize=(13,5.4))
cols=["#c33" if v<0 else "#2a7" for v in vals]
ax1.bar(classes,vals,color=cols); ax1.axhline(0,color="#000",lw=0.9)
ax1.set_ylabel("OOS expectancy (R/trade, cost .02)")
ax1.set_title("#1 pullback entry by asset class — works on CRYPTO/INDEX, fails FX")
ax1.grid(axis="y",alpha=0.25)
for i,v in enumerate(vals): ax1.text(i,v+(0.002 if v>=0 else -0.005),f"{v:+.3f}",ha="center",fontsize=8)

x=np.arange(len(COSTS)); w=0.27
ax2.bar(x-w,[agg(pull[c],{"CRYPTO","INDEX"}) for c in COSTS],w,color="#0a7",label="pullback CRYPTO+INDEX")
ax2.bar(x,  [agg(pull[c]) for c in COSTS],w,color="#7a2",label="pullback all 29")
ax2.bar(x+w,[agg(base[c]) for c in COSTS],w,color="#c33",label="baseline (chase) all")
ax2.axhline(0,color="#000",lw=0.9); ax2.set_xticks(x); ax2.set_xticklabels([f"{int(c*100)}%" for c in COSTS])
ax2.set_xlabel("cost per side (% of ATR)"); ax2.set_ylabel("OOS expectancy (R/trade)")
ax2.set_title("Pullback edge is real but tiny — eaten by realistic cost"); ax2.legend(fontsize=8); ax2.grid(axis="y",alpha=0.25)
fig.suptitle("Pullback entry on DIVERSE real Deriv M15 (29 instruments, N_eff=5.7, OOS): real structural gain, still cost-fragile — WATCH not SHIP",fontsize=10.5)
fig.tight_layout(); fig.savefig("diverse_result.png",dpi=130)
print(f"saved diverse_result.png")
print(f"CRYPTO+INDEX pullback: " + "  ".join(f"cost{c}: exp{agg(pull[c],{'CRYPTO','INDEX'}):+.4f}" for c in COSTS))
print(f"ALL 29 pullback     : " + "  ".join(f"cost{c}: exp{agg(pull[c]):+.4f}" for c in COSTS))
