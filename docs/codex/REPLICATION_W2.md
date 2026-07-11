# Independent Replication of the W2 Inverse-Candle Gate

## Verdict

REPLICATED WITHIN TOLERANCE

Phase A reproduced the recorded baseline, W2 expectancy, passing-cell set, and
seven-gate verdict exactly at the recorded print precision. Phase B independently
recomputed the pooled baseline and W2 expectancies within the assigned tolerance.
No discrepancy was found.

- Replication base: 0ddd90875de86425aacf3bd7adf802e3ae734a65
- Independent-runner commit: 655f9065f69210021d2166b5ae7d928778d25692
- Governing spec: docs/CANDLE_INVERSE_SPEC_2026-07-10.md
- Recorded spec SHA256: 5c7763300ee04bf00e7224a25ff2b9e774fdab6ca962c4fb988153ce85902b47
- FTMO corroboration: not replicated (terminal access not required for this task).

## Phase 0 — provenance

### Fresh main and canonical data

[MEASURED: git pull origin main @ 0ddd90875de86425aacf3bd7adf802e3ae734a65]

~~~text
From https://github.com/Machell1/Scalp-trader-
 * branch            main       -> FETCH_HEAD
   c212fd1..0ddd908  main       -> origin/main
Updating c212fd1..0ddd908
Fast-forward
 docs/codex/SETUP_REPORT.md | 126 +++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 126 insertions(+)
 create mode 100644 docs/codex/SETUP_REPORT.md
~~~

[MEASURED: python backtest/verify_data.py @ 0ddd90875de86425aacf3bd7adf802e3ae734a65]

~~~text
verified 46 OK, 0 missing, 0 mismatched
~~~

### Spec introduction and lineage

[MEASURED: git log --follow --date=iso-strict --format="commit %H%nAuthor: %an <%ae>%nDate: %ad%nSubject: %s" -- docs/CANDLE_INVERSE_SPEC_2026-07-10.md @ 0ddd90875de86425aacf3bd7adf802e3ae734a65]

~~~text
commit e808d14b6384645a934d8ac16f11c25519c5ed14
Author: Machell1 <williamsmachell@gmail.com>
Date: 2026-07-10T22:02:21-05:00
Subject: Inverse candle filter: FIRST full-gate PASS in project history (W2,W3,K2,K3)
~~~

The relevant verbatim commit-message evidence from git log --follow -p is:

~~~text
commit e808d14b6384645a934d8ac16f11c25519c5ed14
Author:     Machell1 <williamsmachell@gmail.com>
AuthorDate: Fri Jul 10 22:02:21 2026 -0500
Commit:     Machell1 <williamsmachell@gmail.com>
CommitDate: Fri Jul 10 22:02:21 2026 -0500

    Inverse candle filter: FIRST full-gate PASS in project history (W2,W3,K2,K3)

    Pre-registered (SHA256 5c776330...) quarter-stitched walk-forward at real
    per-instrument spread cost, pure-bracket config: 4/6 cells clear all 7
    gates (filtered>base, >random-drop placebo95, quarters>=60%, symbols>=8/12,
    DSR>=0.95 @94 trials, 2x cost, n>=250). W2 keep-wicky>=0.3: +0.120R vs
    +0.078R base OOS.
~~~

The commit created the spec as a new file. The exact historical blob and its
SHA256 were measured directly from Git rather than from the current working
tree:

[MEASURED: git rev-parse e808d14b6384645a934d8ac16f11c25519c5ed14:docs/CANDLE_INVERSE_SPEC_2026-07-10.md; Python SHA256 over git cat-file blob @ 0ddd90875de86425aacf3bd7adf802e3ae734a65]

~~~text
SPEC_BLOB=a4a0221e4e332f576578d1a850a8df19f9953b72
BLOB_BYTES=2700
BLOB_SHA256=5c7763300ee04bf00e7224a25ff2b9e774fdab6ca962c4fb988153ce85902b47
~~~

The assigned SHA256 matches the exact Git blob. The following comparison proves
that HEAD still references the introducing blob and that no later commit
changed this path:

[MEASURED: git rev-parse introduction and HEAD blobs; git log introduction..HEAD -- spec path @ 0ddd90875de86425aacf3bd7adf802e3ae734a65]

~~~text
INTRO_SPEC_BLOB=a4a0221e4e332f576578d1a850a8df19f9953b72
HEAD_SPEC_BLOB=a4a0221e4e332f576578d1a850a8df19f9953b72
BLOBS_IDENTICAL=True
LATER_PATH_COMMITS=0
~~~

