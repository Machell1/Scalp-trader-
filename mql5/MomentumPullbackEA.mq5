//+------------------------------------------------------------------+
//|   v1.33-C1 (2026-07-18, harness-CONFIRMED): GEOMETRY RESET of failed |
//|     E3 challenger, owner-authorized. Two input renames with new  |
//|     defaults (house convention: chart-saved V130 values cannot    |
//|     survive):                                                     |
//|       * InpPartialCloseFractionV133 = 0.75 (was 0.50 in v1.31;    |
//|         the failed E3 challenger ran 0.67)                        |
//|       * InpTakeProfitAtrMultV133    = 1.5  (was 2.0)              |
//|     Rationale (pre-registered 6-cell paired grid, 20,000 CRN      |
//|     paths, seed 13020260711, E2 stress, repo harness): C1 tied E3 |
//|     on pass (88.85% vs 88.01%, LB ~0), eliminated ALL hard halts  |
//|     (0/20k vs E3 2/20k vs v1.31 167/20k), cut timeout to 11.15%   |
//|     and median completion to 374d (v1.31: 562d); +8.48pp vs v1.31 |
//|     with paired lower bound +7.55pp.                              |
//|     STATUS: CONFIRMED on the owner's corrected-fidelity harness:  |
//|     100,000 paired E2-stress paths, 88.274% modeled pass,         |
//|     0.266% hard halt, paired lower +11.0265pp vs v1.31.          |
//|     The forward demo remains live execution validation.           |
//|     Everything else is v1.32 unchanged (fidelity fixes A1-A9,     |
//|     gated arms B1-B3 default OFF).                                |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|   v1.32 (2026-07-14): EXECUTION FIDELITY + PRE-REGISTERED ARMS.   |
//|     Part A (default ON; they only make the live EA faithfully     |
//|     realize the already-validated engine - zero strategy change): |
//|     * A1: partial-close retry overhaul - MARKET_CLOSED / no-      |
//|       connection retcodes no longer burn the 5-attempt budget     |
//|       (60s re-arm, retry-until-open), freshness-gated trigger,    |
//|       bar-extreme catch-up trigger (InpPartialBarCatchupV132).    |
//|     * A2: time exit evaluated EVERY heartbeat in                  |
//|       ManageOpenPositions; a rejected close retries next          |
//|       heartbeat instead of waiting a full bar (weekend gap fix).  |
//|     * A3: DEAL_ENTRY_OUT_BY / DEAL_ENTRY_INOUT get the same       |
//|       exit-bar cooldown + LogClosedTrade as DEAL_ENTRY_OUT.       |
//|     * A4: the daily fill cap counts DISTINCT positions, not       |
//|       broker fill fragments (live counter + RestoreRiskLedger).   |
//|     * A5: riskPrice (the R denominator) comes from the ACTUAL     |
//|       placed stop, so the +1R level and R-logs stay honest when   |
//|       the stops-level clamp / tick snap moves the SL.             |
//|     * A6: bounded entry retry (InpEntryMaxRetriesV132) on price-  |
//|       class retcodes (10015/10004/10020/10021) while the signal   |
//|       bar is still bar 1 (the deferred v1.30 "10015" item).       |
//|     * A7: magic-scoped risk-ledger GVs + one-shot legacy migrate. |
//|     * A8: halt pending-cancel spam throttle.                      |
//|     * A9: bar-clock seeding guard - never blind-increment an      |
//|       unseeded clock; recompute retried every bar close.          |
//|     Part B (pre-registered research arms, flag-gated, DEFAULT     |
//|     OFF; defaults reproduce v1.31 behavior exactly):              |
//|     * B1: ENTRY_MARKET entry mode (Alvarez A/B arm B).            |
//|     * B2: EXIT_UNCAPPED_RUNNER - opposite-impulse exit via the    |
//|       factored-out DetectImpulse, InpRunnerMaxBarsV132 backstop,  |
//|       optional stop-and-reverse (InpRunnerReverseV132).           |
//|     * B3: STOP_EVAL_BAR_CLOSE - stop evaluated on bar close; the  |
//|       broker carries only a disaster backstop                     |
//|       (InpDisasterStopMultV132); the intended 1.0 ATR stop stays  |
//|       the R denominator.                                          |
//|     Frozen defaults are bit-identical to v1.31 live behavior.     |
//|                                                                  |
//|   v1.31 (2026-07-13): H1 USDJPY ADMISSION.                        |
//|     * H1 is now the versioned default working timeframe.         |
//|     * Add USDJPY after a 100,000-path stress confirmation.       |
//|     * Keep the validated trio at 0.30% dynamic cash risk and     |
//|       size USDJPY independently at 0.05%; no fixed lots.         |
//|     * Give USDJPY its own FX cluster seat under the global cap.  |
//|                                                                  |
//|   v1.30 (2026-07-13): CORRECTED-ENGINE EARLY BANKING.             |
//|     * Bank 50% once at +1R using the frozen signal-bar Wilder ATR |
//|       and initial stop multiple; the remainder keeps its bracket. |
//|     * TP3 -> TP2 via a versioned input name so an existing chart  |
//|       cannot silently retain the obsolete saved TP3 value.        |
//|     * Partial state is ticket-keyed, restart-safe, tick-checked,   |
//|       lot-step rounded down, and separately logged with slippage. |
//|     * Partial DEAL_ENTRY_OUT events do not trigger full-exit       |
//|       cooldown, trade-final logging, or consecutive-loss logic.   |
//|                                                                  |
//|                                            MomentumPullbackEA.mq5 |
//|   Multi-symbol H1 momentum-continuation EA (pullback entry).      |
//|                                                                  |
//|   v1.1 -- backtest-driven entry rework (2026-06):                 |
//|     * The original entry "chase a STOP order just beyond an       |
//|       already-extended 2-ATR move" was a net LOSER out-of-sample  |
//|       on real Deriv M15 data: it entered at maximum extension     |
//|       (where continuation is weakest / mean-reversion strongest)  |
//|       and defended it with a 1-ATR stop that sits INSIDE the      |
//|       normal retrace band, so a routine pullback stopped it out.  |
//|     * Validated replacement = PULLBACK entry: after the same      |
//|       momentum impulse, place a LIMIT order ~InpPullbackAtr ATR    |
//|       back TOWARD price and enter on the retrace, so the fill is   |
//|       better and the stop sits behind the pullback floor. On a    |
//|       diverse, low-correlation 29-instrument Deriv M15 basket     |
//|       this lifted the entry from 5/29 to 18/29 instruments        |
//|       positive (OOS), the only change in the whole study to do so.|
//|     * Take-profit = 3.0 ATR (let winners run) -- also validated.   |
//|     * Default universe WAS restricted (v1.1, Deriv M15 era) to    |
//|       crypto + indices; superseded by the v1.31 FTMO H1 whitelist.|
//|       Continuation worked on trending assets and LOST on the      |
//|       mean-reverting FX majors (that era's testing).              |
//|                                                                  |
//|   *** HONESTY -- this is an OBSERVE / MINIMUM-SIZE experiment, not |
//|   a proven money-maker. Even the validated pullback edge is small |
//|   and cost-fragile: ~break-even after realistic spread, negative  |
//|   at 2x cost, and it does NOT clear a deflated-Sharpe / walk-      |
//|   forward ship gate. Run on DEMO or minimum size with low-spread  |
//|   execution; only scale if it survives live. The author/EA never  |
//|   guarantees profit. See README.md / backtest/RESULTS.md. ***     |
//|                                                                  |
//|   v1.2 (2026-06): validated against REAL Deriv spread cost.       |
//|   At Deriv's actual spreads the pullback edge WAS POSITIVE net of |
//|   cost on a spread-gated set of majors (+0.044R, t+4, PF 1.11 OOS)|
//|   but a few wide-spread names (LTC, BCH, Mid Cap 400, etc.) lost. |
//|   So v1.2: (a) universe pruned to spread<=0.05 ATR/side majors,   |
//|   (b) a LIVE spread/ATR gate (InpMaxSpreadAtr) skips any symbol    |
//|   whose spread is too wide right now, (c) AVWAP OFF by default     |
//|   (it added no OOS edge). Still observe / minimum-size grade.      |
//|                                                                  |
//|   v1.21 (2026-07): EXIT-ENGINE FIDELITY (see docs/LIVE_TRADE_      |
//|   ANALYSIS_2026-07-01.md). Live was managing lock/trail per tick;  |
//|   the validated harness manages on working-timeframe bar close.   |
//|   InpManageOnBarClose=true, frozen signal-ATR, limit anchored to   |
//|   signal-bar close, per-symbol bar clocks, OnTimer heartbeat.      |
//|                                                                  |
//|   v1.22 (2026-07): P4 hygiene from the post-v1.21 review (see      |
//|   docs/CURSOR_BRIEF_2026-07-01.md §4): SKIP impulse sign aligned   |
//|   with SIGNAL, no-impulse log verbosity input, pending frozen-ATR  |
//|   sweep (broker-side expiry leak), barsClosed recomputed from the  |
//|   entry bar (multi-bar backfill), whitelist-orphan positions get   |
//|   a transient ATR handle, explicit datetime casts. NO change to    |
//|   the validated entry/exit semantics or the review-fix engine.     |
//+------------------------------------------------------------------+
//|                                                                  |
//|   v1.23 (2026-07-02): PURE BRACKET exits by default. The exit-    |
//|   ladder study (backtest/exit_ladder_study.py, 13 pre-registered  |
//|   variants, real Deriv cost, exact independent replication)       |
//|   showed the BE-lock+trail ladder TRUNCATED winners: bracket      |
//|   SL1/TP3/8-bar-time-exit lifts OOS expectancy +0.050->+0.078R,   |
//|   avg win 1.02->1.72R, trades>=+2R 7.5->16.6%, and 5x the 2x-cost |
//|   margin. Trade-off accepted: win rate ~39%, longer loss streaks. |
//|   InpUseLockTrail=true re-enables the old ladder for comparison.  |
//|                                                                  |
//|   v1.24 (2026-07-03): RAW-POINTS SPREAD CAP OFF BY DEFAULT        |
//|   (InpMaxSpreadPoints 200 -> 0). SYMBOL_SPREAD is quoted in       |
//|   POINTS, which scale with nominal price, so the 200-pt cap       |
//|   silently blocked 3 of the 12 validated symbols on EVERY scan:   |
//|   BTCUSD (median 2,424 pts yet the CHEAPEST cost/side at 0.0048   |
//|   ATR and the best backtest performer), ETHUSD (58,000 pts,       |
//|   0.0239) and Japan 225 (500 pts, 0.0348) — all of which PASS     |
//|   the validated gate. The backtest never modeled a points cap;    |
//|   InpMaxSpreadAtr (0.05 ATR/side) is the validated, price-scale-  |
//|   invariant cost filter and remains the load-bearing gate. Same   |
//|   raw-points bug class as Trading-EA PR #1.                       |
//+------------------------------------------------------------------+
#property copyright "Momentum pullback EA"
#property version   "1.33"
#property strict
#property description "Multi-symbol H1 momentum pullback EA v1.33-C1: bank 75% @ +1R, TP 1.5 ATR. Corrected-fidelity 100k confirmation passed; forward demo remains live validation. USDJPY 0.05% sleeve; trio 0.30%; v1.32 fidelity fixes ON; arms B1-B3 OFF."

// v1.33-C1r1: single source for the version tag used in prints and the panel.
// (#property description above cannot expand macros - keep it in sync manually.)
#define MPB_VERSION "v1.33-C1r3"

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/OrderInfo.mqh>

//--- Entry geometry --------------------------------------------------
enum ENUM_ENTRY_MODE
  {
   ENTRY_LIMIT_PULLBACK = 0,  // Pullback LIMIT back into the move (backtest-validated)
   ENTRY_MARKET         = 2   // v1.32 B1: Market at next bar open (research arm)
  };

//--- v1.32 B2: exit mode (validated bracket vs uncapped runner) -------
enum ENUM_EXIT_MODE_V132
  {
   EXIT_BRACKET_V130    = 0,  // validated SL/TP/time bracket
   EXIT_UNCAPPED_RUNNER = 1   // no TP; exit on opposite impulse or backstop bars
  };

//--- v1.32 B3: stop evaluation (touch vs bar close) -------------------
enum ENUM_STOP_EVAL_V132
  {
   STOP_EVAL_TOUCH     = 0,   // validated: broker SL touched intrabar
   STOP_EVAL_BAR_CLOSE = 1    // stop evaluated on bar close; broker holds a disaster backstop
  };

//--- Symbol universe -------------------------------------------------
input group "=== Symbol Universe ==="
input string InpSymbolWhitelistV131 = "US30.cash,US100.cash,JP225.cash,USDJPY";  // v1.31 confirmed H1 portfolio. Versioned so saved trio-only input cannot survive.
#define InpSymbolWhitelist InpSymbolWhitelistV131
input string InpSyntheticBlock   = "Volatility,Crash,Boom,Step,Jump,Range Break,Vol over,Hybrid,Drift,DEX,Multi Step,Skew,1HZ,Basket"; // Skip names containing any of these

//--- Strategy --------------------------------------------------------
input group "=== Candle Filter (retained signal definition; parity-corrected 2026-07-12) ==="
input bool   InpCandleFilter    = true;  // W2 remains the forward-test signal definition; its old post-hoc expectancy claim was overturned by live-parity enumeration.
input double InpMinAdvWickAtr   = 0.30;  // Adverse-wick threshold in frozen signal ATR (0.30 = W2; 0 = off)

input group "=== Momentum Strategy ==="
input ENUM_TIMEFRAMES InpTimeframeV131 = PERIOD_H1; // Confirmed H1 working timeframe; versioned to supersede saved M15 values
#define InpTimeframe InpTimeframeV131
input int    InpMomentumBars     = 6;     // Lookback bars for the move
input double InpMomentumAtrMult  = 2.0;   // Move must be >= this many ATRs to count as "rapid"
input int    InpAtrPeriod        = 14;    // ATR period
input bool   InpTradeBothSides   = true;  // Trade rallies too (false = only falling assets -> sells)

//--- Pending entry ---------------------------------------------------
input group "=== Pending Entry ==="
input ENUM_ENTRY_MODE InpEntryMode = ENTRY_LIMIT_PULLBACK; // Entry geometry (PULLBACK = validated; MARKET = v1.32 B1 research arm)
input double InpPullbackAtr        = 0.6;  // PULLBACK mode: place the LIMIT this many ATR back toward price
input int    InpPendingExpiryBars  = 3;    // Retains v1.29.1's measured live w4 behavior (Bars() omits placement bar); v1.30 retest assumes w4

//--- Risk / exits ----------------------------------------------------
input group "=== Risk & Exits ==="
input double InpRiskPercent      = 0.3;   // Corrected-engine MC sizing; current FTMO chart already uses 0.3%
input double InpUSDJPYRiskPercentV131 = 0.05; // Confirmed USDJPY sleeve; dynamic cash risk, not a fixed lot size
input double InpStopAtrMult      = 1.0;   // Initial stop distance (ATR) - tight = fast loss cut
input double InpTakeProfitAtrMultV133 = 1.5;  // v1.33 C1: TP 1.5 ATR. Renamed again so chart-saved V130=2.0 cannot survive. Revert to 2.0 to restore v1.31 behavior
#define InpTakeProfitAtrMultV130 InpTakeProfitAtrMultV133
input bool   InpUsePartialCloseV130   = true; // Corrected-engine finalist: bank one partial, then leave the remainder on its bracket
input double InpPartialCloseFractionV133 = 0.75; // v1.33 C1: bank 75% at the trigger (E3 ran 0.67; v1.31 ran 0.50). Renamed so chart-saved V130 values cannot survive. Revert to 0.50 for v1.31 behavior
#define InpPartialCloseFractionV130 InpPartialCloseFractionV133
input double InpPartialCloseAtRV130   = 1.0;  // Trigger in initial R, using frozen signal ATR * InpStopAtrMult
input int    InpPartialRetrySecondsV130 = 30; // Reconcile before a bounded retry after a transient server result
input int    InpMaxHoldingBars   = 8;     // Force-close a stagnant trade after N closed bars (0 = off)

//--- Portfolio risk --------------------------------------------------
input group "=== Portfolio Risk ==="
input int    InpMaxConcurrent    = 2;     // Max simultaneous open positions (all symbols)
input int    InpMaxTradesPerDay  = 8;    // Max new trades opened per day (all symbols)
input double InpDailyLossLimitPct= 4.0;   // Halt for the day after this daily loss (% of day-start balance)
input double InpMaxDrawdownPct   = 8.0;  // Halt if equity drawdown from peak exceeds this (v1.26: HARD halt - survives day rollover; peak persisted across re-inits)
input double InpInitialBalance   = 100000.0; // v1.26: initial balance anchoring the STATIC floor below (0 = auto-capture first-seen balance into a terminal global)
input double InpStaticFloorPct   = 9.0;   // v1.26: HARD halt if equity <= initial*(1 - this%). Buffer inside FTMO's 10% breach line; the trailing check above cannot see across re-inits without it. 0 = off.
input int    InpMaxConsecLosses  = 4;     // Pause for the day after this many losses in a row
input double InpMaxSpreadAtr      = 0.05;  // v1.2 KEY GATE: skip if current spread > this many ATR PER SIDE (0.05 = validated ceiling; the edge dies above it, e.g. LTC/BCH/Mid Cap). 0 = off.
// P3 (brief §4): correlation-aware concurrency - ON by compiled default (1 seat per
// cluster, spec on the next line: US30|US100 share one seat; JP225 and USDJPY are
// independent). 0 disables. Originally shipped OFF pending the acceptance study;
// Day-1 saw 4 same-direction Tech-100-cluster entries in 70 min stacking ~1.5%
// correlated heat. NOTE: a chart-saved value under this (unversioned) input name
// overrides the compiled default.
input int    InpMaxPerCluster    = 1;     // Max open+pending per correlation cluster (0 = off; compiled default 1 = ON)
input string InpClusterSpecV131  = "US30.cash|US100.cash;JP225.cash;USDJPY";  // US pair shares a seat; JP225 and USDJPY are independent
#define InpClusterSpec InpClusterSpecV131

//--- Execution -------------------------------------------------------
input group "=== Execution ==="
input long   InpMagicNumber      = 771025;// Magic number tagging this EA's orders
input ulong  InpDeviationPoints  = 30;    // Max slippage in points
input string InpTradeComment     = "MomPullback";   // broker-visible on EVERY order. Deliberately avoids "scalp" (FTMO polices tick-scalping) and any other broker's name.
input int    InpHeartbeatSeconds = 5;     // OnTimer scan/manage heartbeat (0 = chart ticks only)
input bool   InpLogNoImpulse     = false; // Log routine impulse/candle rejection lines (gate/data skips are always logged)

input group "=== v1.32 Execution Fidelity (Part A fixes; default ON, zero strategy-semantics change) ==="
input bool   InpPartialBarCatchupV132 = true; // A1(c): bar-extreme catch-up trigger for the +1R partial (a touch between heartbeats still banks)
input int    InpEntryMaxRetriesV132   = 3;    // A6: extra resends after a price-class rejection (10015/10004/10020/10021) while the signal bar is still bar 1 (0 = v1.31 behavior)

