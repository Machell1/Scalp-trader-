//+------------------------------------------------------------------+
//|                                                DerivScalperEA.mq5 |
//|   Multi-symbol momentum scalper for Deriv MT5.                    |
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
//|   v1.3 (2026-07): EXIT-ENGINE FIDELITY fix (P0 from the first 15  |
//|   live trades — docs/LIVE_TRADE_ANALYSIS_2026-07-01.md). The v1.2 |
//|   EA managed the break-even lock / trail PER TICK, but the engine |
//|   that passed the walk-forward/DSR ship gate manages ON M15 BAR   |
//|   CLOSE (backtest/scalper_confluence.py). 8 of the first 15 live  |
//|   exits were impossible under the validated engine (scratch swarm,|
//|   winners cut ~1R, zero TP exits). v1.3 reverts to the validated  |
//|   mechanics — this is a fidelity fix, NOT a strategy change:      |
//|     * InpManageOnBarClose=true (default): lock/trail update only  |
//|       when a bar CLOSES on the position's OWN symbol, computed    |
//|       from that bar's close; the broker-side SL stays static      |
//|       between bar closes (intrabar execution on a static level = |
//|       the harness's stop-vs-next-bar-range semantics).            |
//|     * Lock/trail/TP distances use the ATR FROZEN at the signal    |
//|       bar (persisted per position; no more per-tick ATR drift).   |
//|     * The pullback LIMIT is anchored to the SIGNAL-BAR CLOSE      |
//|       (iClose(sym,tf,1)), not the live bid/ask.                   |
//|     * Reload guard: scan clocks initialise to the current forming |
//|       bar, so an EA reload can never place mid-bar-anchored orders|
//|     * Time exit counts CLOSED BARS of the position's symbol       |
//|       (was wall-clock seconds).                                   |
//|     * OnTimer heartbeat + per-symbol bar clocks: management and   |
//|       scanning no longer stall when the CHART symbol's market is  |
//|       closed (P1 from the same analysis).                         |
//|     * Signal/spread decision logging (backlog #2; no behaviour    |
//|       change) via InpLogDecisions.                                |
//+------------------------------------------------------------------+
#property copyright "Deriv momentum scalper"
#property version   "1.30"
#property strict
#property description "Multi-symbol M15 momentum PULLBACK scalper for Deriv (spread-gated crypto + indices)."

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
input bool   InpScanMarketWatch  = true;     // Scan Market Watch (used only when the whitelist below is empty)
input string InpSymbolWhitelist  = "BTCUSD,ETHUSD,XRPUSD,SOLUSD,US Tech 100,US SP 500,Wall Street 30,US Small Cap 2000,Germany 40,UK 100,Japan 225,France 40"; // v1.2 SPREAD-GATED universe: only Deriv majors whose real spread<=0.05 ATR/side (positive net of cost, t+4). Dropped LTC/BCH/Mid Cap 400/Australia 200/Hong Kong 50 (spreads too wide). CLEAR to scan all.
input string InpSyntheticBlock   = "Volatility,Crash,Boom,Step,Jump,Range Break,Vol over,Hybrid,Drift,DEX,Multi Step,Skew,1HZ,Basket"; // Skip names containing any of these

//--- Strategy --------------------------------------------------------
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
input int    InpPendingExpiryBars  = 3;    // Cancel an untriggered pending order after N bars
input bool   InpTrailPending       = true; // BREAKOUT mode only: keep the stop pending glued to price

//--- Risk / exits ----------------------------------------------------
input group "=== Risk & Exits ==="
input double InpRiskPercent      = 0.5;   // Risk per trade (% of balance)
input double InpStopAtrMult      = 1.0;   // Initial stop distance (ATR) - tight = fast loss cut
input double InpTakeProfitAtrMult= 3.0;   // Take-profit distance (ATR). 3.0 = let winners run (backtest-validated); 0 = trail only
input double InpLockTriggerAtr   = 0.25;  // Once price is this many ATR in profit, lock the trade
input int    InpLockBufferPoints = 0;     // Extra points locked above break-even (0 = auto: spread+2)
input double InpTrailAtrMult      = 0.5;  // Trailing distance after lock (ATR)
input int    InpMaxHoldingBars   = 8;     // Force-close a stagnant trade after N CLOSED bars of its own symbol (0 = off)
input bool   InpManageOnBarClose = true;  // v1.3 FIDELITY: lock/trail from the position symbol's bar CLOSE with the signal-bar ATR (the validated engine). false = legacy per-tick (NOT validated)

