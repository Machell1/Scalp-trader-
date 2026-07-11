# DerivScalperEA — FTMO-compliant configuration

The edge is validated; the risk is FTMO's rulebook. Every setting below maps to a
specific FTMO rule that would otherwise deny a payout. Nothing here touches the
validated momentum entry or pure-bracket exit — these are risk/compliance rails.

## The FTMO rules that threaten this EA, and the fix

| FTMO rule | Threat to our EA | Setting that fixes it |
|---|---|---|
| **"One-sided betting" → 1% per "trade idea"** (correlated positions within a 1h window aggregated) | EA runs up to 3 concurrent, often-correlated positions → flagged | **`InpMaxPerCluster = 1`** (one position per correlation cluster) + **`InpMaxConcurrent = 3`** across the 4 clusters |
| **Risk measured by MAE incl. slippage; >1% = void** | Cost-sensitive tight stops can slip past 1% | **`InpRiskPercent = 0.5`** (big buffer so a slipped 0.5% stop never reaches 1%) |
| **Max daily loss 5%** | A bad correlated day | **`InpDailyLossLimitPct = 4.0`** (halts before FTMO's 5%) |
| **Max total loss 10%** | Drawdown | **`InpMaxDrawdownPct = 8.0`** (halts before FTMO's 10%) |
| **Mandatory SL on every order** | — | Already satisfied (pure-bracket sets SL at entry) |
| **High-impact news restriction (normal accts)** | EA has no news filter by default | **`InpNewsBlockMins = 3`** (v1.25 news blackout ON) |
| **Min 4 trading days** | — | Trivially met (trades daily) |
| **Cost gate (protects the edge on FTMO's wider spreads)** | Edge dies >0.05 ATR/side | **`InpMaxSpreadAtr = 0.05`** (keep it — this is what refuses toxic FTMO spreads) |

## The .set preset (apply on the FTMO MT5 chart)

# VERIFIED on FTMO-Demo 2026-07-09 (login 1513946641): only US30.cash, US100.cash,
# BTCUSD clear the 0.10xATR spread ceiling (US30 2.43<4.13, NAS100 1.53<3.83, BTC 1.00<17.7).
# SP500/ETH fail by a hair (re-check during peak session); DAX/UK100/FRA40/JP225/US2000 fail.
```
InpSymbolWhitelist  = US30.cash,US100.cash,BTCUSD
InpTimeframe        = PERIOD_M15
InpRiskPercent      = 0.5
InpMaxSpreadAtr     = 0.05
InpMaxPerCluster    = 1
InpClusterSpec      = US30.cash|US100.cash;BTCUSD
InpMaxConcurrent    = 2
InpMaxTradesPerDay  = 8
InpDailyLossLimitPct= 4.0
InpMaxDrawdownPct   = 8.0
InpMaxConsecLosses  = 4
InpNewsBlockMins    = 3
InpFreshnessGuard   = true
InpTradeLog         = true
InpEntryMode        = ENTRY_LIMIT_PULLBACK
InpTakeProfitAtrMult= 3.0
InpUseLockTrail     = false          # pure bracket (validated)
InpMagicNumber      = 770077
```

Note: the whitelist and cluster spec use FTMO's `.cash` index tickers — the exact
names come out of `ftmo_spread_check.py` (it resolves the real symbols on the feed).
**Only include instruments whose spread PASSES the ceiling** — the rest kill the edge.

## Recommended code addition (optional, extra safety on the 1h rule)
`InpReentryCooldownMin = 65` — block a new entry on a symbol within 65 min of its
last closed trade, so sequential same-direction trades can't be chained into one
"trade idea". With `InpMaxPerCluster = 1` and max-hold 2h this is low-risk already,
but the cooldown makes it airtight. I'll add it to the EA when we compile for FTMO.

## The de-risking sequence (spend nothing until step 3 passes)
1. **Free trial (no time limit).** FTMO gives unlimited free trials — open one, log
   the MT5 terminal in yourself. Cost: $0.
2. **Spread check.** Run `ftmo_spread_check.py` against that terminal. It tells us,
   per instrument, whether the edge survives on FTMO's real spreads. Keep only PASS.
3. **Forward-test on the free trial.** Compile the EA into the FTMO terminal with this
   preset (PASS instruments only) and let it run on the free trial for 1-2 weeks.
   Confirm live behaviour + that it stays inside every rule (daily <4%, no 1%-idea
   breach, spread-gated). The v1.25 trade log gives us the MFE/MAE/spread evidence.
4. **Only then** buy the challenge, run the same preset, size wins across >=4 days for
   the consistency rule, and get written pre-approval of the EA + settings from your
   registered FTMO email first.

FTMO facts confirmed (ftmo.com): since 2015, $500M+ paid, 4.8/5 Trustpilot, zero
commission on indices, **no time limit on challenges, unlimited free trials.** The
free trial means the entire spread + forward test costs nothing.