input group "=== v1.32 Research Arms (default OFF; pre-registered forward arms) ==="
input ENUM_EXIT_MODE_V132 InpExitModeV132 = EXIT_BRACKET_V130; // B2: validated bracket vs UNCAPPED RUNNER (opposite-impulse exit; NEW positions only)
input int    InpRunnerMaxBarsV132    = 45;  // B2: runner backstop time exit in closed bars (HARVEST: 45 bars; 0 = off)
input bool   InpRunnerReverseV132    = false; // B2: also open the opposite trade on the runner exit signal (normal scan + exit-bar cooldown govern)
input ENUM_STOP_EVAL_V132 InpStopEvalV132 = STOP_EVAL_TOUCH;  // B3: validated touch stop vs bar-close stop (NEW positions only)
input double InpDisasterStopMultV132 = 3.0; // B3: broker-side disaster stop (ATR) when bar-close mode; the intended InpStopAtrMult stop stays the R denominator

input group "=== v1.25 Hardening (protective GATES + observability; validated entry/exit engine UNCHANGED) ==="
// Zero-regret, ON by default: they never remove a VALID trade, only broken-data trades, and add logging.
input bool   InpFreshnessGuard   = true;  // Block NEW entries on stale ticks / invalid quotes (pure safety; never in a validated backtest but a trade on frozen data is pure risk)
input int    InpMaxTickAgeSec     = 60;    // Max age (s) of the latest tick before a symbol is considered frozen (catches dead feeds, not normal illiquid gaps)
input bool   InpTradeLog          = true;  // Write a per-trade CSV (MFE/MAE in R, spread@entry, exit reason) = the doc's "post-trade learning" data. Pure observability.
input string InpTradeLogFile      = "MomentumPullback_trades.csv";
input string InpPartialLogFileV130= "MomentumPullback_partials_v130.csv"; // Actual partial fill + level-vs-fill slippage
// Protective but it DOES alter the validated trade distribution. InpNewsBlockMins
// defaults ON at 3 min (conservative FTMO-evaluation guard - see its own comment).
input int    InpNewsBlockMins     = 3;     // Protective entry block is ON; evaluation accounts allow news, but this conservative gate remains chart-compatible. 0=off.

input group "=== v1.28 Thought-Process Panel (observability only) ==="
input bool   InpShowPanel         = true;  // On-chart panel: per-symbol scan verdicts, trade state, risk ledger
input int    InpPanelRefreshSec   = 10;    // Panel refresh throttle (never per-tick)

//--- Globals ---------------------------------------------------------
CTrade        trade;
CPositionInfo posInfo;
COrderInfo    ordInfo;

string g_symbols[];      // Tradable, non-synthetic symbols
datetime g_lastScanBar[];// Per-symbol last processed bar (own bar clock, not chart symbol)

// Pending order ticket -> signal-bar ATR frozen at placement (transferred on fill).
// The RAM cache is mirrored to terminal global variables so a restart while an
// order is working cannot replace signal-time geometry with fill-time ATR.
struct PendingSigAtr { ulong orderTicket; double atr; };
PendingSigAtr g_pendingSigAtr[];

enum ENUM_PARTIAL_STATE
  {
   PARTIAL_ARMED     = 0,
   PARTIAL_TRIGGERED = 1,
   PARTIAL_DONE      = 2,
   PARTIAL_SKIPPED   = 3
  };
#define V130_PARTIAL_MAX_ATTEMPTS 5

// Open position metadata for bar-close management (keyed by POSITION_IDENTIFIER).
struct PositionMgmtState
  {
   long     positionId;
   double   signalAtr;
   datetime entryBarTime;
   datetime lastMgmtBarTime;
   int      barsClosed;
   // v1.25 trade-log fields (observability only; never read by the entry/exit engine)
   double   entryPrice;
   double   riskPrice;     // initial stop distance in price (= InpStopAtrMult * signalAtr) -> R denominator
   int      dir;           // +1 buy, -1 sell
   double   spreadAtrEntry;// spread/ATR/side at fill
   double   mfeR;          // max favorable excursion (R), sampled each heartbeat
   double   maeR;          // max adverse excursion (R)
   // v1.30 partial-close lifecycle (all geometry derives from frozen signal ATR).
   double   initialVolume;
   bool     signalAtrFrozen;
   double   partialTargetVolume;
   double   partialLevel;
   int      partialState;
   datetime partialNextRetry;
   int      partialAttempts;
   // v1.32 A1: RAM-only partial-trigger bookkeeping (not persisted; worst case after a
   // restart is one repeated log line, never a trade decision).
   bool     partialGapSeen;      // a market-closed/no-connection gap happened while TRIGGERED
   string   partialTriggerTag;   // "bar-catchup" when the A1(c) catch-up armed the trigger
   // v1.32 A9: false while the entry-bar anchor could not be resolved (unsynced history);
   // an unseeded bar clock is never incremented - the recompute is retried each bar close.
   bool     barClockSeeded;
   // v1.32 B2/B3: which research arm this position was PLACED under (stamped at the first
   // DEAL_ENTRY_IN, persisted via GV; positions already open at attach keep bracket/touch).
   bool     runnerV132;
   bool     barCloseStopV132;
  };
PositionMgmtState g_posState[];

datetime g_currentDay  = 0;
double   g_dayStartBalance = 0.0;
double   g_peakEquity  = 0.0;
int      g_tradesToday = 0;
long     g_fillPosIdsToday[];   // v1.32 A4: distinct DEAL_POSITION_IDs already counted toward the daily fill cap (reset at day rollover)
bool     g_halted      = false;   // daily-loss pause: cleared at day rollover
bool     g_haltedHard  = false;   // v1.26: max-DD / static-floor halt - NEVER auto-cleared
double   g_initialBalance = 0.0;  // v1.26: static-floor anchor
datetime g_initTime       = 0;    // v1.26.1: for the one-shot ledger re-sync below
bool     g_ledgerResynced = false;// v1.26.1: deal history syncs AFTER a cold start; re-read once
bool     g_ledgerValid    = false;// v1.29.1: false until a restore ran on SYNCED account data
bool     g_hedgingOk      = false;// v1.33-C1r3: entries blocked until a SYNCED account
bool     g_hedgingChecked = false;// confirms RETAIL_HEDGING (deferred OnInit race fix)
// v1.27 parity: Wilder ATR cache (one compute per symbol per closed bar) and the
// per-symbol exit-bar cooldown (engine never signals on the bar a trade exited).
double   g_wAtrCache[];
datetime g_wAtrCacheBar[];
datetime g_noSignalUpTo[];
// v1.28 panel: last scan verdict per symbol (display only)
string   g_lastVerdict[];
datetime g_lastVerdictT[];

//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetMarginMode();
   trade.LogLevel(LOG_LEVEL_ERRORS);

   if(InpRiskPercent <= 0.0 || InpUSDJPYRiskPercentV131 <= 0.0 ||
      InpUSDJPYRiskPercentV131 > InpRiskPercent)
     {
      Print("v1.31 invalid risk inputs: base and USDJPY risk must be positive, and USDJPY must not exceed base risk");
      return(INIT_PARAMETERS_INCORRECT);
     }

   if(InpUsePartialCloseV130)
     {
      if(InpPartialCloseFractionV130 <= 0.0 || InpPartialCloseFractionV130 >= 1.0 ||
         InpPartialCloseAtRV130 <= 0.0)
        {
         Print("v1.30 invalid partial-close inputs: fraction must be in (0,1) and trigger R > 0");
         return(INIT_PARAMETERS_INCORRECT);
        }
      // v1.33-C1r3 HOTFIX: the hedging-mode check is DEFERRED to the first synced
      // heartbeat (v1.29.1 ledger pattern). The old hard-refuse here raced account
      // sync - ACCOUNT_LOGIN syncs before ACCOUNT_MARGIN_MODE, so a cold start could
      // read netting(0) on a hedging account and leave the EA dead on the chart
      // (observed live 2026-07-21 09:27:33). g_hedgingOk gates ENTRIES only;
      // management of any existing positions always runs.
     }

   if(!BuildSymbolUniverse())
     {
      Print("No tradable non-synthetic symbols found. Add symbols to Market Watch.");
      return(INIT_FAILED);
     }

   RestorePendingSigAtrFromLiveOrders();

   // v1.32 A7: one-shot migration of the legacy terminal-global ledger anchors into the
   // magic-scoped names (preserves the live ledger on upgrade; legacy GVs are NOT deleted).
   if(!GlobalVariableCheck(PeakEquityGv()) && GlobalVariableCheck("MPB_peak_equity"))
      GlobalVariableSet(PeakEquityGv(), GlobalVariableGet("MPB_peak_equity"));
   if(!GlobalVariableCheck(InitBalanceGv()) && GlobalVariableCheck("MPB_init_balance"))
      GlobalVariableSet(InitBalanceGv(), GlobalVariableGet("MPB_init_balance"));

   RestoreRiskLedger();   // v1.26: reconstruct today's ledger from deal history - a mid-day
                          // re-init must NOT re-arm a fresh daily budget (audit P1)
   g_initTime = TimeCurrent();   // v1.26.1: history may still be syncing; re-run once in ~60s

   // Per-symbol bar clocks: skip mid-bar rescan after reload (see LIVE_TRADE_ANALYSIS §1).
   ArrayResize(g_lastScanBar, ArraySize(g_symbols));
   for(int i = 0; i < ArraySize(g_symbols); i++)
      g_lastScanBar[i] = (datetime)iTime(g_symbols[i], InpTimeframe, 0);

   if(InpHeartbeatSeconds > 0)
      EventSetTimer(InpHeartbeatSeconds);

   PanelInit();   // v1.28 (no-op when InpShowPanel=false)
   bool panelReady = !InpShowPanel ||
                     (ObjectFind(0, "MPBPANEL_BG") >= 0 && ObjectFind(0, "MPBPANEL_L0") >= 0);
   PrintFormat("Panel " + MPB_VERSION + " initialized: requested=%s ready=%s",
               InpShowPanel ? "yes" : "no", panelReady ? "yes" : "no");

   // Register any positions already open (e.g. after EA reload).
   SyncOpenPositionStates();

   // v1.27: print the Wilder ATR per symbol at init (cross-checkable against the
   // Python engine on the same bars; also proves the estimator is alive).
   for(int i = 0; i < ArraySize(g_symbols); i++)
     {
      double wa = 0.0;
      // v1.33-C1r1: only print when the estimator succeeded and wa > 0 - dividing the
      // wick sizes by a failed (0.0) ATR filled the CandleParity line with inf garbage
      // during a cold start with unsynced history, defeating the cross-check.
      if(!WilderAtrForSymbol(g_symbols[i], wa) || wa <= 0.0)
         continue;
      PrintFormat("Wilder ATR(%d) %s = %.5f", InpAtrPeriod, g_symbols[i], wa);
      // v1.29: wick-parity line (verify vs Python candle_features on same bars)
      string ps = "";
      for(int sh = 1; sh <= 3; sh++)
        {
         double o1 = iOpen(g_symbols[i], InpTimeframe, sh), c1 = iClose(g_symbols[i], InpTimeframe, sh);
         double h1 = iHigh(g_symbols[i], InpTimeframe, sh), l1 = iLow(g_symbols[i], InpTimeframe, sh);
         if(h1 <= 0.0)
            continue;
         ps += StringFormat("sh%d up=%.5f dn=%.5f | ", sh,
                            (h1 - MathMax(o1, c1)) / wa, (MathMin(o1, c1) - l1) / wa);
        }
      PrintFormat("CandleParity %s: %s", g_symbols[i], ps);
     }

   PrintFormat("MomentumPullbackEA " + MPB_VERSION + " ready. Entry=%s. Exits=%s + TP%.2f/time. Scanning %d symbols on %s. Base risk=%.2f%%; USDJPY risk=%.2f%%. v1.32 arms: exit=%s stopEval=%s (defaults OFF = v1.31 behavior).",
               (InpEntryMode == ENTRY_LIMIT_PULLBACK ? "PULLBACK(limit)" :
                (InpEntryMode == ENTRY_MARKET ? "MARKET(research)" : "BREAKOUT(stop)")),
               (InpUsePartialCloseV130 ? StringFormat("bank %.0f%% @ +%.2fR", 100.0 * InpPartialCloseFractionV130, InpPartialCloseAtRV130)
                                       : "partial OFF"),
               InpTakeProfitAtrMultV130,
               ArraySize(g_symbols), EnumToString(InpTimeframe), InpRiskPercent,
               InpUSDJPYRiskPercentV131,
               (InpExitModeV132 == EXIT_UNCAPPED_RUNNER ? "UNCAPPED_RUNNER" : "bracket"),
               (InpStopEvalV132 == STOP_EVAL_BAR_CLOSE ? "bar-close" : "touch"));
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   PanelDestroy();   // v1.28
   if(InpHeartbeatSeconds > 0)
      EventKillTimer();
  }

//+------------------------------------------------------------------+
//| Build the list of tradable, non-synthetic symbols                |
//+------------------------------------------------------------------+
bool BuildSymbolUniverse()
  {
   ArrayResize(g_symbols, 0);

   string candidates[];
   if(StringLen(InpSymbolWhitelist) > 0)
     {
      int n = StringSplit(InpSymbolWhitelist, StringGetCharacter(",", 0), candidates);
      for(int i = 0; i < n; i++)
        {
         string s = Trim(candidates[i]);
         if(StringLen(s) > 0)
            AddSymbol(s);
        }
     }
   else
     {
      Print("InpSymbolWhitelist is empty - no symbols to trade.");
     }
   return(ArraySize(g_symbols) > 0);
  }

//+------------------------------------------------------------------+
//| Add a symbol to the universe if it is real + tradable            |
//+------------------------------------------------------------------+
void AddSymbol(string symbol)
  {
   if(IsSynthetic(symbol))
      return;
   if(!SymbolSelect(symbol, true))
      return;
   // Must be fully tradable (not disabled / close-only)
   long mode = SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
   if(mode != SYMBOL_TRADE_MODE_FULL)
      return;

   int idx = ArraySize(g_symbols);
   ArrayResize(g_symbols, idx + 1);
   ArrayResize(g_wAtrCache, idx + 1);      // v1.27
   ArrayResize(g_wAtrCacheBar, idx + 1);
   ArrayResize(g_noSignalUpTo, idx + 1);
   ArrayResize(g_lastVerdict, idx + 1);    // v1.28 panel
   ArrayResize(g_lastVerdictT, idx + 1);
   g_symbols[idx]   = symbol;
   g_wAtrCache[idx] = 0.0;
   g_wAtrCacheBar[idx] = 0;
   g_noSignalUpTo[idx] = 0;
   g_lastVerdict[idx] = "";     // v1.28 panel
   g_lastVerdictT[idx] = 0;
  }