//--- Portfolio risk --------------------------------------------------
input group "=== Portfolio Risk ==="
input int    InpMaxConcurrent    = 3;     // Max simultaneous open positions (all symbols)
input int    InpMaxTradesPerDay  = 20;    // Max new trades opened per day (all symbols)
input double InpDailyLossLimitPct= 3.0;   // Halt for the day after this daily loss (% of day-start balance)
input double InpMaxDrawdownPct   = 15.0;  // Halt if equity drawdown from peak exceeds this
input int    InpMaxConsecLosses  = 4;     // Pause for the day after this many losses in a row
input int    InpMaxSpreadPoints  = 200;   // Skip a symbol if spread (points) exceeds this
input double InpMaxSpreadAtr      = 0.05;  // v1.2 KEY GATE: skip if current spread > this many ATR PER SIDE (0.05 = validated ceiling; the edge dies above it, e.g. LTC/BCH/Mid Cap). 0 = off.

//--- Execution -------------------------------------------------------
input group "=== Execution ==="
input long   InpMagicNumber      = 770077;// Magic number tagging this EA's orders
input ulong  InpDeviationPoints  = 30;    // Max slippage in points
input string InpTradeComment     = "DerivScalper";
input int    InpTimerSeconds     = 5;     // v1.3 heartbeat (sec): manage/scan even when the chart symbol's market is closed (0 = chart ticks only)
input bool   InpLogDecisions     = true;  // v1.3 backlog #2: log one line per momentum signal (impulse/ATR/spread/anchor + take-or-skip reason)

//--- Globals ---------------------------------------------------------
CTrade        trade;
CPositionInfo posInfo;
COrderInfo    ordInfo;

string   g_symbols[];      // Tradable, non-synthetic symbols
int      g_atrHandle[];    // Parallel ATR handle per symbol
datetime g_scanBarTime[];  // Parallel per-symbol scan clock (time of the forming bar last seen)

datetime g_currentDay  = 0;
double   g_dayStartBalance = 0.0;
double   g_peakEquity  = 0.0;
int      g_tradesToday = 0;
bool     g_halted      = false;

//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.LogLevel(LOG_LEVEL_ERRORS);

   if(!BuildSymbolUniverse())
     {
      Print("No tradable non-synthetic symbols found. Add symbols to Market Watch.");
      return(INIT_FAILED);
     }

   g_peakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   ResetDailyState();

   // v1.3 heartbeat: without a timer, OnTick only fires on CHART-symbol ticks, so
   // management of open positions on OTHER symbols freezes whenever the chart
   // symbol's market is closed. The timer keeps manage/scan alive regardless.
   if(InpTimerSeconds > 0)
      EventSetTimer(InpTimerSeconds);

   PrintFormat("DerivScalperEA v1.3 ready. Entry=%s. Manage=%s. Scanning %d symbols on %s. Risk/trade=%.2f%%.",
               (InpEntryMode == ENTRY_LIMIT_PULLBACK ? "PULLBACK(limit)" : "BREAKOUT(stop)"),
               (InpManageOnBarClose ? "BAR-CLOSE(validated)" : "PER-TICK(legacy, NOT validated)"),
               ArraySize(g_symbols), EnumToString(InpTimeframe), InpRiskPercent);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
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
   ArrayResize(g_scanBarTime, 0);

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

   int h = iATR(symbol, InpTimeframe, InpAtrPeriod);
   if(h == INVALID_HANDLE)
      return;

   int idx = ArraySize(g_symbols);
   ArrayResize(g_symbols, idx + 1);
   ArrayResize(g_atrHandle, idx + 1);
   ArrayResize(g_scanBarTime, idx + 1);
   g_symbols[idx]   = symbol;
   g_atrHandle[idx] = h;
   // v1.3 reload-rescan guard: initialise the scan clock to the CURRENT forming bar
   // so an EA reload/attach mid-bar can never emit a mid-bar-anchored order (this
   // happened live at 07:47 - see docs/LIVE_TRADE_ANALYSIS_2026-07-01.md). If data
   // is not synchronised yet (iTime==0) the first-sight guard in Heartbeat() covers it.
   g_scanBarTime[idx] = (datetime)iTime(symbol, InpTimeframe, 0);
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
//| v1.3: OnTick AND a timer drive the same heartbeat, so management  |
//| and scanning keep running when the chart symbol's market is       |
//| closed (previously everything keyed off _Symbol's ticks/bars).    |
//+------------------------------------------------------------------+
void OnTick()  { Heartbeat(); }
void OnTimer() { Heartbeat(); }

