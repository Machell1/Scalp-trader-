"""Overfit-resistant marginal-contribution runner for the confluence candidates.

Every candidate is ONE marginal change vs the tp3.0 baseline (continuation, no AVWAP),
judged on OUT-OF-SAMPLE data with: marginal delta-expectancy, a permutation-vs-random-
subset test (the AVWAP-killer, for FILTER candidates), WFE(OOS/IS), per-quarter sign
stability, a correlation breadth haircut (5 indices ~= 1.2 effective bets), a power floor,
2x cost-stress, and a Deflated Sharpe over ALL cells tried. Emits a SHIP/NO-SHIP table.

Honest expectation: most candidates fail. The runner's job is to say NO reliably.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

import scalper_backtest as B
from scalper_confluence import CParams, simulate_symbol_c, rs_of

RNG = np.random.default_rng(20260630)
COST_REAL = 0.02      # realistic per-side cost (ATR fraction) for Deriv indices
COST_STRESS = 0.04    # 2x stress
EMC = 0.5772156649015329

# ---------------------------------------------------------------------------
# normal cdf / inverse (Acklam) for PSR/DSR
# ---------------------------------------------------------------------------
def ncdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))

def nppf(p):
    a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00]
    b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,6.680131188771972e+01,-1.328068155288572e+01]
    c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,-2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00]
    d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,3.754408661907416e+00]
    pl=0.02425
    if p<pl:
        q=math.sqrt(-2*math.log(p));return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p<=1-pl:
        q=p-0.5;r=q*q;return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q=math.sqrt(-2*math.log(1-p));return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

def psr(r, sr0_per_obs):
    """P(true per-obs Sharpe > sr0), skew/kurtosis adjusted (Bailey & Lopez de Prado)."""
    r = np.asarray(r, float); T = len(r)
    if T < 5 or r.std(ddof=1) == 0: return float("nan")
    sr = r.mean()/r.std(ddof=1)
    s = pd.Series(r); g3 = float(s.skew()); g4 = float(s.kurtosis())+3.0
    denom = math.sqrt(max(1e-12, 1 - g3*sr + (g4-1)/4.0*sr*sr))
    return ncdf((sr - sr0_per_obs)*math.sqrt(T-1)/denom)

# ---------------------------------------------------------------------------
# pooled run helpers
# ---------------------------------------------------------------------------
def pooled_oos(data, p, split="oos", block=True):
    """Return (pooled R array, per-symbol R lists, counters-sum). split: is/oos/all."""
    per = {}; cnt = dict(signals=0, passed=0, nonfill=0)
    p2 = CParams(**{**p.__dict__, "block_overlap": block})
    for sym, df in data.items():
        n=len(df)
        lo,hi = (0,int(n*0.7)) if split=="is" else (int(n*0.7),n) if split=="oos" else (0,n)
        tr,c = simulate_symbol_c(df, p2, lo, hi)
        per[sym] = np.array(rs_of(tr), float)
        for k in cnt: cnt[k]+=c[k]
    pool = np.concatenate([a for a in per.values() if a.size]) if any(a.size for a in per.values()) else np.array([])
    return pool, per, cnt

def stt(a):
    a=np.asarray(a,float)
    if a.size==0: return dict(n=0,exp=0,t=0,win=0,tot=0,sd=0,sr=0)
    sd=a.std(ddof=1) if a.size>1 else 0.0
    return dict(n=a.size, exp=a.mean(), t=(a.mean()/(sd/np.sqrt(a.size)) if sd>0 else 0.0),
                win=(a>0).mean()*100, tot=a.sum(), sd=sd, sr=(a.mean()/sd if sd>0 else 0.0))

def n_eff_symbols(data):
    """Effective # independent symbols from bar-return correlation matrix (participation ratio)."""
    rets = {}
    for sym, df in data.items():
        rets[sym] = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["time"])).pct_change()
    M = pd.concat(rets, axis=1).dropna(how="any")
    if M.shape[0] < 50 or M.shape[1] < 2:
        return float(len(data)), 0.0
    C = M.corr().to_numpy()
    C = np.nan_to_num(C, nan=0.0, posinf=0.0, neginf=0.0)
    try:
        ev = np.linalg.eigvalsh(C)
    except np.linalg.LinAlgError:
        return float(len(data)), 0.0
    ev = ev[ev > 0]
    if ev.size == 0:
        return float(len(data)), 0.0
    pr = (ev.sum() ** 2) / (np.square(ev).sum())   # participation ratio
    mean_r = (C.sum() - len(C)) / (len(C) * (len(C) - 1))
    return pr, mean_r