//+------------------------------------------------------------------+
//| True if the symbol name matches the synthetic blocklist          |
//+------------------------------------------------------------------+
bool IsSynthetic(string symbol)
  {
   string keys[];
   int n = StringSplit(InpSyntheticBlock, StringGetCharacter(",", 0), keys);
   string up = symbol;
   StringToUpper(up);
   for(int i = 0; i < n; i++)
     {
      string k = Trim(keys[i]);
      if(StringLen(k) == 0)
         continue;
      StringToUpper(k);
      if(StringFind(up, k) >= 0)
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
string Trim(string s)
  {
   StringTrimLeft(s);
   StringTrimRight(s);
   return(s);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // v1.26/v1.32: the 5s OnTimer heartbeat already runs the full pipeline (scans are
   // bar-gated; the v1.30 partial and A2 time exit are heartbeat-checked), so per-tick
   // execution adds only redundant load (incl. full-day HistorySelect) on a 24/7 host
   // chart. Ticks drive the pipeline only when the heartbeat is off (0).
   if(InpHeartbeatSeconds > 0)
      return;
   Heartbeat();
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   Heartbeat();
  }

//+------------------------------------------------------------------+
//| Day rollover, position management, and per-symbol entry scans.   |
//| OnTimer keeps this alive when the chart symbol's market closes.  |
//+------------------------------------------------------------------+
void Heartbeat()
  {
   datetime today = DayStart(TimeCurrent());
   if(today != g_currentDay)
      ResetDailyState();

   // v1.29.1: no trading decisions (incl. halt-driven pending cancels) until the
   // ledger has been restored from SYNCED account data. Broker-side brackets
   // protect any open position during the seconds this can last.
   if(!g_ledgerValid)
     {
      RestoreRiskLedger();
      if(!g_ledgerValid)
         return;
     }
   // v1.26.1: cold-start deal history arrives seconds AFTER OnInit; the first ledger
   // reconstruction can miss late-synced deals (observed: $495 short 5s after launch).
   // Re-run ONCE after the feed has settled; idempotent full recount.
   if(!g_ledgerResynced && g_initTime > 0 && TimeCurrent() - g_initTime >= 60)
     {
      g_ledgerResynced = true;
      RestoreRiskLedger();
     }
   // v1.33-C1r3: deferred hedging check on SYNCED data (g_ledgerValid guarantees
   // bal/eq > 0 = the account has reported real state, so ACCOUNT_MARGIN_MODE is
   // authoritative here). One-time: hedging -> entries enabled; netting -> entries
   // permanently blocked with a loud refusal, but management still runs.
   if(!g_hedgingChecked)
     {
      g_hedgingChecked = true;
      g_hedgingOk = ((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)
                     == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
      if(!g_hedgingOk)
         Print("v1.30 partial close requires a hedging account; ENTRIES DISABLED on this netting/exchange-mode account (management still active)");
     }
   ManageAll();
   ScanAllOnNewBars();
   PanelUpdate();   // v1.28: display only, throttled, fails soft
   DecisionCsvMaybe();   // v1.33-C1r1: decoupled from the panel input/throttle (self-gated to one row per closed bar)
  }

//+------------------------------------------------------------------+
//| Scan each symbol once per closed bar on that symbol's own clock. |
//+------------------------------------------------------------------+
void ScanAllOnNewBars()
  {
   UpdatePeakEquity();
   // v1.33-C1r3 (C14 fix): evaluate the HARD lines (static floor / max-DD) BEFORE any
   // early return so a floor/DD breach latches g_haltedHard even while a daily-loss halt
   // is already active (the old g_halted early-return could skip the hard latch until day
   // rollover, and it never latched at all if equity recovered before rollover). Same
   // single CancelAllPendings per trip: the !g_haltedHard guards prevent re-latching.
   if(!g_haltedHard && StaticFloorBreached()) { g_haltedHard = true; CancelAllPendings("static-floor halt"); Print("STATIC FLOOR hit (equity at/below initial - floor%) - HARD halted."); }
   if(!g_haltedHard && DrawdownExceeded())    { g_haltedHard = true; CancelAllPendings("max-drawdown halt"); Print("Max drawdown hit - HARD halted (survives day rollover)."); }
   if(!g_halted && !g_haltedHard && DailyLossExceeded()){ g_halted = true; CancelAllPendings("daily-loss halt"); Print("Daily loss limit hit - paused for the day."); }

   // v1.33-C1r3 (C12 fix): entries may be blocked, but the bar CLOCK is consumed in the
   // loop regardless, so a gate that clears mid-bar (live case: the consec-loss streak
   // ending when a winning position closes) can never make the next heartbeat scan a
   // STALE bar mid-bar with a signal-close anchor up to ~55 min old (was: pre-loop
   // returns skipped the clock). On a non-halted heartbeat blockEntries is false and the
   // loop is byte-identical to the validated engine.
   bool blockEntries = g_halted || g_haltedHard || !g_hedgingOk
                       || (InpMaxConsecLosses > 0 && ConsecutiveLossesToday() >= InpMaxConsecLosses)
                       || (g_tradesToday >= InpMaxTradesPerDay);

   for(int i = 0; i < ArraySize(g_symbols); i++)
     {
      datetime barTime = (datetime)iTime(g_symbols[i], InpTimeframe, 0);
      if(barTime == 0)              // history not synchronized yet - don't corrupt the clock
         continue;
      if(g_lastScanBar[i] == 0)     // unseeded (symbol had no data at init): seed WITHOUT scanning
        {
         g_lastScanBar[i] = barTime;
         continue;
        }
      if(barTime == g_lastScanBar[i])
         continue;
      g_lastScanBar[i] = barTime;   // consume the bar even when blocked/at-capacity (match
                                    // validated-era behavior: signals are dropped, never
                                    // scanned late mid-bar)
      if(blockEntries)
         continue;
      if(CountOpenAndPending() >= InpMaxConcurrent)
         continue;

      ScanSymbol(g_symbols[i]);
     }
  }

//+------------------------------------------------------------------+
//| Transfer signal ATR from pending fill to position state.           |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   if(!HistoryDealSelect(trans.deal))
      return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagicNumber)
      return;
   long dealEntry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   long posId = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   string symbol = HistoryDealGetString(trans.deal, DEAL_SYMBOL);

   if(dealEntry == DEAL_ENTRY_IN)
     {
      // v1.32 A4: the daily cap counts DISTINCT positions, not broker fill fragments
      // (a fragmented entry order emits several DEAL_ENTRY_IN rows for ONE trade).
      // v1.27 B3: the daily cap counts FILLS (engine parity; placements were miscounting).
      bool seenFill = false;
      for(int f = 0; f < ArraySize(g_fillPosIdsToday); f++)
         if(g_fillPosIdsToday[f] == posId)
           {
            seenFill = true;
            break;
           }
      if(!seenFill)
        {
         int nf = ArraySize(g_fillPosIdsToday);
         ArrayResize(g_fillPosIdsToday, nf + 1);
         g_fillPosIdsToday[nf] = posId;
         g_tradesToday++;
        }
      ulong orderTicket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER);
      datetime dealTime = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
      // Peek, do not consume: a partially filled entry order can retain a live
      // residual. Its placement ATR must remain restart-safe until the order is
      // terminal; SweepStalePendingSigAtr performs terminal cleanup.
      double sigAtr = PeekPendingSigAtr(orderTicket);
      bool sigAtrFrozen = (sigAtr > 0.0);
      int existingState = FindPositionState(posId);
      if(sigAtr <= 0.0 && existingState >= 0 && g_posState[existingState].signalAtr > 0.0)
        {
         // A broker may fragment one entry order into several DEAL_ENTRY_IN rows.
         // Never let a later fragment's fill-time fallback replace the first
         // fragment's authoritative signal ATR.
         sigAtr = g_posState[existingState].signalAtr;
         sigAtrFrozen = g_posState[existingState].signalAtrFrozen;
        }
      if(sigAtr <= 0.0)
         ReadAtrForSymbol(symbol, sigAtr);
      RegisterPositionState(posId, symbol, sigAtr, dealTime, sigAtrFrozen);
      // v1.25: freeze entry context for the trade log
      int si = FindPositionState(posId);
      if(si >= 0)
        {
         // v1.32 B2/B3: stamp the research arm this position was PLACED under (only NEW
         // fills pass through here; positions already open at attach keep the validated
         // bracket/touch semantics). Persisted so a restart keeps the arm.
         g_posState[si].runnerV132 = (InpExitModeV132 == EXIT_UNCAPPED_RUNNER);
         g_posState[si].barCloseStopV132 = (InpStopEvalV132 == STOP_EVAL_BAR_CLOSE);
         if(g_posState[si].runnerV132)
            GlobalVariableSet(PositionRunnerGv(posId), 1.0);
         if(g_posState[si].barCloseStopV132)
            GlobalVariableSet(PositionBarStopGv(posId), 1.0);
         double histEntry = 0.0, histInVol = 0.0;
         int histDir = 0;
         if(PositionHistoryEntryContext(posId, histEntry, histDir, histInVol))
           {
            g_posState[si].entryPrice = histEntry; // volume-weighted across fragmented entry fills
            g_posState[si].dir = histDir;
           }
         else
           {
            g_posState[si].entryPrice = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
            g_posState[si].dir = (HistoryDealGetInteger(trans.deal, DEAL_TYPE) == DEAL_TYPE_BUY) ? 1 : -1;
           }
         // v1.32 A5: the R denominator is the ACTUAL placed stop distance (placement
         // clamps to stopsLevel*1.5 and snaps to the tick grid, so the input-based value
         // drifts when the clamp binds). In B3 bar-close-stop mode the placed SL is only
         // a disaster backstop - the intended stop stays the R denominator there.
         double actualSL = 0.0;
         ulong a5ticket = 0; string a5symbol = ""; double a5vol = 0.0;
         if(!g_posState[si].barCloseStopV132 && FindOpenPositionById(posId, a5ticket, a5symbol, a5vol))
            actualSL = posInfo.StopLoss();   // FindOpenPositionById leaves posInfo bound to this position
         if(actualSL > 0.0 && g_posState[si].entryPrice > 0.0)
            g_posState[si].riskPrice = MathAbs(g_posState[si].entryPrice - actualSL);
         else
            g_posState[si].riskPrice = (g_posState[si].signalAtr > 0.0) ? InpStopAtrMult * g_posState[si].signalAtr : 0.0;
         double inVol = 0.0, outVol = 0.0;
         double priorTargetVolume = g_posState[si].partialTargetVolume;
         if(PositionHistoryVolumes(posId, inVol, outVol) && inVol > g_posState[si].initialVolume)
            g_posState[si].initialVolume = inVol;
         RefreshPartialGeometry(si, symbol);
         double vstep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
         if(g_posState[si].partialState == PARTIAL_SKIPPED &&
            priorTargetVolume <= 0.0 && g_posState[si].partialTargetVolume > 0.0)
            SetPartialState(si, PARTIAL_ARMED, "entry fill made the partial-close target volume feasible");
         else if(g_posState[si].partialState == PARTIAL_DONE &&
            g_posState[si].partialTargetVolume > 0.0 &&
            outVol + 0.5 * vstep < g_posState[si].partialTargetVolume)
            SetPartialState(si, PARTIAL_TRIGGERED, "entry fill increased the partial-close target; closing the remainder");
         PersistPartialState(si);
         double pt = SymbolInfoDouble(symbol, SYMBOL_POINT);
         double sprPrice = (double)SymbolInfoInteger(symbol, SYMBOL_SPREAD) * pt;
         g_posState[si].spreadAtrEntry = (g_posState[si].signalAtr > 0.0) ? 0.5 * sprPrice / g_posState[si].signalAtr : 0.0;
        }
      return;
     }

   // v1.32 A3: DEAL_ENTRY_OUT_BY (close-by) and DEAL_ENTRY_INOUT (reversal) are full/
   // partial closes too - ConsecutiveLossesToday already counted OUT_BY, so the ledger
   // was inconsistent when these got no cooldown and no LogClosedTrade.
   if(dealEntry == DEAL_ENTRY_OUT || dealEntry == DEAL_ENTRY_OUT_BY || dealEntry == DEAL_ENTRY_INOUT)
     {
      // v1.30: DEAL_ENTRY_OUT can be the +1R partial. Classify from cumulative
      // position volumes (not event ordering: MetaQuotes does not guarantee it).
      int psi = FindPositionState(posId);
      if(psi < 0)
        {
         ulong ot = 0; string os = ""; double ov = 0.0;
         if(FindOpenPositionById(posId, ot, os, ov))
           {
            RegisterPositionState(posId, os, 0.0,
                                  (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME));
            psi = FindPositionState(posId);
           }
        }
      double entryVol = 0.0, exitVol = 0.0;
      bool haveVolumes = PositionHistoryVolumes(posId, entryVol, exitVol);
      double vstep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
      bool isPartialExit = haveVolumes && entryVol > 0.0 &&
                           exitVol + 0.5 * vstep < entryVol;
      if(isPartialExit)
        {
         if(psi >= 0)
           {
            if(entryVol > g_posState[psi].initialVolume)
               g_posState[psi].initialVolume = entryVol;
            RefreshPartialGeometry(psi, symbol);
            if(g_posState[psi].partialTargetVolume > 0.0 &&
               exitVol + 0.5 * vstep >= g_posState[psi].partialTargetVolume)
               SetPartialState(psi, PARTIAL_DONE, "executed target volume");
            else
               SetPartialState(psi, PARTIAL_TRIGGERED, "partial execution awaiting target remainder");
           }
         LogPartialDeal(trans.deal, posId, symbol);
         return; // partial is NOT a completed trade: no cooldown, full log, or streak event
        }

      // v1.27 B5: forbid signals on the engine-equivalent exit bar. Broker SL/TP
      // fire INTRABAR (exit bar = current bar, shift 0); the EA time exit fires at
      // the OPEN of the bar after the engine exit bar (shift 1).
      int xidx = SymbolIndex(symbol);
      if(xidx >= 0)
        {
         long xreason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
         int sh = (xreason == DEAL_REASON_EXPERT) ? 1 : 0;
         datetime xb = (datetime)iTime(symbol, InpTimeframe, sh);
         if(xb > g_noSignalUpTo[xidx])
            g_noSignalUpTo[xidx] = xb;
        }
      // Full close only. Any preceding partial is aggregated by LogClosedTrade.
      if(InpTradeLog)
         LogClosedTrade(trans.deal, posId, symbol);
     }
  }

//+------------------------------------------------------------------+
//| v1.25 helpers: broken-data guard, hour/news blocks, trade log.    |
//| None of these touch the validated momentum entry or the SL/TP/    |
//| time bracket - they only GATE new entries or RECORD outcomes.     |
//+------------------------------------------------------------------+
bool QuotesFresh(string symbol)
  {
   MqlTick tk;
   if(!SymbolInfoTick(symbol, tk))
      return(false);
   if(tk.bid <= 0.0 || tk.ask <= 0.0 || tk.ask < tk.bid)
      return(false);
   if(InpMaxTickAgeSec > 0 && (long)(TimeCurrent() - tk.time) > InpMaxTickAgeSec)
      return(false);
   return(true);
  }

bool NewsSoonForCurrency(string ccy, datetime now, int win)
  {
   MqlCalendarValue vals[];
   // v1.26: CalendarValueHistory returns bool, NOT a count (audit P1: the old int
   // assignment inspected at most vals[0] and crashed on true-with-empty-array).
   if(!CalendarValueHistory(vals, now - win, now + win, NULL, ccy))
     {
      // v1.33-C1r1: calendar unavailable (disabled in terminal settings / never synced /
      // unsupported feed) means the news guard is silently inoperative - warn once per
      // hour so the operator knows. Behavior unchanged: still fail-open (no block).
      static datetime s_calWarn = 0;
      if(TimeCurrent() - s_calWarn >= 3600)
        {
         s_calWarn = TimeCurrent();
         PrintFormat("WARNING: CalendarValueHistory failed for %s (err %d) - news guard INOPERATIVE for this currency (entries are NOT news-blocked)",
                     ccy, GetLastError());
        }
      return(false);
     }
   int cnt = ArraySize(vals);
   for(int i = 0; i < cnt; i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(vals[i].event_id, ev))
         continue;
      if(ev.importance == CALENDAR_IMPORTANCE_HIGH)
         return(true);
     }
   return(false);
  }

bool NewsSoon(string symbol)
  {
   int win = InpNewsBlockMins * 60;
   if(win <= 0)
      return(false);
   datetime now = TimeCurrent();
   // v1.33-C1r2 (owner-approved behavior change, 2026-07-20): guard BOTH sides of
   // the pair. The profit-currency-only check left USDJPY blind to USD events on
   // the base side; for the index CFDs base==profit (USD-class) so nothing changes
   // there. Base is checked only when it is a distinct 3-letter currency code, so
   // exotic CFD base units can never feed the calendar a non-currency filter.
   string profit = SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT);
   string base   = SymbolInfoString(symbol, SYMBOL_CURRENCY_BASE);
   if(NewsSoonForCurrency(profit, now, win))
      return(true);
   if(StringLen(base) == 3 && base != profit && NewsSoonForCurrency(base, now, win))
      return(true);
   return(false);
  }

