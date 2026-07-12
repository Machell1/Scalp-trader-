"""Run the preregistered first-touch pullback stop-confirmation study."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
SPEC=ROOT/"docs"/"PULLBACK_STOP_CONFIRM_3R_SPEC_2026-07-12.md"; PH="3c0635497fcbee2211ea43c170524458f3b9ffd1b296a9772af5a915db84e664"; RESULT=HERE/"pullback_stop_confirm_3r_results.json"
sys.path.insert(0,str(HERE))
from pullback_stop_confirm_3r import run_confirm,self_test
from parity_engine import prep_symbol
from retest_engine import SPREAD_DIR,TRIO
from retest_fillrealism import run
from walkforward_dsr import real_cost_per_side
H={("Wall_Street_30",0.):(1279,"5f3046b10d91c11632391ccad4a88eaf4029dd392303e8457c9c5838900b64d2"),("Wall_Street_30",.02):(1256,"63c2dfdef6ed6d839f77ddecf111582de1e54e4ca6774c88f2d4f7a9a0c6ec4b"),("Wall_Street_30",.05):(1228,"83cb337253466d36462224f50b5a6fcfea280d47572b60fac83bc5fb5c2b90f1"),("US_Tech_100",0.):(1232,"d1ad13795d5b83cdde3db6dd45ec81ca7bf8640756173f6d920f58a5d717c206"),("US_Tech_100",.02):(1206,"c8d0c24aa5fd6fc571b1b17937aade8e4553db44f9d0f3cc57b6ff39a48a8346"),("US_Tech_100",.05):(1178,"29f854d72945b39c89aae7640715288f4d117fc634d2857799c8de3e44698520"),("Japan_225",0.):(1153,"407314b9c2ebe5379ec275c129d82d28b338f2f66b47e5891ca289eb782390f5"),("Japan_225",.02):(1131,"a05673b0553894f5abfee74147e2bd06a0063a9503622cb5e83e4c56174d775c"),("Japan_225",.05):(1111,"7a0734beb906bdd00b88734ecff54fba46757c8dd7517aac7f98c50098adfe8b")}
def verify():
 b=subprocess.check_output(["git","show",f"HEAD:{SPEC.relative_to(ROOT).as_posix()}"],cwd=ROOT); ls=b.splitlines(True); e=next(i for i,x in enumerate(ls) if x.startswith(b"**PRE-REGISTRATION ENDS")); a=hashlib.sha256(b"".join(ls[:e+1])).hexdigest()
 if a!=PH: raise RuntimeError(f"protocol hash mismatch {a}")
 paths=("docs/PULLBACK_STOP_CONFIRM_3R_SPEC_2026-07-12.md","backtest/pullback_stop_confirm_3r.py","backtest/run_pullback_stop_confirm_3r.py","backtest/retest_fillrealism.py","backtest/parity_engine.py","backtest/retest_engine.py","backtest/walkforward_dsr.py")
 dirty=subprocess.check_output(["git","status","--porcelain","--",*paths],cwd=ROOT,text=True).strip()
 if dirty: raise RuntimeError(f"dirty dependencies\n{dirty}")
 for p in paths: subprocess.check_call(["git","cat-file","-e",f"HEAD:{p}"],cwd=ROOT)
 return a,subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
def sm(rows):
 x=np.asarray([r["r"] for r in rows]); return {"n":len(x),"win_rate":float(np.mean(x>0)) if len(x) else None,"expectancy_r":float(np.mean(x)) if len(x) else None,"total_r":float(np.sum(x))}
def main():
 if RESULT.exists(): raise RuntimeError("result exists")
 ph,commit=verify(); print(f"verified pullback-stop protocol SHA256 {ph}"); subprocess.check_call([sys.executable,str(HERE/"verify_data.py")],cwd=ROOT); self_test()
 data={}; oq={}; cq={}
 for s in TRIO:
  raw=pd.read_csv(os.path.join(SPREAD_DIR,s+".csv")); tc=next(c for c in raw if c.lower()=="time"); t=pd.to_datetime(raw[tc],utc=True); qs=pd.PeriodIndex(t.dt.tz_convert(None),freq="Q"); order=sorted(set(map(str,qs))); oq[s]=set(order[int(len(order)*.7):]); lo,hi=t.min().tz_convert(None),t.max().tz_convert(None); cq[s]={q for q in oq[s] if lo<=pd.Period(q,freq="Q").start_time and hi>=pd.Period(q,freq="Q").end_time.floor("min")}; data[s]=prep_symbol(raw,real_cost_per_side(raw),s)
 reg={}
 for s,d in data.items():
  for b in (0.,.02,.05):
   z=run(d,3.,0.,0.,b); hh=hashlib.sha256(json.dumps(z,separators=(",",":")).encode()).hexdigest(); en,eh=H[(s,b)]; ok=len(z)==en and hh==eh; reg[f"{s}@{b:.2f}"]={"n":len(z),"sha256":hh,"passed":ok}
   if not ok: raise RuntimeError("control regression")
 print("default-mode regression: 9 identical, 0 failed")
 tapes={"C0_PASSIVE_3R":[],"S1_PULLBACK_STOP_CONFIRM_3R":[]}; di={}
 for s,d in data.items():
  a=run(d,3.,0.,0.,.02); b,dd=run_confirm(d,return_diag=True); di[s]=dd
  for name,z in (("C0_PASSIVE_3R",a),("S1_PULLBACK_STOP_CONFIRM_3R",b)):
   for ep,r in z: tapes[name].append({"symbol":s,"epoch":int(ep),"quarter":str(pd.Timestamp(ep,unit="s",tz="UTC").tz_localize(None).to_period("Q")),"r":float(r)})
 res={}
 for name,z in tapes.items():
  oo=[r for r in z if r["quarter"] in oq[r["symbol"]]]; res[name]={"all":sm(z),"stitched_oos":sm(oo),"stitched_oos_by_symbol":{s:sm([r for r in oo if r["symbol"]==s]) for s in TRIO},"stitched_oos_by_quarter":{q:sm([r for r in oo if r["quarter"]==q]) for q in sorted({r["quarter"] for r in oo})}}
 c=res["C0_PASSIVE_3R"]["stitched_oos"]; x=res["S1_PULLBACK_STOP_CONFIRM_3R"]["stitched_oos"]; complete=sorted(set.intersection(*[cq[s] for s in TRIO])); g={"oos_win_rate_lift_at_least_5pp":x["win_rate"]>=c["win_rate"]+.05,"oos_expectancy_positive":x["expectancy_r"]>0,"oos_expectancy_not_below_control":x["expectancy_r"]>=c["expectancy_r"],"every_symbol_oos_expectancy_positive":all(res["S1_PULLBACK_STOP_CONFIRM_3R"]["stitched_oos_by_symbol"][s]["expectancy_r"]>0 for s in TRIO),"every_complete_oos_quarter_positive":all(res["S1_PULLBACK_STOP_CONFIRM_3R"]["stitched_oos_by_quarter"][q]["expectancy_r"]>0 for q in complete),"oos_trade_retention_at_least_35pct":x["n"]>=.35*c["n"],"regression_and_synthetic_pass":all(v["passed"] for v in reg.values())}
 tot={k:sum(v[k] for v in di.values()) for k in next(iter(di.values()))}; out={"protocol_sha256":ph,"commit":commit,"ledger":{"working_start":215,"working_end":216,"charged_cells":1},"regression":reg,"results":res,"diagnostics_all":tot,"diagnostics_by_symbol_all":di,"complete_pooled_oos_quarters":complete,"candidate_minus_control_oos":{"n":x["n"]-c["n"],"retention":x["n"]/c["n"],"win_rate":x["win_rate"]-c["win_rate"],"expectancy_r":x["expectancy_r"]-c["expectancy_r"],"total_r":x["total_r"]-c["total_r"]},"gates":g,"win_rate_above_80pct_diagnostic":x["win_rate"]>.8,"verdict":"ADVANCE" if all(g.values()) else "DISPOSE","terminal_writes":0,"confirmation_accessed":False,"blind_holdout_accessed":False,"ftmo_mc_paths":0}
 RESULT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n"); print(json.dumps(out,indent=2,sort_keys=True)); print(f"RESULT_FILE={RESULT}")
if __name__=="__main__": main()