Conclusion: commit e808d14b6384645a934d8ac16f11c25519c5ed14
introduced the complete protocol, its exact blob SHA256 matches the assigned
value, and the protocol file is byte-identical at HEAD. Provenance caveat:
the introducing commit also has a results-bearing subject and body, so Git
alone does not establish a separately committed pre-results timestamp.

### Failed provenance-tool attempt

The first hashing-tool attempt failed because OpenSSL is unavailable. It did
not read data or run the study. Reported verbatim:

~~~text
SPEC_BLOB=a4a0221e4e332f576578d1a850a8df19f9953b72
openssl : The term 'openssl' is not recognized as the name of a cmdlet, function, script file, or operable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:2 char:151
+ ... -10.md'; "SPEC_BLOB=$blob"; git cat-file blob $blob | openssl dgst -s ...
+                                                           ~~~~~~~
    + CategoryInfo          : ObjectNotFound: (openssl:String) [ ], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
~~~

## Phase A — exact Deriv rerun

The tracked implementation was not edited. The FTMO function was replaced in
memory with a no-op, as allowed by the assignment, and main was called once.

[MEASURED: python -u -c "import sys; sys.path.insert(0, r'backtest'); import inverse_candle_gate as study; study.ftmo_corroboration = lambda: None; study.main()" @ 0ddd90875de86425aacf3bd7adf802e3ae734a65]

Exit status: 0. Stderr was empty. Stdout follows verbatim:

~~~text
loaded 12/12 spread-gated symbols
  BTCUSD                 cost/side 0.0048
  ETHUSD                 cost/side 0.0239
  France 40              cost/side 0.0424
  Germany 40             cost/side 0.0101
  Japan 225              cost/side 0.0348
  SOLUSD                 cost/side 0.0186
  UK 100                 cost/side 0.0354
  US SP 500              cost/side 0.0273
  US Small Cap 2000      cost/side 0.0290
  US Tech 100            cost/side 0.0122
  Wall Street 30         cost/side 0.0163
  XRPUSD                 cost/side 0.0171

building stitched tapes (real cost + 2x cost)...
tape: 34394 trades | stitched OOS quarters: 4 | OOS n=11272 baseline OOS exp=+0.0778R

W1 (keep adv_wick>=0.20): kept 6228/11272 (55.3%)
  base OOS +0.0778R | filtered +0.1074R | placebo95 +0.0978 | DSR 0.999
  2x cost: base +0.0341 filt +0.0647 | quarters 2/4 | symbols 10/12
  gates: G1Y G2Y G3N G4Y G5Y G6Y G7Y  -> no (6/7)

W2 (keep adv_wick>=0.30): kept 4583/11272 (40.7%)
  base OOS +0.0778R | filtered +0.1202R | placebo95 +0.1035 | DSR 0.998
  2x cost: base +0.0341 filt +0.0780 | quarters 3/4 | symbols 9/12
  gates: G1Y G2Y G3Y G4Y G5Y G6Y G7Y  -> PASS (7/7)

W3 (keep adv_wick>=0.50): kept 2470/11272 (21.9%)
  base OOS +0.0778R | filtered +0.1360R | placebo95 +0.1223 | DSR 0.975
  2x cost: base +0.0341 filt +0.0945 | quarters 3/4 | symbols 8/12
  gates: G1Y G2Y G3Y G4Y G5Y G6Y G7Y  -> PASS (7/7)

K1 (drop body>=0.80): kept 8387/11272 (74.4%)
  base OOS +0.0778R | filtered +0.0876R | placebo95 +0.0893 | DSR 0.999
  2x cost: base +0.0341 filt +0.0440 | quarters 3/4 | symbols 6/12
  gates: G1Y G2N G3Y G4N G5Y G6Y G7Y  -> no (5/7)

K2 (drop body>=0.70): kept 6462/11272 (57.3%)
  base OOS +0.0778R | filtered +0.1165R | placebo95 +0.0960 | DSR 1.000
  2x cost: base +0.0341 filt +0.0730 | quarters 3/4 | symbols 10/12
  gates: G1Y G2Y G3Y G4Y G5Y G6Y G7Y  -> PASS (7/7)