void LogClosedTrade(ulong dealTicket, long posId, string symbol)
  {
   int si = FindPositionState(posId);
   double exitPx = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
   double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT)
                 + HistoryDealGetDouble(dealTicket, DEAL_SWAP)
                 + HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
   long reason = HistoryDealGetInteger(dealTicket, DEAL_REASON);
   string rtxt = (reason == DEAL_REASON_SL) ? "SL"
               : (reason == DEAL_REASON_TP) ? "TP"
               : (reason == DEAL_REASON_EXPERT) ? "EA_time"
               : (reason == DEAL_REASON_SO) ? "STOPOUT" : "other";
   double entryPx = 0, riskPx = 0, mfe = 0, mae = 0, sprE = 0, realR = 0;
   int dir = 0, bars = 0;
   if(si >= 0)
     {
      entryPx = g_posState[si].entryPrice; riskPx = g_posState[si].riskPrice;
      dir = g_posState[si].dir; mfe = g_posState[si].mfeR; mae = g_posState[si].maeR;
      sprE = g_posState[si].spreadAtrEntry; bars = g_posState[si].barsClosed;
     }

   // v1.30: aggregate entry, partial, and final deals. The volume-weighted
   // price R is banked_frac*level_R + remainder*exit_R; cash profit includes
   // the actual entry/exit commissions and swaps exactly once.
   bool haveHistory = HistorySelectByPosition((ulong)posId);
   double totalEntryVol = 0.0, entryNotional = 0.0, totalProfit = 0.0;
   if(haveHistory)
     {
      int nd = HistoryDealsTotal();
      for(int i = 0; i < nd; i++)
        {
         ulong dd = HistoryDealGetTicket(i);
         if(dd == 0 || HistoryDealGetInteger(dd, DEAL_MAGIC) != InpMagicNumber)
            continue;
         totalProfit += HistoryDealGetDouble(dd, DEAL_PROFIT)
                      + HistoryDealGetDouble(dd, DEAL_SWAP)
                      + HistoryDealGetDouble(dd, DEAL_COMMISSION);
         long de = HistoryDealGetInteger(dd, DEAL_ENTRY);
         if(de == DEAL_ENTRY_IN || de == DEAL_ENTRY_INOUT)
           {
            double dv = HistoryDealGetDouble(dd, DEAL_VOLUME);
            totalEntryVol += dv;
            entryNotional += dv * HistoryDealGetDouble(dd, DEAL_PRICE);
            if(dir == 0)
               dir = (HistoryDealGetInteger(dd, DEAL_TYPE) == DEAL_TYPE_BUY) ? 1 : -1;
           }
        }
      if(totalEntryVol > 0.0)
         entryPx = entryNotional / totalEntryVol;
      profit = totalProfit;
     }

   if(riskPx <= 0.0)
     {
      double fallbackAtr = 0.0;
      if(ReadAtrForSymbol(symbol, fallbackAtr) && fallbackAtr > 0.0)
         riskPx = InpStopAtrMult * fallbackAtr;
     }

   if(haveHistory && riskPx > 0.0 && entryPx > 0.0 && dir != 0 && totalEntryVol > 0.0)
     {
      double weightedR = 0.0;
      int nd2 = HistoryDealsTotal();
      for(int j = 0; j < nd2; j++)
        {
         ulong dd2 = HistoryDealGetTicket(j);
         if(dd2 == 0 || HistoryDealGetInteger(dd2, DEAL_MAGIC) != InpMagicNumber)
            continue;
         long de2 = HistoryDealGetInteger(dd2, DEAL_ENTRY);
         if(de2 != DEAL_ENTRY_OUT && de2 != DEAL_ENTRY_OUT_BY)
            continue;
         double frac = HistoryDealGetDouble(dd2, DEAL_VOLUME) / totalEntryVol;
         weightedR += frac * dir * (HistoryDealGetDouble(dd2, DEAL_PRICE) - entryPx) / riskPx;
        }
      realR = weightedR;
     }
   else if(riskPx > 0.0 && entryPx > 0.0 && dir != 0)
      realR = dir * (exitPx - entryPx) / riskPx;

   string hdr = "close_time,symbol,dir,entry,exit,risk_px,realized_R,mfe_R,mae_R,spread_atr_entry,bars,exit_reason,profit";
   int h = FileOpen(InpTradeLogFile, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   // v1.33-C1r1: header-schema verification - the filename is unversioned, so a future
   // column change would silently mix schemas (the partials-CSV bug class). On mismatch
   // sideline the old file and start fresh with the current header.
   if(h != INVALID_HANDLE && FileSize(h) > 0)
     {
      FileSeek(h, 0, SEEK_SET);
      string firstLine = FileReadString(h);
      if(firstLine != hdr)
        {
         FileClose(h);
         string bak = InpTradeLogFile + ".schema.bak";
         FileMove(InpTradeLogFile, 0, bak, FILE_REWRITE);
         h = FileOpen(InpTradeLogFile, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
         PrintFormat("v1.33-C1r1: stale trades CSV header detected - old file moved to %s; writing the current header", bak);
        }
     }
   if(h != INVALID_HANDLE)
     {
      if(FileSize(h) == 0)
         FileWriteString(h, hdr + "\r\n");
      FileSeek(h, 0, SEEK_END);
      // v1.33-C1r1: close_time = the deal's DEAL_TIME (was TimeCurrent(), which drifts
      // from the actual close after event delays; the partials CSV already uses DEAL_TIME).
      FileWriteString(h, StringFormat("%s,%s,%s,%.5f,%.5f,%.5f,%.3f,%.3f,%.3f,%.4f,%d,%s,%.2f\r\n",
                      TimeToString((datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME), TIME_DATE | TIME_SECONDS), symbol, dir > 0 ? "BUY" : (dir < 0 ? "SELL" : "NA"),
                      entryPx, exitPx, riskPx, realR, mfe, mae, sprE, bars, rtxt, profit));
      FileClose(h);
     }
   else
     {
      // v1.33-C1r1: never drop a row silently (throttled 60s)
      static datetime s_openWarn = 0;
      if(TimeCurrent() - s_openWarn >= 60)
        {
         s_openWarn = TimeCurrent();
         PrintFormat("WARN: %s open failed (err %d) - row dropped", InpTradeLogFile, GetLastError());
        }
     }
  }

//+------------------------------------------------------------------+
//| v1.32 B2: impulse detection factored out of ScanSymbol so the     |
//| runner exit can evaluate OPPOSITE impulses with the SAME inputs.  |
//| Includes the 6-bar >= InpMomentumAtrMult ATR move, the signal-    |
//| candle direction alignment, and the W2 adverse-wick filter;       |
//| EXCLUDES the VWAP gate, the spread gates, and all entry-only      |
//| guards (those stay in ScanSymbol). Returns true when a tradable   |
//| impulse exists: dir=+1 rising / -1 falling; impulseAtr is signed  |
//| (+ rising), matching the SIGNAL-line convention. forExit=true     |
//| reports both directions regardless of InpTradeBothSides and stays |
//| silent (no panel/log spam from the management path);              |
//| forExit=false reproduces the exact v1.31 reject verdicts/logs.    |
//+------------------------------------------------------------------+
bool DetectImpulse(string symbol, double atr, int &dir, double &impulseAtr, bool forExit)
  {
   dir = 0;
   impulseAtr = 0.0;
   if(atr <= 0.0)
      return(false);

   // spread/ATR/side replica - used ONLY to keep the reject-log arguments identical to
   // v1.31 (the spread GATE itself stays in ScanSymbol; this never filters here).
   // v1.33-C1r1: skipped on the forExit path - its only consumers are !forExit LogSkip calls.
   double spreadAtrSide = 0.0;
   if(!forExit && InpMaxSpreadAtr > 0.0)
     {
      double pt = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double spreadPrice = (double)SymbolInfoInteger(symbol, SYMBOL_SPREAD) * pt;
      spreadAtrSide = 0.5 * spreadPrice / atr;
     }

   double close1    = iClose(symbol, InpTimeframe, 1);
   double closePast = iClose(symbol, InpTimeframe, InpMomentumBars);
   double open1     = iOpen(symbol, InpTimeframe, 1);
   if(close1 == 0.0 || closePast == 0.0)
     {
      if(!forExit)
         LogSkip(symbol, "missing bar data");
      return(false);
     }

   double move = closePast - close1;            // positive => price fell
   double moveAtr = move / atr;

   bool fallingFast = (moveAtr >= InpMomentumAtrMult) && (close1 < open1);
   bool risingFast  = (-moveAtr >= InpMomentumAtrMult) && (close1 > open1);

   // v1.29 W2 candle filter: the signal bar must be CONTESTED (adverse-side wick
   // >= InpMinAdvWickAtr ATR). NOTE (2026-07-12 parity audit): the original expectancy
   // evidence for W2 (+0.120R quarter-stitched WF etc.) was OVERTURNED by live-parity
   // enumeration - W2 is retained as the forward-test SIGNAL DEFINITION only (see the
   // Candle Filter input group). A SELL continuation needs a LOWER wick (buyers fought
   // = still fuel); a BUY needs an UPPER wick. Skips only.
   if(InpCandleFilter && InpMinAdvWickAtr > 0.0 && (fallingFast || risingFast))
     {
      double high1 = iHigh(symbol, InpTimeframe, 1);
      double low1  = iLow(symbol, InpTimeframe, 1);
      // v1.33-C1r3 (C11 fix): unsynced bar data (iHigh/iLow <= 0) must NOT silently
      // bypass the W2 signal definition. The old code fell through with the impulse
      // ACCEPTED; now it skips like the close-price missing-data path above, so a data
      // glitch can never admit a trade the validated signal would reject. On clean
      // historical/live bars high1/low1 are always > 0, so the validated trade
      // distribution is unchanged.
      if(high1 <= 0.0 || low1 <= 0.0)
        {
         if(!forExit)
            LogSkip(symbol, "missing bar data (W2 high/low)");
         return(false);
        }
      double bodyTop  = MathMax(open1, close1);
      double bodyBot  = MathMin(open1, close1);
      double advWick  = risingFast ? (high1 - bodyTop) : (bodyBot - low1);
      double advWickAtr = advWick / atr;
      if(advWickAtr < InpMinAdvWickAtr)
        {
         if(!forExit)
            LogSkip(symbol, StringFormat("candle filter: adv wick %.2f ATR < %.2f (clean climax)",
                    advWickAtr, InpMinAdvWickAtr), atr, spreadAtrSide, -moveAtr);
         return(false);
        }
     }

   // Impulse sign convention matches SIGNAL lines: negative = falling (close1 - closePast).
   impulseAtr = -moveAtr;
   // Entry path (forExit=false): long impulses require InpTradeBothSides (v1.31 semantics).
   // Exit path (forExit=true): both directions are reported for the runner exit.
   bool accepted = fallingFast || (risingFast && (forExit || InpTradeBothSides));
   if(!accepted)
     {
      if(!forExit)
        {
         bool belowThreshold = (MathAbs(impulseAtr) < InpMomentumAtrMult);
         string rejectReason;
         if(belowThreshold)
            rejectReason = StringFormat("no impulse: |%.2f| ATR < %.1f ATR threshold",
                                        impulseAtr, InpMomentumAtrMult);
         else if(risingFast && !InpTradeBothSides)
            rejectReason = StringFormat("long impulse %.2f ATR: long-side trading disabled",
                                        impulseAtr);
         else
           {
            string actualCandle = (close1 > open1) ? "bullish" :
                                  (close1 < open1) ? "bearish" : "doji";
            string requiredCandle = (impulseAtr > 0.0) ? "bullish" : "bearish";
            rejectReason = StringFormat("impulse %.2f ATR: signal candle is %s, requires %s alignment",
                                        impulseAtr, actualCandle, requiredCandle);
           }
         if(InpLogNoImpulse)
            LogSkip(symbol, rejectReason, atr, spreadAtrSide, impulseAtr);
         else
            SetVerdict(symbol, belowThreshold ? rejectReason : "SKIP " + rejectReason);
        }
      return(false);
     }

   dir = fallingFast ? -1 : 1;
   return(true);
  }

//+------------------------------------------------------------------+
//| Evaluate one symbol and place a pending order if momentum is hot |
//+------------------------------------------------------------------+
void ScanSymbol(string symbol)
  {
   if(HasExposure(symbol))           // already trading this symbol
      return;
   if(InpMaxPerCluster > 0)
     {
      int cluster = ClusterOf(symbol);
      if(cluster >= 0 && CountClusterExposure(cluster) >= InpMaxPerCluster)
        {
         LogSkip(symbol, StringFormat("cluster cap (%d in cluster %d)", InpMaxPerCluster, cluster));
         return;
        }
     }
   if(!DataReady(symbol))
     {
      LogSkip(symbol, "data not ready");
      return;
     }
   // v1.27 B5: the validated engine resumes at exit_bar+1, so the bar a trade
   // exited on can never be a signal bar; live we evaluated it one bar early.
   int sidx = SymbolIndex(symbol);
   if(sidx >= 0 && g_noSignalUpTo[sidx] > 0
      && (datetime)iTime(symbol, InpTimeframe, 1) <= g_noSignalUpTo[sidx])
     {
      LogSkip(symbol, "exit-bar cooldown (engine parity)");
      return;
     }
   if(InpFreshnessGuard && !QuotesFresh(symbol))     // v1.25: never trade on frozen/invalid data
     {
      LogSkip(symbol, "stale/invalid quotes (freshness guard)");
      return;
     }
   if(InpNewsBlockMins > 0 && NewsSoon(symbol))       // v1.25: optional HIGH-impact news blackout (ON by default, 3 min)
     {
      LogSkip(symbol, "news blackout");
      return;
     }

   double atr;
   if(!WilderAtrForSymbol(symbol, atr) || atr <= 0.0)   // v1.27: validated-engine estimator
     {
      LogSkip(symbol, "ATR unavailable");
      return;
     }

   // v1.2 spread/ATR gate (the key cost filter). The edge survives only where the
   // round-trip spread is small relative to the 1-ATR stop; skip if the current spread
   // PER SIDE exceeds the validated ceiling (this is what excludes wide-spread names
   // like LTC/BCH/Mid Cap, and protects against spread blow-outs during news).
   double spreadAtrSide = 0.0;
   if(InpMaxSpreadAtr > 0.0)
     {
      double pt = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double spreadPrice = (double)SymbolInfoInteger(symbol, SYMBOL_SPREAD) * pt;
      spreadAtrSide = 0.5 * spreadPrice / atr;
      if(spreadAtrSide > InpMaxSpreadAtr)
        {
         LogSkip(symbol, StringFormat("spread/ATR/side %.4f > %.4f", spreadAtrSide, InpMaxSpreadAtr),
                 atr, spreadAtrSide);
         return;
        }
     }

   double close1    = iClose(symbol, InpTimeframe, 1);
   double closePast = iClose(symbol, InpTimeframe, InpMomentumBars);
   if(close1 == 0.0 || closePast == 0.0)
     {
      LogSkip(symbol, "missing bar data");
      return;
     }

   // v1.32 B2: the impulse core (6-bar move, signal-candle alignment, W2 adverse-wick
   // filter, and every reject verdict) lives in DetectImpulse - ZERO behavior change on
   // this entry path; the helper emits the exact v1.31 verdicts/logs on rejection.
   int impDir = 0;
   double impulseAtr = 0.0;
   if(!DetectImpulse(symbol, atr, impDir, impulseAtr, false))
      return;

   bool fallingFast = (impDir < 0);
   bool risingFast  = (impDir > 0);

   // Continuation in the direction of the move. PULLBACK uses LIMIT orders (enter on
   // the retrace); BREAKOUT uses STOP orders (chase beyond price, the legacy behaviour).
   // v1.32 B1: ENTRY_MARKET sends a market order at the next bar open (research arm).
   ENUM_ORDER_TYPE buyType  = (InpEntryMode == ENTRY_LIMIT_PULLBACK) ? ORDER_TYPE_BUY_LIMIT  :
                              (InpEntryMode == ENTRY_MARKET)         ? ORDER_TYPE_BUY        : ORDER_TYPE_BUY_STOP;
   ENUM_ORDER_TYPE sellType = (InpEntryMode == ENTRY_LIMIT_PULLBACK) ? ORDER_TYPE_SELL_LIMIT :
                              (InpEntryMode == ENTRY_MARKET)         ? ORDER_TYPE_SELL       : ORDER_TYPE_SELL_STOP;

   if(fallingFast)
      PlacePending(symbol, sellType, atr, close1, impulseAtr, spreadAtrSide);
   else if(risingFast && InpTradeBothSides)
      PlacePending(symbol, buyType, atr, close1, impulseAtr, spreadAtrSide);
  }

//+------------------------------------------------------------------+
//| Place a pending order.                                           |
//|  BREAKOUT: STOP just beyond price, in the move's direction.      |
//|  PULLBACK: LIMIT ~InpPullbackAtr ATR back toward price, so we    |
//|            enter on the retrace with the stop behind the floor.  |
//+------------------------------------------------------------------+
void PlacePending(string symbol, ENUM_ORDER_TYPE type, double atr, double signalClose,
                  double impulseAtr, double spreadAtrSide)
  {
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double stopsLevel = (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;

   bool isMarket = (type == ORDER_TYPE_BUY || type == ORDER_TYPE_SELL);   // v1.32 B1: ENTRY_MARKET
   bool isLimit = (type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_SELL_LIMIT);
   bool isBuy   = (type == ORDER_TYPE_BUY || type == ORDER_TYPE_BUY_STOP || type == ORDER_TYPE_BUY_LIMIT);

   // How far the pending sits from the anchor price.
   //   PULLBACK (limit): InpPullbackAtr ATR back from the signal-bar CLOSE (validated harness).
   double offset = InpPullbackAtr * atr;
   offset = MathMax(offset, stopsLevel);     // respect the broker minimum distance
   if(offset <= 0.0)
      offset = 10 * point;

   double stopDist = atr * InpStopAtrMult;   // INTENDED stop distance: the R denominator (A5) and the sizing basis
   double tpDist   = (InpTakeProfitAtrMultV130 > 0.0) ? atr * InpTakeProfitAtrMultV130 : 0.0;
   if(InpExitModeV132 == EXIT_UNCAPPED_RUNNER)
      tpDist = 0.0;   // v1.32 B2: an uncapped runner carries NO take-profit target (research arm)
   if(stopsLevel > 0.0)
     {
      stopDist = MathMax(stopDist, stopsLevel * 1.5);
      if(tpDist > 0.0) tpDist = MathMax(tpDist, stopsLevel * 1.5);
     }
   // v1.32 B3: in bar-close-stop mode the broker holds only a far DISASTER backstop; the
   // intended stop above stays the sizing/R basis and is evaluated on bar close. The
   // disaster stop is never tighter than the intended stop (never naked, never tighter).
   double placedStopDist = stopDist;
   if(InpStopEvalV132 == STOP_EVAL_BAR_CLOSE)
      placedStopDist = MathMax(stopDist, atr * InpDisasterStopMultV132);

   double lots = CalculateLotSize(symbol, stopDist);
   if(lots <= 0.0)
      return;

   datetime expiry = 0;
   ENUM_ORDER_TYPE_TIME ttype = ORDER_TIME_GTC;
   if(InpPendingExpiryBars > 0)
     {
      // v1.27 B2: the engine's fill window (w4 at the default 3: remainder of the placement
      // bar + InpPendingExpiryBars full bars - Bars() omits the placement bar, see the
      // InpPendingExpiryBars input comment) is counted on the SYMBOL'S OWN clock (session
      // breaks produce no bars). Precise expiry = the bar-counted check in
      // ManagePendingOrders; the broker wall-clock expiry stays only as a +3-day backstop
      // for when the EA itself is dead.
      expiry = (datetime)(TimeCurrent() + (long)InpPendingExpiryBars * PeriodSeconds(InpTimeframe) + 259200);
      ttype  = ORDER_TIME_SPECIFIED;
     }

   // v1.32 A6: bounded resend on price-class retcodes (the deferred v1.30 "10015" item).
   // Each attempt re-fetches bid/ask, re-evaluates the v1.27 B4 marketable-limit ->
   // market conversion, and recomputes entry/SL/TP from the fresh quotes. The geometry
   // math is untouched; only the price path changes. Resends stop the moment the signal
   // bar is no longer bar 1, and non-price retcodes abort immediately.
   datetime sigBar1 = (datetime)iTime(symbol, InpTimeframe, 1);
   int maxRetries = MathMax(InpEntryMaxRetriesV132, 0);
   for(int attempt = 0; ; attempt++)
     {
      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);

      double entry, sl, tp;
      bool sendMarket = isMarket;   // v1.32 B1: ENTRY_MARKET goes straight to market
      if(isBuy)
        {
         // BUY_STOP sits above the ask; BUY_LIMIT sits below signal-bar close (pullback).
         entry = isLimit ? (signalClose - offset) : (ask + offset);
         // v1.27 B4: price already retraced through the limit level (gap / fast move).
         // The validated engine fills these at the limit on touch; a live BUY_LIMIT
         // above the ask is rejected 10015 (observed live 08:29 today) and the trade
         // is silently lost. Market entry at the ask is equal-or-BETTER than the
         // engine's assumed limit fill (ask < limit here by construction).
         if(isMarket)
            entry = ask;
         else if(isLimit && entry >= ask - stopsLevel)
           {
            entry = ask;
            sendMarket = true;
           }
         entry = SnapPrice(symbol, entry);
         sl    = SnapPrice(symbol, entry - placedStopDist);
         tp    = (tpDist > 0.0) ? SnapPrice(symbol, entry + tpDist) : 0.0;
        }
      else
        {
         // SELL_STOP sits below the bid; SELL_LIMIT sits above signal-bar close (pullback).
         entry = isLimit ? (signalClose + offset) : (bid - offset);
         if(isMarket)
            entry = bid;   // v1.32 B1: ENTRY_MARKET
         else if(isLimit && entry <= bid + stopsLevel)
           {
            entry = bid;   // v1.27 B4: see BUY branch
            sendMarket = true;
           }
         entry = SnapPrice(symbol, entry);
         sl    = SnapPrice(symbol, entry + placedStopDist);
         tp    = (tpDist > 0.0) ? SnapPrice(symbol, entry - tpDist) : 0.0;
        }

      trade.SetTypeFillingBySymbol(symbol);
      bool ok = false;
      string tag = "";
      if(sendMarket)
        {
         ok = isBuy ? trade.Buy (lots, symbol, 0.0, sl, tp, InpTradeComment)
                    : trade.Sell(lots, symbol, 0.0, sl, tp, InpTradeComment);
         tag = isBuy ? (isMarket ? "BUY MARKET(entry-mode)" : "BUY MARKET(retrace-done)")
                     : (isMarket ? "SELL MARKET(entry-mode)" : "SELL MARKET(retrace-done)");
        }
      else
      switch(type)
        {
         case ORDER_TYPE_BUY_LIMIT:  ok = trade.BuyLimit (lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "BUY LIMIT";  break;
         case ORDER_TYPE_SELL_LIMIT: ok = trade.SellLimit(lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "SELL LIMIT"; break;
         default: return;
        }

      uint rc = trade.ResultRetcode();
      if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED))   // v1.26: bool alone only means "request passed basic checks"
        {
         // v1.27 B3: fills are counted in OnTradeTransaction. v1.32 B1: a MARKET fill
         // routes through the same deal path, so the frozen signal ATR is stored here too.
         StorePendingSigAtr(trade.ResultOrder(), atr);
         SetVerdict(symbol, StringFormat("SIGNAL %s %.2f lots @ %.2f (imp %.2f ATR)", tag, lots, entry, impulseAtr));   // v1.28
         PrintFormat("SIGNAL %s %s %.2f lots entry=%.5f (anchor=%.5f) SL=%.5f TP=%.5f | ATR=%.5f impulse=%.2f spread/ATR/side=%.4f",
                     symbol, tag, lots, entry, signalClose, sl, tp, atr, impulseAtr, spreadAtrSide);
         return;
        }
      // v1.32 A6: only price-class rejections are resent, and only while the signal bar
      // is still bar 1; everything else (no money, trade disabled, invalid volume...)
      // aborts immediately, exactly like v1.31.
      if(!EntryRetcodePriceClass(rc) || attempt >= maxRetries)
        {
         // v1.32: name the actual order type (tag carries e.g. "BUY MARKET(entry-mode)")
         PrintFormat("%s %s order failed: %d (%s)", symbol, tag,
                     trade.ResultRetcode(), trade.ResultRetcodeDescription());
         return;
        }
      if((datetime)iTime(symbol, InpTimeframe, 1) != sigBar1)
        {
         PrintFormat("%s pending abandoned: signal bar rolled during price-class retry (retcode %u)", symbol, rc);
         return;
        }
      PrintFormat("v1.32 ENTRY RETRY %s attempt=%d/%d retcode=%u (%s) - refetching quotes",
                  symbol, attempt + 1, maxRetries, rc, trade.ResultRetcodeDescription());
     }
  }

//+------------------------------------------------------------------+
//| v1.32 A6: price-class retcodes worth a bounded resend.            |
//+------------------------------------------------------------------+
bool EntryRetcodePriceClass(uint rc)
  {
   return(rc == TRADE_RETCODE_INVALID_PRICE || rc == TRADE_RETCODE_REQUOTE ||
          rc == TRADE_RETCODE_PRICE_CHANGED || rc == TRADE_RETCODE_PRICE_OFF);
  }

//+------------------------------------------------------------------+
//| Fixed-fractional lot size from the stop distance                 |
//+------------------------------------------------------------------+
double RiskPercentForSymbol(string symbol)
  {
   if(symbol == "USDJPY")
      return(InpUSDJPYRiskPercentV131);
   return(InpRiskPercent);
  }

//+------------------------------------------------------------------+
double CalculateLotSize(string symbol, double stopDistancePrice)
  {
   if(stopDistancePrice <= 0.0)
      return(0.0);
   double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskPct    = RiskPercentForSymbol(symbol);
   double riskAmount = balance * (riskPct / 100.0);
   if(riskAmount <= 0.0)
      return(0.0);

   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS); // v1.26: loss-side conversion for a stop-loss distance
   if(tickValue <= 0.0)
      tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0)
      return(0.0);

   double lossPerLot = (stopDistancePrice / tickSize) * tickValue;
   if(lossPerLot <= 0.0)
      return(0.0);

   double lots = riskAmount / lossPerLot;

   double minVol  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxVol  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double stepVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(stepVol > 0.0)
      lots = MathFloor(lots / stepVol) * stepVol;

   if(lots < minVol)
     {
      // Sizing up to the broker minimum would over-risk; refuse if > 1.5x budget.
      if(lossPerLot * minVol > riskAmount * 1.5)
         return(0.0);
      PrintFormat("%s: MIN-LOT substitution - risking %.2f (%.3f%% of balance) vs %.2f budget (%.2f%%)",
                  symbol, lossPerLot * minVol, 100.0 * lossPerLot * minVol / balance, riskAmount, riskPct);
      lots = minVol;
     }
   if(lots > maxVol)
      lots = maxVol;

   return(lots);
  }