void Heartbeat()
  {
   //--- Day rollover
   datetime today = DayStart(TimeCurrent());
   if(today != g_currentDay)
      ResetDailyState();

   //--- Manage pendings + open positions (in bar-close mode the lock/trail acts
   //    only when a bar has closed on the position's own symbol; the time exit
   //    and pending expiry are checked every heartbeat).
   ManageAll();

   //--- Scan for new entries once per closed bar of EACH symbol (per-symbol bar
   //    clocks; the chart symbol's clock is irrelevant).
   int due[];
   int nDue = 0;
   for(int i = 0; i < ArraySize(g_symbols); i++)
     {
      datetime barTime = (datetime)iTime(g_symbols[i], InpTimeframe, 0);
      if(barTime == 0 || barTime == g_scanBarTime[i])
         continue;
      bool firstSight = (g_scanBarTime[i] == 0);
      g_scanBarTime[i] = barTime;
      if(firstSight)
         continue;               // reload/late-sync guard: never act on a bar we did not watch open
      ArrayResize(due, nDue + 1);
      due[nDue++] = i;
     }
   if(nDue == 0)
      return;

   UpdatePeakEquity();
   if(g_halted)
      return;
   if(DrawdownExceeded()) { g_halted = true; Print("Max drawdown hit - halted."); return; }
   if(DailyLossExceeded()){ g_halted = true; Print("Daily loss limit hit - paused for the day."); return; }
   if(InpMaxConsecLosses > 0 && ConsecutiveLossesToday() >= InpMaxConsecLosses)
      return;
   if(g_tradesToday >= InpMaxTradesPerDay)
      return;

   for(int k = 0; k < nDue; k++)
     {
      if(CountOpenAndPending() >= InpMaxConcurrent)
         break;
      ScanSymbol(g_symbols[due[k]], g_atrHandle[due[k]]);
     }
  }

