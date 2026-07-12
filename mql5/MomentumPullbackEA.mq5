//+------------------------------------------------------------------+
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
//|   Multi-symbol M15 momentum-continuation EA (pullback entry).     |
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
//|     * Default universe is restricted to where the edge actually   |
//|       exists: CRYPTO + global/US INDICES. Continuation works on   |
//|       trending assets; it LOSES on the mean-reverting FX majors.  |
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
//|   At Deriv's actual spreads the pullback edge is POSITIVE net of  |
//|   cost on a spread-gated set of majors (+0.044R, t+4, PF 1.11 OOS)|
//|   but a few wide-spread names (LTC, BCH, Mid Cap 400, etc.) lose. |
//|   So v1.2: (a) universe pruned to spread<=0.05 ATR/side majors,   |
//|   (b) a LIVE spread/ATR gate (InpMaxSpreadAtr) skips any symbol    |
//|   whose spread is too wide right now, (c) AVWAP OFF by default     |
//|   (it added no OOS edge). Still observe / minimum-size grade.      |
//|                                                                  |
//|   v1.21 (2026-07): EXIT-ENGINE FIDELITY (see docs/LIVE_TRADE_      |
//|   ANALYSIS_2026-07-01.md). Live was managing lock/trail per tick;  |
//|   the validated harness manages on M15 bar close. Default now:     |
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
#property version   "1.30"
#property strict
#property description "Multi-symbol M15 momentum pullback EA v1.30. Bank 50% at +1R, TP2 remainder, fixed SL/time exit."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/OrderInfo.mqh>

//--- Entry geometry --------------------------------------------------
enum ENUM_ENTRY_MODE
  {
   ENTRY_LIMIT_PULLBACK = 0,  // Pullback LIMIT back into the move (backtest-validated)
   ENTRY_STOP_BREAKOUT  = 1    // Breakout STOP beyond price (original; net loser OOS)
  };

//--- Symbol universe -------------------------------------------------
input group "=== Symbol Universe ==="
input bool   InpScanMarketWatch  = false;     // Scan Market Watch (used only when the whitelist below is empty)
input string InpSymbolWhitelist  = "US30.cash,US100.cash,JP225.cash";  // v1.30 corrected-engine trio. Empty = scan Market Watch.
input string InpSyntheticBlock   = "Volatility,Crash,Boom,Step,Jump,Range Break,Vol over,Hybrid,Drift,DEX,Multi Step,Skew,1HZ,Basket"; // Skip names containing any of these

//--- Strategy --------------------------------------------------------
input group "=== Candle Filter (retained signal definition; parity-corrected 2026-07-12) ==="
input bool   InpCandleFilter    = true;  // W2 remains the forward-test signal definition; its old post-hoc expectancy claim was overturned by live-parity enumeration.
input double InpMinAdvWickAtr   = 0.30;  // Adverse-wick threshold in frozen signal ATR (0.30 = W2; 0 = off)

input group "=== Momentum Strategy ==="
input ENUM_TIMEFRAMES InpTimeframe   = PERIOD_M15; // Working timeframe
input int    InpMomentumBars     = 6;     // Lookback bars for the move
input double InpMomentumAtrMult  = 2.0;   // Move must be >= this many ATRs to count as "rapid"
input int    InpAtrPeriod        = 14;    // ATR period
input bool   InpTradeBothSides   = true;  // Trade rallies too (false = only falling assets -> sells)

//--- Anchored VWAP (discount/premium gate) --------------------------
input group "=== Anchored VWAP (AVWAP) ==="
input bool   InpUseVwapGate       = false; // v1.2: AVWAP OFF by default (it added ZERO out-of-sample edge in testing; was overfit). Set true to re-enable.
input int    InpVwapMinBars       = 8;    // Calibration: don't trade until this many bars into the session
input int    InpVwapMaxBars       = 500;  // Safety cap: max bars scanned back to the session (day) open

//--- Pending entry ---------------------------------------------------
input group "=== Pending Entry ==="
input ENUM_ENTRY_MODE InpEntryMode = ENTRY_LIMIT_PULLBACK; // Entry geometry (PULLBACK = validated; BREAKOUT = legacy)
input double InpPullbackAtr        = 0.6;  // PULLBACK mode: place the LIMIT this many ATR back toward price
input double InpEntryOffsetAtr     = 0.05; // BREAKOUT mode: place the STOP this many ATR beyond price
input int    InpPendingExpiryBars  = 3;    // Retains v1.29.1's measured live w4 behavior (Bars() omits placement bar); v1.30 retest assumes w4
input bool   InpTrailPending       = true; // BREAKOUT mode only: keep the stop pending glued to price

//--- Risk / exits ----------------------------------------------------
input group "=== Risk & Exits ==="
input double InpRiskPercent      = 0.3;   // Corrected-engine MC sizing; current FTMO chart already uses 0.3%
input double InpStopAtrMult      = 1.0;   // Initial stop distance (ATR) - tight = fast loss cut
input double InpTakeProfitAtrMultV130 = 2.0; // v1.30 renamed intentionally: chart-saved TP3 must not survive this upgrade
input bool   InpUsePartialCloseV130   = true; // Corrected-engine finalist: bank one partial, then leave the remainder on its bracket
input double InpPartialCloseFractionV130 = 0.50; // Fraction of ORIGINAL position volume to close (rounded DOWN to lot step)
input double InpPartialCloseAtRV130   = 1.0;  // Trigger in initial R, using frozen signal ATR * InpStopAtrMult
input int    InpPartialRetrySecondsV130 = 30; // Reconcile before a bounded retry after a transient server result
input bool   InpUseLockTrail     = false; // Corrected-engine retest: every lock/trail arm remains negative; v1.30 early banking is the only enabled exit overlay.
input double InpLockTriggerAtr   = 0.25;  // (only if InpUseLockTrail) once price is this many ATR in profit, lock the trade
input int    InpLockBufferPoints = 0;     // (only if InpUseLockTrail) extra points locked above break-even (0 = auto: spread+2)
input double InpTrailAtrMult      = 0.5;  // (only if InpUseLockTrail) trailing distance after lock (ATR)
input int    InpMaxHoldingBars   = 8;     // Force-close a stagnant trade after N closed bars (0 = off)
input bool   InpManageOnBarClose = true;  // P0: lock/trail on M15 bar close (validated engine; false = legacy per-tick)