def cluster_robust_paired(deltas, times, n_eff, n_sym, seed=20260702, n_boot=5000):
    """Honest significance for a PAIRED per-signal delta series over CORRELATED instruments.

    The naive SHIP gate tests the raw pooled paired t as if every trade were independent —
    with 12 instruments at N_eff~2.6 that overstates significance ~2x. This returns both the
    N_eff-haircut t (raw_t * sqrt(N_eff/N_sym)) and a DAY-clustered block-bootstrap 95% CI on
    the mean delta (whole calendar days resampled together, so intraday cross-symbol correlation
    is respected). `excludes_zero` on the day-clustered CI is the decision-grade significance
    test — use it, not the raw pooled t, to gate a marginal edge.
    """
    d = np.asarray(deltas, float)
    t = pd.to_datetime(np.asarray(times))
    n = d.size
    if n < 10:
        return dict(n=n, raw_t=0.0, haircut_t=0.0, ci_lo=0.0, ci_hi=0.0, excludes_zero=False)
    sd = d.std(ddof=1)
    raw_t = d.mean() / (sd / math.sqrt(n)) if sd > 0 else 0.0
    haircut_t = raw_t * math.sqrt(max(1e-9, n_eff) / n_sym)
    day = t.floor("D").to_numpy()
    days, inv = np.unique(day, return_inverse=True)
    groups = [d[inv == k] for k in range(len(days))]
    rng = np.random.default_rng(seed)
    nd = len(days)
    boots = np.empty(n_boot)
    for it in range(n_boot):
        pick = rng.integers(0, nd, nd)
        boots[it] = np.concatenate([groups[p] for p in pick]).mean()
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return dict(n=n, raw_t=float(raw_t), haircut_t=float(haircut_t),
                ci_lo=float(lo), ci_hi=float(hi), excludes_zero=bool(lo > 0 or hi < 0))


def quarter_signs(data, p, cost):
    """Per-quarter OOS expectancy sign on the pooled trades (sign-stability)."""
    p2 = CParams(**{**p.__dict__, "cost_atr_frac": cost, "block_overlap": True})
    recs=[]
    for sym,df in data.items():
        n=len(df); lo,hi=int(n*0.7),n
        tr,_=simulate_symbol_c(df,p2,lo,hi)
        tt=pd.to_datetime(df["time"]).to_numpy()
        for t in tr: recs.append((tt[t["i"]], t["r"]))
    if not recs: return {}
    s=pd.DataFrame(recs,columns=["t","r"]); s["q"]=pd.PeriodIndex(pd.to_datetime(s["t"]),freq="Q")
    return {str(q):(g.r.mean(),len(g)) for q,g in s.groupby("q")}

def perm_test(baseline_pool, kept_pool, draws=2000):
    """Filters only: is the kept subset's mean beyond random equal-N subsets of baseline?"""
    bp=np.asarray(baseline_pool,float); m=len(kept_pool)
    if m<10 or bp.size<m: return float("nan")
    km=np.mean(kept_pool)
    means=np.array([RNG.choice(bp,m,replace=False).mean() for _ in range(draws)])
    return float((means>=km).mean())   # p: prob random subset beats the filter

# ---------------------------------------------------------------------------
# Candidate definitions  (each = one marginal change vs tp3.0 baseline)
# ---------------------------------------------------------------------------
BASE = dict(tp_atr=3.0)   # continuation, no AVWAP, stop 1.0, default everything

