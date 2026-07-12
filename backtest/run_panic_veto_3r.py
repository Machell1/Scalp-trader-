"""Run the preregistered panic-rebound veto 3R study."""
from __future__ import annotations

import hashlib, json, os, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = ROOT / "docs" / "PANIC_REBOUND_VETO_3R_SPEC_2026-07-12.md"
PROTOCOL_SHA256 = "239f3889bb36fd0dfcc46ee3376f55b86b48c1d1375c2b3be695b3f892a25467"
RESULT = HERE / "panic_veto_3r_results.json"
BUFFER = 0.02
sys.path.insert(0, str(HERE))

from panic_rebound_veto_3r import admit_unless_panic_rebound, self_test
from parity_engine import prep_symbol
from retest_engine import SPREAD_DIR, TRIO
from retest_fillrealism import run
from walkforward_dsr import real_cost_per_side

HASHES = {
 ("Wall_Street_30",0.00):(1279,"5f3046b10d91c11632391ccad4a88eaf4029dd392303e8457c9c5838900b64d2"),
 ("Wall_Street_30",0.02):(1256,"63c2dfdef6ed6d839f77ddecf111582de1e54e4ca6774c88f2d4f7a9a0c6ec4b"),
 ("Wall_Street_30",0.05):(1228,"83cb337253466d36462224f50b5a6fcfea280d47572b60fac83bc5fb5c2b90f1"),
 ("US_Tech_100",0.00):(1232,"d1ad13795d5b83cdde3db6dd45ec81ca7bf8640756173f6d920f58a5d717c206"),
 ("US_Tech_100",0.02):(1206,"c8d0c24aa5fd6fc571b1b17937aade8e4553db44f9d0f3cc57b6ff39a48a8346"),
 ("US_Tech_100",0.05):(1178,"29f854d72945b39c89aae7640715288f4d117fc634d2857799c8de3e44698520"),
 ("Japan_225",0.00):(1153,"407314b9c2ebe5379ec275c129d82d28b338f2f66b47e5891ca289eb782390f5"),
 ("Japan_225",0.02):(1131,"a05673b0553894f5abfee74147e2bd06a0063a9503622cb5e83e4c56174d775c"),
 ("Japan_225",0.05):(1111,"7a0734beb906bdd00b88734ecff54fba46757c8dd7517aac7f98c50098adfe8b"),
}


def verify_protocol():
    raw=subprocess.check_output(["git","show",f"HEAD:{SPEC.relative_to(ROOT).as_posix()}"],cwd=ROOT)
    lines=raw.splitlines(True); end=next(i for i,x in enumerate(lines) if x.startswith(b"**PRE-REGISTRATION ENDS"))
    actual=hashlib.sha256(b"".join(lines[:end+1])).hexdigest()
    if actual != PROTOCOL_SHA256: raise RuntimeError(f"protocol hash mismatch: {actual}")
    return actual


def clean_commit():
    paths=("docs/PANIC_REBOUND_VETO_3R_SPEC_2026-07-12.md","backtest/retest_fillrealism.py",
           "backtest/panic_rebound_veto_3r.py","backtest/run_panic_veto_3r.py",
           "backtest/parity_engine.py","backtest/retest_engine.py","backtest/walkforward_dsr.py")
    dirty=subprocess.check_output(["git","status","--porcelain","--",*paths],cwd=ROOT,text=True).strip()
    if dirty: raise RuntimeError(f"dirty registered dependency:\n{dirty}")
    for p in paths: subprocess.check_call(["git","cat-file","-e",f"HEAD:{p}"],cwd=ROOT)
    return subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()


def summary(rows):
    x=np.asarray([r["r"] for r in rows],float)
    return {"n":len(x),"win_rate":float(np.mean(x>0)) if len(x) else None,
            "expectancy_r":float(np.mean(x)) if len(x) else None,"total_r":float(np.sum(x))}