//+------------------------------------------------------------------+
//| Evaluate one symbol and place a pending order if momentum is hot |
//+------------------------------------------------------------------+
void ScanSymbol(string symbol, int atrHandle)
  {
   if(!DataReady(symbol))
      return;

   double atr;
   if(!ReadAtr(atrHandle, atr) || atr <= 0.0)
      return;

   double close1    = iClose(symbol, InpTimeframe, 1);
   double closePast = iClose(symbol, InpTimeframe, InpMomentumBars);
   double open1     = iOpen(symbol, InpTimeframe, 1);
   if(close1 == 0.0 || closePast == 0.0)
      return;

   double move = closePast - close1;            // positive => price fell
   double moveAtr = move / atr;

   bool fallingFast = (moveAtr >= InpMomentumAtrMult) && (close1 < open1);
   bool risingFast  = (-moveAtr >= InpMomentumAtrMult) && (close1 > open1);
   if(!fallingFast && !risingFast)
      return;                                   // no signal - nothing to log or place

   double pt = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double spreadPrice = (double)SymbolInfoInteger(symbol, SYMBOL_SPREAD) * pt;
   double spreadAtr = 0.5 * spreadPrice / atr;  // PER-SIDE spread, as in the backtest

   // Gates, cheapest first. All the checks the pre-v1.3 code did before/after the
   // signal are preserved; they are just evaluated after the signal so every
   // gated-away signal gets a logged skip reason (backlog #2).
   string verdict = "TAKE";
   if(HasExposure(symbol))
      verdict = "SKIP exposure";                // already trading this symbol
   else if(SpreadTooWide(symbol))
      verdict = "SKIP spread-points";
   // v1.2 spread/ATR gate (the key cost filter). The edge survives only where the
   // round-trip spread is small relative to the 1-ATR stop; skip if the current spread
   // PER SIDE exceeds the validated ceiling (this is what excludes wide-spread names
   // like LTC/BCH/Mid Cap, and protects against spread blow-outs during news).
   else if(InpMaxSpreadAtr > 0.0 && spreadAtr > InpMaxSpreadAtr)
      verdict = "SKIP spread-atr-gate";
   else if(risingFast && !InpTradeBothSides)
      verdict = "SKIP longs-disabled";

   // Optional Anchored-VWAP discount/premium gate (OFF by default in v1.2 -- it added no
   // out-of-sample edge and was overfit). When enabled: wait for VWAP to calibrate, then
   // buy ONLY at a discount (below VWAP) and sell ONLY at a premium (above VWAP).
   if(verdict == "TAKE" && InpUseVwapGate)
     {
      int sessBars = 0;
      double vwap = AnchoredVwap(symbol, InpTimeframe, 1, InpVwapMaxBars, sessBars);
      if(vwap <= 0.0 || sessBars < InpVwapMinBars)
         verdict = "SKIP vwap-uncalibrated";    // VWAP not calibrated yet this session
      else if(risingFast && close1 >= vwap)
         verdict = "SKIP vwap-no-discount";     // not a discount -> no buy
      else if(fallingFast && close1 <= vwap)
         verdict = "SKIP vwap-no-premium";      // not a premium -> no sell
     }

   // Backlog #2: one structured line per momentum signal (taken OR skipped), so live
   // impulse / ATR / spread-vs-model never has to be reconstructed from bar data.
   // Impulse sign convention matches the report tool: positive = up-move.
   if(InpLogDecisions)
      PrintFormat("DSLOG signal %s %s impulse=%.2fATR atr=%.6f spreadATRside=%.4f anchor=%.5f -> %s",
                  symbol, (fallingFast ? "SELL" : "BUY"), -moveAtr, atr, spreadAtr, close1, verdict);

   if(verdict != "TAKE")
      return;

   // Continuation in the direction of the move. PULLBACK uses LIMIT orders (enter on
   // the retrace, anchored to the SIGNAL-BAR CLOSE - the validated geometry);
   // BREAKOUT uses STOP orders (chase beyond price, the legacy behaviour).
   ENUM_ORDER_TYPE buyType  = (InpEntryMode == ENTRY_LIMIT_PULLBACK) ? ORDER_TYPE_BUY_LIMIT  : ORDER_TYPE_BUY_STOP;
   ENUM_ORDER_TYPE sellType = (InpEntryMode == ENTRY_LIMIT_PULLBACK) ? ORDER_TYPE_SELL_LIMIT : ORDER_TYPE_SELL_STOP;

   if(fallingFast)
      PlacePending(symbol, sellType, atr, close1);
   else if(risingFast)
      PlacePending(symbol, buyType, atr, close1);
  }