CANDIDATES = [
    # label, kind ('filter'|'geom'), param-overrides
    ("#1 pullback limit off0.3",  "geom",   dict(entry_style="limit", entry_offset_atr=0.3, pending_expiry_bars=3)),
    ("#1 pullback limit off0.6",  "geom",   dict(entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3)),
    ("#2 struct stop",            "geom",   dict(stop_mode="struct")),
    ("#2 wider stop 1.5atr",      "geom",   dict(stop_atr=1.5)),
    ("#1+#2 pull0.3+struct",      "geom",   dict(entry_style="limit", entry_offset_atr=0.3, pending_expiry_bars=3, stop_mode="struct")),
    ("#1+#2 pull0.6+struct",      "geom",   dict(entry_style="limit", entry_offset_atr=0.6, pending_expiry_bars=3, stop_mode="struct")),
    ("#3 ADX>=20 +DIagree",       "filter", dict(adx_min=20.0)),
    ("#3 ADX>=25 +DIagree",       "filter", dict(adx_min=25.0)),
    ("#4 HTF H1 ema50",           "filter", dict(htf_minutes=60, htf_ema=50)),
    ("#4 HTF H4 ema50",           "filter", dict(htf_minutes=240, htf_ema=50)),
    ("#5 ER>=0.3",                "filter", dict(er_min=0.3)),
    ("#5 ER>=0.5",                "filter", dict(er_min=0.5)),
    ("#5 body>=0.5",              "filter", dict(body_frac_min=0.5)),
    ("#6 vol band .2-.8",         "filter", dict(rv_pct_lo=0.2, rv_pct_hi=0.8)),
    ("#6 vol band .3-.9",         "filter", dict(rv_pct_lo=0.3, rv_pct_hi=0.9)),
    ("#7 session 0930-1600 ET",   "filter", dict(sess_start_hm=930, sess_end_hm=1600)),
    ("#7 session 0930-1130 ET",   "filter", dict(sess_start_hm=930, sess_end_hm=1130)),
    ("#9 vol>=1.0x (control)",    "filter", dict(vol_gate_k=1.0)),
    ("#9 vol>=1.2x (control)",    "filter", dict(vol_gate_k=1.2)),
]

def mk(overrides, cost):
    return CParams(**{**BASE, **overrides, "cost_atr_frac": cost})

