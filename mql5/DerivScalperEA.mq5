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
//|   v1.21 (2026-07): EXIT-ENGINE FIDELITY (see docs/LIVE_TRADE_      |
//|   ANALYSIS_2026-07-01.md). Live was managing lock/trail per tick;  |
//|   the validated harness manages on M15 bar close. Default now:     |
//|   InpManageOnBarClose=true, frozen signal-ATR, limit anchored to   |
//|   signal-bar close, per-symbol bar clocks, OnTimer heartbeat.      |
//+------------------------------------------------------------------+
#property copyright "Deriv momentum scalper"
#property version   "1.21"
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
input int    InpMaxHoldingBars   = 8;     // Force-close a stagnant trade after N closed bars (0 = off)
input bool   InpManageOnBarClose = true;  // P0: lock/trail on M15 bar close (validated engine; false = legacy per-tick)

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
input int    InpHeartbeatSeconds = 5;     // OnTimer scan/manage heartbeat (0 = chart ticks only)

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

// Open position metadata for bar-close management (keyed by POSITION_IDENTIFIER).
struct PositionMgmtState
  {
   long     positionId;
   double   signalAtr;
   datetime entryBarTime;
   datetime lastMgmtBarTime;
   int      barsClosed;
  };
PositionMgmtState g_posState[];

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

   // Per-symbol bar clocks: skip mid-bar rescan after reload (see LIVE_TRADE_ANALYSIS §1).
   ArrayResize(g_lastScanBar, ArraySize(g_symbols));
   for(int i = 0; i < ArraySize(g_symbols); i++)
      g_lastScanBar[i] = (datetime)iTime(g_symbols[i], InpTimeframe, 0);

   if(InpHeartbeatSeconds > 0)
      EventSetTimer(InpHeartbeatSeconds);

   // Register any positions already open (e.g. after EA reload).
   SyncOpenPositionStates();

   PrintFormat("DerivScalperEA v1.21 ready. Entry=%s. ManageOnBarClose=%s. Scanning %d symbols on %s. Risk/trade=%.2f%%.",
               (InpEntryMode == ENTRY_LIMIT_PULLBACK ? "PULLBACK(limit)" : "BREAKOUT(stop)"),
               (InpManageOnBarClose ? "yes" : "legacy per-tick"),
               ArraySize(g_symbols), EnumToString(InpTimeframe), InpRiskPercent);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
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

   int h = iATR(symbol, InpTimeframe, InpAtrPeriod);
   if(h == INVALID_HANDLE)
      return;

   int idx = ArraySize(g_symbols);
   ArrayResize(g_symbols, idx + 1);
   ArrayResize(g_atrHandle, idx + 1);
   g_symbols[idx]   = symbol;
   g_atrHandle[idx] = h;
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

   ManageAll();
   ScanAllOnNewBars();
  }

//+------------------------------------------------------------------+
//| Scan each symbol once per closed bar on that symbol's own clock. |
//+------------------------------------------------------------------+
void ScanAllOnNewBars()
  {
   UpdatePeakEquity();
   if(g_halted)
      return;
   if(DrawdownExceeded()) { g_halted = true; Print("Max drawdown hit - halted."); return; }
   if(DailyLossExceeded()){ g_halted = true; Print("Daily loss limit hit - paused for the day."); return; }
   if(InpMaxConsecLosses > 0 && ConsecutiveLossesToday() >= InpMaxConsecLosses)
      return;
   if(g_tradesToday >= InpMaxTradesPerDay)
      return;

   for(int i = 0; i < ArraySize(g_symbols); i++)
     {
      if(CountOpenAndPending() >= InpMaxConcurrent)
         break;

      datetime barTime = (datetime)iTime(g_symbols[i], InpTimeframe, 0);
      if(barTime == g_lastScanBar[i])
         continue;
      g_lastScanBar[i] = barTime;

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
   if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_IN)
      return;

   long posId = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   string symbol = HistoryDealGetString(trans.deal, DEAL_SYMBOL);
   ulong orderTicket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER);
   datetime dealTime = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
   double sigAtr = TakePendingSigAtr(orderTicket);
   if(sigAtr <= 0.0)
     {
      int idx = SymbolIndex(symbol);
      if(idx >= 0)
         ReadAtr(g_atrHandle[idx], sigAtr);
     }
   RegisterPositionState(posId, symbol, sigAtr, dealTime);
  }

