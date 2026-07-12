"""Corrected census under live-parity enumeration.

Pre-registered: docs/W2_PARITY_SPEC_2026-07-12.md
  (SHA256 03b9967a8eba3d0e366f78a62fb2b156f59a06d19b47e90570fce13cb1cc9a90)

Columns per config {W2x3, W3x4}:
  control  -- legacy method verbatim (nearmiss_decisions.wick_trades tapes);
              MUST reproduce the documented numbers before anything else counts
  M1       -- live-parity per-symbol (pre-entry W2 + pending occupancy)
  M2       -- + portfolio coupling (global 2 / cluster 1 / day gates), whitelist order
  M2-rev   -- M2 with reversed scan order (intra-epoch ordering sensitivity)
Arms: M2q frozen queue (Codex idea 3), M3 mixed sleeve (idea 2, CONTAMINATED),
W3x4 global-cap=3 sensitivity.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from walkforward_dsr import real_cost_per_side, dsr_hurdle
from prop_mc_scalper import challenge
from experiment import psr
from nearmiss_decisions import wick_trades, daylist, challenge_mc
from parity_engine import prep_symbol, run_live

N_TRIALS = 150   # cumulative ledger after this spec's 4 cells

SPREAD_DIR = os.path.join(HERE, "data", "derivM15_spreadgated")
TRIO = [("Wall_Street_30", 0), ("US_Tech_100", 0), ("Japan_225", 1)]
GER = ("Germany_40", 2)


def load_sym(key, cluster):
    raw = pd.read_csv(os.path.join(SPREAD_DIR, key + ".csv"))
    cost = real_cost_per_side(raw)
    s = prep_symbol(raw, cost, key, cluster)
    dt = pd.to_datetime(raw[[c for c in raw.columns if c.lower() == "time"][0]])
    q = pd.PeriodIndex(dt, freq="Q")
    qs = sorted(q.unique())
    oos_qs = set(qs[int(len(qs) * 0.7):])
    return s, q, oos_qs


def tape_stats(trades, qinfo, label, mc=True):
    """trades: list of Trade. qinfo: dict sym -> (q PeriodIndex, oos set)."""
    if not trades:
        print(f"  {label}: EMPTY tape")
        return None
    r = np.array([t.r for t in trades])
    r2 = np.array([t.r - 2.0 * t.cost for t in trades])
    oos_mask = np.array([qinfo[t.sym][0][t.sig] in qinfo[t.sym][1] for t in trades])
    ro, r2o = r[oos_mask], r2[oos_mask]
    out = dict(n=len(r), exp=r.mean(), win=(r > 0).mean(),
               n_oos=int(oos_mask.sum()),
               oos=ro.mean() if len(ro) else np.nan,
               oos2x=r2o.mean() if len(r2o) else np.nan,
               dsr=psr(ro, dsr_hurdle(n_trials=N_TRIALS, n_obs=ro.size)) if ro.size > 10 else np.nan)
    if mc:
        tape = sorted((int(t.ep_sig), float(t.r)) for t in trades)
        both, bust, med = challenge_mc(daylist(tape))
        fund, fdays = timeline_mc(daylist(tape))
        out.update(both=both, bust=bust, med=med, funded=fund, fdays=fdays)
    print(f"  {label}: n={out['n']:5d} exp={out['exp']:+.4f} win={out['win']:.1%} "
          f"| OOS n={out['n_oos']} exp={out['oos']:+.4f} 2x={out['oos2x']:+.4f} DSR={out['dsr']:.3f}"
          + (f" | MC both={out['both']:.1%} bust={out['bust']:.1%} medP1={out['med']}d"
             f" | funded={out['funded']:.1%} med={out['fdays']}d" if mc else ""))
    return out


def timeline_mc(dl, nsim=8000, risk=0.3):
    rng = np.random.default_rng(7)
    funded, days = 0, []
    for _ in range(nsim):
        s1, d1 = challenge(dl, rng, risk, 10.0, 365)
        if s1 != 1:
            continue
        s2, d2 = challenge(dl, rng, risk, 5.0, 365)
        if s2 == 1:
            funded += 1
            days.append(d1 + d2)
    return funded / nsim, (int(np.median(days)) if days else -1)


def legacy_control(files_thr, label, expect=None):
    tape = []
    for fn, thr in files_thr:
        tape += wick_trades(fn, thr)
    both, bust, med = challenge_mc(daylist(tape))
    fund, fdays = timeline_mc(daylist(tape))
    r = np.array([x[1] for x in tape])
    print(f"  {label} (legacy): n={len(tape)} exp={r.mean():+.4f} | MC both={both:.1%} "
          f"bust={bust:.1%} medP1={med}d | funded={fund:.1%} med={fdays}d")
    if expect is not None:
        eb, ebu, em = expect
        ok = abs(both - eb) < 0.002 and abs(bust - ebu) < 0.002 and med == em
        print(f"    reproduction vs documented ({eb:.1%}/{ebu:.1%}/{em}d): {'PASS' if ok else 'FAIL'}")
        if not ok:
            print("    PIPELINE BROKEN per spec -- stopping.")
            sys.exit(1)
    return tape, (both, bust, med, fund, fdays)


def trade_key(t):
    return (t.sym, t.sig, t.entry_bar)


def main():
    caps = dict(fills_day=8, consec=4, cluster=1)
    caps["global"] = 2

    print("=" * 100)
    print("LOAD")
    syms3, qinfo = [], {}
    for key, cl in TRIO:
        s, q, oq = load_sym(key, cl)
        syms3.append(s)
        qinfo[key] = (q, oq)
        print(f"  {key}: {len(s.c)} bars, cost/side {s.cost:.4f} ATR, cluster {cl}")
    sger, qg, oqg = load_sym(*GER)
    qinfo[GER[0]] = (qg, oqg)
    syms4 = syms3 + [sger]
    print(f"  {GER[0]}: {len(sger.c)} bars, cost/side {sger.cost:.4f} ATR, cluster {GER[1]}")

    for cfg_name, syms, thr_val, expect in (
            ("W2x3", syms3, 0.30, (0.874, 0.068, 52)),
            ("W3x4", syms4, 0.50, None)):
        print("\n" + "=" * 100)
        print(f"CONFIG {cfg_name} (wick >= {thr_val})")
        thr = {s.name: thr_val for s in syms}

        files_thr = [(s.name + ".csv", thr_val) for s in syms]
        legacy_control(files_thr, f"{cfg_name} control", expect)

        for W in (4, 3):
            tag = "as-deployed w=4" if W == 4 else "post-fix w=3"
            print(f"  --- window {W} ({tag}) ---")
            m1 = []
            for s in syms:
                tr, _ = run_live([s], thr={s.name: thr_val}, caps=None, window=W)
                m1 += tr
            tape_stats(m1, qinfo, f"{cfg_name} w{W} M1 per-symbol")

            m2, cen = run_live(syms, thr=thr, caps=caps, window=W)
            tape_stats(m2, qinfo, f"{cfg_name} w{W} M2 coupled")
            print(f"    M2 drop census: occupied={cen.occupied} cooldown={cen.cooldown} "
                  f"w2_fail={cen.w2_fail} cap_global={cen.cap_global} "
                  f"cap_cluster={cen.cap_cluster} day_fills={cen.day_fills} "
                  f"day_consec={cen.day_consec}")

            if W == 4:
                m2r, _ = run_live(syms, thr=thr, caps=caps, window=W, reverse_scan=True)
                tape_stats(m2r, qinfo, f"{cfg_name} w{W} M2 reversed-order")

                m2q, cenq = run_live(syms, thr=thr, caps=caps, window=W, queue=True)
                base_keys = {trade_key(t) for t in m2}
                q_keys = {trade_key(t) for t in m2q}
                added = [t for t in m2q if trade_key(t) not in base_keys]
                released = [t for t in m2q if t.queued]
                tape_stats(m2q, qinfo, f"{cfg_name} w{W} M2q queue")
                print(f"    queue census: stashed={cenq.q_stashed} released={cenq.q_released} "
                      f"expired={cenq.q_expired} stale={cenq.q_stale} replaced={cenq.q_replaced}")
                print(f"    vs M2: kept={len(base_keys & q_keys)} LOST={len(base_keys - q_keys)} "
                      f"added={len(added)} (released={len(released)})")
                if added:
                    ar = np.array([t.r for t in added])
                    ao = np.array([t.r for t in added
                                   if qinfo[t.sym][0][t.sig] in qinfo[t.sym][1]])
                    print(f"    added trades: n={len(ar)} exp={ar.mean():+.4f} "
                          f"| OOS n={len(ao)} exp={(ao.mean() if len(ao) else float('nan')):+.4f}")

            # exploratory, implementable recovery arm: newest-signal-wins replacement
            mrep, _ = run_live(syms, thr=thr, caps=caps, window=W, replace_on_signal=True)
            tape_stats(mrep, qinfo, f"{cfg_name} w{W} M2-REPLACE (exploratory)")

    # --- W3x4 global-cap sensitivity (cap=3 needs an input edit live) ---
    print("\n" + "=" * 100)
    print("W3x4 SENSITIVITY: global cap 3 at w=4 (would require InpMaxConcurrent edit)")
    thr4 = {s.name: 0.50 for s in syms4}
    caps3 = dict(caps)
    caps3["global"] = 3
    m2c3, _ = run_live(syms4, thr=thr4, caps=caps3, window=4)
    tape_stats(m2c3, qinfo, "W3x4 w4 M2 cap=3")

    # --- M3 mixed sleeve (Codex idea 2) -- CONTAMINATED, decision analysis only ---
    print("\n" + "=" * 100)
    print("M3 MIXED SLEEVE trio@0.30 + GER40@0.50 at w=4 -- CONTAMINATED (GER40-W3 "
          "selected on this data); decision analysis only, can never ship from this frame")
    thr_mix = {s.name: 0.30 for s in syms3}
    thr_mix[GER[0]] = 0.50
    m3, _ = run_live(syms4, thr=thr_mix, caps=caps, window=4)
    tape_stats(m3, qinfo, "M3 mixed sleeve w4")

    # persist the headline corrected tape for the verification pass
    m2_w2, _ = run_live(syms3, thr={s.name: 0.30 for s in syms3}, caps=caps, window=4)
    pd.DataFrame([(t.sym, t.sig, t.entry_bar, t.exit_bar, t.side, t.r, t.reason, t.ep_sig)
                  for t in m2_w2],
                 columns=["sym", "sig", "entry_bar", "exit_bar", "side", "r", "reason",
                          "ep_sig"]).to_csv(os.path.join(HERE, "parity_w2x3_m2.csv"),
                                            index=False)
    print("\nDone. Headline tape written to parity_w2x3_m2.csv (w=4 M2)")


if __name__ == "__main__":
    main()