def main():
    if RESULT.exists(): raise RuntimeError(f"refusing to overwrite {RESULT}")
    protocol=verify_protocol(); commit=clean_commit()
    print(f"verified panic-veto protocol SHA256 {protocol}",flush=True)
    subprocess.check_call([sys.executable,str(HERE/"verify_data.py")],cwd=ROOT); self_test()
    data={}; oosq={}; complete={}
    for sym in TRIO:
        raw=pd.read_csv(os.path.join(SPREAD_DIR,sym+".csv")); tc=next(c for c in raw if c.lower()=="time")
        times=pd.to_datetime(raw[tc],utc=True); qs=pd.PeriodIndex(times.dt.tz_convert(None),freq="Q")
        ordered=sorted(set(map(str,qs))); oosq[sym]=set(ordered[int(len(ordered)*.7):])
        lo,hi=times.min().tz_convert(None),times.max().tz_convert(None)
        complete[sym]={q for q in oosq[sym] if lo<=pd.Period(q,freq="Q").start_time and hi>=pd.Period(q,freq="Q").end_time.floor("min")}
        data[sym]=prep_symbol(raw,real_cost_per_side(raw),sym)
    regression={}
    for sym,s in data.items():
        for buf in (0.,.02,.05):
            rows=run(s,3.,0.,0.,buf); raw=json.dumps(rows,separators=(",",":")).encode(); h=hashlib.sha256(raw).hexdigest(); en,eh=HASHES[(sym,buf)]
            ok=len(rows)==en and h==eh; regression[f"{sym}@{buf:.2f}"]={"n":len(rows),"sha256":h,"passed":ok}
            if not ok: raise RuntimeError(f"default regression mismatch {sym}@{buf:.2f}")
    print("default-mode regression: 9 identical, 0 failed",flush=True)
    tapes={"C0_PASSIVE_3R":[],"P1_PANIC_REBOUND_VETO_3R":[]}; diagnostics={}
    for sym,s in data.items():
        c0=run(s,3.,0.,0.,BUFFER); p1,diag=run(s,3.,0.,0.,BUFFER,pre_entry=admit_unless_panic_rebound,return_diag=True); diagnostics[sym]=diag
        for name,rows in (("C0_PASSIVE_3R",c0),("P1_PANIC_REBOUND_VETO_3R",p1)):
            for ep,r in rows:
                q=str(pd.Timestamp(ep,unit="s",tz="UTC").tz_localize(None).to_period("Q")); tapes[name].append({"symbol":sym,"epoch":int(ep),"quarter":q,"r":float(r)})
    results={}
    for name,rows in tapes.items():
        oo=[r for r in rows if r["quarter"] in oosq[r["symbol"]]]
        results[name]={"all":summary(rows),"stitched_oos":summary(oo),
          "stitched_oos_by_symbol":{s:summary([r for r in oo if r["symbol"]==s]) for s in TRIO},
          "stitched_oos_by_quarter":{q:summary([r for r in oo if r["quarter"]==q]) for q in sorted({r["quarter"] for r in oo})}}
    c0=results["C0_PASSIVE_3R"]["stitched_oos"]; p1=results["P1_PANIC_REBOUND_VETO_3R"]["stitched_oos"]; cq=sorted(set.intersection(*[complete[s] for s in TRIO]))
    gates={"oos_win_rate_lift_at_least_5pp":p1["win_rate"]>=c0["win_rate"]+.05,
      "oos_expectancy_positive":p1["expectancy_r"]>0,"oos_expectancy_not_below_control":p1["expectancy_r"]>=c0["expectancy_r"],
      "every_symbol_oos_expectancy_positive":all(results["P1_PANIC_REBOUND_VETO_3R"]["stitched_oos_by_symbol"][s]["expectancy_r"]>0 for s in TRIO),
      "every_complete_oos_quarter_positive":all(results["P1_PANIC_REBOUND_VETO_3R"]["stitched_oos_by_quarter"][q]["expectancy_r"]>0 for q in cq),
      "oos_trade_retention_at_least_35pct":p1["n"]>=.35*c0["n"],"default_regression_and_synthetic_pass":all(x["passed"] for x in regression.values())}
    total={k:sum(d[k] for d in diagnostics.values()) for k in next(iter(diagnostics.values()))}; total["veto_rate"]=total["vetoed"]/total["frozen_signals"]
    out={"protocol_sha256":protocol,"commit":commit,"ledger":{"working_start":214,"working_end":215,"charged_cells":1},"regression":regression,
      "complete_pooled_oos_quarters":cq,"results":results,"panic_diagnostics_all":total,"panic_diagnostics_by_symbol_all":diagnostics,
      "candidate_minus_control_oos":{"n":p1["n"]-c0["n"],"retention":p1["n"]/c0["n"],"win_rate":p1["win_rate"]-c0["win_rate"],"expectancy_r":p1["expectancy_r"]-c0["expectancy_r"],"total_r":p1["total_r"]-c0["total_r"]},
      "win_rate_above_80pct_diagnostic":p1["win_rate"]>.8,"gates":gates,"verdict":"ADVANCE" if all(gates.values()) else "DISPOSE",
      "confirmation_accessed":False,"blind_holdout_accessed":False,"ftmo_mc_paths":0,"terminal_writes":0}
    RESULT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n"); print(json.dumps(out,indent=2,sort_keys=True),flush=True); print(f"RESULT_FILE={RESULT}")


if __name__=="__main__": main()
