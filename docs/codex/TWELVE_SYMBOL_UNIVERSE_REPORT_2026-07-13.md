# Twelve-symbol H1 universe diagnostic

## Verdict

**FAILED — DO NOT EXPAND THE LIVE WHITELIST.** The fixed 12-symbol basket more
than doubled historical fills, but averaged only 2.404118 fills per FTMO
weekday, not the required 6.000. Five candidate symbols also had negative E2
coupled expectancy. Account Monte Carlo was not run because the basket had
already failed binding frequency and edge gates.

The deployed four-symbol v1.31 EA and FTMO terminal were not changed.

## Provenance

The protocol was committed before the census at `bed7ffd`, with recorded
pre-registration SHA256
`ab5e4be70b5cd76cec22579a1e0839522365d41b946a3844cb35ff94e01b0872`.

```text
verified 46 OK, 0 missing, 0 mismatched
```

[MEASURED: `python backtest/verify_data.py` @ `d925398`]

The exact committed rerun produced result JSON SHA256
`88318a90ee6d611d0ca7ad7124cfa5a92dbee5ae9accc75a6350dd8e7c49821e`.
[MEASURED: `python -u backtest/run_twelve_symbol_census.py` @ `d925398`]

## Basket

The control is `US30.cash`, `US100.cash`, `JP225.cash`, and `USDJPY`. The
candidate adds `US500.cash`, `FRA40.cash`, `AUS200.cash`, `EURUSD`, `XAUUSD`,
`XCUUSD`, `XPTUSD`, and `LTCUSD`. These additions were fixed from already-seen
H1 outcomes, so this is an optimistic historical diagnostic, not blind
confirmation. [MEASURED: registered protocol @ `bed7ffd`]

## Frequency census

All counts are after symbol, cluster, and two-seat global coupling, but before
account-policy min-lot rejection or challenge halts. They are therefore an
upper bound on realizable live frequency.

| Metric | Current 4 | Candidate 12 | Delta |
|---|---:|---:|---:|
| Accepted pending lifecycles | 1,645 | 3,178 | +1,533 |
| Actual entries | 969 | 1,939 | +970 |
| Weekday entries | 967 | 1,868 | +901 |
| Weekend entries | 2 | 71 | +69 |
| Unfilled cancellations | 676 | 1,239 | +563 |
| Fill rate | 58.9058% | 61.0132% | +2.1074 pp |
| Mean fills/calendar day | 0.938953 | 1.783809 | +0.844855 |
| Mean fills/weekday | 1.310298 | 2.404118 | +1.093820 |
| Median fills/weekday | 1 | 2 | +1 |
| P10 fills/weekday | 0 | 1 | +1 |
| P90 fills/weekday | 3 | 4 | +1 |
| Maximum fills/weekday | 6 | 7 | +1 |
| Zero-fill weekdays | 211/738 | 76/777 | different frame |
| Weekdays with at least 6 fills | 0.2710% | 2.3166% | +2.0456 pp |

[MEASURED: same command @ `d925398`; DERIVED: deltas]

The 12-symbol basket reaches only 40.069% of the six-fill target. Even this
overstates executable frequency because low-risk symbols can be rejected by
FTMO minimum-volume rules. [DERIVED from 2.404118 / 6.000 and account-policy
ordering]

Entries by cluster were US indices 420, FX 430, metals 368, Asia indices 320,
crypto 238, and Europe indices 163. Energy contributed zero because the fixed
basket contained no energy symbol. [MEASURED: same command @ `d925398`]

## Coupled E2 edge census

The expectancy column charges the registered cost on both sides, matching the
trade resolver's convention.

| Symbol | Entries | E2 expectancy | Win rate | Result |
|---|---:|---:|---:|---|
| AUS200.cash | 139 | -0.009696R | 44.6043% | fail |
| EURUSD | 233 | -0.008089R | 43.3476% | fail |
| FRA40.cash | 163 | +0.083684R | 42.9448% | positive |
| JP225.cash | 181 | +0.003867R | 44.7514% | positive |
| LTCUSD | 238 | -0.084947R | 41.1765% | fail |
| US100.cash | 137 | +0.126825R | 39.4161% | positive |
| US30.cash | 244 | +0.175024R | 47.9508% | positive |
| US500.cash | 39 | -0.060583R | 38.4615% | fail |
| USDJPY | 197 | +0.035359R | 44.6701% | positive |
| XAUUSD | 223 | +0.103644R | 44.8430% | positive |
| XCUUSD | 19 | -0.307113R | 31.5789% | fail |
| XPTUSD | 126 | +0.086624R | 50.0000% | positive |

The coupled candidate pooled expectancy was +0.043201R versus +0.079031R for
the four-symbol control, a dilution of 0.035830R per fill. Five of the eight
proposed additions were negative. [MEASURED: same command @ `d925398`;
DERIVED: difference]

## Cost-ledger discrepancy

The current H1 account-event builder records the E2 per-side cost in
`fixed_slippage_r`, and the account engine debits that value once at entry.
The reference resolver charges `2 × per-side cost` for the round trip. On the
same lifecycles, the one-debit account tape reports +0.118240R for the
12-symbol candidate while the registered round-trip convention reports
+0.043201R, a +0.075039R discrepancy. The control discrepancy is +0.057315R.
[MEASURED: same command and source inspection @ `d925398`]

Because of this mismatch, the older H1 account probabilities were not reused
to promote the basket. The discrepancy requires a separately registered
control re-measurement before any future H1 account claim.

## Decision

Adding symbols does raise opportunity count, but 12 H1 symbols do not produce
six quality fills per weekday and dilute the measured edge. This exact basket
is disposed of. A larger all-in shadow cohort could avoid further symbol
cherry-picking, but it would still require future prospective data and a
corrected cost ledger before any live admission.
