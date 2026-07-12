"""High-ADX first-touch EMA20 strategy for the registered 3R study."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
from scalper_backtest import wilder_atr


def _rma(x, p):
    y=np.full(len(x),np.nan); valid=np.asarray(x,float)
    if len(x)<p: return y
    y[p-1]=np.nanmean(valid[:p])
    for i in range(p,len(x)): y[i]=(y[i-1]*(p-1)+valid[i])/p
    return y


def indicators(s,p=14):
    h,l,c=np.asarray(s.h,float),np.asarray(s.l,float),np.asarray(s.c,float); n=len(c)
    up=np.r_[0.,np.diff(h)]; down=np.r_[0.,-np.diff(l)]
    pdm=np.where((up>down)&(up>0),up,0.); mdm=np.where((down>up)&(down>0),down,0.)
    atr=wilder_atr(h,l,c,p); ps=_rma(pdm,p); ms=_rma(mdm,p)
    with np.errstate(divide="ignore",invalid="ignore"):
        pdi=100*ps/atr; mdi=100*ms/atr; dx=100*np.abs(pdi-mdi)/(pdi+mdi)
    adx=np.full(n,np.nan); seed=2*p-2
    if n>seed:
        adx[seed]=np.nanmean(dx[p-1:seed+1])
        for i in range(seed+1,n): adx[i]=(adx[i-1]*(p-1)+dx[i])/p
    ema=pd.Series(c).ewm(span=20,adjust=False).mean().to_numpy()
    return atr,adx,pdi,mdi,ema


def run_h1(s,buf_frac=.02,hold=8,ind=None,return_diag=False):
    atr,adx,pdi,mdi,ema=ind if ind is not None else indicators(s)
    n=len(s.c); i=40; out=[]; d={"setups":0,"touches":0,"invalidated":0,"touch_expired":0,"confirm_expired":0,"confirmed":0,"trades":0}
    while i<n-2:
        long=np.isfinite(adx[i]) and adx[i]>30 and pdi[i]>mdi[i] and s.c[i]>ema[i] and s.h[i]>np.max(s.h[i-19:i])
        short=np.isfinite(adx[i]) and adx[i]>30 and mdi[i]>pdi[i] and s.c[i]<ema[i] and s.l[i]<np.min(s.l[i-19:i])
        if not (long or short): i+=1; continue
        sd=1 if long else -1; d["setups"]+=1; touch=-1; invalid=-1; end=min(i+21,n)
        for t in range(i+1,end):
            aligned=(pdi[t]>mdi[t]) if sd>0 else (mdi[t]>pdi[t])
            if not np.isfinite(adx[t]) or adx[t]<=30 or not aligned: invalid=t; break
            if (sd>0 and s.l[t]<=ema[t]) or (sd<0 and s.h[t]>=ema[t]): touch=t; break
        if invalid>=0: d["invalidated"]+=1; i=invalid+1; continue
        if touch<0: d["touch_expired"]+=1; i=end; continue
        d["touches"]+=1; a=float(atr[touch]); buf=buf_frac*a; stop=float(s.h[touch])+buf if sd>0 else float(s.l[touch])-buf
        trigger=-1; ce=min(touch+5,n-1)
        for b in range(touch+1,ce):
            if (sd>0 and s.h[b]>=stop) or (sd<0 and s.l[b]<=stop): trigger=b; break
        if trigger<0: d["confirm_expired"]+=1; i=ce; continue
        entry_bar=trigger+1
        if entry_bar>=n: d["confirm_expired"]+=1; break
        d["confirmed"]+=1; entry=float(s.o[entry_bar]); sl=entry-a*sd; tp=entry+3*a*sd; xb=xp=None
        for k in range(entry_bar,min(entry_bar+hold,n)):
            if sd>0:
                if s.l[k]<=sl: xb,xp=k,sl; break
                if s.h[k]>=tp+buf: xb,xp=k,tp; break
            else:
                if s.h[k]>=sl: xb,xp=k,sl; break
                if s.l[k]<=tp-buf: xb,xp=k,tp; break
        if xb is None: xb=min(entry_bar+hold-1,n-1); xp=float(s.c[xb])
        r=(xp-entry)*sd/a-2*float(s.cost)*float(atr[touch])/a
        out.append((int(s.ep[i]),float(r))); d["trades"]+=1; i=xb+1
    return (out,d) if return_diag else out


def self_test():
    passed=[]
    def check(n,c):
        if not c: raise AssertionError(n)
        passed.append(n)
    n=140; up=SimpleNamespace(h=np.arange(n,dtype=float)+2,l=np.arange(n,dtype=float),c=np.arange(n,dtype=float)+1,o=np.arange(n,dtype=float)+.5)
    _,a,p,m,_=indicators(up); check("wilder_uptrend_adx_di",a[-1]>90 and p[-1]>m[-1])
    dn=SimpleNamespace(h=200-np.arange(n,dtype=float)+2,l=200-np.arange(n,dtype=float),c=201-np.arange(n,dtype=float),o=200.5-np.arange(n,dtype=float))
    _,a,p,m,_=indicators(dn); check("wilder_downtrend_adx_di",a[-1]>90 and m[-1]>p[-1])
    def fx(side=1,stop_first=False,no_confirm=False,invalidate=False):
        n=80; o=np.full(n,100.); h=np.full(n,101.); l=np.full(n,99.); c=np.full(n,100.); ep=np.arange(n)*900; atr=np.full(n,10.); adx=np.full(n,np.nan); pdi=np.zeros(n); mdi=np.zeros(n); ema=np.full(n,100.); i=45
        adx[i:i+10]=40
        if side>0: pdi[i:i+10]=30; mdi[i:i+10]=10; h[i]=110; c[i]=105; l[i+1]=99; h[i+1]=106; stop=106.2; h[i+2]=105 if no_confirm else stop; o[i+3]=107; l[i+3]=96 if stop_first else 106; h[i+4]=101 if no_confirm else 137.2
        else: mdi[i:i+10]=30; pdi[i:i+10]=10; l[i]=90; c[i]=95; h[i+1]=101; l[i+1]=94; stop=93.8; l[i+2]=95 if no_confirm else stop; o[i+3]=93; h[i+3]=104 if stop_first else 94; l[i+4]=99 if no_confirm else 62.8
        if invalidate: adx[i+1]=30
        s=SimpleNamespace(o=o,h=h,l=l,c=c,ep=ep,cost=0.)
        return s,(atr,adx,pdi,mdi,ema)
    s,z=fx(1); rows,d=run_h1(s,ind=z,return_diag=True); check("long_first_touch_next_open_3r",len(rows)==1 and rows[0][1]==3 and d["confirmed"]==1)
    s,z=fx(-1); rows,d=run_h1(s,ind=z,return_diag=True); check("short_first_touch_next_open_3r",len(rows)==1 and rows[0][1]==3)
    s,z=fx(1,no_confirm=True); rows,d=run_h1(s,ind=z,return_diag=True); check("no_same_bar_or_missing_confirmation",len(rows)==0 and d["confirm_expired"]==1)
    s,z=fx(1,invalidate=True); rows,d=run_h1(s,ind=z,return_diag=True); check("adx_invalidation",len(rows)==0 and d["invalidated"]==1)
    s,z=fx(1,stop_first=True); rows,_=run_h1(s,ind=z,return_diag=True); check("stop_first",len(rows)==1 and rows[0][1]==-1)
    print(f"holy-grail synthetic checks: {len(passed)} passed")
    for n in passed: print(f"PASS {n}")
    return tuple(passed)


if __name__=="__main__": self_test()
