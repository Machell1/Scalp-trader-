"""First-touch pullback stop-confirmation enumerator for the 3R study."""
from types import SimpleNamespace
import numpy as np
from parity_engine import START
from retest_engine import W


def run_confirm(s, buf_frac=0.02, thr=0.30, offset=0.6, hold=8, return_diag=False):
    out=[]; diag={"signals":0,"pullback_touch":0,"confirmed":0,"unfilled":0,"unconfirmed":0,"trades":0}
    n=len(s.c); i=START
    while i<n-1:
        if not (s.side[i]!=0 and np.isfinite(s.watr[i]) and s.watr[i]>=thr): i+=1; continue
        diag["signals"]+=1; sd=int(s.side[i]); a=float(s.atr[i]); buf=buf_frac*a
        limit=float(s.c[i])-offset*a*sd; end=min(i+1+W,n); touch=-1
        for b in range(i+1,end):
            if (sd>0 and s.l[b]<=limit-buf) or (sd<0 and s.h[b]>=limit+buf): touch=b; break
        if touch<0: diag["unfilled"]+=1; i+=W; continue
        diag["pullback_touch"]+=1
        confirm=float(s.h[touch])+buf if sd>0 else float(s.l[touch])-buf; j=-1
        for b in range(touch+1,end):
            if (sd>0 and s.h[b]>=confirm) or (sd<0 and s.l[b]<=confirm): j=b; break
        if j<0: diag["unconfirmed"]+=1; i+=W; continue
        diag["confirmed"]+=1; entry=confirm; risk=a; sl=entry-risk*sd; tp=entry+3*a*sd
        xb=xp=None
        for k in range(j,min(j+hold,n)):
            if sd>0:
                if s.l[k]<=sl: xb,xp=k,sl; break
                if s.h[k]>=tp+buf: xb,xp=k,tp; break
            else:
                if s.h[k]>=sl: xb,xp=k,sl; break
                if s.l[k]<=tp-buf: xb,xp=k,tp; break
        if xb is None: xb=min(j+hold-1,n-1); xp=float(s.c[xb])
        r=(xp-entry)*sd/risk-2*float(s.cost)*a/risk
        out.append((int(s.ep[i]),float(r))); diag["trades"]+=1; i=xb+1
    return (out,diag) if return_diag else out


def self_test():
    passed=[]
    def check(n,c):
        if not c: raise AssertionError(n)
        passed.append(n)
    def fx(side, subsequent_confirm=True, stop_first=False, same_bar_extreme=False):
        n=START+15; o=np.full(n,100.); h=np.full(n,100.); l=np.full(n,100.); c=np.full(n,100.); atr=np.full(n,10.); watr=np.full(n,np.nan); sides=np.zeros(n,dtype=np.int8); ep=np.arange(n)*900
        sides[START]=side; watr[START]=.3; t=START+1
        if side>0:
            l[t]=93.; h[t]=130. if same_bar_extreme else 96.; c[t]=95.; confirm=h[t]+.2
            if subsequent_confirm: h[t+1]=confirm; l[t+1]=confirm-(11 if stop_first else 1); h[t+2]=confirm+30.2
            else: h[t+1:t+5]=confirm-1.0
        else:
            h[t]=107.; l[t]=70. if same_bar_extreme else 104.; c[t]=105.; confirm=l[t]-.2
            if subsequent_confirm: l[t+1]=confirm; h[t+1]=confirm+(11 if stop_first else 1); l[t+2]=confirm-30.2
            else: l[t+1:t+5]=confirm+1.0
        return SimpleNamespace(o=o,h=h,l=l,c=c,atr=atr,watr=watr,side=sides,ep=ep,cost=0.)
    rows,d=run_confirm(fx(1),return_diag=True); check("long_confirm_3r",len(rows)==1 and abs(rows[0][1]-3)<1e-12 and d["confirmed"]==1)
    rows,d=run_confirm(fx(-1),return_diag=True); check("short_confirm_3r",len(rows)==1 and abs(rows[0][1]-3)<1e-12 and d["confirmed"]==1)
    rows,d=run_confirm(fx(1,subsequent_confirm=False,same_bar_extreme=True),return_diag=True); check("same_bar_cannot_confirm",len(rows)==0 and d["unconfirmed"]==1)
    rows,d=run_confirm(fx(-1,subsequent_confirm=False),return_diag=True); check("expiry_cancels_unconfirmed",len(rows)==0 and d["unconfirmed"]==1)
    rows,_=run_confirm(fx(1,stop_first=True),return_diag=True); check("stop_first_after_confirm",len(rows)==1 and rows[0][1]==-1.)
    print(f"pullback-stop synthetic checks: {len(passed)} passed")
    for n in passed: print(f"PASS {n}")
    return tuple(passed)


if __name__=="__main__": self_test()
