# H1 USDJPY universe admission and v1.31 build

## Decision

USDJPY is admitted to the H1 portfolio at 0.05% dynamic cash risk per trade.
US30.cash, US100.cash, and JP225.cash remain at 0.30%. No fixed lot size is
used. [DERIVED: pre-registered selector applied to the confirmation result]

The owner amended the absolute stress requirement from 80.000% to 78.887%
after the AUS200 result was visible. The original 80% verdict is preserved;
the paired-improvement, hard-halt, and timeout gates were not relaxed.

## Provenance and costs

`python backtest/verify_data.py` printed `verified 46 OK, 0 missing, 0
mismatched`. [MEASURED: command @ `41069cf` plus the pre-registered working-tree
runner]

FTMO metadata for 33 symbols were captured read-only from demo account
1513946641, terminal build 5836, and frozen in
`backtest/h1_universe_broker_meta.json`, SHA256
`ba1f3cdeaca429764129685f79a4267e1bbc55b2fead70c8187db431fd828928`.
[MEASURED: frozen metadata artifact @ `62563aa`]

The cost model follows FTMO's published instrument rules: indices have zero
commission, Forex is USD 5 per lot round turn (USD 2.50 per side in the study),
and crypto is 0.0325% of notional per side. Sources:
https://ftmo.com/en/symbols/,
https://ftmo.com/en/blog/zero-commissions-on-indices/, and
https://ftmo.com/en/blog/ftmo-enhances-crypto-trading-new-instruments-and-better-spreads/.

## Full-universe screen

All 30 predeclared non-control symbols are recorded in
`backtest/h1_universe_screen_results.json`, SHA256
`6e38637ee0b0a1b98ea1e967ba17fa1f14dd49884c8eed9c0d8b29ed60495d04`.
Five passed the causal per-symbol gate. Their E2 OOS results were FRA40.cash
81 trades at +0.087627R, AUS200.cash 68 at +0.013948R, USDJPY 78 at
+0.069033R, XAUUSD 107 at +0.110202R, and LTCUSD 101 at +0.023011R.
[MEASURED: `python backtest/run_h1_universe_screen.py` @ `62563aa` plus runner]

Their equal-0.30%-risk, 20,000-path account cells were:

| Candidate | Both phases | Wilson lower | Hard halt | Timeout | Paired lower | Original 80% | Amended 78.887% |
|---|---:|---:|---:|---:|---:|---|---|
| AUS200.cash | 79.775% | 79.3038% | 1.390% | 18.835% | -0.5266 pp | FAIL | FAIL: paired + hard |
| FRA40.cash | 79.680% | 79.2080% | 1.995% | 18.325% | -0.6843 pp | FAIL | FAIL: paired + hard |
| LTCUSD | 79.850% | 79.3794% | 4.470% | 15.680% | -0.9525 pp | FAIL | FAIL: paired + hard |
| USDJPY | 82.225% | 81.7760% | 1.520% | 16.255% | +4.0188 pp | FAIL: hard | FAIL: hard |
| XAUUSD | 71.795% | 71.2687% | 10.425% | 17.780% | -5.2420 pp | FAIL | FAIL |

[MEASURED: `python backtest/run_h1_universe_account.py` @ `62563aa` plus
runner; complete JSON SHA256
`e4e51d01811791a78c3d796d7c9faf7d0b2711f30a6b8977a6903f1ad32dcf53`]

This is why AUS200 was not admitted despite its 79.3038% Wilson lower bound:
the amended absolute gate passed, but adding it made paired outcomes worse and
raised hard halts above 1%. [DERIVED: gate evaluation]

## USDJPY dynamic-risk sleeve

The registered five-cell screen used 20,000 common paths and 117 common
eligible blocks. Python and C# rows matched exactly on path 0 for the control
and all policies.

| USDJPY risk | Both phases | Wilson lower | Hard halt | Timeout | Paired lower | Result |
|---:|---:|---:|---:|---:|---:|---|
| 0.05% | 85.7150% | 85.3032% | 0.3400% | 13.9450% | +7.5415 pp | PASS |
| 0.10% | 85.4650% | 85.0503% | 0.2350% | 14.3000% | +7.2977 pp | PASS |
| 0.15% | 85.1600% | 84.7418% | 0.2650% | 14.5750% | +6.9857 pp | PASS |
| 0.20% | 84.7600% | 84.3373% | 0.4250% | 14.8150% | +6.5836 pp | PASS |
| 0.25% | 83.7300% | 83.2962% | 0.7250% | 15.5450% | +5.5416 pp | PASS |

[MEASURED: `python -u backtest/run_h1_usdjpy_risk.py` @ `41069cf` plus
pre-registered runner]

The frozen selector chose 0.05%. On 100,000 confirmation paths it produced
85.4740% both-phases pass (85,474 paths), 85.2898% one-sided Wilson lower,
92.2660% phase-1 pass, 92.6387% phase-2 conditional pass, 0.3700% hard halt
(0.4030% Wilson upper), and 14.1560% timeout. Successful-path completion was
676 median and 1,090 p90 days. The paired control produced 76.8220% pass,
76.6018% Wilson lower, 0.3700% hard halt, and 22.8080% timeout. Paired counts
were n10=19,854 and n01=11,202; the registered paired lower improvement was
+8.2080 percentage points. [MEASURED: same command; result JSON SHA256
`c03ffd636c15b8e07ecadc8b8b5a94d1be3a1b37378948dacf203c8c579fe74c`]

## v1.31 build and checks

The EA changes only the versioned H1 default, whitelist, cluster map, and
symbol-specific risk lookup. Entry/exit geometry is unchanged. MetaEditor
compiled the repository source with `Result: 0 errors, 0 warnings, 10580 ms
elapsed, cpu='X64 Regular'`. Source SHA256 is
`84410515cdd76a23d66a0699adf29bd33b4db600319714757ecbdba1165672f4`;
EX5 SHA256 is
`c21f03a322d1a5adf7d8cdec7b096bcc6b845391e2252b88aa1ec1fdfa890fa1`.
[MEASURED: MetaEditor compile @ `41069cf` plus v1.31 working tree]

The first compile invocation returned process exit 0 but produced no log and
did not refresh the binary; it was rejected. The corrected invocation returned
process exit 1 but its compiler log recorded 0 errors/0 warnings and refreshed
the binary. An auxiliary `check_v130_pass_policy_csharp.py` call first failed
because `--mode` and `--path-id` were omitted; the corrected call terminated
after `STAGE inputs_start` and is not evidence. These failures were not filled
in or reconciled.

Before deployment inspection, MetaTrader5 reported account 1513946641 balance
and equity 99,375.21, `POSITIONS 0`, and `ORDERS 0`. [MEASURED: read-only MT5
query @ `41069cf` plus v1.31 working tree]

## Terminal-write journal

No terminal write had occurred when this report section was created. Deployment
requires a second flat-account check, backup hashes, graceful shutdown, source
and binary replacement, graceful restart, and a verified v1.31 H1 init line.
