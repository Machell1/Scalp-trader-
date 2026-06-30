"""Confirmation test of the pre-registered lead (#1 pullback-limit entry) on the
DIVERSE real Deriv M15 basket (29 instruments across FX/metals/energy/crypto/global indices).

This is the breadth test the 5 correlated US indices could not provide. We compare the
tp3.0 baseline (chase-at-extension stop) against the pullback-limit entry, report
per-instrument and per-asset-class results, the genuine effective breadth, and the ship-gate.
"""
from __future__ import annotations
import math, os
import numpy as np, pandas as pd
import scalper_backtest as B
from scalper_confluence import CParams, simulate_symbol_c, rs_of
from experiment import ncdf, nppf, psr, stt, EMC

DATA_TF = "derivM15_diverse"

CLASS = {
    **{s:"FX" for s in ["EURUSD","GBPUSD","USDJPY","USDCAD","USDCHF","NZDUSD","EURJPY","GBPJPY","EURGBP","AUDJPY"]},
    **{s:"METAL" for s in ["XAUUSD","XAGUSD","XPTUSD","XCUUSD"]},
    **{s:"ENERGY" for s in ["US_Oil","UK_Brent_Oil","NGAS"]},
    **{s:"CRYPTO" for s in ["BTCUSD","ETHUSD","LTCUSD","XRPUSD","SOLUSD","BCHUSD"]},
    **{s:"INDEX" for s in ["Germany_40","UK_100","Japan_225","France_40","Australia_200","Hong_Kong_50"]},
}

BASE = dict(tp_atr=3.0)
CANDS = [
    ("baseline tp3.0",        dict()),
    ("#1 pullback 0.6",       dict(entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3)),
    ("#1 pullback 0.3",       dict(entry_style="limit", entry_offset_atr=0.3, pending_expiry_bars=3)),
    ("#1+#2 0.6+struct",      dict(entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3, stop_mode="struct")),
]

def mkp(ov, cost): return CParams(**{**BASE, **ov, "cost_atr_frac": cost})

def per_symbol_oos(data, ov, cost):
    out={}
    for sym,df in data.items():
        n=len(df); lo,hi=int(n*0.7),n
        tr,_=simulate_symbol_c(df, mkp(ov,cost), lo, hi)
        out[sym]=np.array(rs_of(tr),float)
    return out

def n_eff(data):
    rets={}
    for sym,df in data.items():
        rets[sym]=pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["time"])).pct_change()
    M=pd.concat(rets,axis=1,sort=True).dropna()
    C=M.corr().to_numpy()
    ev=np.linalg.eigvalsh(C); ev=ev[ev>0]
    pr=(ev.sum()**2)/np.square(ev).sum()
    mr=(C.sum()-len(C))/(len(C)*(len(C)-1))
    return pr, mr, len(C)

def quarter_signs(persym_dict, data, ov, cost):
    recs=[]
    for sym,df in data.items():
        n=len(df); lo,hi=int(n*0.7),n
        tr,_=simulate_symbol_c(df, mkp(ov,cost), lo, hi)
        tt=pd.to_datetime(df["time"]).to_numpy()
        for t in tr: recs.append((tt[t["i"]], t["r"]))
    if not recs: return 0,0
    s=pd.DataFrame(recs,columns=["t","r"]); s["q"]=pd.PeriodIndex(pd.to_datetime(s["t"]),freq="Q")
    g=s.groupby("q").r.mean()
    return int((g>0).sum()), int(len(g))