//+------------------------------------------------------------------+
//| Place a pending order.                                           |
//|  BREAKOUT: STOP just beyond price, in the move's direction.      |
//|  PULLBACK: LIMIT ~InpPullbackAtr ATR back from the SIGNAL-BAR    |
//|            CLOSE (`anchor`, v1.3 - matches the validated engine; |
//|            pre-v1.3 anchored to live bid/ask), so we enter on    |
//|            the retrace with the stop behind the pullback floor.  |
//+------------------------------------------------------------------+
void PlacePending(string symbol, ENUM_ORDER_TYPE type, double atr, double anchor)
  {
   double ask   = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid   = SymbolInfoDouble(symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int    digits= (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double stopsLevel = (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;

   bool isLimit = (type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_SELL_LIMIT);
   bool isBuy   = (type == ORDER_TYPE_BUY_STOP  || type == ORDER_TYPE_BUY_LIMIT);

   // How far the pending sits from its anchor.
   //   PULLBACK (limit): InpPullbackAtr ATR back from the signal-bar close.
   //   BREAKOUT (stop) : small InpEntryOffsetAtr ATR just beyond live price.
   double offset = isLimit ? (InpPullbackAtr * atr) : (InpEntryOffsetAtr * atr);
   offset = MathMax(offset, stopsLevel);     // respect the broker minimum distance
   if(offset <= 0.0)
      offset = 10 * point;

   double stopDist = atr * InpStopAtrMult;
   double tpDist   = (InpTakeProfitAtrMult > 0.0) ? atr * InpTakeProfitAtrMult : 0.0;
   if(stopsLevel > 0.0)
     {
      stopDist = MathMax(stopDist, stopsLevel * 1.5);
      if(tpDist > 0.0) tpDist = MathMax(tpDist, stopsLevel * 1.5);
     }

   double entry, sl, tp;
   if(isBuy)
     {
      // BUY_LIMIT sits below the signal-bar close (pullback); BUY_STOP above the ask.
      entry = isLimit ? NormalizeDouble(anchor - offset, digits)
                      : NormalizeDouble(ask + offset, digits);
      sl    = NormalizeDouble(entry - stopDist, digits);
      tp    = (tpDist > 0.0) ? NormalizeDouble(entry + tpDist, digits) : 0.0;
     }
   else
     {
      // SELL_LIMIT sits above the signal-bar close (pullback); SELL_STOP below the bid.
      entry = isLimit ? NormalizeDouble(anchor + offset, digits)
                      : NormalizeDouble(bid - offset, digits);
      sl    = NormalizeDouble(entry + stopDist, digits);
      tp    = (tpDist > 0.0) ? NormalizeDouble(entry - tpDist, digits) : 0.0;
     }

   // The signal-close anchor can be on the wrong side of the live market if price
   // gapped more than the pullback offset in the seconds since the bar closed. The
   // broker would reject such a limit; skip rather than invent an unvalidated
   // market entry (the harness would simply have filled at the limit next touch).
   if(isLimit)
     {
      bool placeable = isBuy ? (entry <= ask - stopsLevel - point)
                             : (entry >= bid + stopsLevel + point);
      if(!placeable)
        {
         PrintFormat("%s limit anchor already crossed (entry=%.5f bid=%.5f ask=%.5f) - signal skipped.",
                     symbol, entry, bid, ask);
         return;
        }
     }

   double lots = CalculateLotSize(symbol, stopDist);
   if(lots <= 0.0)
      return;

   datetime expiry = 0;
   ENUM_ORDER_TYPE_TIME ttype = ORDER_TIME_GTC;
   if(InpPendingExpiryBars > 0)
     {
      expiry = TimeCurrent() + (long)InpPendingExpiryBars * PeriodSeconds(InpTimeframe);
      ttype  = ORDER_TIME_SPECIFIED;
     }

   trade.SetTypeFillingBySymbol(symbol);
   bool ok = false;
   string tag = "";
   switch(type)
     {
      case ORDER_TYPE_BUY_STOP:   ok = trade.BuyStop  (lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "BUY STOP";   break;
      case ORDER_TYPE_SELL_STOP:  ok = trade.SellStop (lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "SELL STOP";  break;
      case ORDER_TYPE_BUY_LIMIT:  ok = trade.BuyLimit (lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "BUY LIMIT";  break;
      case ORDER_TYPE_SELL_LIMIT: ok = trade.SellLimit(lots, entry, symbol, sl, tp, ttype, expiry, InpTradeComment); tag = "SELL LIMIT"; break;
      default: return;
     }

   if(ok)
     {
      g_tradesToday++;
      // v1.3: FREEZE the signal-bar ATR for this trade's whole life. The position
      // opened by a pending order inherits the order ticket as its POSITION_IDENTIFIER,
      // so management can always find this value again - including after an EA reload
      // or terminal restart (terminal global variables persist on disk).
      ulong ordTicket = trade.ResultOrder();
      if(ordTicket > 0)
         StoreFrozenAtr(ordTicket, atr);
      PrintFormat("%s %s %.2f lots entry=%.5f SL=%.5f TP=%.5f sigATR=%.6f",
                  symbol, tag, lots, entry, sl, tp, atr);
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

   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
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
   ManageOpenPositions();
  }

//+------------------------------------------------------------------+
//| Expire stale pendings; trail BREAKOUT stop orders toward price.  |
//| PULLBACK limit orders are left to sit and wait for the retrace   |
//| (matches the validated backtest, which did not trail pendings).  |
//+------------------------------------------------------------------+
void ManagePendingOrders()
  {
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
         datetime maxAge = ordInfo.TimeSetup() + (long)InpPendingExpiryBars * PeriodSeconds(InpTimeframe);
         if(TimeCurrent() >= maxAge)
           {
            if(trade.OrderDelete(ticket))
               DeleteFrozenAtr(ticket);   // v1.3: drop the stored signal ATR with the order
            continue;
           }
        }

      // Only BREAKOUT stop orders are trailed to stay in front of price.
      if(!isStop || !InpTrailPending)
         continue;

      double atr;
      int idx = SymbolIndex(symbol);
      if(idx < 0 || !ReadAtr(g_atrHandle[idx], atr) || atr <= 0.0)
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
         double newEntry = NormalizeDouble(ask + offset, digits);
         // Only ratchet the entry DOWN toward price (price rising stays "in front").
         if(newEntry < curPrice - point)
           {
            double sl = NormalizeDouble(newEntry - stopDist, digits);
            double tp = (InpTakeProfitAtrMult > 0.0)
                        ? NormalizeDouble(newEntry + atr * InpTakeProfitAtrMult, digits) : 0.0;
            trade.OrderModify(ticket, newEntry, sl, tp, keepType, keepExpiry);
           }
        }
      else // SELL_STOP
        {
         double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
         double newEntry = NormalizeDouble(bid - offset, digits);
         // Only ratchet the entry UP toward price (price falling stays "in front").
         if(newEntry > curPrice + point)
           {
            double sl = NormalizeDouble(newEntry + stopDist, digits);
            double tp = (InpTakeProfitAtrMult > 0.0)
                        ? NormalizeDouble(newEntry - atr * InpTakeProfitAtrMult, digits) : 0.0;
            trade.OrderModify(ticket, newEntry, sl, tp, keepType, keepExpiry);
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Lock-to-breakeven, trail and time exit on open positions.        |
//|                                                                  |
//| v1.3 (InpManageOnBarClose=true, the VALIDATED engine):           |
//|   * The lock/trail decision uses the CLOSE of the last CLOSED    |
//|     bar on the position's OWN symbol - never the live tick -     |
//|     and the ATR FROZEN at the signal bar. Recomputing this every |
//|     heartbeat is idempotent within a bar (it depends only on     |
//|     bar-1 data + a ratchet), so no per-position clock is needed  |
//|     and the logic is reload-safe.                                |
//|   * Between bar closes the broker-side SL is static, so an       |
//|     intrabar tag of that static level reproduces the harness's   |
//|     "stop tested against the next bar's range" semantics.        |
//|   * Time exit fires after InpMaxHoldingBars CLOSED bars of the   |
//|     position's symbol (the harness exits at the close of bar     |
//|     entry+N-1, i.e. when N bars since entry have closed).        |
//| Legacy (false): the pre-v1.3 per-tick engine - NOT validated.    |
//+------------------------------------------------------------------+
void ManageOpenPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !posInfo.SelectByTicket(ticket))
         continue;
      if(posInfo.Magic() != InpMagicNumber)
         continue;

      string symbol = posInfo.Symbol();
      int idx = SymbolIndex(symbol);

      double point  = SymbolInfoDouble(symbol, SYMBOL_POINT);
      int digits    = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double bid    = SymbolInfoDouble(symbol, SYMBOL_BID);
      double ask    = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double entry  = posInfo.PriceOpen();
      double curSL  = posInfo.StopLoss();
      double curTP  = posInfo.TakeProfit();
      long   spread = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
      double stopsLevel = (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;

      // Time-based exit for stagnant trades.
      if(InpMaxHoldingBars > 0 && HoldingTimeUp(symbol, (datetime)posInfo.Time()))
        {
         if(trade.PositionClose(ticket))
            DeleteFrozenAtr((ulong)posInfo.Identifier());
         continue;
        }

      // ATR for the management distances: FROZEN signal-bar ATR in bar-close mode
      // (validated); re-read live in legacy per-tick mode (the old drifting behaviour).
      double atr = 0.0;
      bool haveAtr = InpManageOnBarClose
                     ? FrozenAtr((ulong)posInfo.Identifier(), idx, atr)
                     : (idx >= 0 && ReadAtr(g_atrHandle[idx], atr) && atr > 0.0);
      if(!haveAtr)
         continue;

      // Reference price for the lock/trail decision.
      double refPrice;
      if(InpManageOnBarClose)
        {
         datetime curBar = (datetime)iTime(symbol, InpTimeframe, 0);
         if(curBar == 0 || (datetime)posInfo.Time() >= curBar)
            continue;                    // entry bar has not closed yet - hands off
         refPrice = iClose(symbol, InpTimeframe, 1);
         if(refPrice <= 0.0)
            continue;
        }
      else
         refPrice = (posInfo.PositionType() == POSITION_TYPE_BUY) ? bid : ask;

      // Documented delta vs the harness: the harness locks to EXACT entry (0 gross);
      // the EA locks to entry +/- (spread+2)pts so a locked exit nets >= 0 after
      // spread. ~0.01 ATR, and conservative in the profitable direction.
      double lockBuffer  = ((InpLockBufferPoints > 0) ? InpLockBufferPoints : (spread + 2)) * point;
      double lockTrigger = InpLockTriggerAtr * atr;
      double trailDist   = InpTrailAtrMult * atr;

      if(posInfo.PositionType() == POSITION_TYPE_BUY)
        {
         double profit = refPrice - entry;
         double newSL = curSL;

         // Sufficiently green at the reference price -> lock, then trail. Ratchet only.
         if(profit >= lockTrigger)
           {
            double lockSL = NormalizeDouble(entry + lockBuffer, digits);
            if(lockSL > newSL)
               newSL = lockSL;
            double trailSL = NormalizeDouble(refPrice - trailDist, digits);
            if(trailSL > newSL)
               newSL = trailSL;
           }
         // Half-point epsilon: never re-send an SL the broker already holds.
         if(newSL > curSL + 0.5 * point)
           {
            if(newSL < bid - stopsLevel)
               trade.PositionModify(ticket, newSL, curTP);
            else if(newSL >= bid && InpManageOnBarClose)
              {
               // Price has already fallen through the bar-close stop level intrabar;
               // the validated engine would be out at that level - exit at market now.
               if(trade.PositionClose(ticket))
                  DeleteFrozenAtr((ulong)posInfo.Identifier());
              }
            // else: inside the broker freeze band - retry next heartbeat.
           }
        }
      else // SELL
        {
         double profit = entry - refPrice;
         double newSL = curSL;
         if(profit >= lockTrigger)
           {
            double lockSL = NormalizeDouble(entry - lockBuffer, digits);
            if(curSL == 0.0 || lockSL < newSL)
               newSL = lockSL;
            double trailSL = NormalizeDouble(refPrice + trailDist, digits);
            if(trailSL < newSL)
               newSL = trailSL;
           }
         // Half-point epsilon: never re-send an SL the broker already holds.
         if(curSL == 0.0 ? (newSL > 0.0) : (newSL < curSL - 0.5 * point))
           {
            if(newSL > ask + stopsLevel)
               trade.PositionModify(ticket, newSL, curTP);
            else if(newSL <= ask && InpManageOnBarClose)
              {
               if(trade.PositionClose(ticket))
                  DeleteFrozenAtr((ulong)posInfo.Identifier());
              }
            // else: inside the broker freeze band - retry next heartbeat.
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Time exit predicate.                                             |
//|  Bar-close mode: true once InpMaxHoldingBars bars of the         |
//|  position's OWN symbol have CLOSED since entry (validated).      |
//|  Legacy mode: wall-clock seconds (the pre-v1.3 behaviour).       |
//+------------------------------------------------------------------+
bool HoldingTimeUp(string symbol, datetime openTime)
  {
   if(InpManageOnBarClose)
     {
      int elapsed = iBarShift(symbol, InpTimeframe, openTime);
      return(elapsed >= InpMaxHoldingBars);
     }
   int barSecs = PeriodSeconds(InpTimeframe);
   return(barSecs > 0 && (long)(TimeCurrent() - openTime) >= (long)InpMaxHoldingBars * barSecs);
  }

//+------------------------------------------------------------------+
//| v1.3 frozen signal-ATR store (terminal global variables, which   |
//| persist across EA reloads and terminal restarts). Keyed by the   |
//| opening order's ticket == the position's POSITION_IDENTIFIER.    |
//+------------------------------------------------------------------+
string FrozenAtrName(ulong id)
  {
   return(StringFormat("DScalp.%I64d.ATR.%I64u", InpMagicNumber, id));
  }

void StoreFrozenAtr(ulong id, double atr)
  {
   GlobalVariableSet(FrozenAtrName(id), atr);
  }

void DeleteFrozenAtr(ulong id)
  {
   string name = FrozenAtrName(id);
   if(GlobalVariableCheck(name))
      GlobalVariableDel(name);
  }

bool FrozenAtr(ulong id, int idx, double &atr)
  {
   string name = FrozenAtrName(id);
   if(GlobalVariableCheck(name))
     {
      atr = GlobalVariableGet(name);
      return(atr > 0.0);
     }
   // Fallback (position predates v1.3, or the terminal variables were wiped):
   // freeze the CURRENT ATR from now on so distances at least stop drifting.
   if(idx < 0 || !ReadAtr(g_atrHandle[idx], atr) || atr <= 0.0)
      return(false);
   StoreFrozenAtr(id, atr);
   PrintFormat("Position %I64u had no stored signal ATR - froze current ATR %.6f from now on.", id, atr);
   return(true);
  }

//+------------------------------------------------------------------+
//| Garbage-collect stale frozen-ATR variables (positions closed by  |
//| the broker's SL/TP never pass through our delete path). Max      |
//| trade life is InpMaxHoldingBars*M15 ~ 2h, so anything older than |
//| 2 days is certainly orphaned. Runs once per day.                 |
//+------------------------------------------------------------------+
void SweepFrozenAtr()
  {
   string prefix = StringFormat("DScalp.%I64d.ATR.", InpMagicNumber);
   datetime cutoff = TimeCurrent() - 2 * 86400;
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
     {
      string name = GlobalVariableName(i);
      if(StringFind(name, prefix) != 0)
         continue;
      if(GlobalVariableTime(name) < cutoff)
         GlobalVariableDel(name);
     }
  }

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
int SymbolIndex(string symbol)
  {
   for(int i = 0; i < ArraySize(g_symbols); i++)
      if(g_symbols[i] == symbol)
         return(i);
   return(-1);
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
   if(InpMaxSpreadPoints <= 0)
      return(false);
   return(SymbolInfoInteger(symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints);
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
   SweepFrozenAtr();
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
      g_peakEquity = eq;
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

int ConsecutiveLossesToday()
  {
   if(!HistorySelect(g_currentDay, TimeCurrent()))
      return(0);
   int streak = 0;
   int total = HistoryDealsTotal();
   for(int i = total - 1; i >= 0; i--)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0)
         continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagicNumber)
         continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT)
         continue;
      double pnl = HistoryDealGetDouble(d, DEAL_PROFIT)
                 + HistoryDealGetDouble(d, DEAL_SWAP)
                 + HistoryDealGetDouble(d, DEAL_COMMISSION);
      if(pnl < 0.0)
         streak++;
      else if(pnl > 0.0)
         break;
     }
   return(streak);
  }
//+------------------------------------------------------------------+
