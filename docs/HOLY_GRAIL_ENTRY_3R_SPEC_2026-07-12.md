# High-ADX first-touch EMA20 entry with 3R target — pre-registration

**Date:** 2026-07-12 UTC  
**Branch:** `codex/holy-grail-entry-3r`  
**Base:** main `57ac06aa87167e3aea7292cb51c5dced70c85db3`

## Scope and hypothesis

The owner authorizes a materially different entry strategy. This study tests one
fixed Raschke Holy-Grail-style architecture: enter the first EMA20 pullback after
a fresh 20-bar extreme in a strong ADX trend, confirmed by a later break of the
pullback bar. The existing strategy's W2/momentum signal is not used.

Hypothesis: this standalone entry can achieve >80% net positive trades while
retaining positive expectancy with a 1 ATR stop and 3 ATR target. The 80% target
is a hard gate, not a tuning objective.

## Exact candidate H1

Indicators use Wilder smoothing and closed bars only: ATR(14), ADX(14), +DI/-DI,
and EMA(20).

Long setup at closed bar `i` (mirror short):

1. `high[i] > max(high[i-19:i])` (fresh high versus the previous 19 bars);
2. close is above EMA20;
3. ADX14 > 30 and +DI > -DI.

Track one setup per symbol for at most 20 subsequent bars. Invalidate immediately
if ADX <=30 or directional DI alignment reverses. The first later bar whose low
touches or crosses EMA20 is the only eligible pullback; freeze that bar's ATR.
Set a buy stop at its high + 0.02 frozen ATR. Search the next four bars only.
When a later bar trades through the stop, enter at the following bar's open; same-
bar confirmation is forbidden. If untriggered, cancel after four bars. No second
EMA touch belongs to the setup.

From actual next-open entry: SL = 1 frozen touch-bar ATR, TP = 3 frozen ATR, hold
at most eight bars. Stop touch fills pessimistically; TP needs 0.02 frozen ATR
trade-through. Debit the existing round-trip `real_cost_per_side` cost. After a
failed setup resume after its invalidation/expiry; after a trade resume at exit+1.
No overlapping setup per symbol.

No ADX sweep, alternate EMA, alternate setup/confirmation expiry, W2, FIP,
reclaim, panic veto, session, volume, liquidation, partial, trail, or exit grid.

## Data and frames

Require exact canonical verification `verified 46 OK, 0 missing, 0 mismatched`.
Use frozen spreadgated Wall Street 30, US Tech 100, and Japan 225 only. Stitched
OOS is the final 30% of quarters per symbol; endpoint partial quarters are
reported but excluded from complete-quarter gates. No confirmation, blind,
terminal, or fresh data access.

## Controls, tests, outputs

Report the realistic passive W2 3R baseline for context, but it is not an
identical-signal control. The candidate is one charged cell. Synthetic tests cover
Wilder ADX/DI invariants, long/short setup, first-touch enforcement, invalidation,
no same-bar confirmation, next-open entry, stop-first, 3R TP and expiry. Also
reproduce the nine frozen baseline hashes before H1.

Registered command: `python backtest/run_holy_grail_entry_3r.py`

Report all/OOS n, win rate, expectancy and total R; every symbol/quarter; setup,
touch, invalidation, confirmation, expiry and trade counts.

## Gates

H1 advances only if all pass:

1. pooled stitched-OOS win rate strictly >80%;
2. pooled stitched-OOS expectancy >0;
3. every symbol stitched-OOS expectancy >0 and n >=75;
4. every complete stitched-OOS quarter expectancy >0;
5. pooled stitched-OOS n >=300;
6. all synthetic and baseline regression checks pass;
7. no timing, source, manifest, or reporting discrepancy.

Failure disposes H1. Pass only unlocks executable-price confirmation and FTMO MC;
it never authorizes live deployment.

One new cell; proposed working ledger `216 -> 217`. EA, terminal, order and
settings writes: zero.

**PRE-REGISTRATION ENDS — hash all UTF-8/LF bytes through this line, including its newline.**

**Recorded protocol SHA256:** `PENDING`

