# v1.31 challenger test prompt

Use this prompt for the next research pass:

> You are testing `mql5/MomentumPullbackV131ChallengerEA.mq5` against the existing `mql5/MomentumPullbackEA.mq5` v1.31 control in this repository.
>
> **Objective:** determine whether the E3 exit upgrade is reproducibly better than v1.31. Do not change the signal, entry, symbol universe, risk percentages, cost model, or portfolio gates.
>
> **Control:** H1; `US30.cash`, `US100.cash`, `JP225.cash` at 0.30% dynamic risk and `USDJPY` at 0.05%; six-bar impulse of at least 2.0 Wilder ATR(14); W2 adverse wick at least 0.30 ATR; 0.6 ATR pullback limit; three-bar pending window; 1 ATR stop; 50% close at +1R; 2.0 ATR remainder target; maximum hold eight bars.
>
> **Candidate:** identical to control except close 66.6666667% of original volume at +1R and target 1.5 ATR on the remainder. Keep the challenger magic number separate. Keep live order submission disabled.
>
> **Protocol:**
> 1. Start from a clean checkout and record `git rev-parse HEAD`.
> 2. Run `python backtest/verify_data.py`; stop if the pinned data check is not exactly `verified 46 OK, 0 missing, 0 mismatched`.
> 3. Use the registered causal H1 tape and common moving-block bootstrap (`seed=13020260711`, block length 20). Run Python/C# path-0 parity before any Monte Carlo summary.
> 4. Screen the preregistered exit family at 20,000 paths. Confirm only a screen passer at 100,000 paths; do not select a variant after looking at confirmation results.
> 5. A confirmation passes only if candidate both-phase probability is strictly above 85.4740%, candidate Wilson lower bound is strictly above 85.2898%, hard-halt probability is no greater than 0.3700%, timeout probability is strictly below 14.1560%, and the paired-control lower bound is positive. Report point estimates, Wilson bounds, paired counts, p-value, common block count, and row SHA256 hashes.
> 6. If no cell passes confirmation, report `NO_CONFIRMATION_PASS` and do not claim an upgrade. If one passes, write the result JSON and a short report naming the exact selected cell.
>
> **Safety:** research only; do not attach to a live terminal, submit orders, modify existing positions, or overwrite the v1.31 control. Compile the challenger separately and run the repository regression tests. The hard challenger lot cap must remain at 0.01.

The confirmed local result for this prompt is archived in the originating workspace, but this repository copy must be re-run from its own pinned checkout before any deployment decision.