K3 (drop clean-climax): kept 8074/11272 (71.6%)
  base OOS +0.0778R | filtered +0.1027R | placebo95 +0.0934 | DSR 1.000
  2x cost: base +0.0341 filt +0.0593 | quarters 3/4 | symbols 10/12
  gates: G1Y G2Y G3Y G4Y G5Y G6Y G7Y  -> PASS (7/7)

==== FINAL VERDICT: PASS on W2,W3,K2,K3 ====
~~~

FTMO corroboration: not replicated (terminal access not required for this task).

### Cell-by-cell recorded-versus-reproduced comparison

The tracked lineage records the passing set W2, W3, K2, K3 and the rounded
baseline/W2 core values. It does not contain a historical line-by-line stdout
artifact for the other cell metrics, so untracked historical numbers are not
invented below.

[MEASURED: Phase A command above and git log --follow evidence @ 0ddd90875de86425aacf3bd7adf802e3ae734a65]

| Cell | Recorded verdict | Reproduced verdict | Gate score | Reproduced filtered OOS | Result |
|---|---:|---:|---:|---:|---|
| W1 | no | no | 6/7 | +0.1074R | exact verdict match |
| W2 | PASS | PASS | 7/7 | +0.1202R | exact verdict and recorded expectancy match |
| W3 | PASS | PASS | 7/7 | +0.1360R | exact verdict match |
| K1 | no | no | 5/7 | +0.0876R | exact verdict match |
| K2 | PASS | PASS | 7/7 | +0.1165R | exact verdict match |
| K3 | PASS | PASS | 7/7 | +0.1027R | exact verdict match |

| Recorded core metric | Recorded | Phase A | Difference at recorded precision |
|---|---:|---:|---:|
| Baseline stitched OOS expectancy | +0.0778R | +0.0778R | 0.0000R |
| W2 filtered stitched OOS expectancy | +0.1202R | +0.1202R | 0.0000R |
| Passing set | W2, W3, K2, K3 | W2, W3, K2, K3 | exact |

Phase A result: REPLICATED EXACTLY for every result preserved in the assignment
and tracked lineage.

### Failed Phase A entry-point inspection

Before the one study execution, a read-only AST command failed from shell
quoting. It did not execute the study. Reported verbatim:

~~~text
  File "<string>", line 1
    import ast,pathlib; p=pathlib.Path('backtest/inverse_candle_gate.py'); t=ast.parse(p.read_text(encoding='utf-8')); print('FUNCTIONS'); print('\\n'.join(n.name for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)))); print('MAIN_CALLS'); [print(ast.unparse(x.value)) for n in t.body if isinstance(n,ast.If) and ast.unparse(n.test)==" __name__ == __main__ \
                                                                                                                                                                                                                                                                                                                                                                 ^
SyntaxError: unterminated string literal (detected at line 1)
~~~

## Phase B — independent core recomputation

### Independence and method

The independent runner was written from
docs/CANDLE_INVERSE_SPEC_2026-07-10.md and the explicit feature definition in
docs/CANDLE_SPEC_2026-07-10.md. Before its first numerical execution it was
committed as backtest/replicate_w2_independent.py at
655f9065f69210021d2166b5ae7d928778d25692. Neither study implementation nor
its history was inspected or imported before the numbers below existed.

The runner used:

- scalper_backtest.simulate_symbol with signals_out;
- the pure-bracket parameters specified by the protocol;
- walkforward_dsr.real_cost_per_side;
- signal-bar Wilder ATR;
- buy adverse wick = high - max(open, close);
- sell adverse wick = min(open, close) - low;
- W2 keep rule adv_wick_atr >= 0.30;
- one baseline-derived stitched OOS quarter set applied identically to baseline
  and W2.

### Verbatim independent output

[MEASURED: python -u backtest/replicate_w2_independent.py @ 655f9065f69210021d2166b5ae7d928778d25692]

Exit status: 0. Stdout follows verbatim:

~~~text
PHASE_B_INDEPENDENT_W2
formula=buy:(high-max(open,close))/ATR;sell:(min(open,close)-low)/ATR
w2_keep=adv_wick_atr>=0.30
oos_quarters=2025Q4,2026Q1,2026Q2,2026Q3
symbol,baseline_n,baseline_exp_r,w2_n,w2_exp_r,delta_r
BTCUSD,1189,0.1595985685,550,0.2752862629,0.1156876945
ETHUSD,1104,0.0873583725,598,0.1009303724,0.0135719999
XRPUSD,1177,0.0829996435,530,0.1259046843,0.0429050408
SOLUSD,1188,0.1031640475,566,0.1116208538,0.0084568063
US Tech 100,818,0.1339873505,284,0.2251528732,0.0911655228
US SP 500,827,0.0124941571,288,-0.0190682396,-0.0315623967
Wall Street 30,832,0.0829425275,322,0.0662149042,-0.0167276233
US Small Cap 2000,813,0.0340599931,284,0.1702222173,0.1361622242
Germany 40,814,0.1125200280,296,0.1585115062,0.0459914782
UK 100,838,0.0105947716,281,-0.0010260903,-0.0116208619
Japan 225,837,0.0666607245,303,0.0966108403,0.0299501157
France 40,835,-0.0026626990,281,0.0183301629,0.0209928618
POOLED,11272,0.0778149824,4583,0.1201923849,0.0423774025
~~~

### Per-symbol independent results

[MEASURED: python -u backtest/replicate_w2_independent.py @ 655f9065f69210021d2166b5ae7d928778d25692]

| Symbol | Baseline n | Baseline exp R | W2 n | W2 exp R | Delta R |
|---|---:|---:|---:|---:|---:|
| BTCUSD | 1189 | 0.1595985685 | 550 | 0.2752862629 | 0.1156876945 |
| ETHUSD | 1104 | 0.0873583725 | 598 | 0.1009303724 | 0.0135719999 |
| XRPUSD | 1177 | 0.0829996435 | 530 | 0.1259046843 | 0.0429050408 |
| SOLUSD | 1188 | 0.1031640475 | 566 | 0.1116208538 | 0.0084568063 |
| US Tech 100 | 818 | 0.1339873505 | 284 | 0.2251528732 | 0.0911655228 |
| US SP 500 | 827 | 0.0124941571 | 288 | -0.0190682396 | -0.0315623967 |
| Wall Street 30 | 832 | 0.0829425275 | 322 | 0.0662149042 | -0.0167276233 |
| US Small Cap 2000 | 813 | 0.0340599931 | 284 | 0.1702222173 | 0.1361622242 |
| Germany 40 | 814 | 0.1125200280 | 296 | 0.1585115062 | 0.0459914782 |
| UK 100 | 838 | 0.0105947716 | 281 | -0.0010260903 | -0.0116208619 |
| Japan 225 | 837 | 0.0666607245 | 303 | 0.0966108403 | 0.0299501157 |
| France 40 | 835 | -0.0026626990 | 281 | 0.0183301629 | 0.0209928618 |
| POOLED | 11272 | 0.0778149824 | 4583 | 0.1201923849 | 0.0423774025 |

### Phase A versus independent Phase B

[MEASURED: python comparison command @ 655f9065f69210021d2166b5ae7d928778d25692]

~~~text
baseline_abs_delta=0.0000149824
w2_abs_delta=0.0000076151
tolerance=0.0005000000
within_tolerance=True
~~~

| Metric | Phase A printed | Phase B independent | Absolute gap to recorded/Phase A print | Tolerance result |
|---|---:|---:|---:|---|
| Baseline pooled OOS expectancy | +0.0778R | +0.0778149824R | 0.0000149824R | PASS |
| W2 pooled OOS expectancy | +0.1202R | +0.1201923849R | 0.0000076151R | PASS |
| Baseline pooled OOS n | 11272 | 11272 | 0 | exact |
| W2 pooled OOS n | 4583 | 4583 | 0 | exact |

After Phase B numbers were fixed, the study code was inspected. Its buy-side
upper-wick and sell-side lower-wick formulas and its W2 >= 0.30 rule are
identical to the independent derivation. No computation was rerun after this
inspection.

## Scope, ledger, and compliance

- [DERIVED] Trial-ledger increment: 0. This replication tests no new hypothesis.
- The FTMO corroboration was not replicated, and no terminal was initialized or
  accessed.
- No strategy, production code, canonical dataset, EA, terminal state, order,
  position, or repository setting was changed.
- What was not established: Git does not provide a separately committed
  pre-results version of the spec; it proves the supplied hash and unchanged
  lineage of the introducing blob.
- What could invalidate the result: a different canonical data manifest, a
  different audited-engine commit, or any unreported change to the locked
  protocol. None occurred in this replication.

Article compliance: work occurred only on codex/replicate-w2-gate; canonical
data verified before analysis; every executed result and failure is reported;
the locked protocol was not changed; ledger increment is zero; live systems
were not accessed.