def main():
    data=B.load_dataset(DATA_TF)
    pr,mr,k=n_eff(data)
    haircut=math.sqrt(pr/k)
    print(f"DIVERSE DERIV M15: {k} instruments  mean pairwise r={mr:.3f}  N_eff={pr:.1f}  (vs 1.3 on the 5 US indices)  t-haircut x{haircut:.2f}\n")

    base_oos={c: np.concatenate(list(per_symbol_oos(data, {}, c).values())) for c in (0.0,0.02,0.04)}
    bexp={c:base_oos[c].mean() for c in base_oos}

    # collect trial sharpes for DSR hurdle
    trial_sr=[]
    results=[]
    for label, ov in CANDS:
        ps_oos=per_symbol_oos(data, ov, 0.02)
        pool=np.concatenate(list(ps_oos.values()))
        ps_is=per_symbol_oos(data, ov, 0.02)  # placeholder; IS below
        # IS pooled
        is_pool=[]
        for sym,df in data.items():
            n=len(df); tr,_=simulate_symbol_c(df, mkp(ov,0.02), 0, int(n*0.7)); is_pool+=rs_of(tr)
        is_pool=np.array(is_pool)
        so=stt(pool); si=stt(is_pool)
        pool0=np.concatenate(list(per_symbol_oos(data,ov,0.0).values()))
        pool4=np.concatenate(list(per_symbol_oos(data,ov,0.04).values()))
        pos=sum(1 for a in ps_oos.values() if a.size>=20 and a.mean()>0)
        tot=sum(1 for a in ps_oos.values() if a.size>=20)
        dexp=so["exp"]-bexp[0.02]
        wfe=(so["exp"]/si["exp"]) if si["exp"]>0 else float("nan")
        qpos,qn=quarter_signs(ps_oos,data,ov,0.02)
        trial_sr.append(so["sr"])
        # per asset class exp@0.02
        cls={}
        for sym,a in ps_oos.items():
            c=CLASS.get(sym,"?")
            cls.setdefault(c,[]).extend(a.tolist())
        results.append(dict(label=label, so=so, dexp=dexp, exp0=pool0.mean(), exp4=pool4.mean(),
                            pos=pos, tot=tot, wfe=wfe, qpos=qpos, qn=qn, t_hc=so["t"]*haircut,
                            n_eff_tr=so["n"]*(pr/k), pool=pool, cls=cls, ps=ps_oos))

    sr=np.array([s for s in trial_sr if np.isfinite(s)]); N=max(2,len(sr))
    var=float(np.var(sr,ddof=1)) if len(sr)>1 else 0.0
    z1=nppf(1-1/N); z2=nppf(1-1/N*math.exp(-1)); sr0=math.sqrt(var)*((1-EMC)*z1+EMC*z2) if var>0 else 0.0

    print(f"BASELINE tp3.0 diverse OOS: exp@0 {bexp[0.0]:+.4f}  exp@.02 {bexp[0.02]:+.4f}  exp@.04 {bexp[0.04]:+.4f}\n")
    hdr=f"{'candidate':20s}{'N':>7s}{'exp@0':>8s}{'exp.02':>8s}{'exp.04':>8s}{'dExp':>8s}{'t':>6s}{'t_hc':>6s}{'+inst':>7s}{'WFE':>6s}{'Qpos':>7s}{'DSR':>6s}  VERDICT"
    print(hdr); print("-"*len(hdr))
    for r in results:
        if r["label"].startswith("baseline"):
            print(f"{r['label']:20s}{r['so']['n']:7d}{r['exp0']:+8.4f}{r['so']['exp']:+8.4f}{r['exp4']:+8.4f}{'':8s}{r['so']['t']:+6.2f}{r['t_hc']:+6.2f}{r['pos']:4d}/{r['tot']:<2d}{'':6s}{r['qpos']:4d}/{r['qn']:<2d}")
            continue
        dsr=psr(r["pool"], sr0)
        gates=[r["dexp"]>0, r["so"]["exp"]>0, (np.isfinite(r["wfe"]) and r["wfe"]>=0.3),
               (np.isfinite(dsr) and dsr>=0.95), (r["n_eff_tr"]>=250 and r["so"]["exp"]>1.3*(1.96+0.84)/math.sqrt(max(1,r["n_eff_tr"]))),
               r["exp4"]>0, (r["qn"]>0 and r["qpos"]>=math.ceil(r["qn"]*0.6)), r["t_hc"]>=1.96]
        verdict="SHIP" if all(gates) else ("WATCH" if (r["dexp"]>0 and r["so"]["exp"]>0) else "NO-SHIP")
        wfe=f"{r['wfe']:6.2f}" if np.isfinite(r["wfe"]) else "   nan"
        print(f"{r['label']:20s}{r['so']['n']:7d}{r['exp0']:+8.4f}{r['so']['exp']:+8.4f}{r['exp4']:+8.4f}{r['dexp']:+8.4f}{r['so']['t']:+6.2f}{r['t_hc']:+6.2f}{r['pos']:4d}/{r['tot']:<2d}{wfe}{r['qpos']:4d}/{r['qn']:<2d}{dsr:6.2f}  {verdict}")

    # per-asset-class + per-instrument for the primary lead
    lead=[r for r in results if r["label"]=="#1 pullback 0.6"][0]
    print(f"\n#1 pullback 0.6 — OOS exp@.02 by ASSET CLASS:")
    for c in ["FX","METAL","ENERGY","CRYPTO","INDEX"]:
        a=np.array(lead["cls"].get(c,[]))
        if a.size: print(f"   {c:7s} N={a.size:5d}  exp={a.mean():+.4f}  win={(a>0).mean()*100:4.1f}%  tot={a.sum():+7.1f}")
    print(f"\n#1 pullback 0.6 — per-instrument OOS exp@.02 (sorted):")
    items=sorted(lead["ps"].items(), key=lambda kv:-(kv[1].mean() if kv[1].size else -9))
    for sym,a in items:
        if a.size: print(f"   {sym:16s}[{CLASS.get(sym,'?'):6s}] N={a.size:5d} exp={a.mean():+.4f}")

if __name__=="__main__":
    main()