//+------------------------------------------------------------------+
//| Evaluate one symbol and place a pending order if momentum is hot |
//+------------------------------------------------------------------+
void ScanSymbol(string symbol, int atrHandle)
  {
   if(HasExposure(symbol))           // already trading this symbol
      return;
   if(!DataReady(symbol))
     {
      LogSkip(symbol, "data not ready");
      return;
     }
   if(SpreadTooWide(symbol))
     {
      LogSkip(symbol, "spread points gate");
      return;
     }

   double atr;
   if(!ReadAtr(atrHandle, atr) || atr <= 0.0)
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

   if(!fallingFast && !(risingFast && InpTradeBothSides))
     {
      LogSkip(symbol, StringFormat("no impulse (move=%.2f ATR)", moveAtr), atr, spreadAtrSide, moveAtr);
      return;
     }

   // Continuation in the direction of the move. PULLBACK uses LIMIT orders (enter on
   // the retrace); BREAKOUT uses STOP orders (chase beyond price, the legacy behaviour).
   ENUM_ORDER_TYPE buyType  = (InpEntryMode == ENTRY_LIMIT_PULLBACK) ? ORDER_TYPE_BUY_LIMIT  : ORDER_TYPE_BUY_STOP;
   ENUM_ORDER_TYPE sellType = (InpEntryMode == ENTRY_LIMIT_PULLBACK) ? ORDER_TYPE_SELL_LIMIT : ORDER_TYPE_SELL_STOP;

   if(fallingFast)
      PlacePending(symbol, sellType, atr, close1, (close1 - closePast) / atr, spreadAtrSide);
   else if(risingFast && InpTradeBothSides)
      PlacePending(symbol, buyType, atr, close1, (close1 - closePast) / atr, spreadAtrSide);
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
   double tpDist   = (InpTakeProfitAtrMult > 0.0) ? atr * InpTakeProfitAtrMult : 0.0;
   if(stopsLevel > 0.0)
     {
      stopDist = MathMax(stopDist, stopsLevel * 1.5);
      if(tpDist > 0.0) tpDist = MathMax(tpDist, stopsLevel * 1.5);
     }

   double entry, sl, tp;
   if(isBuy)
     {
      // BUY_STOP sits above the ask; BUY_LIMIT sits below signal-bar close (pullback).
      entry = isLimit ? NormalizeDouble(signalClose - offset, digits)
                      : NormalizeDouble(ask + offset, digits);
      sl    = NormalizeDouble(entry - stopDist, digits);
      tp    = (tpDist > 0.0) ? NormalizeDouble(entry + tpDist, digits) : 0.0;
     }
   else
     {
      // SELL_STOP sits below the bid; SELL_LIMIT sits above signal-bar close (pullback).
      entry = isLimit ? NormalizeDouble(signalClose + offset, digits)
                      : NormalizeDouble(bid - offset, digits);
      sl    = NormalizeDouble(entry + stopDist, digits);
      tp    = (tpDist > 0.0) ? NormalizeDouble(entry - tpDist, digits) : 0.0;
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
      StorePendingSigAtr(trade.ResultOrder(), atr);
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
            trade.OrderDelete(ticket);
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
   if(curBarTime == g_posState[stateIdx].lastMgmtBarTime)
      return;

   g_posState[stateIdx].lastMgmtBarTime = curBarTime;
   g_posState[stateIdx].barsClosed++;

   if(InpMaxHoldingBars > 0 && g_posState[stateIdx].barsClosed >= InpMaxHoldingBars)
     {
      trade.PositionClose(ticket);
      return;
     }

   double signalAtr = g_posState[stateIdx].signalAtr;
   if(signalAtr <= 0.0)
     {
      int idx = SymbolIndex(symbol);
      if(idx < 0 || !ReadAtr(g_atrHandle[idx], signalAtr) || signalAtr <= 0.0)
         return;
      g_posState[stateIdx].signalAtr = signalAtr;
     }

   double barClose = iClose(symbol, InpTimeframe, 1);
   if(barClose <= 0.0)
      return;

   int digits    = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double entry  = posInfo.PriceOpen();
   double curSL  = posInfo.StopLoss();
   double curTP  = posInfo.TakeProfit();
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

      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      if(newSL > curSL && newSL < bid)
         trade.PositionModify(ticket, newSL, curTP);
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

      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      if((curSL == 0.0 || newSL < curSL) && newSL > ask)
         trade.PositionModify(ticket, newSL, curTP);
     }
  }

//+------------------------------------------------------------------+
//| Legacy per-tick management (InpManageOnBarClose=false only).      |
//+------------------------------------------------------------------+
void ManagePositionPerTick(ulong ticket, int stateIdx)
  {
   string symbol = posInfo.Symbol();
   int idx = SymbolIndex(symbol);
   double atr = g_posState[stateIdx].signalAtr;
   if(atr <= 0.0)
     {
      if(idx < 0 || !ReadAtr(g_atrHandle[idx], atr) || atr <= 0.0)
         return;
     }

   datetime curBarTime = (datetime)iTime(symbol, InpTimeframe, 0);
   if(curBarTime != g_posState[stateIdx].lastMgmtBarTime)
     {
      g_posState[stateIdx].lastMgmtBarTime = curBarTime;
      g_posState[stateIdx].barsClosed++;
      if(InpMaxHoldingBars > 0 && g_posState[stateIdx].barsClosed >= InpMaxHoldingBars)
        {
         trade.PositionClose(ticket);
         return;
        }
     }

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

void RegisterPositionState(long positionId, string symbol, double signalAtr, datetime openTime)
  {
   if(FindPositionState(positionId) >= 0)
      return;

   datetime entryBar = (datetime)iTime(symbol, InpTimeframe, 0);
   int shift = iBarShift(symbol, InpTimeframe, openTime, false);
   if(shift >= 0)
      entryBar = (datetime)iTime(symbol, InpTimeframe, shift);

   if(signalAtr <= 0.0)
     {
      int idx = SymbolIndex(symbol);
      if(idx >= 0)
         ReadAtr(g_atrHandle[idx], signalAtr);
     }

   int barsClosed = 0;
   for(int s = 1; s < 500; s++)
     {
      datetime bt = (datetime)iTime(symbol, InpTimeframe, s);
      if(bt == 0 || bt <= entryBar)
         break;
      barsClosed++;
     }

   int n = ArraySize(g_posState);
   ArrayResize(g_posState, n + 1);
   g_posState[n].positionId = positionId;
   g_posState[n].signalAtr = signalAtr;
   g_posState[n].entryBarTime = entryBar;
   g_posState[n].lastMgmtBarTime = (datetime)iTime(symbol, InpTimeframe, 0);
   g_posState[n].barsClosed = barsClosed;
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