//+------------------------------------------------------------------+
//| Manage every pending order and open position                     |
//+------------------------------------------------------------------+
void ManageAll()
  {
   ManagePendingOrders();
   SweepStalePendingSigAtr();
   ManageOpenPositions();
  }

//+------------------------------------------------------------------+
//| Prune frozen-ATR entries whose pending order no longer exists     |
//| (broker-side ORDER_TIME_SPECIFIED expiry never reaches our        |
//| OrderDelete path, so entries could leak; bounded but untidy).     |
//| A FILLED order whose OnTradeTransaction event has not been        |
//| delivered yet gets its ATR transferred to the position state      |
//| here instead of being dropped.                                    |
//+------------------------------------------------------------------+
void SweepStalePendingSigAtr()
  {
   for(int i = ArraySize(g_pendingSigAtr) - 1; i >= 0; i--)
     {
      ulong ticket = g_pendingSigAtr[i].orderTicket;
      if(ordInfo.Select(ticket))
         continue;                          // still live
      if(!HistoryOrderSelect(ticket))
         continue;                          // resync window: neither live nor in history yet.
                                            // KEEP the frozen ATR and retry next heartbeat —
                                            // dropping here could hand a later fill the wrong
                                            // (fill-time) ATR (review fix).
      // Order is in history. If it produced a position (filled, or partial-then-
      // canceled/expired), transfer the frozen ATR to that position's state.
      long posId = HistoryOrderGetInteger(ticket, ORDER_POSITION_ID);
      if(posId != 0)
        {
         string sym = HistoryOrderGetString(ticket, ORDER_SYMBOL);
         double atr = TakePendingSigAtr(ticket);
         RegisterPositionState(posId, sym, atr,
                               (datetime)HistoryOrderGetInteger(ticket, ORDER_TIME_DONE), atr > 0.0);
         continue;
        }
      // Terminal state with no position (canceled / expired / rejected unfilled): drop.
      TakePendingSigAtr(ticket);
     }
  }

//+------------------------------------------------------------------+
//| Expire stale pendings; trail BREAKOUT stop orders toward price.  |
//| PULLBACK limit orders are left to sit and wait for the retrace   |
//| (matches the validated backtest, which did not trail pendings).  |
//+------------------------------------------------------------------+
void ManagePendingOrders()
  {
   // v1.32 A8: halt cancel-spam throttle. v1.31 re-issued CancelAllPendings on EVERY
   // heartbeat while halted. Cancel once per halt episode; re-cancel only when a pending
   // with our magic (re)appears or the halt flag transitions (reset below when clear).
   static bool s_haltCancelled = false;
   if(g_halted || g_haltedHard)     // v1.26: a halt must also clear RESTING orders -
     {                              // a pending filling after "paused for the day" adds
      bool anyOurs = false;         // fresh risk on top of a -4% day (audit P1)
      for(int i = OrdersTotal() - 1; i >= 0; i--)
        {
         ulong t = OrderGetTicket(i);
         if(t != 0 && ordInfo.Select(t) && ordInfo.Magic() == InpMagicNumber)
           {
            anyOurs = true;
            break;
           }
        }
      if(!s_haltCancelled || anyOurs)
        {
         CancelAllPendings("halt active");
         s_haltCancelled = true;
        }
      return;
     }
   s_haltCancelled = false;         // halt cleared: the next halt episode cancels again
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !ordInfo.Select(ticket))
         continue;
      if(ordInfo.Magic() != InpMagicNumber)
         continue;

      string symbol = ordInfo.Symbol();
      ENUM_ORDER_TYPE type = ordInfo.OrderType();
      bool isStop  = (type == ORDER_TYPE_BUY_STOP  || type == ORDER_TYPE_SELL_STOP);
      bool isLimit = (type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_SELL_LIMIT);
      if(!isStop && !isLimit)
         continue;

      // PRIMARY expiry: this bar-counted check is the engine's precise fill window. The
      // broker-side ORDER_TIME_SPECIFIED expiry is set +3 days LATE at placement and is
      // only a backstop for when the EA itself is dead (see PlacePending). Applies to
      // both stop and limit orders.
      if(InpPendingExpiryBars > 0)
        {
         // v1.27 B2 / v1.29.1: engine parity - the fill window is counted on the SYMBOL'S OWN
         // clock via Bars(TimeSetup, now), which OMITS the placement bar (its open predates
         // TimeSetup). Deletion fires when ageBars > InpPendingExpiryBars, so the order lives
         // the remainder of the placement bar + InpPendingExpiryBars full bars (w4 at the
         // default 3 - the measured live behavior the v1.30 retest assumes; see the input
         // comment on InpPendingExpiryBars). Wall-clock aging expired pendings mid-session-
         // break after fewer tradable bars than validated.
         int ageBars = Bars(symbol, InpTimeframe, ordInfo.TimeSetup(), TimeCurrent());
         if(ageBars > InpPendingExpiryBars)
           {
            bool delOk = trade.OrderDelete(ticket);
            uint drc = trade.ResultRetcode();
            if(delOk && (drc == TRADE_RETCODE_DONE || drc == TRADE_RETCODE_PLACED))
               TakePendingSigAtr(ticket);   // v1.26: only drop the frozen ATR once the delete is CONFIRMED
            continue;                       // (a failed delete + later fill needs the true signal ATR)
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Lock-to-breakeven, tight trail and time exit on open positions   |
//+------------------------------------------------------------------+
void ManageOpenPositions()
  {
   static datetime s_lastTimeExitLog = 0;   // v1.32 A2: throttle the time-exit failure log to 1/minute
   PruneClosedPositionStates();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !posInfo.SelectByTicket(ticket))
         continue;
      if(posInfo.Magic() != InpMagicNumber)
         continue;

      string symbol = posInfo.Symbol();
      long posId = (long)posInfo.Identifier();
      int stateIdx = FindPositionState(posId);
      if(stateIdx < 0)
        {
         RegisterPositionState(posId, symbol, 0.0, posInfo.Time());
         stateIdx = FindPositionState(posId);
         if(stateIdx < 0)
            continue;
        }

      // v1.25: sample MFE/MAE in R for the trade log (observability only; each heartbeat).
      if(g_posState[stateIdx].riskPrice > 0.0 && g_posState[stateIdx].entryPrice > 0.0)
        {
         int d = g_posState[stateIdx].dir;
         double exitSide = (d > 0) ? SymbolInfoDouble(symbol, SYMBOL_BID) : SymbolInfoDouble(symbol, SYMBOL_ASK);
         if(exitSide > 0.0)
           {
            double curR = d * (exitSide - g_posState[stateIdx].entryPrice) / g_posState[stateIdx].riskPrice;
            if(curR > g_posState[stateIdx].mfeR) g_posState[stateIdx].mfeR = curR;
            if(curR < g_posState[stateIdx].maeR) g_posState[stateIdx].maeR = curR;
           }
        }

      // v1.30 partial is tick-checked on every heartbeat, independent of the
      // bar-close lock/trail cadence. A sent close request owns this heartbeat
      // so time/SL management cannot race the server transaction chain.
      if(ManagePartialClose(ticket, stateIdx))
         continue;

      // v1.32 A2: the time exit lives HERE now, evaluated EVERY heartbeat right after
      // the partial check (v1.31 consumed the bar clock inside the bar-close/per-tick
      // managers BEFORE trade.PositionClose, so a rejected forced close - requote,
      // market closed, freeze - was silently deferred a full H1 bar; over a weekend
      // that was days of unplanned exposure). Same counter, same threshold; a failure
      // simply retries on the next heartbeat. v1.32 B2: runner positions use the
      // InpRunnerMaxBarsV132 backstop instead of InpMaxHoldingBars.
      int maxHoldBars = (g_posState[stateIdx].runnerV132) ? InpRunnerMaxBarsV132 : InpMaxHoldingBars;
      if(maxHoldBars > 0 && g_posState[stateIdx].barsClosed >= maxHoldBars)
        {
         if(trade.PositionClose(ticket))
            continue;                             // position gone
         if(TimeCurrent() - s_lastTimeExitLog >= 60)
           {
            s_lastTimeExitLog = TimeCurrent();
            PrintFormat("v1.32 time-exit close RETRY position=%I64d %s barsClosed=%d/%d retcode=%u (%s) - retried every heartbeat",
                        g_posState[stateIdx].positionId, symbol,
                        g_posState[stateIdx].barsClosed, maxHoldBars,
                        trade.ResultRetcode(), trade.ResultRetcodeDescription());
           }
         continue;                                // do not run other managers against a position we are trying to close
        }

      ManagePositionBarClose(ticket, stateIdx);
     }
  }

//+------------------------------------------------------------------+
//| Validated engine: lock/trail/time-exit only on symbol bar close.  |
//+------------------------------------------------------------------+
void ManagePositionBarClose(ulong ticket, int stateIdx)
  {
   static datetime s_lastArmExitLog = 0;   // v1.32: throttle the arm-exit failure log to 1/minute
   string symbol = posInfo.Symbol();
   datetime curBarTime = (datetime)iTime(symbol, InpTimeframe, 0);
   if(curBarTime == 0)                     // history desync: don't corrupt the bar clock
      return;
   if(curBarTime == g_posState[stateIdx].lastMgmtBarTime)
      return;

   g_posState[stateIdx].lastMgmtBarTime = curBarTime;
   UpdateBarsClosed(stateIdx, symbol);

   // v1.32 A2: the bar-count time exit moved to ManageOpenPositions (evaluated and
   // retried every heartbeat). Only NEW-bar exit logic remains here.

   // v1.32 B3: bar-close stop evaluation (arm default OFF; NEW positions stamped
   // STOP_EVAL_BAR_CLOSE only). The broker SL is just the disaster backstop - the
   // VALIDATED stop is the close of bar 1 beyond entry -+ InpStopAtrMult*signalAtr.
   if(g_posState[stateIdx].barCloseStopV132)
     {
      double sigAtr = g_posState[stateIdx].signalAtr;
      if(sigAtr <= 0.0)
        {
         if(ReadAtrForSymbol(symbol, sigAtr) && sigAtr > 0.0)
            g_posState[stateIdx].signalAtr = sigAtr;
        }
      if(sigAtr > 0.0)
        {
         double stopClose = iClose(symbol, InpTimeframe, 1);
         double stopEntry = posInfo.PriceOpen();
         if(stopClose > 0.0 && stopEntry > 0.0)
           {
            double intendedDist = InpStopAtrMult * sigAtr;
            bool stopHit = (posInfo.PositionType() == POSITION_TYPE_BUY)
                           ? (stopClose <= stopEntry - intendedDist)
                           : (stopClose >= stopEntry + intendedDist);
            if(stopHit)
              {
               // fills ~= next bar open, per the pre-registered arm; the disaster-stop
               // level is logged so the tail-risk column can be audited.
               PrintFormat("v1.32 BAR_CLOSE stop exit; broker disaster stop was at %.5f (position=%I64d %s barClose=%.5f entry=%.5f intendedDist=%.5f)",
                           posInfo.StopLoss(), g_posState[stateIdx].positionId, symbol,
                           stopClose, stopEntry, intendedDist);
               SetVerdict(symbol, "BAR_CLOSE stop exit");
               if(!trade.PositionClose(ticket))
                 {
                  // v1.32: a rejected arm exit must not wait a full bar - log the retcode
                  // (throttled 60s, same pattern as the A2 time exit) and reset the bar
                  // clock so the NEXT heartbeat re-enters this manager and retries.
                  if(TimeCurrent() - s_lastArmExitLog >= 60)
                    {
                     s_lastArmExitLog = TimeCurrent();
                     PrintFormat("v1.32 BAR_CLOSE stop exit RETRY position=%I64d %s retcode=%u (%s) - retried next heartbeat",
                                 g_posState[stateIdx].positionId, symbol,
                                 trade.ResultRetcode(), trade.ResultRetcodeDescription());
                    }
                  g_posState[stateIdx].lastMgmtBarTime = 0;
                 }
               return;
              }
           }
        }
     }

   // v1.32 B2: UNCAPPED RUNNER - exit at market when a NEW bar shows an impulse
   // OPPOSITE the position direction (arm default OFF; the runner carries no TP).
   // DetectImpulse(forExit=true) reports both directions with the same entry inputs.
   if(g_posState[stateIdx].runnerV132)
     {
      double atrExit = 0.0;
      if(WilderAtrForSymbol(symbol, atrExit) && atrExit > 0.0)
        {
         int impDir = 0;
         double impAtr = 0.0;
         if(DetectImpulse(symbol, atrExit, impDir, impAtr, true))
           {
            int posDir = (posInfo.PositionType() == POSITION_TYPE_BUY) ? 1 : -1;
            if(impDir == -posDir)
              {
               PrintFormat("v1.32 RUNNER exit on opposite impulse: position=%I64d %s impulse=%+.2f ATR vs posDir=%+d",
                           g_posState[stateIdx].positionId, symbol, impAtr, posDir);
               SetVerdict(symbol, "RUNNER exit on opposite impulse");
               if(!trade.PositionClose(ticket))
                 {
                  // v1.32: same retry-until-close treatment as the B3 stop above - log
                  // the retcode (throttled 60s) and reset the bar clock so the NEXT
                  // heartbeat re-enters this manager and retries immediately.
                  if(TimeCurrent() - s_lastArmExitLog >= 60)
                    {
                     s_lastArmExitLog = TimeCurrent();
                     PrintFormat("v1.32 RUNNER exit RETRY position=%I64d %s retcode=%u (%s) - retried next heartbeat",
                                 g_posState[stateIdx].positionId, symbol,
                                 trade.ResultRetcode(), trade.ResultRetcodeDescription());
                    }
                  g_posState[stateIdx].lastMgmtBarTime = 0;
                  return;
                 }
               if(!InpRunnerReverseV132)
                 {
                  // Stop-and-reverse arm OFF: suppress the immediate opposite re-entry
                  // one bar beyond the standard exit-bar cooldown (the reverse arm lets
                  // the normal scan take it, governed by the exit-bar cooldown alone).
                  int xidx = SymbolIndex(symbol);
                  if(xidx >= 0)
                    {
                     datetime curB = (datetime)iTime(symbol, InpTimeframe, 0);
                     if(curB > g_noSignalUpTo[xidx])
                        g_noSignalUpTo[xidx] = curB;
                    }
                 }
               return;
              }
           }
        }
     }

   // v1.23 PURE BRACKET: nothing to manage here between fill and exit - the broker-side
   // SL/TP set at placement ARE the exit engine, plus the v1.30 +1R partial bank and the
   // bar-count time exit, both evaluated every heartbeat in ManageOpenPositions (time exit
   // moved there in v1.32 A2). (Exit-ladder study: the lock/trail ladder cut avg win from
   // 1.72R to 1.02R and cost ~0.027R/trade of OOS expectancy, so it was removed.)
  }

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
void LogSkip(string symbol, string reason, double atr=0.0, double spreadAtrSide=0.0, double impulseAtr=0.0)
  {
   SetVerdict(symbol, "SKIP " + reason);   // v1.28 panel
   if(atr > 0.0)
      PrintFormat("SKIP %s: %s | ATR=%.5f spread/ATR/side=%.4f impulse=%.2f",
                  symbol, reason, atr, spreadAtrSide, impulseAtr);
   else
      PrintFormat("SKIP %s: %s", symbol, reason);
  }

string PendingSigAtrGv(ulong orderTicket)
  {
   return("MPB_v130_pending_atr_" + (string)orderTicket);
  }

int FindPendingSigAtr(ulong orderTicket)
  {
   for(int i = 0; i < ArraySize(g_pendingSigAtr); i++)
      if(g_pendingSigAtr[i].orderTicket == orderTicket)
         return(i);
   return(-1);
  }

double PeekPendingSigAtr(ulong orderTicket)
  {
   int idx = FindPendingSigAtr(orderTicket);
   if(idx >= 0)
      return(g_pendingSigAtr[idx].atr);
   string gv = PendingSigAtrGv(orderTicket);
   if(GlobalVariableCheck(gv))
      return(GlobalVariableGet(gv));
   return(0.0);
  }

void StorePendingSigAtr(ulong orderTicket, double atr)
  {
   if(orderTicket == 0 || atr <= 0.0)
      return;
   int idx = FindPendingSigAtr(orderTicket);
   if(idx < 0)
     {
      idx = ArraySize(g_pendingSigAtr);
      ArrayResize(g_pendingSigAtr, idx + 1);
      g_pendingSigAtr[idx].orderTicket = orderTicket;
     }
   g_pendingSigAtr[idx].atr = atr;
   GlobalVariableSet(PendingSigAtrGv(orderTicket), atr);
   GlobalVariablesFlush();
  }

double TakePendingSigAtr(ulong orderTicket)
  {
   // v1.33-C1r1: single FindPendingSigAtr lookup (was scanned twice via Peek);
   // RAM-first-then-GV order, removal, GV delete and flush preserved exactly.
   int idx = FindPendingSigAtr(orderTicket);
   double atr = (idx >= 0) ? g_pendingSigAtr[idx].atr
                           : (GlobalVariableCheck(PendingSigAtrGv(orderTicket))
                              ? GlobalVariableGet(PendingSigAtrGv(orderTicket)) : 0.0);
   if(idx >= 0)
     {
      for(int j = idx; j < ArraySize(g_pendingSigAtr) - 1; j++)
         g_pendingSigAtr[j] = g_pendingSigAtr[j + 1];
      ArrayResize(g_pendingSigAtr, ArraySize(g_pendingSigAtr) - 1);
     }
   GlobalVariableDel(PendingSigAtrGv(orderTicket));
   GlobalVariablesFlush();
   return(atr);
  }