//--- Portfolio risk --------------------------------------------------
input group "=== Portfolio Risk ==="
input int    InpMaxConcurrent    = 2;     // Max simultaneous open positions (all symbols)
input int    InpMaxTradesPerDay  = 8;    // Max new trades opened per day (all symbols)
input double InpDailyLossLimitPct= 4.0;   // Halt for the day after this daily loss (% of day-start balance)
input double InpMaxDrawdownPct   = 8.0;  // Halt if equity drawdown from peak exceeds this (v1.26: HARD halt - survives day rollover; peak persisted across re-inits)
input double InpInitialBalance   = 100000.0; // v1.26: initial balance anchoring the STATIC floor below (0 = auto-capture first-seen balance into a terminal global)
input double InpStaticFloorPct   = 9.0;   // v1.26: HARD halt if equity <= initial*(1 - this%). Buffer inside FTMO's 10% breach line; the trailing check above cannot see across re-inits without it. 0 = off.
input int    InpMaxConsecLosses  = 4;     // Pause for the day after this many losses in a row
input int    InpMaxSpreadPtsRaw  = 0;     // Raw POINTS spread cap — OFF (v1.24). Points scale with nominal price, so the old 200 cap structurally blocked BTCUSD/ETHUSD/Japan 225 (validated symbols that PASS the ATR gate). Use InpMaxSpreadAtr below; >0 re-enables at your own risk. (Renamed from InpMaxSpreadPoints so the new default supersedes chart-saved values on upgrade.)
input double InpMaxSpreadAtr      = 0.05;  // v1.2 KEY GATE: skip if current spread > this many ATR PER SIDE (0.05 = validated ceiling; the edge dies above it, e.g. LTC/BCH/Mid Cap). 0 = off.
// P3 (brief §4): correlation-aware concurrency. OFF (0) by default - adoption requires the
// acceptance study (lower drawdown at equal pooled expectancy). Day-1 saw 4 same-direction
// Tech-100-cluster entries in 70 min stacking ~1.5% correlated heat.
input int    InpMaxPerCluster    = 1;     // Max open+pending per correlation cluster (0 = off, current behavior)
input string InpClusterSpec      = "US30.cash|US100.cash;JP225.cash";  // v1.30 clusters: one US-index seat; JP225 independent

//--- Execution -------------------------------------------------------
input group "=== Execution ==="
input long   InpMagicNumber      = 771025;// Magic number tagging this EA's orders
input ulong  InpDeviationPoints  = 30;    // Max slippage in points
input string InpTradeComment     = "MomPullback";   // broker-visible on EVERY order. Deliberately avoids "scalp" (FTMO polices tick-scalping) and any other broker's name.
input int    InpHeartbeatSeconds = 5;     // OnTimer scan/manage heartbeat (0 = chart ticks only)
input bool   InpLogNoImpulse     = false; // Log "no impulse" SKIP lines (~1,100/day; gate/data skips are always logged)

input group "=== v1.25 Hardening (protective GATES + observability; validated entry/exit engine UNCHANGED) ==="
// Zero-regret, ON by default: they never remove a VALID trade, only broken-data trades, and add logging.
input bool   InpFreshnessGuard   = true;  // Block NEW entries on stale ticks / invalid quotes (pure safety; never in a validated backtest but a trade on frozen data is pure risk)
input int    InpMaxTickAgeSec     = 60;    // Max age (s) of the latest tick before a symbol is considered frozen (catches dead feeds, not normal illiquid gaps)
input bool   InpTradeLog          = true;  // Write a per-trade CSV (MFE/MAE in R, spread@entry, exit reason) = the doc's "post-trade learning" data. Pure observability.
input string InpTradeLogFile      = "MomentumPullback_trades.csv";
input string InpPartialLogFileV130= "MomentumPullback_partials_v130.csv"; // Actual partial fill + level-vs-fill slippage
// Protective but they DO alter the validated trade distribution -> OFF by default; flip on deliberately.
input int    InpNewsBlockMins     = 3;     // Protective entry block is ON; evaluation accounts allow news, but this conservative gate remains chart-compatible. 0=off.
input string InpBlockHours        = "";

input group "=== v1.28 Thought-Process Panel (observability only) ==="
input bool   InpShowPanel         = true;  // On-chart panel: per-symbol scan verdicts, trade state, risk ledger
input int    InpPanelRefreshSec   = 10;    // Panel refresh throttle (never per-tick)    // Server hours to block NEW entries, comma-sep e.g. "20,21,22" (rollover). Empty=off. The ATR/spread gate already handles most toxic spread dynamically for this crypto/index universe.

//--- Globals ---------------------------------------------------------
CTrade        trade;
CPositionInfo posInfo;
COrderInfo    ordInfo;

string g_symbols[];      // Tradable, non-synthetic symbols
int    g_atrHandle[];    // Parallel ATR handle per symbol
datetime g_lastScanBar[];// Per-symbol last processed bar (own bar clock, not chart symbol)

// Pending order ticket -> signal-bar ATR frozen at placement (transferred on fill).
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
   double   desiredSL;     // pending SL level to apply (retried every heartbeat until it sticks)
   // v1.25 trade-log fields (observability only; never read by the entry/exit engine)
   double   entryPrice;
   double   riskPrice;     // initial stop distance in price (= InpStopAtrMult * signalAtr) -> R denominator
   int      dir;           // +1 buy, -1 sell
   double   spreadAtrEntry;// spread/ATR/side at fill
   double   mfeR;          // max favorable excursion (R), sampled each heartbeat
   double   maeR;          // max adverse excursion (R)
   // v1.30 partial-close lifecycle (all geometry derives from frozen signal ATR).
   double   initialVolume;
   double   partialTargetVolume;
   double   partialLevel;
   int      partialState;
   datetime partialTriggerTime;
   datetime partialNextRetry;
   int      partialAttempts;
  };
PositionMgmtState g_posState[];

