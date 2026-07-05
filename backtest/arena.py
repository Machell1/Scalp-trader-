"""Model arena — competing AI-authored strategy candidates vs the champion.

Multiple AI models each author ONE candidate improvement to the DerivScalper
strategy as a *declarative* parameter file in `arena/candidates/` (see
`arena/README.md` for the contract). Every candidate is executed by the SAME
trusted simulator (`scalper_confluence.simulate_symbol_c`) so nobody can cheat
with custom simulation code.

Anti-overfit protocol (mirrors the repo's HANDOFF bar, adapted to proxy data):
  * DEV split (first 70% of bars) is all a model may see while iterating.
  * The TOURNAMENT is judged only on the HOLDOUT split (last 30%) that no
    model saw during development.
  * The tournament winner then plays a TITLE MATCH against the champion
    (arena/champion.json) with stricter gates: positive marginal expectancy,
    no 2x-cost regression, per-dataset consistency, a sample-size floor,
    monthly sign stability, and a permutation test for filter candidates.
  * Guardrails from HANDOFF.md are enforced mechanically: pullback LIMIT
    entry only, TP >= 3.0 ATR, no AVWAP, bounded parameter ranges.

HONESTY NOTE: this environment has no MT5, so the arena runs on Yahoo proxy
data (yahooM15 60d + yahooH1 730d). Per HANDOFF.md, Yahoo is SCREENING ONLY.
A promoted arena champion is a *staged* config: it must still clear the real
Deriv M15 walk-forward gate (walkforward_dsr.py) before the EA defaults change.

Usage:
  python arena.py --list
  python arena.py --dev [--candidate arena/candidates/foo.py]   # models use this
  python arena.py --tournament                                  # holdout leaderboard
  python arena.py --title-match [--candidate FILE] [--promote]  # winner vs champion
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import math
import os
import sys

import numpy as np
import pandas as pd

import scalper_backtest as B
from scalper_confluence import CParams, simulate_symbol_c

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARENA = os.path.join(ROOT, "arena")
CAND_DIR = os.path.join(ARENA, "candidates")
CHAMPION_JSON = os.path.join(ARENA, "champion.json")
RESULTS_JSON = os.path.join(ARENA, "tournament_results.json")

RNG = np.random.default_rng(20260705)

COST_REAL = 0.02     # realistic per-side cost (fraction of ATR) — repo convention
COST_STRESS = 0.04   # 2x stress

# Yahoo analog of the spread-gated Deriv majors (crypto + index majors only;
# FX/metals/wide-spread names excluded per HANDOFF validated facts).
UNIVERSE = [
    "BTCUSD", "ETHUSD", "XRPUSD", "SOLUSD",
    "NDX", "SPX", "DJI",
    "Germany_40", "UK_100", "Japan_225", "France_40",
]
DATASETS = ["yahooM15", "yahooH1"]
DEV_FRAC = 0.70      # first 70% of bars = DEV; last 30% = HOLDOUT

# ---------------------------------------------------------------------------
# Guardrails (HANDOFF.md, enforced mechanically)
# ---------------------------------------------------------------------------
# key: (min, max) bound, or a set of allowed values, or None = any value of the
# field's type. Keys not listed are NOT settable by candidates.
ALLOWED = {
    # signal
    "momentum_bars":       (3, 12),
    "momentum_atr":        (1.0, 4.0),
    "atr_period":          (7, 28),
    # entry geometry — pullback LIMIT only (HANDOFF fact #1)
    "entry_style":         {"limit"},
    "entry_offset_atr":    (0.2, 1.2),
    "pending_expiry_bars": (1, 6),
    "cancel_beyond_atr":   (0.0, 4.0),
    # exits — TP >= 3.0 (HANDOFF fact #2); 0/negative TP not allowed
    "stop_atr":            (0.5, 2.5),
    "stop_mode":           {"atr", "struct"},
    "tp_atr":              (3.0, 8.0),
    "lock_trigger_atr":    (0.05, 1e9),
    "trail_atr":           (0.0, 3.0),
    "max_hold_bars":       (4, 32),
    "hold_ext_bars":       (0, 48),
    "hold_ext_min_r":      (0.0, 3.0),
    # optional filters (all previously-failed ones stay available — the gates decide)
    "trend_ema":           (0, 400),
    "adx_min":             (0.0, 40.0),
    "adx_period":          (7, 28),
    "require_di_agree":    None,
    "htf_minutes":         {0, 60, 240},
    "htf_ema":             (10, 200),
    "er_min":              (0.0, 0.9),
    "body_frac_min":       (0.0, 0.9),
    "persist_min":         (0, 6),
    "rv_pct_lo":           (0.0, 0.9),
    "rv_pct_hi":           (0.1, 1.0),
    "rv_win":              (8, 96),
    "rv_rank_win":         (200, 4000),
    "sess_start_hm":       (-1, 2359),
    "sess_end_hm":         (-1, 2359),
    "sess_tz":             None,
    "vol_gate_k":          (0.0, 3.0),
    "vol_sma":             (5, 100),
    "long_only":           None,
    "short_only":          None,
}
FORBIDDEN_NOTE = {
    "vwap_window": "AVWAP is a validated overfit (HANDOFF fact #3) — not settable",
    "direction": "fade/reversion is out of scope — continuation only",
    "cost_atr_frac": "cost is runner-controlled",
    "block_overlap": "engine flag is runner-controlled",
}


def validate_overrides(ov: dict) -> list[str]:
    errs = []
    valid_fields = set(CParams.__dataclass_fields__)
    for k, v in ov.items():
        if k in FORBIDDEN_NOTE:
            errs.append(f"{k}: {FORBIDDEN_NOTE[k]}")
            continue
        if k not in valid_fields:
            errs.append(f"{k}: not a CParams field")
            continue
        if k not in ALLOWED:
            errs.append(f"{k}: not candidate-settable")
            continue
        rule = ALLOWED[k]
        if rule is None:
            continue
        if isinstance(rule, set):
            if v not in rule:
                errs.append(f"{k}={v!r}: must be one of {sorted(rule, key=str)}")
        else:
            lo, hi = rule
            try:
                if not (lo <= v <= hi):
                    errs.append(f"{k}={v!r}: out of bounds [{lo}, {hi}]")
            except TypeError:
                errs.append(f"{k}={v!r}: wrong type")
    return errs


# ---------------------------------------------------------------------------
# Candidate + champion loading
# ---------------------------------------------------------------------------
def load_champion() -> dict:
    with open(CHAMPION_JSON) as f:
        return json.load(f)


def load_candidates(paths=None) -> list[dict]:
    files = sorted(paths) if paths else sorted(glob.glob(os.path.join(CAND_DIR, "*.py")))
    out = []
    for f in files:
        ns: dict = {}
        try:
            with open(f) as fh:
                exec(compile(fh.read(), f, "exec"), ns)
        except Exception as e:
            print(f"  LOAD-FAIL {os.path.basename(f)}: {e}")
            continue
        cand = ns.get("CANDIDATE")
        if not isinstance(cand, dict) or "overrides" not in cand:
            print(f"  LOAD-FAIL {os.path.basename(f)}: no CANDIDATE dict with 'overrides'")
            continue
        cand = dict(cand)
        cand.setdefault("name", os.path.splitext(os.path.basename(f))[0])
        cand.setdefault("model", "unknown")
        cand.setdefault("kind", "mixed")   # 'filter' | 'geom' | 'exit' | 'mixed'
        cand["file"] = os.path.relpath(f, ROOT)
        errs = validate_overrides(cand["overrides"])
        if errs:
            print(f"  GUARDRAIL-REJECT {cand['name']} ({cand['file']}):")
            for e in errs:
                print(f"      - {e}")
            continue
        out.append(cand)
    return out


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------
_DATA_CACHE: dict = {}


def get_data(ds: str) -> dict:
    if ds not in _DATA_CACHE:
        raw = B.load_dataset(ds)
        _DATA_CACHE[ds] = {s: df for s, df in raw.items() if s in UNIVERSE}
    return _DATA_CACHE[ds]


def mk_params(overrides: dict, cost: float, block=True) -> CParams:
    return CParams(**{**overrides, "cost_atr_frac": cost, "block_overlap": block})


def run_split(ds: str, overrides: dict, split: str, cost: float, block=True):
    """Return (pooled R array, {sym: trade list}, {(sym, signal_i): r})."""
    data = get_data(ds)
    p = mk_params(overrides, cost, block)
    per, keyed = {}, {}
    for sym, df in data.items():
        n = len(df)
        if split == "dev":
            lo, hi = 0, int(n * DEV_FRAC)
        elif split == "holdout":
            lo, hi = int(n * DEV_FRAC), n
        else:
            lo, hi = 0, n
        trades, _ = simulate_symbol_c(df, p, lo, hi)
        per[sym] = trades
        for t in trades:
            keyed[(sym, t["i"])] = t["r"]
    pool = np.array([t["r"] for trs in per.values() for t in trs], float)
    return pool, per, keyed


def stt(a) -> dict:
    a = np.asarray(a, float)
    if a.size == 0:
        return dict(n=0, exp=0.0, t=0.0, win=0.0, tot=0.0, pf=0.0)
    sd = a.std(ddof=1) if a.size > 1 else 0.0
    pos = a[a > 0].sum(); neg = -a[a < 0].sum()
    return dict(n=int(a.size), exp=float(a.mean()), sd=float(sd),
                t=float(a.mean() / (sd / np.sqrt(a.size))) if sd > 0 else 0.0,
                win=float((a > 0).mean() * 100), tot=float(a.sum()),
                pf=float(pos / neg) if neg > 0 else float("inf"))


def monthly_sign_frac(ds: str, overrides: dict, split: str, cost: float):
    """Fraction of calendar months with positive pooled expectancy on the split."""
    data = get_data(ds)
    p = mk_params(overrides, cost, True)
    recs = []
    for sym, df in data.items():
        n = len(df)
        lo, hi = (int(n * DEV_FRAC), n) if split == "holdout" else (0, int(n * DEV_FRAC))
        trades, _ = simulate_symbol_c(df, p, lo, hi)
        tt = pd.to_datetime(df["time"]).to_numpy()
        for t in trades:
            recs.append((tt[t["i"]], t["r"]))
    if not recs:
        return float("nan"), 0
    s = pd.DataFrame(recs, columns=["t", "r"])
    s["m"] = pd.PeriodIndex(pd.to_datetime(s["t"]), freq="M")
    g = s.groupby("m")["r"].mean()
    return float((g > 0).mean()), int(len(g))


def evaluate(overrides: dict, split: str) -> dict:
    """Full metric block for one config on one split, both datasets + combined."""
    out = {"datasets": {}}
    pools_real, pools_2x = [], []
    for ds in DATASETS:
        pr, per, _ = run_split(ds, overrides, split, COST_REAL)
        p0, _, _ = run_split(ds, overrides, split, 0.0)
        p2, _, _ = run_split(ds, overrides, split, COST_STRESS)
        sym_pos = [s for s, trs in per.items() if trs and np.mean([t["r"] for t in trs]) > 0]
        sym_traded = [s for s, trs in per.items() if trs]
        mfrac, mn = monthly_sign_frac(ds, overrides, split, COST_REAL)
        out["datasets"][ds] = dict(
            real=stt(pr), free=stt(p0), stress=stt(p2),
            sym_pos=len(sym_pos), sym_traded=len(sym_traded),
            month_pos_frac=mfrac, months=mn,
        )
        pools_real.append(pr); pools_2x.append(p2)
    cr = np.concatenate(pools_real) if pools_real else np.array([])
    c2 = np.concatenate(pools_2x) if pools_2x else np.array([])
    out["combined"] = dict(real=stt(cr), stress=stt(c2))
    return out


def perm_test(champ_pool, kept_pool, draws=3000):
    """P(random same-N subset of champion signal-level pool >= candidate mean)."""
    bp = np.asarray(champ_pool, float); m = len(kept_pool)
    if m < 10 or bp.size < m:
        return float("nan")
    km = float(np.mean(kept_pool))
    means = np.array([RNG.choice(bp, m, replace=False).mean() for _ in range(draws)])
    return float((means >= km).mean())


def paired_delta(overrides_a: dict, overrides_b: dict, split: str):
    """Paired per-signal delta (a - b) on entries common to both configs (combined datasets).
    Only meaningful when entry population overlaps (exit-only changes)."""
    diffs = []
    common = total_a = 0
    for ds in DATASETS:
        _, _, ka = run_split(ds, overrides_a, split, COST_REAL)
        _, _, kb = run_split(ds, overrides_b, split, COST_REAL)
        keys = set(ka) & set(kb)
        common += len(keys); total_a += len(ka)
        diffs.extend(ka[k] - kb[k] for k in keys)
    overlap = common / total_a if total_a else 0.0
    d = np.asarray(diffs, float)
    if d.size < 10:
        return dict(overlap=overlap, n=int(d.size), mean=float("nan"), t=float("nan"))
    sd = d.std(ddof=1)
    return dict(overlap=overlap, n=int(d.size), mean=float(d.mean()),
                t=float(d.mean() / (sd / np.sqrt(d.size))) if sd > 0 else 0.0)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def fmt_row(name, model, ev, extra=""):
    c = ev["combined"]["real"]; c2 = ev["combined"]["stress"]
    m15 = ev["datasets"].get("yahooM15", {}).get("real", dict(exp=float("nan"), n=0))
    h1 = ev["datasets"].get("yahooH1", {}).get("real", dict(exp=float("nan"), n=0))
    return (f"{name[:34]:34s}{model[:22]:22s}{c['n']:6d}{c['exp']:+9.4f}{c['t']:+7.2f}"
            f"{c2['exp']:+9.4f}{m15['exp']:+9.4f}{h1['exp']:+9.4f}  {extra}")


HDR = (f"{'candidate':34s}{'model':22s}{'N':>6s}{'exp@.02':>9s}{'t':>7s}"
       f"{'exp@.04':>9s}{'M15':>9s}{'H1':>9s}")


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
def mode_list():
    champ = load_champion()
    print(f"CHAMPION: {champ['name']}  (model: {champ['model']}, since {champ['since']})")
    print(f"  overrides: {champ['overrides']}\n")
    cands = load_candidates()
    if not cands:
        print("No candidates in arena/candidates/.")
    for c in cands:
        print(f"  {c['name']:34s} model={c['model']:24s} kind={c['kind']:8s} {c['file']}")


def mode_dev(paths):
    """DEV-split evaluation — the only view models get while iterating."""
    champ = load_champion()
    cands = load_candidates(paths)
    print(f"=== DEV SPLIT (first {DEV_FRAC:.0%} of bars) — universe: {len(UNIVERSE)} majors, "
          f"datasets: {', '.join(DATASETS)}, cost {COST_REAL}/side (stress {COST_STRESS}) ===\n")
    ev_ch = evaluate(champ["overrides"], "dev")
    print(HDR); print("-" * len(HDR))
    print(fmt_row("CHAMPION: " + champ["name"], champ["model"], ev_ch))
    base = ev_ch["combined"]["real"]["exp"]
    for c in cands:
        ev = evaluate(c["overrides"], "dev")
        d = ev["combined"]["real"]["exp"] - base
        print(fmt_row(c["name"], c["model"], ev, extra=f"dExp={d:+.4f}"))
    print("\nNOTE: holdout results are hidden until --tournament. Do not overfit dev.")


def mode_tournament():
    champ = load_champion()
    cands = load_candidates()
    if not cands:
        print("No candidates — nothing to run.")
        return
    print(f"=== TOURNAMENT — HOLDOUT split (last {1-DEV_FRAC:.0%} of bars), "
          f"cost {COST_REAL}/side ===\n")
    ev_ch = evaluate(champ["overrides"], "holdout")
    ch_n = ev_ch["combined"]["real"]["n"]
    rows = []
    for c in cands:
        ev = evaluate(c["overrides"], "holdout")
        comb = ev["combined"]["real"]
        elig, why = True, []
        if comb["n"] < 150:
            elig, why = False, why + [f"N={comb['n']}<150"]
        for ds in DATASETS:
            ch_exp = ev_ch["datasets"][ds]["real"]["exp"]
            if ev["datasets"][ds]["real"]["exp"] < ch_exp - 0.05:
                elig = False
                why.append(f"{ds} exp more than 0.05R below champion")
        rows.append(dict(cand=c, ev=ev, score=comb["exp"], t=comb["t"],
                         eligible=elig, why=";".join(why)))
    rows.sort(key=lambda r: (-int(r["eligible"]), -r["score"], -r["t"]))

    print(HDR + "  status"); print("-" * (len(HDR) + 8))
    print(fmt_row("CHAMPION: " + champ["name"], champ["model"], ev_ch, extra="(reference)"))
    for r in rows:
        status = "ELIGIBLE" if r["eligible"] else f"OUT ({r['why']})"
        print(fmt_row(r["cand"]["name"], r["cand"]["model"], r["ev"], extra=status))

    eligible = [r for r in rows if r["eligible"]]
    winner = eligible[0] if eligible else None
    result = dict(
        run_at=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        champion=dict(name=champ["name"], holdout=ev_ch),
        leaderboard=[dict(name=r["cand"]["name"], model=r["cand"]["model"],
                          file=r["cand"]["file"], kind=r["cand"]["kind"],
                          score=r["score"], t=r["t"], eligible=r["eligible"],
                          why=r["why"], holdout=r["ev"]) for r in rows],
        winner=(winner["cand"]["file"] if winner else None),
    )
    with open(RESULTS_JSON, "w") as f:
        json.dump(result, f, indent=2, default=float)
    print(f"\nResults written to {os.path.relpath(RESULTS_JSON, ROOT)}")
    if winner:
        w = winner["cand"]
        print(f"\n>>> TOURNAMENT WINNER: {w['name']} (model {w['model']}) "
              f"— advances to the title match vs the champion.")
    else:
        print("\n>>> No eligible candidate. Champion retains by default.")


def mode_title(path, promote):
    champ = load_champion()
    if path is None:
        if not os.path.exists(RESULTS_JSON):
            print("No tournament results — run --tournament first (or pass --candidate).")
            return
        with open(RESULTS_JSON) as f:
            res = json.load(f)
        if not res.get("winner"):
            print("Tournament produced no eligible winner — champion retains.")
            return
        path = os.path.join(ROOT, res["winner"])
    cands = load_candidates([path])
    if not cands:
        print("Challenger failed to load / guardrails.")
        return
    chal = cands[0]

    print(f"=== TITLE MATCH (holdout) ===\nCHAMPION : {champ['name']}  ({champ['model']})")
    print(f"CHALLENGER: {chal['name']}  ({chal['model']}, kind={chal['kind']})\n")

    ev_ch = evaluate(champ["overrides"], "holdout")
    ev_cl = evaluate(chal["overrides"], "holdout")
    print(HDR); print("-" * len(HDR))
    print(fmt_row("CHAMPION: " + champ["name"], champ["model"], ev_ch))
    print(fmt_row("CHALLENGER: " + chal["name"], chal["model"], ev_cl))

    cch, ccl = ev_ch["combined"], ev_cl["combined"]
    d_real = ccl["real"]["exp"] - cch["real"]["exp"]
    d_2x = ccl["stress"]["exp"] - cch["stress"]["exp"]

    pd_ = paired_delta(chal["overrides"], champ["overrides"], "holdout")
    print(f"\npaired per-signal delta (common entries, {pd_['overlap']:.0%} overlap, "
          f"N={pd_['n']}): mean={pd_['mean']:+.4f} t={pd_['t']:+.2f}"
          if np.isfinite(pd_.get("mean", float("nan")))
          else f"\npaired delta: insufficient entry overlap ({pd_['overlap']:.0%}) — pooled comparison only")

    # permutation test for filter-kind challengers (does it SELECT good trades?)
    pperm = float("nan")
    if chal["kind"] == "filter":
        ch_pools, cl_pools = [], []
        for ds in DATASETS:
            ch_pools.append(run_split(ds, champ["overrides"], "holdout", COST_REAL, block=False)[0])
            cl_pools.append(run_split(ds, chal["overrides"], "holdout", COST_REAL, block=False)[0])
        pperm = perm_test(np.concatenate(ch_pools), np.concatenate(cl_pools))
        print(f"permutation test (filter): p(random subset >= challenger) = {pperm:.3f}")

    h1_months = ev_cl["datasets"]["yahooH1"]["month_pos_frac"]

    def _se_diff(ds):
        """1 standard error of the expectancy difference on this dataset."""
        s_ch, s_cl = ev_ch["datasets"][ds]["real"], ev_cl["datasets"][ds]["real"]
        if s_ch["n"] < 2 or s_cl["n"] < 2:
            return float("inf")
        return math.sqrt(s_ch["sd"] ** 2 / s_ch["n"] + s_cl["sd"] ** 2 / s_cl["n"])

    # noise-aware: challenger may not lag champion by more than 1 SE (min 0.005 R)
    per_ds = {ds: (ev_cl["datasets"][ds]["real"]["exp"]
                   - ev_ch["datasets"][ds]["real"]["exp"],
                   max(0.005, _se_diff(ds))) for ds in DATASETS}
    per_ds_ok = all(d >= -tol for d, tol in per_ds.values())
    per_ds_txt = ", ".join(f"{ds} d={d:+.4f} (tol {tol:.3f})"
                           for ds, (d, tol) in per_ds.items())
    gates = [
        ("marginal OOS expectancy > champion", d_real > 0,
         f"d={d_real:+.4f}"),
        ("no 2x-cost regression", d_2x >= -0.002,
         f"d2x={d_2x:+.4f}"),
        ("consistent across both datasets (within noise)", per_ds_ok, per_ds_txt),
        ("sample floor (N >= max(150, 50% of champion))",
         ccl["real"]["n"] >= max(150, int(0.5 * cch["real"]["n"])),
         f"N={ccl['real']['n']} vs champion {cch['real']['n']}"),
        ("monthly sign stability (H1 holdout >= 50% months positive)",
         np.isfinite(h1_months) and h1_months >= 0.5,
         f"{h1_months:.0%} of {ev_cl['datasets']['yahooH1']['months']} months"),
    ]
    if chal["kind"] == "filter":
        gates.append(("permutation p < 0.10 (selects, not just prunes)",
                      np.isfinite(pperm) and pperm < 0.10, f"p={pperm:.3f}"))

    print("\nGATES:")
    ok = True
    for name, passed, detail in gates:
        ok &= bool(passed)
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  ({detail})")

    if not ok:
        print(f"\n>>> CHAMPION RETAINS. {chal['name']} did not clear the gates.")
        return

    print(f"\n>>> CHALLENGER WINS: {chal['name']} beats the champion on the holdout.")
    if not promote:
        print("    (dry run — rerun with --promote to update arena/champion.json)")
        return

    old = dict(name=champ["name"], model=champ["model"], since=champ["since"],
               overrides=champ["overrides"],
               dethroned=_dt.date.today().isoformat())
    new = dict(
        name=chal["name"], model=chal["model"],
        since=_dt.date.today().isoformat(),
        description=chal.get("description", ""),
        overrides={**champ["overrides"], **chal["overrides"]},
        history=[old] + champ.get("history", []),
        pending_validation="PROMOTED ON YAHOO PROXY DATA — must clear the real-Deriv "
                           "M15 walk-forward gate (walkforward_dsr.py, HANDOFF.md) "
                           "before the EA defaults change.",
    )
    with open(CHAMPION_JSON, "w") as f:
        json.dump(new, f, indent=2)
    print(f"    PROMOTED. arena/champion.json updated "
          f"(old champion archived in history). Real-Deriv validation still required "
          f"before touching mql5/DerivScalperEA.mq5 defaults.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--tournament", action="store_true")
    ap.add_argument("--title-match", action="store_true")
    ap.add_argument("--candidate", action="append", help="candidate file path(s)")
    ap.add_argument("--promote", action="store_true")
    args = ap.parse_args()
    if args.list:
        mode_list()
    elif args.dev:
        mode_dev(args.candidate)
    elif args.tournament:
        mode_tournament()
    elif args.title_match:
        mode_title(args.candidate[0] if args.candidate else None, args.promote)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