void RestorePendingSigAtrFromLiveOrders()
  {
   int restored = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !ordInfo.Select(ticket) || ordInfo.Magic() != InpMagicNumber)
         continue;
      double atr = PeekPendingSigAtr(ticket);
      if(atr <= 0.0)
         continue;
      StorePendingSigAtr(ticket, atr);
      restored++;
     }
   if(restored > 0)
      PrintFormat("v1.30 restored %d pending signal-ATR record(s)", restored);
  }

double TakePendingSigAtrForPosition(long positionId)
  {
   if(!HistorySelectByPosition((ulong)positionId))
      return(0.0);
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0 || HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagicNumber)
         continue;
      long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_IN && entry != DEAL_ENTRY_INOUT)
         continue;
      ulong orderTicket = (ulong)HistoryDealGetInteger(deal, DEAL_ORDER);
      double atr = PeekPendingSigAtr(orderTicket);
      if(atr > 0.0)
        {
         // Keep the order GV if a residual is still working. A terminal order's
         // ATR has now been promoted to the position and can be removed.
         if(ordInfo.Select(orderTicket))
            return(atr);
         return(TakePendingSigAtr(orderTicket));
        }
     }
   return(0.0);
  }

int FindPositionState(long positionId)
  {
   for(int i = 0; i < ArraySize(g_posState); i++)
      if(g_posState[i].positionId == positionId)
         return(i);
   return(-1);
  }

void LogPartialDeal(ulong dealTicket, long posId, string symbol)
  {
   if(!InpTradeLog || StringLen(InpPartialLogFileV130) == 0)
      return;
   int si = FindPositionState(posId);
   double fill = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
   double vol = HistoryDealGetDouble(dealTicket, DEAL_VOLUME);
   double level = (si >= 0) ? g_posState[si].partialLevel : 0.0;
   double risk = (si >= 0) ? g_posState[si].riskPrice : 0.0;
   double initialVol = (si >= 0) ? g_posState[si].initialVolume : 0.0;
   double targetVol = (si >= 0) ? g_posState[si].partialTargetVolume : 0.0;
   int dir = (si >= 0) ? g_posState[si].dir : 0;
   double slipPrice = (dir != 0 && level > 0.0) ? dir * (fill - level) : 0.0;
   double slipR = (risk > 0.0) ? slipPrice / risk : 0.0;
   int h = FileOpen(InpPartialLogFileV130, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   // v1.33-C1r1: header-schema verification. v1.32 appended a 14th column (trigger_tag)
   // to the row schema while keeping the v1.30 filename, so a file created pre-v1.32
   // carries a stale 13-column header under 14-field rows (this blocked a downstream
   // audit). Sideline such a file once and start fresh with the current header.
   if(h != INVALID_HANDLE && FileSize(h) > 0)
     {
      FileSeek(h, 0, SEEK_SET);
      string firstLine = FileReadString(h);
      if(StringFind(firstLine, "trigger_tag") < 0)
        {
         FileClose(h);
         string bak = InpPartialLogFileV130 + ".pre_v132.bak";
         FileMove(InpPartialLogFileV130, 0, bak, FILE_REWRITE);
         h = FileOpen(InpPartialLogFileV130, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
         PrintFormat("v1.33-C1r1: stale pre-v1.32 partials CSV header detected - old file moved to %s; writing the current header", bak);
        }
     }
   if(h != INVALID_HANDLE)
     {
      if(FileSize(h) == 0)
         FileWriteString(h, "time,deal,position_id,symbol,dir,initial_volume,target_volume,deal_volume,level,fill,slippage_price,slippage_R,state,trigger_tag\r\n");   // v1.32 A1(c): appended column, nothing removed
      FileSeek(h, 0, SEEK_END);
      FileWriteString(h, StringFormat("%s,%I64u,%I64d,%s,%s,%.2f,%.2f,%.2f,%.5f,%.5f,%.5f,%.5f,%s,%s\r\n",
                      TimeToString((datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME), TIME_DATE | TIME_SECONDS),
                      dealTicket, posId, symbol, dir > 0 ? "BUY" : (dir < 0 ? "SELL" : "NA"),
                      initialVol, targetVol, vol, level, fill, slipPrice, slipR,
                      (si >= 0) ? PartialStateText(g_posState[si].partialState) : "UNKNOWN",
                      (si >= 0) ? g_posState[si].partialTriggerTag : ""));   // v1.32 A1(c): "bar-catchup" when the catch-up armed the trigger
      FileClose(h);
     }
   else
     {
      // v1.33-C1r1: never drop a row silently (throttled 60s)
      static datetime s_openWarn = 0;
      if(TimeCurrent() - s_openWarn >= 60)
        {
         s_openWarn = TimeCurrent();
         PrintFormat("WARN: %s open failed (err %d) - row dropped", InpPartialLogFileV130, GetLastError());
        }
     }
   PrintFormat("v1.30 PARTIAL FILL position=%I64d deal=%I64u %s vol=%.2f level=%.5f fill=%.5f slip=%+.5f (%+.4fR)",
               posId, dealTicket, symbol, vol, level, fill, slipPrice, slipR);
  }

string PartialStateGv(long positionId)   { return("MPB_v130_so_state_" + (string)positionId); }
string PartialVolumeGv(long positionId)  { return("MPB_v130_so_initvol_" + (string)positionId); }
string PartialTriggerGv(long positionId) { return("MPB_v130_so_trigger_" + (string)positionId); }
string PartialAttemptsGv(long positionId){ return("MPB_v130_so_attempts_" + (string)positionId); }
string PositionFrozenAtrGv(long positionId){ return("MPB_v130_frozen_atr_" + (string)positionId); }
// v1.32 B2/B3: persisted research-arm stamps (the position keeps its arm across restarts).
string PositionRunnerGv(long positionId)   { return("MPB_v132_runner_" + (string)positionId); }
string PositionBarStopGv(long positionId)  { return("MPB_v132_barstop_" + (string)positionId); }

string PartialStateText(int state)
  {
   if(state == PARTIAL_ARMED)     return("ARMED");
   if(state == PARTIAL_TRIGGERED) return("TRIGGERED");
   if(state == PARTIAL_DONE)      return("DONE");
   if(state == PARTIAL_SKIPPED)   return("SKIPPED");
   return("UNKNOWN");
  }

int VolumeDigits(double step)
  {
   for(int d = 0; d <= 8; d++)
      if(MathAbs(NormalizeDouble(step, d) - step) < 1e-10)
         return(d);
   return(8);
  }

double FloorVolumeToStep(string symbol, double volume)
  {
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0 || volume <= 0.0)
      return(0.0);
   double units = MathFloor((volume + 1e-12) / step);
   return(NormalizeDouble(units * step, VolumeDigits(step)));
  }

double PartialTargetVolume(string symbol, double initialVolume)
  {
   if(!InpUsePartialCloseV130 || initialVolume <= 0.0)
      return(0.0);
   double minVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double raw = initialVolume * InpPartialCloseFractionV130;
   if(raw + 1e-12 < minVol)                 // binding: never round a sub-min partial upward
      return(0.0);
   double target = FloorVolumeToStep(symbol, raw);
   if(target + 1e-12 < minVol)
      return(0.0);
   if(initialVolume - target + 1e-12 < minVol) // a partial must leave a valid remainder
      return(0.0);
   return(target);
  }

bool PositionHistoryVolumes(long positionId, double &entryVolume, double &exitVolume)
  {
   entryVolume = 0.0;
   exitVolume = 0.0;
   if(!HistorySelectByPosition((ulong)positionId))
      return(false);
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0 || HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagicNumber)
         continue;
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      double v = HistoryDealGetDouble(d, DEAL_VOLUME);
      if(e == DEAL_ENTRY_IN || e == DEAL_ENTRY_INOUT)
         entryVolume += v;
      else if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_OUT_BY)
         exitVolume += v;
     }
   return(entryVolume > 0.0);
  }

bool PositionHistoryEntryContext(long positionId, double &entryPrice, int &dir, double &entryVolume)
  {
   entryPrice = 0.0;
   dir = 0;
   entryVolume = 0.0;
   if(!HistorySelectByPosition((ulong)positionId))
      return(false);
   double weightedPrice = 0.0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0 || HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagicNumber)
         continue;
      long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_IN && entry != DEAL_ENTRY_INOUT)
         continue;
      long type = HistoryDealGetInteger(deal, DEAL_TYPE);
      if(type != DEAL_TYPE_BUY && type != DEAL_TYPE_SELL)
         continue;
      double volume = HistoryDealGetDouble(deal, DEAL_VOLUME);
      if(volume <= 0.0)
         continue;
      weightedPrice += HistoryDealGetDouble(deal, DEAL_PRICE) * volume;
      entryVolume += volume;
      if(dir == 0)
         dir = (type == DEAL_TYPE_BUY) ? 1 : -1;
     }
   if(entryVolume <= 0.0 || dir == 0)
      return(false);
   entryPrice = weightedPrice / entryVolume;
   return(entryPrice > 0.0);
  }

bool FindOpenPositionById(long positionId, ulong &ticket, string &symbol, double &volume)
  {
   ticket = 0;
   symbol = "";
   volume = 0.0;
   for(int p = PositionsTotal() - 1; p >= 0; p--)
     {
      ulong t = PositionGetTicket(p);
      if(t == 0 || !posInfo.SelectByTicket(t) || posInfo.Magic() != InpMagicNumber)
         continue;
      if((long)posInfo.Identifier() != positionId)
         continue;
      ticket = t;
      symbol = posInfo.Symbol();
      volume = posInfo.Volume();
      return(true);
     }
   return(false);
  }

void PersistPartialState(int stateIdx)
  {
   if(stateIdx < 0 || stateIdx >= ArraySize(g_posState))
      return;
   long id = g_posState[stateIdx].positionId;
   GlobalVariableSet(PartialStateGv(id), (double)g_posState[stateIdx].partialState);
   if(g_posState[stateIdx].initialVolume > 0.0)
      GlobalVariableSet(PartialVolumeGv(id), g_posState[stateIdx].initialVolume);
   GlobalVariableSet(PartialAttemptsGv(id), (double)g_posState[stateIdx].partialAttempts);
   GlobalVariablesFlush();
  }

void DeletePartialGlobals(long positionId)
  {
   GlobalVariableDel(PartialStateGv(positionId));
   GlobalVariableDel(PartialVolumeGv(positionId));
   GlobalVariableDel(PartialTriggerGv(positionId));
   GlobalVariableDel(PartialAttemptsGv(positionId));
   GlobalVariablesFlush();
  }

void RefreshPartialGeometry(int stateIdx, string symbol)
  {
   if(stateIdx < 0 || stateIdx >= ArraySize(g_posState))
      return;
   if(g_posState[stateIdx].entryPrice > 0.0 && g_posState[stateIdx].riskPrice > 0.0 && g_posState[stateIdx].dir != 0)
      g_posState[stateIdx].partialLevel = g_posState[stateIdx].entryPrice
                                           + g_posState[stateIdx].dir * InpPartialCloseAtRV130
                                             * g_posState[stateIdx].riskPrice;
   if(g_posState[stateIdx].initialVolume > 0.0)
      g_posState[stateIdx].partialTargetVolume = PartialTargetVolume(symbol, g_posState[stateIdx].initialVolume);
  }

void RestorePartialState(int stateIdx, string symbol, double currentVolume)
  {
   if(stateIdx < 0 || stateIdx >= ArraySize(g_posState))
      return;
   long id = g_posState[stateIdx].positionId;
   if(GlobalVariableCheck(PartialVolumeGv(id)))
      g_posState[stateIdx].initialVolume = GlobalVariableGet(PartialVolumeGv(id));

   double inVol = 0.0, outVol = 0.0;
   if(PositionHistoryVolumes(id, inVol, outVol) && inVol > g_posState[stateIdx].initialVolume)
      g_posState[stateIdx].initialVolume = inVol;
   if(g_posState[stateIdx].initialVolume <= 0.0)
      g_posState[stateIdx].initialVolume = currentVolume;

   if(GlobalVariableCheck(PartialStateGv(id)))
      g_posState[stateIdx].partialState = (int)GlobalVariableGet(PartialStateGv(id));
   if(GlobalVariableCheck(PartialAttemptsGv(id)))
      g_posState[stateIdx].partialAttempts = (int)GlobalVariableGet(PartialAttemptsGv(id));

   RefreshPartialGeometry(stateIdx, symbol);
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double reduced = MathMax(outVol, g_posState[stateIdx].initialVolume - currentVolume);
   if(g_posState[stateIdx].partialTargetVolume <= 0.0)
      g_posState[stateIdx].partialState = PARTIAL_SKIPPED;
   else if(reduced + 0.5 * step >= g_posState[stateIdx].partialTargetVolume)
      g_posState[stateIdx].partialState = PARTIAL_DONE;
   else if(g_posState[stateIdx].partialState == PARTIAL_DONE)
      g_posState[stateIdx].partialState = PARTIAL_ARMED; // stale/corrupt GV cannot suppress a missing partial
   PersistPartialState(stateIdx);
  }

bool PartialRetcodeRetryable(uint rc)
  {
   return(rc == TRADE_RETCODE_REQUOTE || rc == TRADE_RETCODE_PRICE_CHANGED ||
          rc == TRADE_RETCODE_TIMEOUT || rc == TRADE_RETCODE_CONNECTION ||
          rc == TRADE_RETCODE_TOO_MANY_REQUESTS || rc == TRADE_RETCODE_PRICE_OFF ||
          rc == TRADE_RETCODE_LOCKED || rc == TRADE_RETCODE_MARKET_CLOSED);
  }

void SetPartialState(int stateIdx, int state, string reason)
  {
   if(stateIdx < 0 || stateIdx >= ArraySize(g_posState))
      return;
   if(g_posState[stateIdx].partialState == state)
      return;
   g_posState[stateIdx].partialState = state;
   PersistPartialState(stateIdx);
   PrintFormat("v1.30 PARTIAL STATE position=%I64d state=%s: %s",
               g_posState[stateIdx].positionId, PartialStateText(state), reason);
  }

bool ManagePartialClose(ulong ticket, int stateIdx)
  {
   if(!InpUsePartialCloseV130 || stateIdx < 0 || stateIdx >= ArraySize(g_posState))
      return(false);
   if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      SetPartialState(stateIdx, PARTIAL_SKIPPED, "account is not in hedging mode");
      return(false);
     }
   string symbol = posInfo.Symbol();
   double currentVolume = posInfo.Volume();
   RefreshPartialGeometry(stateIdx, symbol);
   int state = g_posState[stateIdx].partialState;
   if(state == PARTIAL_DONE || state == PARTIAL_SKIPPED)
      return(false);
   if(g_posState[stateIdx].partialLevel <= 0.0 || g_posState[stateIdx].riskPrice <= 0.0)
      return(false);

   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick) || tick.bid <= 0.0 || tick.ask <= 0.0)
      return(false);
   double exitSide = (g_posState[stateIdx].dir > 0) ? tick.bid : tick.ask;
   bool reached = (g_posState[stateIdx].dir > 0)
                  ? (exitSide >= g_posState[stateIdx].partialLevel)
                  : (exitSide <= g_posState[stateIdx].partialLevel);
   if(state == PARTIAL_ARMED)
     {
      // v1.32 A1(b): freshness guard on the trigger - a stale/weekend tick must not arm
      // the partial. A stale tick simply DEFERS the check to the next heartbeat (reuses
      // the entry guard: InpFreshnessGuard / InpMaxTickAgeSec).
      if(InpFreshnessGuard && !QuotesFresh(symbol))
         return(false);

      // v1.32 A1(c): bar-extreme catch-up trigger. A spike to +1R BETWEEN heartbeats
      // never touches the 5s tick check; if the CURRENT forming bar (which must have
      // opened AFTER the entry bar) already traded through the level, treat as TRIGGERED
      // and close at market NOW. The entry bar itself is skipped (its extreme may predate
      // the fill) - the tick trigger above still covers it.
      bool barCatchup = false;
      if(!reached && InpPartialBarCatchupV132 && g_posState[stateIdx].entryBarTime > 0)
        {
         datetime curBar = (datetime)iTime(symbol, InpTimeframe, 0);
         if(curBar > g_posState[stateIdx].entryBarTime)
           {
            double hi = iHigh(symbol, InpTimeframe, 0);
            double lo = iLow(symbol, InpTimeframe, 0);
            if(hi > 0.0 && lo > 0.0 &&
               ((g_posState[stateIdx].dir > 0 && hi >= g_posState[stateIdx].partialLevel) ||
                (g_posState[stateIdx].dir < 0 && lo <= g_posState[stateIdx].partialLevel)))
              {
               reached = true;
               barCatchup = true;
              }
           }
        }
      if(!reached)
         return(false);
      g_posState[stateIdx].partialState = PARTIAL_TRIGGERED;
      g_posState[stateIdx].partialNextRetry = 0;
      g_posState[stateIdx].partialAttempts = 0;
      g_posState[stateIdx].partialGapSeen = false;                                  // v1.32 A1(a)
      g_posState[stateIdx].partialTriggerTag = barCatchup ? "bar-catchup" : "";     // v1.32 A1(c): reason tag for the partials CSV
      PersistPartialState(stateIdx);
      if(barCatchup)
         PrintFormat("v1.32 PARTIAL TRIGGER (bar-catchup) position=%I64d %s level=%.5f - bar extreme reached between heartbeats; closing at market",
                     g_posState[stateIdx].positionId, symbol, g_posState[stateIdx].partialLevel);
      else
         PrintFormat("v1.30 PARTIAL TRIGGER position=%I64d %s level=%.5f exitSide=%.5f initialVol=%.2f targetVol=%.2f",
                     g_posState[stateIdx].positionId, symbol, g_posState[stateIdx].partialLevel,
                     exitSide, g_posState[stateIdx].initialVolume, g_posState[stateIdx].partialTargetVolume);
     }

   if(TimeCurrent() < g_posState[stateIdx].partialNextRetry)
      return(false);

   double inVol = 0.0, outVol = 0.0;
   PositionHistoryVolumes(g_posState[stateIdx].positionId, inVol, outVol);
   double reduced = MathMax(outVol, g_posState[stateIdx].initialVolume - currentVolume);
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double minVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double remaining = g_posState[stateIdx].partialTargetVolume - reduced;
   if(remaining <= 0.5 * step)
     {
      SetPartialState(stateIdx, PARTIAL_DONE, "reconciled target volume");
      return(false);
     }
   double closeVolume = FloorVolumeToStep(symbol, remaining);
   if(closeVolume + 1e-12 < minVol || currentVolume - closeVolume + 1e-12 < minVol)
     {
      SetPartialState(stateIdx, PARTIAL_SKIPPED, "partial volume is below broker min/step or leaves invalid remainder");
      return(false);
     }
   if(g_posState[stateIdx].partialAttempts >= V130_PARTIAL_MAX_ATTEMPTS)
     {
      SetPartialState(stateIdx, PARTIAL_SKIPPED, "bounded retry limit reached");
      return(false);
     }

   trade.SetTypeFillingBySymbol(symbol);
   bool ok = trade.PositionClosePartial(ticket, closeVolume, InpDeviationPoints);
   uint rc = trade.ResultRetcode();
   // v1.32 A1(a): per-retcode budgets. A closed market / lost connection is NOT a trade-
   // server rejection: do NOT burn the V130_PARTIAL_MAX_ATTEMPTS budget on it - stay
   // TRIGGERED and retry every 60s until the market reopens (weekend-skip fix: v1.31
   // exhausted all 5 retries in ~2.5 min on a late-Friday +1R touch and the validated
   // 50% bank was SKIPPED forever). MQL5's "no connection" retcode is TRADE_RETCODE_CONNECTION.
   if(rc == TRADE_RETCODE_MARKET_CLOSED || rc == TRADE_RETCODE_CONNECTION)
     {
      g_posState[stateIdx].partialNextRetry = TimeCurrent() + 60;
      g_posState[stateIdx].partialGapSeen = true;
      PersistPartialState(stateIdx);
      return(false);
     }
   if(g_posState[stateIdx].partialGapSeen)
     {
      // The first attempt after a market-closed gap logs the re-arm exactly once.
      g_posState[stateIdx].partialGapSeen = false;
      PrintFormat("v1.32 PARTIAL re-arm after market reopen: position=%I64d %s retcode=%u (%s) - attempt budget intact (%d/%d)",
                  g_posState[stateIdx].positionId, symbol, rc, trade.ResultRetcodeDescription(),
                  g_posState[stateIdx].partialAttempts, V130_PARTIAL_MAX_ATTEMPTS);
     }
   g_posState[stateIdx].partialAttempts++;
   g_posState[stateIdx].partialNextRetry = TimeCurrent() + MathMax(InpPartialRetrySecondsV130, 5);
   PersistPartialState(stateIdx);
   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL))
     {
      PrintFormat("v1.30 PARTIAL REQUEST position=%I64d %s closeVol=%.2f retcode=%u (%s) deal=%I64u price=%.5f",
                  g_posState[stateIdx].positionId, symbol, closeVolume, rc,
                  trade.ResultRetcodeDescription(), trade.ResultDeal(), trade.ResultPrice());
      return(true); // avoid a same-heartbeat full-management race; deal event/reconcile finalizes state
     }
   if(!PartialRetcodeRetryable(rc))
      SetPartialState(stateIdx, PARTIAL_SKIPPED, StringFormat("non-retryable retcode %u (%s)", rc, trade.ResultRetcodeDescription()));
   else
      PrintFormat("v1.30 PARTIAL RETRY position=%I64d %s attempt=%d/%d retcode=%u (%s)",
                  g_posState[stateIdx].positionId, symbol, g_posState[stateIdx].partialAttempts,
                  V130_PARTIAL_MAX_ATTEMPTS, rc, trade.ResultRetcodeDescription());
   return(false);
  }