datetime g_currentDay  = 0;
double   g_dayStartBalance = 0.0;
double   g_peakEquity  = 0.0;
int      g_tradesToday = 0;
bool     g_halted      = false;   // daily-loss pause: cleared at day rollover
bool     g_haltedHard  = false;   // v1.26: max-DD / static-floor halt - NEVER auto-cleared
double   g_initialBalance = 0.0;  // v1.26: static-floor anchor
datetime g_initTime       = 0;    // v1.26.1: for the one-shot ledger re-sync below
bool     g_ledgerResynced = false;// v1.26.1: deal history syncs AFTER a cold start; re-read once
bool     g_ledgerValid    = false;// v1.29.1: false until a restore ran on SYNCED account data
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

   if(InpUsePartialCloseV130)
     {
      if(InpPartialCloseFractionV130 <= 0.0 || InpPartialCloseFractionV130 >= 1.0 ||
         InpPartialCloseAtRV130 <= 0.0)
        {
         Print("v1.30 invalid partial-close inputs: fraction must be in (0,1) and trigger R > 0");
         return(INIT_PARAMETERS_INCORRECT);
        }
      long accountLogin = AccountInfoInteger(ACCOUNT_LOGIN);
      if(accountLogin > 0 &&
         (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
        {
         Print("v1.30 partial close requires a hedging account; refusing to initialize on netting/exchange mode");
         return(INIT_PARAMETERS_INCORRECT);
        }
     }

   if(!BuildSymbolUniverse())
     {
      Print("No tradable non-synthetic symbols found. Add symbols to Market Watch.");
      return(INIT_FAILED);
     }

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
   PrintFormat("Panel v1.30 initialized: requested=%s ready=%s",
               InpShowPanel ? "yes" : "no", panelReady ? "yes" : "no");

   // Register any positions already open (e.g. after EA reload).
   SyncOpenPositionStates();

   // v1.27: print the Wilder ATR per symbol at init (cross-checkable against the
   // Python engine on the same bars; also proves the estimator is alive).
   for(int i = 0; i < ArraySize(g_symbols); i++)
     {
      double wa;
      if(WilderAtrForSymbol(g_symbols[i], wa))
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

   PrintFormat("MomentumPullbackEA v1.30 ready. Entry=%s. Exits=%s + TP%.2f/time. ManageOnBarClose=%s. Scanning %d symbols on %s. Risk/trade=%.2f%%.",
               (InpEntryMode == ENTRY_LIMIT_PULLBACK ? "PULLBACK(limit)" : "BREAKOUT(stop)"),
               (InpUsePartialCloseV130 ? StringFormat("bank %.0f%% @ +%.2fR", 100.0 * InpPartialCloseFractionV130, InpPartialCloseAtRV130)
                                       : "partial OFF"),
               InpTakeProfitAtrMultV130,
               (InpManageOnBarClose ? "yes" : "legacy per-tick"),
               ArraySize(g_symbols), EnumToString(InpTimeframe), InpRiskPercent);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   PanelDestroy();   // v1.28
   if(InpHeartbeatSeconds > 0)
      EventKillTimer();
   for(int i = 0; i < ArraySize(g_atrHandle); i++)
      if(g_atrHandle[i] != INVALID_HANDLE)
         IndicatorRelease(g_atrHandle[i]);
  }

//+------------------------------------------------------------------+
//| Build the list of tradable, non-synthetic symbols + ATR handles  |
//+------------------------------------------------------------------+
bool BuildSymbolUniverse()
  {
   ArrayResize(g_symbols, 0);
   ArrayResize(g_atrHandle, 0);

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
   else if(InpScanMarketWatch)
     {
      int total = SymbolsTotal(true); // Market Watch only
      for(int i = 0; i < total; i++)
        {
         string s = SymbolName(i, true);
         if(StringLen(s) > 0)
            AddSymbol(s);
        }
     }
   else
     {
      Print("InpScanMarketWatch is false and InpSymbolWhitelist is empty - no symbols to trade.");
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

   // ATR handle creation can fail transiently at terminal startup (history not yet
   // synchronized, err 4805). Do NOT silently drop the symbol: keep it with an invalid
   // handle and let the heartbeat retry until it recovers (RetryFailedAtrHandles).
   int h = iATR(symbol, InpTimeframe, InpAtrPeriod);
   if(h == INVALID_HANDLE)
      PrintFormat("WARN: ATR handle failed for %s at init (err %d) - will retry on heartbeat",
                  symbol, GetLastError());

   int idx = ArraySize(g_symbols);
   ArrayResize(g_symbols, idx + 1);
   ArrayResize(g_atrHandle, idx + 1);
   ArrayResize(g_wAtrCache, idx + 1);      // v1.27
   ArrayResize(g_wAtrCacheBar, idx + 1);
   ArrayResize(g_noSignalUpTo, idx + 1);
   ArrayResize(g_lastVerdict, idx + 1);    // v1.28 panel
   ArrayResize(g_lastVerdictT, idx + 1);
   g_symbols[idx]   = symbol;
   g_atrHandle[idx] = h;   // retained for startup data-sync tracking only; ATR VALUES come from WilderAtrForSymbol (v1.27)
   g_wAtrCache[idx] = 0.0;
   g_wAtrCacheBar[idx] = 0;
   g_noSignalUpTo[idx] = 0;
   g_lastVerdict[idx] = "";     // v1.28 panel
   g_lastVerdictT[idx] = 0;
  }

//+------------------------------------------------------------------+
//| Retry ATR handles that failed at init (startup history race).    |
//| No-op once every handle is valid.                                |
//+------------------------------------------------------------------+
void RetryFailedAtrHandles()
  {
   static datetime s_lastTry = 0;      // v1.26: cap retries at 1/second (was every tick while broken)
   datetime nowT = TimeCurrent();
   if(nowT == s_lastTry)
      return;
   s_lastTry = nowT;
   for(int i = 0; i < ArraySize(g_atrHandle); i++)
     {
      if(g_atrHandle[i] != INVALID_HANDLE)
         continue;
      g_atrHandle[i] = iATR(g_symbols[i], InpTimeframe, InpAtrPeriod);
      if(g_atrHandle[i] != INVALID_HANDLE)
         PrintFormat("ATR handle recovered for %s - symbol active", g_symbols[i]);
     }
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
   // v1.26: with the 5s timer + bar-close management every decision is bar-gated,
   // so the per-tick pipeline (incl. full-day HistorySelect) is pure waste on a
   // 24/7 host chart. Per-tick mode is kept for the legacy per-tick config.
   if(InpHeartbeatSeconds > 0 && InpManageOnBarClose)
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

   RetryFailedAtrHandles();   // recover symbols whose ATR failed at startup (no-op when healthy)
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
   ManageAll();
   ScanAllOnNewBars();
   PanelUpdate();   // v1.28: display only, throttled, fails soft
  }

//+------------------------------------------------------------------+
//| Scan each symbol once per closed bar on that symbol's own clock. |
//+------------------------------------------------------------------+
void ScanAllOnNewBars()
  {
   UpdatePeakEquity();
   if(g_halted || g_haltedHard)
      return;
   if(StaticFloorBreached()) { g_haltedHard = true; CancelAllPendings("static-floor halt"); Print("STATIC FLOOR hit (equity at/below initial - floor%) - HARD halted."); return; }
   if(DrawdownExceeded()) { g_haltedHard = true; CancelAllPendings("max-drawdown halt"); Print("Max drawdown hit - HARD halted (survives day rollover)."); return; }
   if(DailyLossExceeded()){ g_halted = true; CancelAllPendings("daily-loss halt"); Print("Daily loss limit hit - paused for the day."); return; }
   if(InpMaxConsecLosses > 0 && ConsecutiveLossesToday() >= InpMaxConsecLosses)
      return;
   if(g_tradesToday >= InpMaxTradesPerDay)
      return;

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
      g_lastScanBar[i] = barTime;   // consume the bar even when at capacity (match validated-era
                                    // behavior: signals are dropped, never scanned late mid-bar)
      if(CountOpenAndPending() >= InpMaxConcurrent)
         continue;

      ScanSymbol(g_symbols[i], g_atrHandle[i]);
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
      g_tradesToday++;   // v1.27 B3: the daily cap counts FILLS (engine parity; placements were miscounting)
      ulong orderTicket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER);
      datetime dealTime = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
      double sigAtr = TakePendingSigAtr(orderTicket);
      if(sigAtr <= 0.0)
         ReadAtrForSymbol(symbol, sigAtr);
      RegisterPositionState(posId, symbol, sigAtr, dealTime);
      // v1.25: freeze entry context for the trade log
      int si = FindPositionState(posId);
      if(si >= 0)
        {
         g_posState[si].entryPrice = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
         g_posState[si].dir = (HistoryDealGetInteger(trans.deal, DEAL_TYPE) == DEAL_TYPE_BUY) ? 1 : -1;
         g_posState[si].riskPrice = (g_posState[si].signalAtr > 0.0) ? InpStopAtrMult * g_posState[si].signalAtr : 0.0;
         double inVol = 0.0, outVol = 0.0;
         if(PositionHistoryVolumes(posId, inVol, outVol) && inVol > g_posState[si].initialVolume)
            g_posState[si].initialVolume = inVol;
         RefreshPartialGeometry(si, symbol);
         PersistPartialState(si);
         double pt = SymbolInfoDouble(symbol, SYMBOL_POINT);
         double sprPrice = (double)SymbolInfoInteger(symbol, SYMBOL_SPREAD) * pt;
         g_posState[si].spreadAtrEntry = (g_posState[si].signalAtr > 0.0) ? 0.5 * sprPrice / g_posState[si].signalAtr : 0.0;
        }
      return;
     }

   if(dealEntry == DEAL_ENTRY_OUT)
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

bool BlockedByHour()
  {
   if(StringLen(InpBlockHours) == 0)
      return(false);
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   string parts[];
   int np = StringSplit(InpBlockHours, ',', parts);
   for(int i = 0; i < np; i++)
      if((int)StringToInteger(parts[i]) == dt.hour)
         return(true);
   return(false);
  }

bool NewsSoon(string symbol)
  {
   int win = InpNewsBlockMins * 60;
   if(win <= 0)
      return(false);
   datetime now = TimeCurrent();
   string ccy = SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT);
   MqlCalendarValue vals[];
   // v1.26: CalendarValueHistory returns bool, NOT a count (audit P1: the old int
   // assignment inspected at most vals[0] and crashed on true-with-empty-array).
   if(!CalendarValueHistory(vals, now - win, now + win, NULL, ccy))
      return(false);
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

   int h = FileOpen(InpTradeLogFile, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE)
     {
      if(FileSize(h) == 0)
         FileWriteString(h, "close_time,symbol,dir,entry,exit,risk_px,realized_R,mfe_R,mae_R,spread_atr_entry,bars,exit_reason,profit\r\n");
      FileSeek(h, 0, SEEK_END);
      FileWriteString(h, StringFormat("%s,%s,%s,%.5f,%.5f,%.5f,%.3f,%.3f,%.3f,%.4f,%d,%s,%.2f\r\n",
                      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), symbol, dir > 0 ? "BUY" : (dir < 0 ? "SELL" : "NA"),
                      entryPx, exitPx, riskPx, realR, mfe, mae, sprE, bars, rtxt, profit));
      FileClose(h);
     }
  }

