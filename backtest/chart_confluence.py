"""Chart the confluence experiment: marginal OOS dExp per candidate + the pullback cost curve."""
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import scalper_backtest as B
from scalper_confluence import CParams, simulate_symbol_c, rs_of

data=B.load_dataset("derivM15")
def oos_exp(ov, cost):
    p=CParams(**{**dict(tp_atr=3.0), **ov, "cost_atr_frac":cost})
    rs=[]
    for sym,df in data.items():
        n=len(df); tr,_=simulate_symbol_c(df,p,int(n*0.7),n); rs+=rs_of(tr)
    a=np.array(rs); return a.mean(), a.size

base=oos_exp({},0.02)[0]
cands=[("#1 pull 0.6","geom",dict(entry_style="limit",entry_offset_atr=0.6,pending_expiry_bars=3)),
 ("#1+#2 0.6+struct","geom",dict(entry_style="limit",entry_offset_atr=0.6,pending_expiry_bars=3,stop_mode="struct")),
 ("#1 pull 0.3","geom",dict(entry_style="limit",entry_offset_atr=0.3,pending_expiry_bars=3)),
 ("#2 struct stop","geom",dict(stop_mode="struct")),
 ("#7 sess 930-1130","filt",dict(sess_start_hm=930,sess_end_hm=1130)),
 ("#6 vol .3-.9","filt",dict(rv_pct_lo=0.3,rv_pct_hi=0.9)),
 ("#3 ADX>=20","filt",dict(adx_min=20.0)),
 ("#4 HTF H4","filt",dict(htf_minutes=240)),
 ("#5 ER>=0.3","filt",dict(er_min=0.3)),
 ("#9 vol1.0 (ctrl)","filt",dict(vol_gate_k=1.0)),
 ("#5 body>=0.5","filt",dict(body_frac_min=0.5))]
res=[(l,k,oos_exp(ov,0.02)[0]-base) for l,k,ov in cands]
res.sort(key=lambda x:x[2])

fig,(ax1,ax2)=plt.subplots(1,2,figsize=(13,5.6))
cols=["#2a7" if k=="geom" else "#999" for _,k,_ in res]
ax1.barh([r[0] for r in res],[r[2] for r in res],color=cols)
ax1.axvline(0,color="#000",lw=0.8); ax1.set_xlabel("OOS marginal ΔExpectancy vs tp3.0 baseline (R/trade, cost .02)")
ax1.set_title("Confluence candidates — only entry-geometry (green) helps")
ax1.grid(axis="x",alpha=0.25)

costs=np.linspace(0,0.06,13)
pull=[oos_exp(dict(entry_style="limit",entry_offset_atr=0.6,pending_expiry_bars=3),c)[0] for c in costs]
bl=[oos_exp({},c)[0] for c in costs]
ax2.plot(costs*100,pull,marker="o",ms=3,color="#2a7",lw=1.6,label="#1 pullback limit 0.6 ATR")
ax2.plot(costs*100,bl,marker="o",ms=3,color="#c33",lw=1.6,label="baseline tp3.0 (chase-at-extension)")
ax2.axhline(0,color="#000",lw=0.9); ax2.axvspan(2,4,color="#fdd",alpha=0.5,label="realistic Deriv cost")
ax2.set_xlabel("cost per side (% of ATR)"); ax2.set_ylabel("OOS expectancy (R/trade)")
ax2.set_title("Pullback entry lifts OOS expectancy above zero — but cost-fragile")
ax2.legend(fontsize=8.5); ax2.grid(alpha=0.25)
fig.suptitle("DerivScalper confluence test on REAL Deriv M15 (5 indices, OOS = last 30%) — 0 of 19 ship; pullback geometry is the lead",fontsize=10.5)
fig.tight_layout(); fig.savefig("confluence_result.png",dpi=130)
print("saved confluence_result.png")
PY = None