//+------------------------------------------------------------------+
//| barsClosed = closed bars since (and including) the entry bar,     |
//| recomputed from the entry bar's shift so a multi-bar backfill     |
//| after a connection outage counts every bar, not just one          |
//| (review P4: prevents a LATE time exit after outages).             |
//+------------------------------------------------------------------+
void UpdateBarsClosed(int stateIdx, string symbol)
  {
   datetime entryBar = g_posState[stateIdx].entryBarTime;
   // v1.32 A9: an unseeded clock with no anchor yet re-anchors to the current bar 0
   // (same fallback v1.31 used at registration) so the recompute below can retry.
   if(entryBar <= 0 && !g_posState[stateIdx].barClockSeeded)
     {
      entryBar = (datetime)iTime(symbol, InpTimeframe, 0);
      g_posState[stateIdx].entryBarTime = entryBar;
     }
   if(entryBar > 0)
     {
      int shift = iBarShift(symbol, InpTimeframe, entryBar, false);
      if(shift >= 0)
        {
         // Entry bar at shift s => s bars opened after it => s closes elapsed
         // (the entry bar's own close is counted, matching RegisterPositionState).
         g_posState[stateIdx].barsClosed = shift;
         g_posState[stateIdx].barClockSeeded = true;   // v1.32 A9: recompute succeeded
         return;
        }
     }
   // v1.32 A9: the anchor lookup FAILED (unsynced/truncated history) - mark the clock
   // unseeded and retry the recompute on the next bar close. NEVER blind-increment an
   // unseeded clock: v1.31's ++ fallback could fire the time exit up to 8 bars late
   // after a cold restart.
   g_posState[stateIdx].barClockSeeded = false;
  }

//+------------------------------------------------------------------+
//| Single ATR accessor - thin alias for WilderAtrForSymbol (v1.27:   |
//| one estimator everywhere, CopyRates on closed bars; no iATR       |
//| handles involved). Works for ANY symbol including whitelist-      |
//| orphan positions - only the per-symbol CACHE is universe-indexed. |
//+------------------------------------------------------------------+
bool ReadAtrForSymbol(string symbol, double &value)
  {
   return(WilderAtrForSymbol(symbol, value));   // v1.27: single estimator everywhere
  }

void RegisterPositionState(long positionId, string symbol, double signalAtr, datetime openTime,
                           bool signalAtrAuthoritative=false)
  {
   int existing = FindPositionState(positionId);
   if(existing >= 0)
     {
      // A pending may fill while the terminal is offline. Retry recovery from its
      // persisted order-ticket ATR before accepting a current-ATR fallback.
      if(!signalAtrAuthoritative && !g_posState[existing].signalAtrFrozen)
        {
         double recoveredAtr = 0.0;
         if(GlobalVariableCheck(PositionFrozenAtrGv(positionId)))
            recoveredAtr = GlobalVariableGet(PositionFrozenAtrGv(positionId));
         if(recoveredAtr <= 0.0)
            recoveredAtr = TakePendingSigAtrForPosition(positionId);
         if(recoveredAtr > 0.0)
           {
            signalAtr = recoveredAtr;
            signalAtrAuthoritative = true;
           }
        }
      // A real signal ATR may replace a fallback registration. A later fragmented
      // entry fill may not replace an already-authoritative ATR.
      if(signalAtr > 0.0 &&
         (signalAtrAuthoritative || g_posState[existing].signalAtr <= 0.0) &&
         (g_posState[existing].signalAtr != signalAtr ||
          g_posState[existing].signalAtrFrozen != signalAtrAuthoritative))
        {
         g_posState[existing].signalAtr = signalAtr;
         g_posState[existing].signalAtrFrozen = signalAtrAuthoritative;
         GlobalVariableSet("DSv121_atr_" + (string)positionId, signalAtr);
         if(signalAtrAuthoritative)
            GlobalVariableSet(PositionFrozenAtrGv(positionId), signalAtr);
         GlobalVariablesFlush();
         if(g_posState[existing].entryPrice > 0.0)
           {
            // v1.32 A5: keep the R denominator honest with the ACTUAL placed stop when
            // one is readable (in B3 mode the placed SL is only a disaster backstop).
            double slNow = 0.0;
            ulong t5 = 0; string s5 = ""; double v5 = 0.0;
            if(!g_posState[existing].barCloseStopV132 && FindOpenPositionById(positionId, t5, s5, v5))
               slNow = posInfo.StopLoss();
            g_posState[existing].riskPrice = (slNow > 0.0) ? MathAbs(g_posState[existing].entryPrice - slNow)
                                                           : InpStopAtrMult * signalAtr;
           }
         RefreshPartialGeometry(existing, symbol);
        }
      return;
     }

   // v1.32 A9: guard DataReady before the first compute; when the entry-bar anchor
   // cannot be resolved (unsynced history), mark the bar clock UNSEEDED (RAM only) -
   // UpdateBarsClosed then retries the recompute on every bar close and never
   // blind-increments (v1.31 fell back to iTime(0) and could time-exit 8 bars late).
   datetime entryBar = (datetime)iTime(symbol, InpTimeframe, 0);
   bool barSeeded = true;
   int shift = -1;
   if(DataReady(symbol))
      shift = iBarShift(symbol, InpTimeframe, openTime, false);
   if(shift >= 0)
      entryBar = (datetime)iTime(symbol, InpTimeframe, shift);
   else
      barSeeded = false;

   // Frozen-ATR persistence: prefer an authoritative position GV, then recover
   // the placement-time ATR through the entry deal's persisted order-ticket GV.
   if(!signalAtrAuthoritative && GlobalVariableCheck(PositionFrozenAtrGv(positionId)))
     {
      signalAtr = GlobalVariableGet(PositionFrozenAtrGv(positionId));
      signalAtrAuthoritative = (signalAtr > 0.0);
     }
   if(!signalAtrAuthoritative)
     {
      double recoveredAtr = TakePendingSigAtrForPosition(positionId);
      if(recoveredAtr > 0.0)
        {
         signalAtr = recoveredAtr;
         signalAtrAuthoritative = true;
        }
     }

   // Legacy fallback GV can contain a current-ATR recovery from older versions;
   // retain it for continuity but never label it authoritative.
   string gvName = "DSv121_atr_" + (string)positionId;   // legacy DerivScalper-era GV name, kept for cross-version restart continuity
   if(signalAtr <= 0.0 && GlobalVariableCheck(gvName))
      signalAtr = GlobalVariableGet(gvName);
   if(signalAtr <= 0.0)
      ReadAtrForSymbol(symbol, signalAtr);
   if(signalAtr > 0.0)
      GlobalVariableSet(gvName, signalAtr);
   if(signalAtrAuthoritative && signalAtr > 0.0)
      GlobalVariableSet(PositionFrozenAtrGv(positionId), signalAtr);
   GlobalVariablesFlush();

   int barsClosed = 0;
   for(int s = 1; s < 500; s++)
     {
      datetime bt = (datetime)iTime(symbol, InpTimeframe, s);
      if(bt == 0 || bt < entryBar)   // count the entry bar's own close too (review fix:
         break;                      // `<=` undercounted by 1 after mid-trade reloads)
      barsClosed++;
     }

   int n = ArraySize(g_posState);
   ArrayResize(g_posState, n + 1);
   g_posState[n].positionId = positionId;
   g_posState[n].signalAtr = signalAtr;
   g_posState[n].entryBarTime = entryBar;
   g_posState[n].lastMgmtBarTime = (datetime)iTime(symbol, InpTimeframe, 0);
   g_posState[n].barsClosed = barsClosed;
   g_posState[n].entryPrice = 0.0;
   g_posState[n].riskPrice = 0.0;
   g_posState[n].dir = 0;
   g_posState[n].spreadAtrEntry = 0.0;
   g_posState[n].mfeR = 0.0;
   g_posState[n].maeR = 0.0;
   g_posState[n].initialVolume = 0.0;
   g_posState[n].signalAtrFrozen = signalAtrAuthoritative;
   g_posState[n].partialTargetVolume = 0.0;
   g_posState[n].partialLevel = 0.0;
   g_posState[n].partialState = PARTIAL_ARMED;
   g_posState[n].partialNextRetry = 0;
   g_posState[n].partialAttempts = 0;
   g_posState[n].partialGapSeen = false;        // v1.32 A1(a)
   g_posState[n].partialTriggerTag = "";        // v1.32 A1(c)
   g_posState[n].barClockSeeded = barSeeded;    // v1.32 A9
   // v1.32 B2/B3: restore a persisted research-arm stamp (the position was placed under
   // an arm and the EA restarted); positions already open at attach have no stamp and
   // keep the validated bracket/touch semantics.
   g_posState[n].runnerV132 = (GlobalVariableCheck(PositionRunnerGv(positionId)) &&
                               GlobalVariableGet(PositionRunnerGv(positionId)) > 0.5);
   g_posState[n].barCloseStopV132 = (GlobalVariableCheck(PositionBarStopGv(positionId)) &&
                                     GlobalVariableGet(PositionBarStopGv(positionId)) > 0.5);

   // v1.26: populate entry context from the LIVE position so trade-log rows survive
   // registrations outside the DEAL_ENTRY_IN path (reload sync, prune race) -
   // previously such rows logged dir=SELL entry=0 realized_R=0 (audit).
   double currentVolume = 0.0;
   for(int p = PositionsTotal() - 1; p >= 0; p--)
     {
      ulong pt = PositionGetTicket(p);
      if(pt == 0 || !posInfo.SelectByTicket(pt))
         continue;
      if((long)posInfo.Identifier() != positionId)
         continue;
      g_posState[n].entryPrice = posInfo.PriceOpen();
      g_posState[n].dir = (posInfo.PositionType() == POSITION_TYPE_BUY) ? 1 : -1;
      currentVolume = posInfo.Volume();
      double slp = posInfo.StopLoss();
      // v1.32 A5: honest R from the ACTUAL placed stop when one is readable; in B3
      // bar-close-stop mode the placed SL is only a disaster backstop, so the intended
      // stop (InpStopAtrMult * signalAtr) remains the R denominator there.
      if(slp > 0.0 && !g_posState[n].barCloseStopV132)
         g_posState[n].riskPrice = MathAbs(g_posState[n].entryPrice - slp);
      else if(signalAtr > 0.0)
         g_posState[n].riskPrice = InpStopAtrMult * signalAtr;
      else if(slp > 0.0)
         g_posState[n].riskPrice = MathAbs(g_posState[n].entryPrice - slp);   // degraded fallback only
      break;
     }
   RestorePartialState(n, symbol, currentVolume);
  }

void SyncOpenPositionStates()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !posInfo.SelectByTicket(ticket))
         continue;
      if(posInfo.Magic() != InpMagicNumber)
         continue;
      RegisterPositionState((long)posInfo.Identifier(), posInfo.Symbol(), 0.0, posInfo.Time());
     }
  }

void PruneClosedPositionStates()
  {
   for(int i = ArraySize(g_posState) - 1; i >= 0; i--)
     {
      bool open = false;
      for(int p = PositionsTotal() - 1; p >= 0; p--)
        {
         ulong ticket = PositionGetTicket(p);
         if(ticket == 0 || !posInfo.SelectByTicket(ticket))
            continue;
         if(posInfo.Magic() != InpMagicNumber)
            continue;
         if((long)posInfo.Identifier() == g_posState[i].positionId)
           {
            open = true;
            break;
           }
        }
      if(!open)
        {
         GlobalVariableDel("DSv121_atr_" + (string)g_posState[i].positionId);
         GlobalVariableDel(PositionFrozenAtrGv(g_posState[i].positionId));
         GlobalVariableDel(PositionRunnerGv(g_posState[i].positionId));    // v1.32 B2
         GlobalVariableDel(PositionBarStopGv(g_posState[i].positionId));   // v1.32 B3
         DeletePartialGlobals(g_posState[i].positionId);
         for(int j = i; j < ArraySize(g_posState) - 1; j++)
            g_posState[j] = g_posState[j + 1];
         ArrayResize(g_posState, ArraySize(g_posState) - 1);
        }
     }
  }

int SymbolIndex(string symbol)
  {
   for(int i = 0; i < ArraySize(g_symbols); i++)
      if(g_symbols[i] == symbol)
         return(i);
   return(-1);
  }

// v1.27 B1: Wilder ATR (RMA, alpha=1/period) computed from closed bars - the
// exact estimator of the validated engine (scalper_backtest.py::wilder_atr).
// MT5 built-in iATR is a sliding SIMPLE mean of TR (Examples/ATR.mq5 line 92)
// and diverges 12-14% median; the impulse gate disagreed on ~1/5 of signals.
// Seeded with SMA(period) then RMA over ~400 bars: seed influence (13/14)^386 ~ 0.
bool WilderAtrForSymbol(string symbol, double &value)
  {
   value = 0.0;
   int idx = SymbolIndex(symbol);
   datetime bar1 = (datetime)iTime(symbol, InpTimeframe, 1);
   if(idx >= 0 && bar1 > 0 && g_wAtrCacheBar[idx] == bar1 && g_wAtrCache[idx] > 0.0)
     {
      value = g_wAtrCache[idx];
      return(true);
     }
   MqlRates rates[];
   int need = 400;
   int got = CopyRates(symbol, InpTimeframe, 1, need, rates);   // shift 1 = closed bars only
   if(got < InpAtrPeriod * 3)
      return(false);
   double atr = 0.0;
   // seed: SMA of TR over bars 1..period (index 0 has no prev close -> excluded)
   for(int k = 1; k <= InpAtrPeriod; k++)
     {
      double tr = MathMax(rates[k].high - rates[k].low,
                  MathMax(MathAbs(rates[k].high - rates[k - 1].close),
                          MathAbs(rates[k].low  - rates[k - 1].close)));
      atr += tr;
     }
   atr /= InpAtrPeriod;
   for(int k = InpAtrPeriod + 1; k < got; k++)
     {
      double tr = MathMax(rates[k].high - rates[k].low,
                  MathMax(MathAbs(rates[k].high - rates[k - 1].close),
                          MathAbs(rates[k].low  - rates[k - 1].close)));
      atr += (tr - atr) / InpAtrPeriod;
     }
   if(atr <= 0.0)
      return(false);
   value = atr;
   if(idx >= 0 && bar1 > 0)
     {
      g_wAtrCache[idx] = atr;
      g_wAtrCacheBar[idx] = bar1;
     }
   return(true);
  }

// v1.27 B6: snap a price to the symbol's trade tick grid (servers reject off-grid
// prices with 10015/10016). No-op where tick size == point (current universe).
double SnapPrice(string symbol, double price)
  {
   double tick = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0.0)
      tick = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(tick <= 0.0)
      return(price);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   return(NormalizeDouble(MathRound(price / tick) * tick, digits));
  }

bool DataReady(string symbol)
  {
   if(!SymbolIsSynchronized(symbol))
     {
      SymbolSelect(symbol, true);
      return(false);
     }
   return(Bars(symbol, InpTimeframe) > InpMomentumBars + InpAtrPeriod + 2);
  }

bool HasExposure(string symbol)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t != 0 && posInfo.SelectByTicket(t) &&
         posInfo.Symbol() == symbol && posInfo.Magic() == InpMagicNumber)
         return(true);
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t != 0 && ordInfo.Select(t) &&
         ordInfo.Symbol() == symbol && ordInfo.Magic() == InpMagicNumber)
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Correlation cluster index for a symbol per InpClusterSpec         |
//| (';' between clusters, '|' between symbols). -1 = unclustered.    |
//+------------------------------------------------------------------+
int ClusterOf(string symbol)
  {
   string clusters[];
   int nc = StringSplit(InpClusterSpec, StringGetCharacter(";", 0), clusters);
   for(int ci = 0; ci < nc; ci++)
     {
      string members[];
      int nm = StringSplit(clusters[ci], StringGetCharacter("|", 0), members);
      for(int mi = 0; mi < nm; mi++)
         if(Trim(members[mi]) == symbol)
            return(ci);
     }
   return(-1);
  }

//+------------------------------------------------------------------+
//| Open positions + pendings (ours) whose symbol is in the cluster  |
//+------------------------------------------------------------------+
int CountClusterExposure(int cluster)
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t != 0 && posInfo.SelectByTicket(t) && posInfo.Magic() == InpMagicNumber &&
         ClusterOf(posInfo.Symbol()) == cluster)
         count++;
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t != 0 && ordInfo.Select(t) && ordInfo.Magic() == InpMagicNumber &&
         ClusterOf(ordInfo.Symbol()) == cluster)
         count++;
     }
   return(count);
  }