//+------------------------------------------------------------------+
//| Evaluate one symbol and place a pending order if momentum is hot |
//+------------------------------------------------------------------+
void ScanSymbol(string symbol, int atrHandle)
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
   if(SpreadTooWide(symbol))
     {
      LogSkip(symbol, "spread points gate");
      return;
     }
   if(InpFreshnessGuard && !QuotesFresh(symbol))     // v1.25: never trade on frozen/invalid data
     {
      LogSkip(symbol, "stale/invalid quotes (freshness guard)");
      return;
     }
   if(BlockedByHour())                                // v1.25: optional server-hour blackout (off by default)
     {
      LogSkip(symbol, "blocked server hour");
      return;
     }
   if(InpNewsBlockMins > 0 && NewsSoon(symbol))       // v1.25: optional HIGH-impact news blackout (off by default)
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
   double open1     = iOpen(symbol, InpTimeframe, 1);
   if(close1 == 0.0 || closePast == 0.0)
     {
      LogSkip(symbol, "missing bar data");
      return;
     }

   double move = closePast - close1;            // positive => price fell
   double moveAtr = move / atr;

   bool fallingFast = (moveAtr >= InpMomentumAtrMult) && (close1 < open1);
   bool risingFast  = (-moveAtr >= InpMomentumAtrMult) && (close1 > open1);

   // Optional Anchored-VWAP discount/premium gate (OFF by default in v1.2 -- it added no
   // out-of-sample edge and was overfit). When enabled: wait for VWAP to calibrate, then
   // buy ONLY at a discount (below VWAP) and sell ONLY at a premium (above VWAP).
   if(InpUseVwapGate)
     {
      int sessBars = 0;
      double vwap = AnchoredVwap(symbol, InpTimeframe, 1, InpVwapMaxBars, sessBars);
      if(vwap <= 0.0 || sessBars < InpVwapMinBars)
        {
         LogSkip(symbol, "VWAP not calibrated");
         return;
        }
      if(risingFast && close1 >= vwap)        // not a discount -> no buy
         risingFast = false;
      if(fallingFast && close1 <= vwap)       // not a premium -> no sell
         fallingFast = false;
     }

   // v1.29 W2 candle filter: the signal bar must be CONTESTED (adverse-side wick
   // >= InpMinAdvWickAtr ATR). Gate evidence: quarter-stitched WF at real cost
   // +0.120R vs +0.078R baseline, beats random-drop placebo, 9/12 symbols,
   // 2x cost OK; direction confirmed on never-used FTMO M15 both symbols and on
   // 24k never-analyzed IS trades. A SELL continuation needs a LOWER wick
   // (buyers fought = still fuel); a BUY needs an UPPER wick. Skips only.
   if(InpCandleFilter && InpMinAdvWickAtr > 0.0 && (fallingFast || risingFast))
     {
      double high1 = iHigh(symbol, InpTimeframe, 1);
      double low1  = iLow(symbol, InpTimeframe, 1);
      if(high1 > 0.0 && low1 > 0.0)
        {
         double bodyTop  = MathMax(open1, close1);
         double bodyBot  = MathMin(open1, close1);
         double advWick  = risingFast ? (high1 - bodyTop) : (bodyBot - low1);
         double advWickAtr = advWick / atr;
         if(advWickAtr < InpMinAdvWickAtr)
           {
            LogSkip(symbol, StringFormat("candle filter: adv wick %.2f ATR < %.2f (clean climax)",
                    advWickAtr, InpMinAdvWickAtr), atr, spreadAtrSide, -moveAtr);
            return;
           }
        }
     }

   // Impulse sign convention matches SIGNAL lines: negative = falling (close1 - closePast).
   double impulseAtr = -moveAtr;
   if(!fallingFast && !(risingFast && InpTradeBothSides))
     {
      if(InpLogNoImpulse)
         LogSkip(symbol, StringFormat("no impulse (impulse=%.2f ATR)", impulseAtr), atr, spreadAtrSide, impulseAtr);
      else
         SetVerdict(symbol, StringFormat("no impulse (%.2f ATR, need %.1f)", impulseAtr, InpMomentumAtrMult));   // v1.28
      return;
     }

   // Continuation in the direction of the move. PULLBACK uses LIMIT orders (enter on
   // the retrace); BREAKOUT uses STOP orders (chase beyond price, the legacy behaviour).
   ENUM_ORDER_TYPE buyType  = (InpEntryMode == ENTRY_LIMIT_PULLBACK) ? ORDER_TYPE_BUY_LIMIT  : ORDER_TYPE_BUY_STOP;
   ENUM_ORDER_TYPE sellType = (InpEntryMode == ENTRY_LIMIT_PULLBACK) ? ORDER_TYPE_SELL_LIMIT : ORDER_TYPE_SELL_STOP;

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
   double ask   = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid   = SymbolInfoDouble(symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int    digits= (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double stopsLevel = (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;

   bool isLimit = (type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_SELL_LIMIT);
   bool isBuy   = (type == ORDER_TYPE_BUY_STOP  || type == ORDER_TYPE_BUY_LIMIT);

   // How far the pending sits from the anchor price.
   //   PULLBACK (limit): InpPullbackAtr ATR back from the signal-bar CLOSE (validated harness).
   //   BREAKOUT (stop) : small InpEntryOffsetAtr ATR just beyond live bid/ask.
   double offset = isLimit ? (InpPullbackAtr * atr) : (InpEntryOffsetAtr * atr);
   offset = MathMax(offset, stopsLevel);     // respect the broker minimum distance
   if(offset <= 0.0)
      offset = 10 * point;

   double stopDist = atr * InpStopAtrMult;
   double tpDist   = (InpTakeProfitAtrMultV130 > 0.0) ? atr * InpTakeProfitAtrMultV130 : 0.0;
   if(stopsLevel > 0.0)
     {
      stopDist = MathMax(stopDist, stopsLevel * 1.5);
      if(tpDist > 0.0) tpDist = MathMax(tpDist, stopsLevel * 1.5);
     }

   double entry, sl, tp;
   bool sendMarket = false;
   if(isBuy)
     {
      // BUY_STOP sits above the ask; BUY_LIMIT sits below signal-bar close (pullback).
      entry = isLimit ? (signalClose - offset) : (ask + offset);
      // v1.27 B4: price already retraced through the limit level (gap / fast move).
      // The validated engine fills these at the limit on touch; a live BUY_LIMIT
      // above the ask is rejected 10015 (observed live 08:29 today) and the trade
      // is silently lost. Market entry at the ask is equal-or-BETTER than the
      // engine's assumed limit fill (ask < limit here by construction).
      if(isLimit && entry >= ask - stopsLevel)
        {
         entry = ask;
         sendMarket = true;
        }
      entry = SnapPrice(symbol, entry);
      sl    = SnapPrice(symbol, entry - stopDist);
      tp    = (tpDist > 0.0) ? SnapPrice(symbol, entry + tpDist) : 0.0;
     }
   else
     {
      // SELL_STOP sits below the bid; SELL_LIMIT sits above signal-bar close (pullback).
      entry = isLimit ? (signalClose + offset) : (bid - offset);
      if(isLimit && entry <= bid + stopsLevel)
        {
         entry = bid;   // v1.27 B4: see BUY branch
         sendMarket = true;
        }
      entry = SnapPrice(symbol, entry);
      sl    = SnapPrice(symbol, entry + stopDist);
      tp    = (tpDist > 0.0) ? SnapPrice(symbol, entry - tpDist) : 0.0;
     }

   double lots = CalculateLotSize(symbol, stopDist);
   if(lots <= 0.0)
      return;

   datetime expiry = 0;
   ENUM_ORDER_TYPE_TIME ttype = ORDER_TIME_GTC;
   if(InpPendingExpiryBars > 0)
     {
      // v1.27 B2: the engine's 3-bar fill window is counted on the SYMBOL'S OWN
      // clock (session breaks produce no bars). Precise expiry = the bar-counted
      // check in ManagePendingOrders; the broker wall-clock expiry stays only as
      // a +3-day backstop for when the EA itself is dead.
      expiry = (datetime)(TimeCurrent() + (long)InpPendingExpiryBars * PeriodSeconds(InpTimeframe) + 259200);
      ttype  = ORDER_TIME_SPECIFIED;
     }

   trade.SetTypeFillingBySymbol(symbol);
   bool ok = false;
   string tag = "";
   if(sendMarket)
     {
      ok = isBuy ? trade.Buy (lots, symbol, 0.0, sl, tp, InpTradeComment)
                 : trade.Sell(lots, symbol, 0.0, sl, tp, InpTradeComment);
      tag = isBuy ? "BUY MARKET(retrace-done)" : "SELL MARKET(retrace-done)";
     }
   else
   switch(type)
     {
      case ORDER_TYPE_BUY_STOP:   ok = trade.BuyStop  (lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "BUY STOP";   break;
      case ORDER_TYPE_SELL_STOP:  ok = trade.SellStop (lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "SELL STOP";  break;
      case ORDER_TYPE_BUY_LIMIT:  ok = trade.BuyLimit (lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "BUY LIMIT";  break;
      case ORDER_TYPE_SELL_LIMIT: ok = trade.SellLimit(lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "SELL LIMIT"; break;
      default: return;
     }

   uint rc = trade.ResultRetcode();
   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED))   // v1.26: bool alone only means "request passed basic checks"
     {
      StorePendingSigAtr(trade.ResultOrder(), atr);   // v1.27 B3: fills are counted in OnTradeTransaction
      SetVerdict(symbol, StringFormat("SIGNAL %s %.2f lots @ %.2f (imp %.2f ATR)", tag, lots, entry, impulseAtr));   // v1.28
      PrintFormat("SIGNAL %s %s %.2f lots entry=%.5f (anchor=%.5f) SL=%.5f TP=%.5f | ATR=%.5f impulse=%.2f spread/ATR/side=%.4f",
                  symbol, tag, lots, entry, signalClose, sl, tp, atr, impulseAtr, spreadAtrSide);
     }
   else
      PrintFormat("%s pending failed: %d (%s)", symbol,
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
//| Fixed-fractional lot size from the stop distance                 |
//+------------------------------------------------------------------+
double CalculateLotSize(string symbol, double stopDistancePrice)
  {
   if(stopDistancePrice <= 0.0)
      return(0.0);
   double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * (InpRiskPercent / 100.0);
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
                  symbol, lossPerLot * minVol, 100.0 * lossPerLot * minVol / balance, riskAmount, InpRiskPercent);
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
                               (datetime)HistoryOrderGetInteger(ticket, ORDER_TIME_DONE));
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
   if(g_halted || g_haltedHard)     // v1.26: a halt must also clear RESTING orders -
     {                              // a pending filling after "paused for the day" adds
      CancelAllPendings("halt active");   // fresh risk on top of a -4% day (audit P1)
      return;
     }
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

      // Manual expiry safety net for ANY of our pendings (in case the broker ignores
      // ORDER_TIME_SPECIFIED). Applies to both stop and limit orders.
      if(InpPendingExpiryBars > 0)
        {
         // v1.27 B2: engine parity - the fill window is InpPendingExpiryBars BARS on
         // the symbol's own clock (placement bar = 1). Wall-clock aging expired
         // pendings mid-session-break after fewer tradable bars than validated.
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

      // Only BREAKOUT stop orders are trailed to stay in front of price.
      if(!isStop || !InpTrailPending)
         continue;

      double atr;
      if(!WilderAtrForSymbol(symbol, atr) || atr <= 0.0)   // v1.27
         continue;

      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      int digits   = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double stopsLevel = (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
      double offset = MathMax(stopsLevel, InpEntryOffsetAtr * atr);
      double stopDist = MathMax(atr * InpStopAtrMult, stopsLevel * 1.5);

      double curPrice = ordInfo.PriceOpen();

      // Preserve the original expiry so trailing never turns a timed order into a GTC one.
      datetime keepExpiry = (datetime)ordInfo.TimeExpiration();
      ENUM_ORDER_TYPE_TIME keepType = (keepExpiry > 0) ? ORDER_TIME_SPECIFIED : ORDER_TIME_GTC;

      if(type == ORDER_TYPE_BUY_STOP)
        {
         double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
         double newEntry = SnapPrice(symbol, ask + offset);   // v1.27 B6
         // Only ratchet the entry DOWN toward price (price rising stays "in front").
         if(newEntry < curPrice - point)
           {
            double sl = SnapPrice(symbol, newEntry - stopDist);
            double tp = (InpTakeProfitAtrMultV130 > 0.0)
                        ? SnapPrice(symbol, newEntry + atr * InpTakeProfitAtrMultV130) : 0.0;
            trade.OrderModify(ticket, newEntry, sl, tp, keepType, keepExpiry);
           }
        }
      else // SELL_STOP
        {
         double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
         double newEntry = SnapPrice(symbol, bid - offset);   // v1.27 B6
         // Only ratchet the entry UP toward price (price falling stays "in front").
         if(newEntry > curPrice + point)
           {
            double sl = SnapPrice(symbol, newEntry + stopDist);
            double tp = (InpTakeProfitAtrMultV130 > 0.0)
                        ? SnapPrice(symbol, newEntry - atr * InpTakeProfitAtrMultV130) : 0.0;
            trade.OrderModify(ticket, newEntry, sl, tp, keepType, keepExpiry);
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Lock-to-breakeven, tight trail and time exit on open positions   |
//+------------------------------------------------------------------+
void ManageOpenPositions()
  {
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

      // Retry any SL update that failed/was deferred on a previous heartbeat (blocker fix).
      if(g_posState[stateIdx].desiredSL > 0.0)
        {
         ApplyDesiredSL(ticket, stateIdx);
         if(!posInfo.SelectByTicket(ticket))   // ApplyDesiredSL may have closed the position
            continue;
        }

      // v1.30 partial is tick-checked on every heartbeat, independent of the
      // bar-close lock/trail cadence. A sent close request owns this heartbeat
      // so time/SL management cannot race the server transaction chain.
      if(ManagePartialClose(ticket, stateIdx))
         continue;

      if(InpManageOnBarClose)
         ManagePositionBarClose(ticket, stateIdx);
      else
         ManagePositionPerTick(ticket, stateIdx);
     }
  }

//+------------------------------------------------------------------+
//| Validated engine: lock/trail/time-exit only on symbol bar close.  |
//+------------------------------------------------------------------+
void ManagePositionBarClose(ulong ticket, int stateIdx)
  {
   string symbol = posInfo.Symbol();
   datetime curBarTime = (datetime)iTime(symbol, InpTimeframe, 0);
   if(curBarTime == 0)                     // history desync: don't corrupt the bar clock
      return;
   if(curBarTime == g_posState[stateIdx].lastMgmtBarTime)
      return;

   g_posState[stateIdx].lastMgmtBarTime = curBarTime;
   UpdateBarsClosed(stateIdx, symbol);

   if(InpMaxHoldingBars > 0 && g_posState[stateIdx].barsClosed >= InpMaxHoldingBars)
     {
      trade.PositionClose(ticket);
      return;
     }

   // v1.23 PURE BRACKET: with the lock/trail ladder disabled there is nothing to manage
   // between fill and exit — the broker-side SL/TP set at placement ARE the exit engine,
   // plus the bar-count time exit above. (Exit-ladder study: the ladder cut avg win from
   // 1.72R to 1.02R and cost ~0.027R/trade of OOS expectancy.)
   if(!InpUseLockTrail)
      return;

   double signalAtr = g_posState[stateIdx].signalAtr;
   if(signalAtr <= 0.0)
     {
      if(!ReadAtrForSymbol(symbol, signalAtr) || signalAtr <= 0.0)
         return;
      g_posState[stateIdx].signalAtr = signalAtr;
     }

   double barClose = iClose(symbol, InpTimeframe, 1);
   if(barClose <= 0.0)
      return;

   int digits    = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double entry  = posInfo.PriceOpen();
   double curSL  = posInfo.StopLoss();
   long   spread = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   double point  = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double lockBuffer = ((InpLockBufferPoints > 0) ? InpLockBufferPoints : (spread + 2)) * point;
   double lockTrigger = InpLockTriggerAtr * signalAtr;
   double trailDist   = InpTrailAtrMult * signalAtr;

   if(posInfo.PositionType() == POSITION_TYPE_BUY)
     {
      double profit = barClose - entry;
      if(profit < lockTrigger)
         return;

      double newSL = curSL;
      double lockSL = NormalizeDouble(entry + lockBuffer, digits);
      if(lockSL > newSL)
         newSL = lockSL;
      double trailSL = NormalizeDouble(barClose - trailDist, digits);
      if(trailSL > newSL)
         newSL = trailSL;

      if(newSL > curSL)
        {
         // Record the harness-mandated stop and apply it reliably: if the market has
         // already gapped through it, the validated engine's stop was HIT this bar ->
         // close at market; on broker rejection keep retrying every heartbeat.
         g_posState[stateIdx].desiredSL = newSL;
         ApplyDesiredSL(ticket, stateIdx);
        }
     }
   else
     {
      double profit = entry - barClose;
      if(profit < lockTrigger)
         return;

      double newSL = curSL;
      double lockSL = NormalizeDouble(entry - lockBuffer, digits);
      if(curSL == 0.0 || lockSL < newSL)
         newSL = lockSL;
      double trailSL = NormalizeDouble(barClose + trailDist, digits);
      if((trailSL < newSL || newSL == 0.0) && trailSL > 0.0)
         newSL = trailSL;

      if(curSL == 0.0 || newSL < curSL)
        {
         g_posState[stateIdx].desiredSL = newSL;
         ApplyDesiredSL(ticket, stateIdx);
        }
     }
  }

//+------------------------------------------------------------------+
//| Apply the pending desired SL faithfully (blocker fix, review):    |
//|  * market already at/through the level -> the validated engine's  |
//|    stop was hit this bar -> close at market (honest exit).        |
//|  * within the broker stops/freeze distance -> clamp just outside. |
//|  * broker rejection / no quote -> keep desiredSL, retry on every  |
//|    heartbeat until it sticks (ratchet is idempotent).             |
//+------------------------------------------------------------------+
void ApplyDesiredSL(ulong ticket, int stateIdx)
  {
   double want = g_posState[stateIdx].desiredSL;
   if(want <= 0.0)
      return;

   string symbol = posInfo.Symbol();
   int    digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double point  = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double minDist = MathMax((double)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL),
                            (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * point;
   double curSL = posInfo.StopLoss();
   double curTP = posInfo.TakeProfit();

   if(posInfo.PositionType() == POSITION_TYPE_BUY)
     {
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      if(bid <= 0.0)
         return;                                  // no quote (session break): retry later
      if(want <= curSL)
        {
         g_posState[stateIdx].desiredSL = 0.0;    // already ratcheted past - nothing to do
         return;
        }
      if(want >= bid)
        {
         // Validated engine already exited at this stop level this bar.
         if(trade.PositionClose(ticket))
            g_posState[stateIdx].desiredSL = 0.0;
         return;
        }
      double lvl = want;
      if(minDist > 0.0 && lvl > bid - minDist)
         lvl = NormalizeDouble(bid - minDist, digits);   // clamp inside broker constraint
      if(lvl <= curSL)
         return;                                  // clamp made it useless now; retry later
      if(trade.PositionModify(ticket, lvl, curTP))
         g_posState[stateIdx].desiredSL = 0.0;
      // on failure desiredSL stays set -> retried next heartbeat
     }
   else
     {
      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      if(ask <= 0.0)
         return;
      if(curSL != 0.0 && want >= curSL)
        {
         g_posState[stateIdx].desiredSL = 0.0;
         return;
        }
      if(want <= ask)
        {
         if(trade.PositionClose(ticket))
            g_posState[stateIdx].desiredSL = 0.0;
         return;
        }
      double lvl = want;
      if(minDist > 0.0 && lvl < ask + minDist)
         lvl = NormalizeDouble(ask + minDist, digits);
      if(curSL != 0.0 && lvl >= curSL)
         return;
      if(trade.PositionModify(ticket, lvl, curTP))
         g_posState[stateIdx].desiredSL = 0.0;
     }
  }

//+------------------------------------------------------------------+
//| Legacy per-tick management (InpManageOnBarClose=false only).      |
//+------------------------------------------------------------------+
void ManagePositionPerTick(ulong ticket, int stateIdx)
  {
   string symbol = posInfo.Symbol();
   double atr = g_posState[stateIdx].signalAtr;
   if(atr <= 0.0)
     {
      if(!ReadAtrForSymbol(symbol, atr) || atr <= 0.0)
         return;
     }

   datetime curBarTime = (datetime)iTime(symbol, InpTimeframe, 0);
   if(curBarTime != 0 && curBarTime != g_posState[stateIdx].lastMgmtBarTime)
     {
      g_posState[stateIdx].lastMgmtBarTime = curBarTime;
      UpdateBarsClosed(stateIdx, symbol);
      if(InpMaxHoldingBars > 0 && g_posState[stateIdx].barsClosed >= InpMaxHoldingBars)
        {
         trade.PositionClose(ticket);
         return;
        }
     }

   if(!InpUseLockTrail)                 // v1.23 pure bracket: SL/TP are broker-side, nothing to trail
      return;

   double point  = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits    = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double bid    = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask    = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double entry  = posInfo.PriceOpen();
   double curSL  = posInfo.StopLoss();
   double curTP  = posInfo.TakeProfit();
   long   spread = SymbolInfoInteger(symbol, SYMBOL_SPREAD);

   double lockBuffer = ((InpLockBufferPoints > 0) ? InpLockBufferPoints : (spread + 2)) * point;
   double lockTrigger = InpLockTriggerAtr * atr;
   double trailDist   = InpTrailAtrMult * atr;

   if(posInfo.PositionType() == POSITION_TYPE_BUY)
     {
      double profit = bid - entry;
      double newSL = curSL;

      if(profit >= lockTrigger)
        {
         double lockSL = NormalizeDouble(entry + lockBuffer, digits);
         if(lockSL > newSL)
            newSL = lockSL;
         double trailSL = NormalizeDouble(bid - trailDist, digits);
         if(trailSL > newSL && trailSL < bid)
            newSL = trailSL;
        }
      if(newSL > curSL && newSL < bid)
         trade.PositionModify(ticket, newSL, curTP);
     }
   else
     {
      double profit = entry - ask;
      double newSL = curSL;
      if(profit >= lockTrigger)
        {
         double lockSL = NormalizeDouble(entry - lockBuffer, digits);
         if(curSL == 0.0 || lockSL < newSL)
            newSL = lockSL;
         double trailSL = NormalizeDouble(ask + trailDist, digits);
         if((trailSL < newSL || newSL == 0.0) && trailSL > ask)
            newSL = trailSL;
        }
      if((curSL == 0.0 || newSL < curSL) && newSL > ask)
         trade.PositionModify(ticket, newSL, curTP);
     }
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

void StorePendingSigAtr(ulong orderTicket, double atr)
  {
   if(orderTicket == 0 || atr <= 0.0)
      return;
   int n = ArraySize(g_pendingSigAtr);
   ArrayResize(g_pendingSigAtr, n + 1);
   g_pendingSigAtr[n].orderTicket = orderTicket;
   g_pendingSigAtr[n].atr = atr;
  }

double TakePendingSigAtr(ulong orderTicket)
  {
   for(int i = 0; i < ArraySize(g_pendingSigAtr); i++)
     {
      if(g_pendingSigAtr[i].orderTicket == orderTicket)
        {
         double atr = g_pendingSigAtr[i].atr;
         for(int j = i; j < ArraySize(g_pendingSigAtr) - 1; j++)
            g_pendingSigAtr[j] = g_pendingSigAtr[j + 1];
         ArrayResize(g_pendingSigAtr, ArraySize(g_pendingSigAtr) - 1);
         return(atr);
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
   int h = FileOpen(InpPartialLogFileV130, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE)
     {
      if(FileSize(h) == 0)
         FileWriteString(h, "time,deal,position_id,symbol,dir,initial_volume,target_volume,deal_volume,level,fill,slippage_price,slippage_R,state\r\n");
      FileSeek(h, 0, SEEK_END);
      FileWriteString(h, StringFormat("%s,%I64u,%I64d,%s,%s,%.2f,%.2f,%.2f,%.5f,%.5f,%.5f,%.5f,%s\r\n",
                      TimeToString((datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME), TIME_DATE | TIME_SECONDS),
                      dealTicket, posId, symbol, dir > 0 ? "BUY" : (dir < 0 ? "SELL" : "NA"),
                      initialVol, targetVol, vol, level, fill, slipPrice, slipR,
                      (si >= 0) ? PartialStateText(g_posState[si].partialState) : "UNKNOWN"));
      FileClose(h);
     }
   PrintFormat("v1.30 PARTIAL FILL position=%I64d deal=%I64u %s vol=%.2f level=%.5f fill=%.5f slip=%+.5f (%+.4fR)",
               posId, dealTicket, symbol, vol, level, fill, slipPrice, slipR);
  }

string PartialStateGv(long positionId)   { return("MPB_v130_so_state_" + (string)positionId); }
string PartialVolumeGv(long positionId)  { return("MPB_v130_so_initvol_" + (string)positionId); }
string PartialTriggerGv(long positionId) { return("MPB_v130_so_trigger_" + (string)positionId); }
string PartialAttemptsGv(long positionId){ return("MPB_v130_so_attempts_" + (string)positionId); }

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
   if(raw + 1e-12 < minVol)                 // binding: never round a sub-min half upward
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
   if(g_posState[stateIdx].partialTriggerTime > 0)
      GlobalVariableSet(PartialTriggerGv(id), (double)g_posState[stateIdx].partialTriggerTime);
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
   if(GlobalVariableCheck(PartialTriggerGv(id)))
      g_posState[stateIdx].partialTriggerTime = (datetime)GlobalVariableGet(PartialTriggerGv(id));
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
   if(state == PARTIAL_ARMED && !reached)
      return(false);
   if(state == PARTIAL_ARMED)
     {
      g_posState[stateIdx].partialState = PARTIAL_TRIGGERED;
      g_posState[stateIdx].partialTriggerTime = TimeCurrent();
      g_posState[stateIdx].partialNextRetry = 0;
      g_posState[stateIdx].partialAttempts = 0;
      PersistPartialState(stateIdx);
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
      SetPartialState(stateIdx, PARTIAL_SKIPPED, "half volume is below broker min/step or leaves invalid remainder");
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
   if(entryBar > 0)
     {
      int shift = iBarShift(symbol, InpTimeframe, entryBar, false);
      if(shift >= 0)
        {
         // Entry bar at shift s => s bars opened after it => s closes elapsed
         // (the entry bar's own close is counted, matching RegisterPositionState).
         g_posState[stateIdx].barsClosed = shift;
         return;
        }
     }
   g_posState[stateIdx].barsClosed++;   // fallback: old increment semantics
  }

//+------------------------------------------------------------------+
//| ATR for any symbol we hold a position in - falls back to an       |
//| on-demand iATR handle when the symbol is no longer in the         |
//| whitelist universe (review P4: whitelist-orphan positions kept    |
//| their time exit but silently lost lock/trail).                    |
//| iATR returns the SAME cached handle for identical parameters, so  |
//| calling it repeatedly does not leak handles.                      |
//+------------------------------------------------------------------+
bool ReadAtrForSymbol(string symbol, double &value)
  {
   return(WilderAtrForSymbol(symbol, value));   // v1.27: single estimator everywhere
  }

void RegisterPositionState(long positionId, string symbol, double signalAtr, datetime openTime)
  {
   int existing = FindPositionState(positionId);
   if(existing >= 0)
     {
      // v1.26: a REAL frozen ATR arriving after a fallback registration must win
      // (the fallback used current ATR; downstream riskPrice/R math needs the true one).
      if(signalAtr > 0.0 && g_posState[existing].signalAtr != signalAtr)
        {
         g_posState[existing].signalAtr = signalAtr;
         GlobalVariableSet("DSv121_atr_" + (string)positionId, signalAtr);
         if(g_posState[existing].entryPrice > 0.0)
            g_posState[existing].riskPrice = InpStopAtrMult * signalAtr;
         RefreshPartialGeometry(existing, symbol);
        }
      return;
     }

   datetime entryBar = (datetime)iTime(symbol, InpTimeframe, 0);
   int shift = iBarShift(symbol, InpTimeframe, openTime, false);
   if(shift >= 0)
      entryBar = (datetime)iTime(symbol, InpTimeframe, shift);

   // Frozen-ATR persistence (review fix): restore the ORIGINAL signal ATR across EA
   // reloads via a terminal global variable, before falling back to the current ATR.
   string gvName = "DSv121_atr_" + (string)positionId;
   if(signalAtr <= 0.0 && GlobalVariableCheck(gvName))
      signalAtr = GlobalVariableGet(gvName);
   if(signalAtr <= 0.0)
      ReadAtrForSymbol(symbol, signalAtr);
   if(signalAtr > 0.0)
      GlobalVariableSet(gvName, signalAtr);

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
   g_posState[n].desiredSL = 0.0;
   g_posState[n].entryPrice = 0.0;
   g_posState[n].riskPrice = 0.0;
   g_posState[n].dir = 0;
   g_posState[n].spreadAtrEntry = 0.0;
   g_posState[n].mfeR = 0.0;
   g_posState[n].maeR = 0.0;
   g_posState[n].initialVolume = 0.0;
   g_posState[n].partialTargetVolume = 0.0;
   g_posState[n].partialLevel = 0.0;
   g_posState[n].partialState = PARTIAL_ARMED;
   g_posState[n].partialTriggerTime = 0;
   g_posState[n].partialNextRetry = 0;
   g_posState[n].partialAttempts = 0;

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
      if(signalAtr > 0.0)
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

bool ReadAtr(int handle, double &value)
  {
   double tmp[];
   if(handle == INVALID_HANDLE)
      return(false);
   if(CopyBuffer(handle, 0, 1, 1, tmp) != 1)
      return(false);
   value = tmp[0];
   return(value > 0.0);
  }

//+------------------------------------------------------------------+
//| Session-anchored VWAP: cumulative from the session (day) open up  |
//| to bar `shift`, resetting every session. Tick-volume weighted.    |
//+------------------------------------------------------------------+
double AnchoredVwap(string symbol, ENUM_TIMEFRAMES tf, int shift, int maxBars, int &barsInSession)
  {
   barsInSession = 0;
   datetime anchorTime = iTime(symbol, tf, shift);
   if(anchorTime == 0)
      return(0.0);
   MqlDateTime ref;
   TimeToStruct(anchorTime, ref);

   double pv = 0.0, vv = 0.0;
   for(int j = shift; j < shift + maxBars; j++)
     {
      datetime bt = iTime(symbol, tf, j);
      if(bt == 0)
         break;
      MqlDateTime st;
      TimeToStruct(bt, st);
      // Stop at the session boundary (new calendar day = new VWAP anchor).
      if(st.day != ref.day || st.mon != ref.mon || st.year != ref.year)
         break;
      barsInSession++;
      double hi = iHigh(symbol, tf, j);
      double lo = iLow(symbol, tf, j);
      double cl = iClose(symbol, tf, j);
      if(hi <= 0.0 || lo <= 0.0 || cl <= 0.0)
         continue;
      double typical = (hi + lo + cl) / 3.0;
      double vol = (double)iTickVolume(symbol, tf, j);
      if(vol <= 0.0)
         vol = 1.0;             // equal-weight fallback if no volume
      pv += typical * vol;
      vv += vol;
     }
   return(vv > 0.0 ? pv / vv : 0.0);
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

bool SpreadTooWide(string symbol)
  {
   if(InpMaxSpreadPtsRaw <= 0)
      return(false);
   return(SymbolInfoInteger(symbol, SYMBOL_SPREAD) > InpMaxSpreadPtsRaw);
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
   g_halted          = false;
  }

datetime DayStart(datetime t)
  {
   MqlDateTime st;
   TimeToStruct(t, st);
   st.hour = 0; st.min = 0; st.sec = 0;
   return(StructToTime(st));
  }

void UpdatePeakEquity()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEquity)
     {
      g_peakEquity = eq;
      GlobalVariableSet("MPB_peak_equity", g_peakEquity);   // v1.26: the trailing halt must see across re-inits
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
   if(GlobalVariableCheck("MPB_peak_equity"))
      g_peakEquity = MathMax(GlobalVariableGet("MPB_peak_equity"), eq);
   GlobalVariableSet("MPB_peak_equity", g_peakEquity);

   g_initialBalance = InpInitialBalance;
   if(g_initialBalance <= 0.0)
     {
      if(!GlobalVariableCheck("MPB_init_balance"))
         GlobalVariableSet("MPB_init_balance", bal);
      g_initialBalance = GlobalVariableGet("MPB_init_balance");
     }

   g_currentDay = DayStart(TimeCurrent());
   double dayPnl = 0.0;
   int placements = 0;
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
         if(HistoryDealGetInteger(d, DEAL_MAGIC) == InpMagicNumber &&
            HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
            placements++;
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
   int streak = 0;
   int total = HistoryDealsTotal();
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
   PanelSet(ln++, StringFormat("MomentumPullbackEA v1.30  THOUGHT PROCESS   %s srv",
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
      string so = (si >= 0) ? StringFormat("%s@%.2f", PartialStateText(g_posState[si].partialState),
                                            g_posState[si].partialLevel) : "UNKNOWN";
      PanelSet(ln++, StringFormat("POS %s %s %.2f @ %.2f | b%d/%d | MFE%+.2f MAE%+.2f | SO %s",
                posInfo.Symbol(), posInfo.PositionType() == POSITION_TYPE_BUY ? "BUY " : "SELL",
                posInfo.Volume(), posInfo.PriceOpen(), bars, InpMaxHoldingBars, mfe, mae, so),
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
   DecisionCsvMaybe();
  }

// One row per closed M15 bar -> monthly CSV (bounded growth; S3 shadow substrate).
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
   int h = FileOpen(fn, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   if(FileSize(h) == 0)
      FileWriteString(h, "time,verdicts,fills,day_pnl,halted,hard,positions,pendings,partial_states\r\n");
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