def main():
    data = B.load_dataset("derivM15")
    pr, mean_r = n_eff_symbols(data)
    haircut = math.sqrt(pr/len(data))     # breadth t-stat haircut
    print(f"REAL DERIV M15: {len(data)} symbols  mean pairwise r={mean_r:.3f}  N_eff(symbols)={pr:.2f}  -> t-haircut x{haircut:.2f}\n")

    # --- baselines ---
    base_oos = {c: pooled_oos(data, mk({}, c), "oos", block=True)[0] for c in (0.0, COST_REAL, COST_STRESS)}
    base_oos_nb = pooled_oos(data, mk({}, COST_REAL), "oos", block=False)[0]   # signal-level for perm test
    base_is = pooled_oos(data, mk({}, COST_REAL), "is", block=True)[0]
    bs = stt(base_oos[COST_REAL])
    print(f"BASELINE tp3.0  OOS  cost0: exp{stt(base_oos[0.0])['exp']:+.4f}  "
          f"cost{COST_REAL}: exp{bs['exp']:+.4f} t{bs['t']:+.2f} N{bs['n']}  "
          f"cost{COST_STRESS}: exp{stt(base_oos[COST_STRESS])['exp']:+.4f}\n")

    # --- evaluate every cell; collect OOS Sharpe for DSR ---
    rows=[]; trial_sr=[]
    for label, kind, ov in CANDIDATES:
        oos = pooled_oos(data, mk(ov, COST_REAL), "oos", block=True)[0]
        iss = pooled_oos(data, mk(ov, COST_REAL), "is", block=True)[0]
        oos0 = pooled_oos(data, mk(ov, 0.0), "oos", block=True)[0]
        oos2 = pooled_oos(data, mk(ov, COST_STRESS), "oos", block=True)[0]
        so, si = stt(oos), stt(iss)
        dExp = so["exp"] - bs["exp"]
        dTot = so["tot"] - bs["tot"]
        wfe = (so["exp"]/si["exp"]) if si["exp"]>0 else (float("nan") if so["exp"]<=0 else float("inf"))
        # permutation (filters): kept subset vs random subsets of baseline non-block
        if kind=="filter":
            kept_nb = pooled_oos(data, mk(ov, COST_REAL), "oos", block=False)[0]
            pperm = perm_test(base_oos_nb, kept_nb)
        else:
            pperm = float("nan")
        # breadth-haircut t and power
        t_hair = so["t"]*haircut
        n_eff_tr = so["n"]*(pr/len(data))
        mde = 1.3*(1.96+0.84)/math.sqrt(max(1,n_eff_tr))
        # quarter sign stability
        qs = quarter_signs(data, mk(ov, COST_REAL), COST_REAL)
        qpos = sum(1 for v in qs.values() if v[0]>0); qn=len(qs)
        # DSR contributions
        trial_sr.append(so["sr"])
        rows.append(dict(label=label, kind=kind, so=so, dExp=dExp, dTot=dTot, wfe=wfe,
                         pperm=pperm, t_hair=t_hair, n_eff_tr=n_eff_tr, mde=mde,
                         exp0=stt(oos0)["exp"], exp2=stt(oos2)["exp"], qpos=qpos, qn=qn,
                         oos_r=oos))

    # --- DSR hurdle from the whole search ---
    sr_arr=np.array([s for s in trial_sr if np.isfinite(s)])
    N=len(sr_arr); var_sr=float(np.var(sr_arr,ddof=1))
    z1=nppf(1-1.0/N); z2=nppf(1-1.0/N*math.exp(-1))
    sr0=math.sqrt(var_sr)*((1-EMC)*z1+EMC*z2)
    print(f"DSR hurdle: searched N={N} cells; expected-max per-obs Sharpe under null = {sr0:.4f}\n")

    # --- table ---
    hdr=(f"{'candidate':30s}{'kind':7s}{'N':>6s}{'exp.02':>8s}{'dExp':>8s}{'dTotR':>8s}"
         f"{'t':>6s}{'t_hc':>6s}{'WFE':>6s}{'perm_p':>7s}{'exp0':>8s}{'exp.04':>8s}{'Qpos':>7s}{'DSR':>6s}  VERDICT")
    print(hdr); print("-"*len(hdr))
    for r in sorted(rows, key=lambda r:-r["dExp"]):
        so=r["so"]; ship=decide(r, sr0)
        wfe = f"{r['wfe']:6.2f}" if np.isfinite(r["wfe"]) else "   nan"
        pp  = f"{r['pperm']:7.3f}" if np.isfinite(r["pperm"]) else "    -- "
        print(f"{r['label']:30s}{r['kind']:7s}{so['n']:6d}{so['exp']:+8.4f}{r['dExp']:+8.4f}{r['dTot']:+8.1f}"
              f"{so['t']:+6.2f}{r['t_hair']:+6.2f}{wfe}{pp}{r['exp0']:+8.4f}{r['exp2']:+8.4f}"
              f"{r['qpos']:4d}/{r['qn']:<2d}{ship['dsr']:6.2f}  {ship['verdict']}")
    print("\nLegend: dExp/dTotR = OOS marginal vs tp3.0 baseline (cost .02); t_hc = breadth-haircut t (x"
          f"{haircut:.2f}); WFE=OOS/IS exp; perm_p=P(random subset>=filter) [filters only];")
    print("  exp0/exp.04 = OOS expectancy frictionless / at 2x-cost stress; Qpos = OOS quarters positive; "
          "DSR>=0.95 + all gates => SHIP.")
    ship_rows=[r for r in rows if decide(r,sr0)["verdict"]=="SHIP"]
    print(f"\n>>> SHIP: {len(ship_rows)} of {len(rows)} candidates."
          + ("" if ship_rows else "  (none cleared the ship gate)"))


def decide(r, sr0):
    so=r["so"]
    dsr = psr(r["oos_r"], sr0)
    gates = [
        r["dExp"]>0,
        (r["pperm"]<0.05) if r["kind"]=="filter" else (r["dExp"]>0 and r["dTot"]>0),
        (np.isfinite(r["wfe"]) and r["wfe"]>=0.3),
        (np.isfinite(dsr) and dsr>=0.95),
        (r["n_eff_tr"]>=250 and so["exp"]>r["mde"]),
        r["exp2"]>0,
        (r["qn"]>0 and r["qpos"]>=math.ceil(r["qn"]*0.6)),
    ]
    verdict = "SHIP" if all(gates) else ("watch" if (r["dExp"]>0 and so["exp"]>0) else "NO-SHIP")
    return dict(verdict=verdict, dsr=(dsr if np.isfinite(dsr) else 0.0))

if __name__ == "__main__":
    main()