int CountOpenAndPending()
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t != 0 && posInfo.SelectByTicket(t) && posInfo.Magic() == InpMagicNumber)
         count++;
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t != 0 && ordInfo.Select(t) && ordInfo.Magic() == InpMagicNumber)
         count++;
     }
   return(count);
  }

//+------------------------------------------------------------------+
//| Day / risk state                                                 |
//+------------------------------------------------------------------+
void ResetDailyState()
  {
   g_currentDay      = DayStart(TimeCurrent());
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_tradesToday     = 0;
   ArrayResize(g_fillPosIdsToday, 0);   // v1.32 A4: day-scoped distinct-position set resets with the cap
   g_halted          = false;
  }

datetime DayStart(datetime t)
  {
   MqlDateTime st;
   TimeToStruct(t, st);
   st.hour = 0; st.min = 0; st.sec = 0;
   return(StructToTime(st));
  }

// v1.32 A7: magic-scoped risk-ledger GV names (the legacy terminal-global names were
// shared by every instance of this EA on the terminal -> multi-instance interference).
string PeakEquityGv()  { return("MPB_" + (string)InpMagicNumber + "_peak_equity"); }
string InitBalanceGv() { return("MPB_" + (string)InpMagicNumber + "_init_balance"); }

void UpdatePeakEquity()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEquity)
     {
      g_peakEquity = eq;
      GlobalVariableSet(PeakEquityGv(), g_peakEquity);   // v1.26: the trailing halt must see across re-inits (v1.32 A7: magic-scoped)
     }
  }

bool DrawdownExceeded()
  {
   if(InpMaxDrawdownPct <= 0.0 || g_peakEquity <= 0.0)
      return(false);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   return((g_peakEquity - eq) / g_peakEquity * 100.0 >= InpMaxDrawdownPct);
  }

bool DailyLossExceeded()
  {
   if(InpDailyLossLimitPct <= 0.0 || g_dayStartBalance <= 0.0)
      return(false);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   return((g_dayStartBalance - eq) >= g_dayStartBalance * (InpDailyLossLimitPct / 100.0));
  }

// v1.26: hard-halt floor - FTMO terminates at equity < 90% of INITIAL balance; the
// trailing peak check alone re-anchors on re-init and can sink below that line.
bool StaticFloorBreached()
  {
   if(InpStaticFloorPct <= 0.0 || g_initialBalance <= 0.0)
      return(false);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   return(eq <= g_initialBalance * (1.0 - InpStaticFloorPct / 100.0));
  }

// v1.26: delete every resting pending with our magic (halt enforcement).
void CancelAllPendings(string why)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0 || !ordInfo.Select(t) || ordInfo.Magic() != InpMagicNumber)
         continue;
      bool ok = trade.OrderDelete(t);
      uint rc = trade.ResultRetcode();
      if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED))
        {
         TakePendingSigAtr(t);
         PrintFormat("Cancelled pending #%I64u (%s)", t, why);
        }
      else
         PrintFormat("Cancel FAILED for pending #%I64u (%s): retcode %u - will retry next heartbeat", t, why, rc);
     }
  }

// v1.26: reconstruct the daily risk ledger + persistent anchors on (re)init.
// A plain reset here was audit P1: any mid-day recompile/restart/input-change
// re-armed a fresh 4% daily budget and re-anchored the trailing-DD peak.
void RestoreRiskLedger()
  {
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   // v1.29.1: a cold start can run this BEFORE the account syncs (observed 16:50:
   // bal/eq=0 -> dayStartBal=799, both halts latched on garbage). Defer instead.
   if(bal <= 0.0 || eq <= 0.0)
     {
      g_ledgerValid = false;
      Print("Risk ledger: account not synced yet (bal/eq<=0) - restore deferred");
      return;
     }
   g_ledgerValid = true;

   g_peakEquity = eq;
   if(GlobalVariableCheck(PeakEquityGv()))   // v1.32 A7: magic-scoped (migrated in OnInit)
      g_peakEquity = MathMax(GlobalVariableGet(PeakEquityGv()), eq);
   GlobalVariableSet(PeakEquityGv(), g_peakEquity);

   g_initialBalance = InpInitialBalance;
   if(g_initialBalance <= 0.0)
     {
      if(!GlobalVariableCheck(InitBalanceGv()))   // v1.32 A7: magic-scoped
         GlobalVariableSet(InitBalanceGv(), bal);
      g_initialBalance = GlobalVariableGet(InitBalanceGv());
     }

   g_currentDay = DayStart(TimeCurrent());
   double dayPnl = 0.0;
   int placements = 0;
   ArrayResize(g_fillPosIdsToday, 0);   // v1.32 A4: rebuilt alongside the count below
   if(HistorySelect(g_currentDay, TimeCurrent()))
     {
      int nd = HistoryDealsTotal();
      for(int i = 0; i < nd; i++)
        {
         ulong d = HistoryDealGetTicket(i);
         if(d == 0)
            continue;
         long ty = HistoryDealGetInteger(d, DEAL_TYPE);
         if(ty != DEAL_TYPE_BUY && ty != DEAL_TYPE_SELL)
            continue;                          // skip balance/credit rows
         dayPnl += HistoryDealGetDouble(d, DEAL_PROFIT)
                 + HistoryDealGetDouble(d, DEAL_SWAP)
                 + HistoryDealGetDouble(d, DEAL_COMMISSION);   // account-wide, matches the FTMO day
         // v1.27 B3: the daily cap counts FILLS now - reconstruct the same way.
         // v1.32 A4: ...but count DISTINCT positions, not broker fill fragments, so a
         // restart lands on the same count as the live counter.
         if(HistoryDealGetInteger(d, DEAL_MAGIC) == InpMagicNumber &&
            HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
           {
            long pid = HistoryDealGetInteger(d, DEAL_POSITION_ID);
            bool dup = false;
            for(int s = 0; s < ArraySize(g_fillPosIdsToday); s++)
               if(g_fillPosIdsToday[s] == pid)
                 {
                  dup = true;
                  break;
                 }
            if(!dup)
              {
               int np = ArraySize(g_fillPosIdsToday);
               ArrayResize(g_fillPosIdsToday, np + 1);
               g_fillPosIdsToday[np] = pid;
               placements++;
              }
           }
        }
     }

   g_dayStartBalance = bal - dayPnl;
   g_tradesToday     = placements;
   g_halted          = DailyLossExceeded();
   g_haltedHard      = (DrawdownExceeded() || StaticFloorBreached());
   PrintFormat("Risk ledger restored: dayStartBal=%.2f dayPnL=%.2f fillsToday=%d peakEq=%.2f initBal=%.2f halted=%s hard=%s",
               g_dayStartBalance, dayPnl, g_tradesToday, g_peakEquity, g_initialBalance,
               g_halted ? "yes" : "no", g_haltedHard ? "yes" : "no");
  }

int ConsecutiveLossesToday()
  {
   if(!HistorySelect(g_currentDay, TimeCurrent()))
      return(0);
   int total = HistoryDealsTotal();
   // v1.33-C1r3 (C10 fix): memoize the streak - it can only change when the day rolls
   // over, a new deal lands, or a position opens/closes. Keying on all three makes the
   // cache EXACT (any change recomputes); on a cache hit we skip the O(deals^2) rescan
   // that ran every 5s heartbeat. Behavior-identical: the fallback is always a full
   // recompute, so a stale cache can only cost work, never miss a halt.
   static datetime s_cacheDay   = 0;
   static int      s_cacheDeals = -1;
   static int      s_cachePos   = -1;
   static int      s_cacheStreak = 0;
   int posTotal = PositionsTotal();
   if(g_currentDay == s_cacheDay && total == s_cacheDeals && posTotal == s_cachePos)
      return(s_cacheStreak);

   int streak = 0;
   long seen[];
   ArrayResize(seen, 0);
   for(int i = total - 1; i >= 0; i--)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0)
         continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagicNumber)
         continue;
      long de = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(de != DEAL_ENTRY_OUT && de != DEAL_ENTRY_OUT_BY)
         continue;
      long posId = HistoryDealGetInteger(d, DEAL_POSITION_ID);
      bool duplicate = false;
      for(int s = 0; s < ArraySize(seen); s++)
         if(seen[s] == posId) { duplicate = true; break; }
      if(duplicate)
         continue;

      // A still-open position has only emitted a v1.30 partial; it is not a
      // completed win/loss and cannot reset or extend the daily streak.
      ulong openTicket = 0; string openSymbol = ""; double openVolume = 0.0;
      if(FindOpenPositionById(posId, openTicket, openSymbol, openVolume))
         continue;

      int ns = ArraySize(seen);
      ArrayResize(seen, ns + 1);
      seen[ns] = posId;
      double pnl = 0.0;
      for(int j = 0; j < total; j++)
        {
         ulong pd = HistoryDealGetTicket(j);
         if(pd == 0 || HistoryDealGetInteger(pd, DEAL_MAGIC) != InpMagicNumber ||
            HistoryDealGetInteger(pd, DEAL_POSITION_ID) != posId)
            continue;
         pnl += HistoryDealGetDouble(pd, DEAL_PROFIT)
              + HistoryDealGetDouble(pd, DEAL_SWAP)
              + HistoryDealGetDouble(pd, DEAL_COMMISSION);
        }
      if(pnl < 0.0)
         streak++;
      else if(pnl > 0.0)
         break;
     }
   s_cacheDay = g_currentDay; s_cacheDeals = total; s_cachePos = posTotal; s_cacheStreak = streak;
   return(streak);
  }

//+------------------------------------------------------------------+
//| v1.28 THOUGHT-PROCESS PANEL - observability only, fails soft.     |
//| No function below touches orders, positions, or risk state.       |
//+------------------------------------------------------------------+
#define MPB_PANEL_LINES 10

void SetVerdict(string symbol, string text)
  {
   int i = SymbolIndex(symbol);
   if(i < 0 || i >= ArraySize(g_lastVerdict))
      return;
   g_lastVerdict[i]  = text;
   g_lastVerdictT[i] = TimeCurrent();
  }

void PanelInit()
  {
   if(!InpShowPanel)
      return;
   string bg = "MPBPANEL_BG";
   if(ObjectFind(0, bg) < 0)
      ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, bg, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, 8);
   ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, 118);
   ObjectSetInteger(0, bg, OBJPROP_XSIZE, 590);
   ObjectSetInteger(0, bg, OBJPROP_YSIZE, 16 * MPB_PANEL_LINES + 14);
   ObjectSetInteger(0, bg, OBJPROP_BGCOLOR, C'14,14,22');
   ObjectSetInteger(0, bg, OBJPROP_COLOR, clrDimGray);
   ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, bg, OBJPROP_HIDDEN, true);
   for(int i = 0; i < MPB_PANEL_LINES; i++)
     {
      string nm = "MPBPANEL_L" + (string)i;
      if(ObjectFind(0, nm) < 0)
         ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 14);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 124 + 16 * i);
      ObjectSetString (0, nm, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 8);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, clrSilver);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetString (0, nm, OBJPROP_TEXT, " ");
     }
  }

void PanelDestroy()
  {
   ObjectsDeleteAll(0, "MPBPANEL_");
  }

void PanelSet(int line, string text, color clr = clrSilver)
  {
   string nm = "MPBPANEL_L" + (string)line;
   ObjectSetString (0, nm, OBJPROP_TEXT, StringLen(text) > 0 ? text : " ");
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
  }

void PanelUpdate()
  {
   if(!InpShowPanel)
      return;
   static datetime s_last = 0;
   datetime now = TimeCurrent();
   if(now - s_last < InpPanelRefreshSec)
      return;
   s_last = now;

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double dayPnl = eq - g_dayStartBalance;
   int ln = 0;
   PanelSet(ln++, StringFormat("MomentumPullbackEA " + MPB_VERSION + "  THOUGHT PROCESS   %s srv",
             TimeToString(now, TIME_DATE | TIME_SECONDS)), clrGoldenrod);

   for(int i = 0; i < ArraySize(g_symbols) && ln < MPB_PANEL_LINES - 4; i++)
     {
      string v = (i < ArraySize(g_lastVerdict) && StringLen(g_lastVerdict[i]) > 0)
                 ? g_lastVerdict[i] : "(no scan event yet this session)";
      string ts = (i < ArraySize(g_lastVerdictT) && g_lastVerdictT[i] > 0)
                  ? TimeToString(g_lastVerdictT[i], TIME_MINUTES) : "--:--";
      color cc = (StringFind(v, "SIGNAL") == 0) ? clrLimeGreen
               : (StringFind(v, "no impulse") >= 0) ? clrGray : clrTomato;
      PanelSet(ln++, StringFormat("%-11s [%s] %s", g_symbols[i], ts, StringSubstr(v, 0, 60)), cc);
     }

   int shown = 0;
   for(int p = PositionsTotal() - 1; p >= 0 && ln < MPB_PANEL_LINES - 2; p--)
     {
      ulong tk = PositionGetTicket(p);
      if(tk == 0 || !posInfo.SelectByTicket(tk) || posInfo.Magic() != InpMagicNumber)
         continue;
      int si = FindPositionState((long)posInfo.Identifier());
      double mfe = (si >= 0) ? g_posState[si].mfeR : 0.0;
      double mae = (si >= 0) ? g_posState[si].maeR : 0.0;
      int bars = (si >= 0) ? g_posState[si].barsClosed : 0;
      // v1.32 B2: display the runner backstop for runner positions (display only).
      int maxB = (si >= 0 && g_posState[si].runnerV132) ? InpRunnerMaxBarsV132 : InpMaxHoldingBars;
      string so = (si >= 0) ? StringFormat("%s@%.2f", PartialStateText(g_posState[si].partialState),
                                            g_posState[si].partialLevel) : "UNKNOWN";
      PanelSet(ln++, StringFormat("POS %s %s %.2f @ %.2f | b%d/%d | MFE%+.2f MAE%+.2f | SO %s",
                posInfo.Symbol(), posInfo.PositionType() == POSITION_TYPE_BUY ? "BUY " : "SELL",
                posInfo.Volume(), posInfo.PriceOpen(), bars, maxB, mfe, mae, so),
                clrDeepSkyBlue);
      shown++;
     }
   int pend = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t2 = OrderGetTicket(i);
      if(t2 != 0 && ordInfo.Select(t2) && ordInfo.Magic() == InpMagicNumber)
         pend++;
     }
   if(shown == 0 && ln < MPB_PANEL_LINES - 2)
      PanelSet(ln++, StringFormat("positions: none | resting pendings: %d", pend), clrSilver);

   PanelSet(ln++, StringFormat("fills %d/%d | dayPnL %+.2f (day-halt at %+.0f) | eq %.2f",
            g_tradesToday, InpMaxTradesPerDay, dayPnl,
            -g_dayStartBalance * InpDailyLossLimitPct / 100.0, eq),
            (dayPnl >= 0) ? clrLimeGreen : clrOrange);
   PanelSet(ln++, StringFormat("peak %.2f (dd-halt %.0f) | static floor %.0f | halted %s / %s",
            g_peakEquity, g_peakEquity * (1.0 - InpMaxDrawdownPct / 100.0),
            g_initialBalance * (1.0 - InpStaticFloorPct / 100.0),
            g_halted ? "DAY" : "no", g_haltedHard ? "HARD" : "no"),
            (g_halted || g_haltedHard) ? clrRed : clrSilver);
   while(ln < MPB_PANEL_LINES)
      PanelSet(ln++, " ");
   ChartRedraw(0);
  }

// One row per closed working-timeframe bar -> monthly CSV (bounded growth; S3 shadow substrate).   // v1.32: was "M15 bar", stale since the H1 default
void DecisionCsvMaybe()
  {
   static datetime s_lastBar = 0;
   if(ArraySize(g_symbols) == 0)
      return;
   datetime b = (datetime)iTime(g_symbols[0], InpTimeframe, 0);
   if(b == 0 || b == s_lastBar)
      return;
   s_lastBar = b;
   MqlDateTime st;
   TimeToStruct(TimeCurrent(), st);
   string fn = StringFormat("MomentumPullback_decisions_v130_%04d%02d.csv", st.year, st.mon);
   string hdr = "time,verdicts,fills,day_pnl,halted,hard,positions,pendings,partial_states";
   int h = FileOpen(fn, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   // v1.33-C1r1: header-schema verification (same guard as the trades/partials CSVs;
   // monthly rotation already bounds exposure - the check makes it zero).
   if(h != INVALID_HANDLE && FileSize(h) > 0)
     {
      FileSeek(h, 0, SEEK_SET);
      string firstLine = FileReadString(h);
      if(firstLine != hdr)
        {
         FileClose(h);
         string bak = fn + ".schema.bak";
         FileMove(fn, 0, bak, FILE_REWRITE);
         h = FileOpen(fn, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
         PrintFormat("v1.33-C1r1: stale decisions CSV header detected - old file moved to %s; writing the current header", bak);
        }
     }
   if(h == INVALID_HANDLE)
     {
      // v1.33-C1r1: never drop a row silently (throttled 60s)
      static datetime s_openWarn = 0;
      if(TimeCurrent() - s_openWarn >= 60)
        {
         s_openWarn = TimeCurrent();
         PrintFormat("WARN: %s open failed (err %d) - row dropped", fn, GetLastError());
        }
      return;
     }
   if(FileSize(h) == 0)
      FileWriteString(h, hdr + "\r\n");
   FileSeek(h, 0, SEEK_END);
   string vs = "";
   for(int i = 0; i < ArraySize(g_symbols); i++)
      vs += (i ? " ; " : "") + g_symbols[i] + ": " +
            ((i < ArraySize(g_lastVerdict) && StringLen(g_lastVerdict[i]) > 0) ? g_lastVerdict[i] : "-");
   StringReplace(vs, ",", "|");
   int pend = 0, poss = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t2 = OrderGetTicket(i);
      if(t2 != 0 && ordInfo.Select(t2) && ordInfo.Magic() == InpMagicNumber) pend++;
     }
   for(int p = PositionsTotal() - 1; p >= 0; p--)
     {
      ulong tk = PositionGetTicket(p);
      if(tk != 0 && posInfo.SelectByTicket(tk) && posInfo.Magic() == InpMagicNumber) poss++;
     }
   string partials = "";
   for(int s = 0; s < ArraySize(g_posState); s++)
      partials += (s ? " ; " : "") + (string)g_posState[s].positionId + ":" +
                  PartialStateText(g_posState[s].partialState) + "@" +
                  DoubleToString(g_posState[s].partialLevel, 5);
   StringReplace(partials, ",", "|");
   FileWriteString(h, StringFormat("%s,%s,%d,%.2f,%s,%s,%d,%d,%s\r\n",
                    TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), vs,
                    g_tradesToday, AccountInfoDouble(ACCOUNT_EQUITY) - g_dayStartBalance,
                    g_halted ? "y" : "n", g_haltedHard ? "y" : "n", poss, pend, partials));
   FileClose(h);
  }
//+------------------------------------------------------------------+
