//+------------------------------------------------------------------+
//|                          Sentinel_V9_FUSION_ULTIMATE.mq5         |
//|         V7 Risk Core + V6 Active Management + V8 Python Bridge   |
//|                        Copyright 2026, Ambity Project            |
//+------------------------------------------------------------------+
#property copyright "Ambity Project"
#property version   "9.00"
#property strict
#property description "Fusion: V7 Risk Engine + V6 Trailing/Breakeven + V8 Bridge + Native Strategy"

#include <Trade\Trade.mqh>
CTrade trade;

#define DEV_POINTS_NORMAL 10
#define DEV_POINTS_VOLATILITY 50
#define RETCODE_INVALID_STOPS 10016
#define MIN_PATTERN_LENGTH 3

//============================ INPUTS ==============================//

input group "=== CORE SYSTEM ==="
input long   MAGIC_NUMBER        = 777777;
input int    TimerMilliseconds   = 500;
input bool   EnableHUD           = true;
input bool   SaveStateOnDisk     = true;

input group "=== RISK ENGINE (V7 - The Shield) ==="
input double MaxDailyDrawdownPercent = 5.0;  // Arrêt si perte journalière > X%
input double MaxRiskPerTradePercent  = 1.5;
input double MaxExposurePercent      = 6.0;  // Limite exposition (lots max = X/10)
input double MaxLotSize              = 2.0;

input group "=== EXECUTION FILTERS ==="
input double MaxAllowedSpreadPoints  = 300;

input group "=== TAKE PROFIT ==="
input double TakeProfitUSD        = 1.50;    // TP fixe en $ (0 = désactivé)

input group "=== TRAILING & BREAKEVEN (V6 - Active) ==="
input bool   EnableTrailingStop   = true;
input double TrailingStartPoints  = 500;     // Points de profit pour déclencher trailing
input double TrailingStepPoints   = 250;     // Distance de suivi en points
input bool   EnableAutoBreakeven  = true;
input double BreakevenTriggerProfit = 5.0;   // $ de profit pour breakeven

input group "=== STRATEGY HYBRID ==="
input bool   EnableNativeStrategy  = false;  // Bot interne (momentum M1)
input int    TrendPeriod           = 14;
input double MomentumThreshold     = 0.0008;

input bool   EnableAIBridge        = true;   // Écoute Python (TUDOR_TRADE, TRADE)
input bool   EnableTudorStrategies = true;
input double TudorRiskPercent      = 2.0;
input double MinAIConfidence       = 0.70;

input group "=== TUDOR STRATEGY SELECT ==="
enum ENUM_TUDOR_STRATEGY { TUDOR_REVERSAL = 1, TUDOR_MACRO_TREND = 2, TUDOR_VOLATILITY_BREAKOUT = 3, TUDOR_RISK_PARITY = 4 };
input ENUM_TUDOR_STRATEGY ActiveStrategy = TUDOR_REVERSAL;

input group "=== TESTING & EXPORT ==="
input bool   TestingMode          = true;   // Ignore risk halt si true
input string TradeSymbol          = "Volatility 100 Index";
input string ExportSymbols        = "Volatility 100 Index,EURUSD,XAUUSD,BTCUSD,ETHUSD";

//============================ STATE ===============================//
struct SentinelState {
   double dailyHighWaterMark;
   bool   tradingEnabled;
   bool   isBusy;
   string lastAction;
   string lastTudorPattern;
   double lastTudorSignalStrength;
   ENUM_TUDOR_STRATEGY currentStrategy;
   double totalExposureLots;
   datetime lastErrorNotification;
};

SentinelState SystemState;
string watermarkFile = "Sentinel_V9_State.dat";
string tickFile = "ticks_v3.json";
string tickFileTemp = "ticks_v3_temp.json";
string m5BarsFile = "m5_bars.json";
string m5BarsFileTemp = "m5_bars_temp.json";
string statusFile = "status.json";

//============================ PROTOTYPES ==========================//
string ExtractJsonValue(string source, string key);
void   Processing();
void   CheckRiskEngine();
void   ManagePositions();
void   ScanForCommands();
void   ScanNativeMarket();
void   ProcessCommandFile(string path);
void   ExecuteTudorTrade(string json);
void   ExecutePythonTrade(string json);
void   ExecuteNativeOrder(string symbol, string typeStr, double slPoints, string comment);
double CalculatePositionSize(string symbol, double stopLossPips, double riskPercentOverride = 0);
double CurrentExposureLots();
double CurrentExposurePercent();
bool   CheckSpread(string symbol);
bool   NormalizeStopLoss(string symbol, double &sl, double price, ENUM_ORDER_TYPE orderType);
double CalculateTakeProfitPrice(string symbol, double volume, string type, double entryPrice);
bool   IsTudorPatternValid(string pattern, double strength);
void   CloseAllPositions(string reason);
void   ExportTickData();
void   ExportM5Bars();
void   BroadcastStatus();
void   UpdateHUD();
void   LoadState();
void   SaveState();

//============================ INIT ================================//
int OnInit() {
   trade.SetExpertMagicNumber(MAGIC_NUMBER);
   trade.SetDeviationInPoints(DEV_POINTS_NORMAL);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   EventSetMillisecondTimer(TimerMilliseconds);

   if(SaveStateOnDisk) LoadState();

   if(SystemState.dailyHighWaterMark == 0)
      SystemState.dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);

   SystemState.tradingEnabled = true;
   SystemState.lastAction = "INIT V9";
   SystemState.totalExposureLots = 0;
   SystemState.isBusy = false;
   SystemState.currentStrategy = ActiveStrategy;
   SystemState.lastTudorPattern = "";
   SystemState.lastTudorSignalStrength = 0;

   if(TestingMode && !SystemState.tradingEnabled) {
      SystemState.tradingEnabled = true;
      if(SaveStateOnDisk) SaveState();
   }

   string symList[];
   int count = StringSplit(ExportSymbols, ',', symList);
   for(int i = 0; i < count; i++) {
      StringTrimLeft(symList[i]); StringTrimRight(symList[i]);
      if(!SymbolSelect(symList[i], true))
         Print("⚠️ Symbole non trouvé: ", symList[i]);
   }

   string modeStr = (EnableAIBridge && EnableNativeStrategy) ? "HYBRID" : (EnableAIBridge ? "AI BRIDGE" : "NATIVE");
   Print("🚀 SENTINEL V9 FUSION INITIALIZED | MODE: ", modeStr);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
   EventKillTimer();
   if(SaveStateOnDisk) SaveState();
   Comment("");
}

//============================ MAIN LOOP ===========================//
void OnTimer() {
   if(SystemState.isBusy) return;
   SystemState.isBusy = true;
   Processing();
   SystemState.isBusy = false;
}

void Processing() {
   CheckRiskEngine();
   SystemState.totalExposureLots = CurrentExposureLots();

   if(SystemState.tradingEnabled) {
      ManagePositions();

      if(EnableNativeStrategy) ScanNativeMarket();
      if(EnableAIBridge)       ScanForCommands();

      ExportTickData();
      ExportM5Bars();
   }

   BroadcastStatus();
   if(EnableHUD) UpdateHUD();
}

//============================ RISK ENGINE (V7) =====================//
void CheckRiskEngine() {
   if(!SystemState.tradingEnabled) return;
   if(TestingMode) return;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > SystemState.dailyHighWaterMark)
      SystemState.dailyHighWaterMark = equity;

   double ddPercent = ((SystemState.dailyHighWaterMark - equity) / SystemState.dailyHighWaterMark) * 100.0;

   if(ddPercent >= MaxDailyDrawdownPercent) {
      CloseAllPositions("Daily DD Limit Hit");
      SystemState.tradingEnabled = false;
      SystemState.lastAction = "🛑 HALTED (DD LIMIT)";
      if(SaveStateOnDisk) SaveState();
      Print("🛑 SENTINEL HALTED: Drawdown ", DoubleToString(ddPercent, 2), "% >= ", DoubleToString(MaxDailyDrawdownPercent, 1), "%");
   }
}

double CurrentExposureLots() {
   double lots = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i))) {
         if(PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
            lots += PositionGetDouble(POSITION_VOLUME);
      }
   }
   return lots;
}

double CurrentExposurePercent() {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity <= 0) return 0;
   return (CurrentExposureLots() / equity) * 100.0;
}

bool CheckSpread(string symbol) {
   if(MaxAllowedSpreadPoints <= 0) return true;
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(point <= 0) return true;
   double spread = (SymbolInfoDouble(symbol, SYMBOL_ASK) - SymbolInfoDouble(symbol, SYMBOL_BID)) / point;
   return (spread <= MaxAllowedSpreadPoints);
}

// Max exposure: V9 style (lots cap = MaxExposurePercent/10)
bool IsExposureLimitReached() {
   double cap = MaxExposurePercent / 10.0;
   return (SystemState.totalExposureLots >= cap);
}

//============================ POSITION MANAGEMENT (V6) ============//
void ManagePositions() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;

      double profit = PositionGetDouble(POSITION_PROFIT);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      string symbol = PositionGetString(POSITION_SYMBOL);
      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double price = (posType == POSITION_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_BID) : SymbolInfoDouble(symbol, SYMBOL_ASK);
      bool modified = false;

      // 1. BREAKEVEN (V6)
      if(EnableAutoBreakeven && profit >= BreakevenTriggerProfit) {
         bool needsBE = false;
         if(posType == POSITION_TYPE_BUY && (currentSL < openPrice - point || currentSL == 0)) needsBE = true;
         else if(posType == POSITION_TYPE_SELL && (currentSL < openPrice - point || currentSL == 0)) needsBE = true;
         if(needsBE) {
            double beSL = openPrice;
            ENUM_ORDER_TYPE oType = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
            if(NormalizeStopLoss(symbol, beSL, price, oType) && trade.PositionModify(ticket, beSL, currentTP)) {
               SystemState.lastAction = "Breakeven " + symbol;
               modified = true;
            }
         }
      }

      // 2. TRAILING STOP (V6)
      if(EnableTrailingStop && TrailingStartPoints > 0 && TrailingStepPoints > 0 && !modified) {
         double distancePoints = MathAbs(price - openPrice) / point;
         if(distancePoints >= TrailingStartPoints) {
            double newSL = 0;
            if(posType == POSITION_TYPE_BUY) {
               newSL = price - TrailingStepPoints * point;
               if(newSL > currentSL && newSL > openPrice && NormalizeStopLoss(symbol, newSL, price, ORDER_TYPE_BUY)) {
                  if(trade.PositionModify(ticket, newSL, currentTP)) {
                     SystemState.lastAction = "Trailing " + symbol;
                  }
               }
            } else {
               newSL = price + TrailingStepPoints * point;
               if((newSL < currentSL || currentSL == 0) && newSL < openPrice && NormalizeStopLoss(symbol, newSL, price, ORDER_TYPE_SELL)) {
                  if(trade.PositionModify(ticket, newSL, currentTP)) {
                     SystemState.lastAction = "Trailing " + symbol;
                  }
               }
            }
         }
      }
   }
}

//============================ BRIDGE COMMANDS ======================//
void ScanForCommands() {
   string filename;
   long handle = FileFindFirst("Command\\*.json", filename);
   if(handle != INVALID_HANDLE) {
      do {
         ProcessCommandFile("Command\\" + filename);
      } while(FileFindNext(handle, filename));
      FileFindClose(handle);
   }
}

void ProcessCommandFile(string path) {
   int h = FileOpen(path, FILE_READ | FILE_BIN);
   if(h == INVALID_HANDLE) return;
   ulong fsize = FileSize(h);
   uchar buffer[];
   ArrayResize(buffer, (int)fsize);
   FileReadArray(h, buffer);
   FileClose(h);
   string jsonStr = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_UTF8);

   string action = ExtractJsonValue(jsonStr, "action");

   if(EnableTudorStrategies && StringFind(action, "TUDOR_") == 0)
      ExecuteTudorTrade(jsonStr);
   else if(action == "TRADE")
      ExecutePythonTrade(jsonStr);
   else if(action == "CLOSE_ALL")
      CloseAllPositions("Panic Button");
   else if(action == "RESET_RISK") {
      SystemState.tradingEnabled = true;
      SystemState.dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
      if(SaveStateOnDisk) SaveState();
      SystemState.lastAction = "RESET_RISK";
   }
   FileDelete(path);
}

//============================ TUDOR TRADE (V8 Compat) ==============//
void ExecuteTudorTrade(string json) {
   if(!SystemState.tradingEnabled) return;
   if(IsExposureLimitReached()) {
      Print("⚠️ Exposition max atteinte. Ordre TUDOR refusé.");
      return;
   }

   string symbol = ExtractJsonValue(json, "symbol");
   if(symbol == "") symbol = TradeSymbol;
   if(!CheckSpread(symbol)) {
      Print("🚫 Spread trop haut: ", symbol);
      return;
   }

   uint savedDev = DEV_POINTS_NORMAL;
   if(StringFind(symbol, "Volatility") >= 0)
      trade.SetDeviationInPoints(DEV_POINTS_VOLATILITY);

   string type = ExtractJsonValue(json, "type");
   double signalStrength = StringToDouble(ExtractJsonValue(json, "signal_strength"));
   string pattern = ExtractJsonValue(json, "pattern");
   double stopLossPips = StringToDouble(ExtractJsonValue(json, "stop_loss_pips"));
   double aiRiskMultiplier = 1.0;
   double aiConfidence = 1.0;
   string aiRiskStr = ExtractJsonValue(json, "ai_risk_multiplier");
   string aiConfStr = ExtractJsonValue(json, "ai_confidence_score");
   if(aiRiskStr != "") aiRiskMultiplier = StringToDouble(aiRiskStr);
   if(aiConfStr != "") aiConfidence = StringToDouble(aiConfStr);
   if(aiConfidence < MinAIConfidence && aiConfStr != "") {
      Print("🛑 Rejet AI: conf=", DoubleToString(aiConfidence, 2), " < ", DoubleToString(MinAIConfidence, 2));
      trade.SetDeviationInPoints(DEV_POINTS_NORMAL);
      return;
   }

   if(!IsTudorPatternValid(pattern, signalStrength)) {
      trade.SetDeviationInPoints(DEV_POINTS_NORMAL);
      return;
   }

   double riskPercent = TudorRiskPercent * MathMax(0.1, MathMin(10.0, aiRiskMultiplier));

   double volume = CalculatePositionSize(symbol, stopLossPips, riskPercent);
   if(volume <= 0) volume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLotSym = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double globalMax = MathMin(maxLotSym, MaxLotSize);
   if(volume > globalMax) volume = globalMax;
   if(StringFind(symbol, "Volatility") >= 0 && volume < 0.5) volume = 0.5;

   SystemState.lastTudorSignalStrength = signalStrength;
   SystemState.lastTudorPattern = pattern;

   double sl = 0, tp = 0;
   double slDistance = 0;
   double entryPrice = (type == "BUY") ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
   if(TakeProfitUSD > 0) tp = CalculateTakeProfitPrice(symbol, volume, type, entryPrice);

   if(stopLossPips > 0) {
      long digits = SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double pointsPerPip = (digits == 3 || digits == 5) ? 10 : 1;
      slDistance = stopLossPips * pointsPerPip * point;
      long stopsLevel = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double minDist = (double)stopsLevel * point;
      if(minDist > 0 && slDistance < minDist) slDistance = minDist;
      double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickSize <= 0) tickSize = point;

      if(type == "BUY") {
         double askPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
         sl = askPrice - slDistance;
         sl = MathFloor(sl / tickSize) * tickSize;
         if(sl >= askPrice) sl = askPrice - minDist;
         if(!NormalizeStopLoss(symbol, sl, askPrice, ORDER_TYPE_BUY)) sl = 0;
      } else if(type == "SELL") {
         double bidPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
         sl = bidPrice + slDistance;
         sl = MathCeil(sl / tickSize) * tickSize;
         if(sl <= bidPrice) sl = bidPrice + minDist;
         if(!NormalizeStopLoss(symbol, sl, bidPrice, ORDER_TYPE_SELL)) sl = 0;
      }
   }

   if(sl == 0 && stopLossPips > 0) {
      Print("🚫 STOP LOSS OBLIGATOIRE: Impossible de normaliser SL. Ordre refusé.");
      trade.SetDeviationInPoints(DEV_POINTS_NORMAL);
      return;
   }
   if(stopLossPips <= 0) {
      Print("🚫 STOP LOSS OBLIGATOIRE: stop_loss_pips manquant ou 0. Ordre refusé.");
      trade.SetDeviationInPoints(DEV_POINTS_NORMAL);
      return;
   }

   bool ok = false;
   string comment = "Aladdin " + pattern;
   if(type == "BUY")
      ok = trade.Buy(volume, symbol, 0, sl, tp, comment);
   else if(type == "SELL")
      ok = trade.Sell(volume, symbol, 0, sl, tp, comment);

   if(!ok && trade.ResultRetcode() == RETCODE_INVALID_STOPS) {
      double slDist2 = slDistance * 1.5;
      ENUM_ORDER_TYPE ot = ORDER_TYPE_BUY;
      if(type == "SELL") ot = ORDER_TYPE_SELL;
      if(type == "BUY") sl = entryPrice - slDist2;
      else sl = entryPrice + slDist2;
      if(NormalizeStopLoss(symbol, sl, entryPrice, ot)) {
         if(type == "BUY") ok = trade.Buy(volume, symbol, 0, sl, tp, comment);
         else ok = trade.Sell(volume, symbol, 0, sl, tp, comment);
      }
      if(!ok) {
         Print("🚫 STOP LOSS OBLIGATOIRE: Broker refuse SL (10016). Ordre ANNULÉ pour protéger le capital.");
         trade.SetDeviationInPoints(DEV_POINTS_NORMAL);
         return;
      }
   }

   if(ok) {
      SystemState.lastAction = "TUDOR_" + type;
      Print("✅ TUDOR: ", type, " ", symbol, " vol=", DoubleToString(volume, 2));
   } else {
      SystemState.lastAction = "TUDOR_FAIL";
      Print("❌ TUDOR échec: ", trade.ResultRetcode());
   }
   trade.SetDeviationInPoints(DEV_POINTS_NORMAL);
}

//============================ PYTHON TRADE (V8 Compat) =============//
void ExecutePythonTrade(string json) {
   if(!SystemState.tradingEnabled) return;
   if(IsExposureLimitReached()) {
      Print("⚠️ Exposition max. Ordre Python refusé.");
      return;
   }

   string symbol = ExtractJsonValue(json, "symbol");
   if(symbol == "") symbol = TradeSymbol;
   if(!CheckSpread(symbol)) {
      Print("🚫 Spread trop haut: ", symbol);
      return;
   }

   string type = ExtractJsonValue(json, "type");
   double volume = StringToDouble(ExtractJsonValue(json, "volume"));
   if(volume <= 0) volume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLotSym = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double globalMax = MathMin(maxLotSym, MaxLotSize);
   if(volume > globalMax) volume = globalMax;

   double sl = 0, tp = 0;
   double entryPrice = (type == "BUY") ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
   if(TakeProfitUSD > 0) tp = CalculateTakeProfitPrice(symbol, volume, type, entryPrice);

   bool ok = false;
   if(type == "BUY")
      ok = trade.Buy(volume, symbol, 0, sl, tp);
   else if(type == "SELL")
      ok = trade.Sell(volume, symbol, 0, sl, tp);

   if(ok) {
      SystemState.lastAction = "PYTHON_" + type;
      Print("✅ Python: ", type, " ", symbol, " vol=", DoubleToString(volume, 2));
   } else {
      SystemState.lastAction = "PYTHON_FAIL";
      Print("❌ Python échec: ", type, " ", symbol);
   }
}

//============================ NATIVE STRATEGY (V9) =================//
void ScanNativeMarket() {
   if(CurrentExposureLots() > 0) return;
   if(IsExposureLimitReached()) return;

   double close[];
   ArraySetAsSeries(close, true);
   if(CopyClose(TradeSymbol, PERIOD_M1, 0, TrendPeriod + 2, close) < TrendPeriod + 1) return;

   double currentPrice = close[0];
   double prevPrice = close[1];
   double sum = 0;
   for(int i = 0; i < TrendPeriod; i++) sum += close[i];
   double ma = sum / TrendPeriod;
   double momentum = currentPrice - prevPrice;
   double slPoints = 400.0;

   if(currentPrice > ma && momentum > MomentumThreshold) {
      ExecuteNativeOrder(TradeSymbol, "BUY", slPoints, "V9 Native Buy");
   } else if(currentPrice < ma && momentum < -MomentumThreshold) {
      ExecuteNativeOrder(TradeSymbol, "SELL", slPoints, "V9 Native Sell");
   }
}

void ExecuteNativeOrder(string symbol, string typeStr, double slPoints, string comment) {
   if(!SystemState.tradingEnabled) return;
   if(!CheckSpread(symbol)) return;
   if(IsExposureLimitReached()) return;

   double stopLossPips = slPoints / ((SymbolInfoInteger(symbol, SYMBOL_DIGITS) == 3 || SymbolInfoInteger(symbol, SYMBOL_DIGITS) == 5) ? 10 : 1);
   double volume = CalculatePositionSize(symbol, stopLossPips);
   if(volume <= 0) volume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   if(volume > MaxLotSize) volume = MaxLotSize;

   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double sl = 0, tp = 0;
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   if(TakeProfitUSD > 0) {
      double entry = (typeStr == "BUY") ? ask : bid;
      tp = CalculateTakeProfitPrice(symbol, volume, typeStr, entry);
   }

   if(slPoints > 0) {
      if(typeStr == "BUY") {
         sl = ask - slPoints * point;
         if(NormalizeStopLoss(symbol, sl, ask, ORDER_TYPE_BUY))
            trade.Buy(volume, symbol, ask, sl, tp, comment);
         else
            trade.Buy(volume, symbol, ask, 0, tp, comment);
      } else {
         sl = bid + slPoints * point;
         if(NormalizeStopLoss(symbol, sl, bid, ORDER_TYPE_SELL))
            trade.Sell(volume, symbol, bid, sl, tp, comment);
         else
            trade.Sell(volume, symbol, bid, 0, tp, comment);
      }
   } else {
      if(typeStr == "BUY") trade.Buy(volume, symbol, ask, 0, tp, comment);
      else trade.Sell(volume, symbol, bid, 0, tp, comment);
   }
   SystemState.lastAction = "NATIVE_" + typeStr;
}

//============================ POSITION SIZE (V7) ===================//
double CalculatePositionSize(string symbol, double stopLossPips, double riskPercentOverride = 0) {
   if(stopLossPips <= 0) return SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double riskPct = (riskPercentOverride > 0) ? riskPercentOverride : MaxRiskPerTradePercent;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * riskPct / 100.0;
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue == 0 || tickSize == 0) return SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);

   long digits = SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double pointsPerPip = (digits == 3 || digits == 5) ? 10 : 1;
   double pointValue = tickValue / tickSize;
   double pipValue = pointValue * pointsPerPip;
   double volume = riskAmount / (stopLossPips * pipValue);

   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLot = MathMin(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX), MaxLotSize);
   volume = MathMax(minLot, MathMin(maxLot, volume));
   volume = MathFloor(volume / step) * step;
   return volume;
}

bool IsTudorPatternValid(string pattern, double strength) {
   return (StringLen(pattern) >= MIN_PATTERN_LENGTH && strength >= 0.6);
}

double CalculateTakeProfitPrice(string symbol, double volume, string type, double entryPrice) {
   if(TakeProfitUSD <= 0 || volume <= 0) return 0;
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0) return 0;
   double priceChange = TakeProfitUSD * tickSize / (tickValue * volume);
   double tp = (type == "BUY") ? entryPrice + priceChange : entryPrice - priceChange;
   if(tickSize > 0) tp = MathRound(tp / tickSize) * tickSize;
   return tp;
}

bool NormalizeStopLoss(string symbol, double &sl, double price, ENUM_ORDER_TYPE orderType) {
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   long stopsLevel = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = stopsLevel * point;
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0) tickSize = point;
   sl = MathRound(sl / tickSize) * tickSize;
   double distance = (orderType == ORDER_TYPE_BUY) ? price - sl : sl - price;
   if(minDist > 0 && distance < minDist - point / 2) {
      if(orderType == ORDER_TYPE_BUY) sl = price - minDist;
      else sl = price + minDist;
      sl = MathRound(sl / tickSize) * tickSize;
   }
   if((orderType == ORDER_TYPE_BUY && sl >= price) || (orderType == ORDER_TYPE_SELL && sl <= price))
      return false;
   return true;
}

//============================ UTILITIES ===========================//
void CloseAllPositions(string reason) {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
         trade.PositionClose(ticket);
   }
   SystemState.lastAction = "CLOSE_ALL: " + reason;
   Print("📴 ", reason);
}

//============================ EXPORTS (Python Bridge) ==============//
void ExportTickData() {
   static datetime lastExport = 0;
   if(TimeCurrent() - lastExport < 2) return;
   lastExport = TimeCurrent();

   string symbols[];
   int count = StringSplit(ExportSymbols, ',', symbols);
   double totalPnL = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
         totalPnL += PositionGetDouble(POSITION_PROFIT);
   }

   string json = "{\"t\":" + IntegerToString((int)lastExport) + ",\"account_pnl\":" + DoubleToString(totalPnL, 2) +
      ",\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) +
      ",\"strategy\":\"" + EnumToString(SystemState.currentStrategy) + "\"" +
      ",\"last_pattern\":\"" + SystemState.lastTudorPattern + "\"" +
      ",\"signal_strength\":" + DoubleToString(SystemState.lastTudorSignalStrength, 2) + ",\"ticks\":{";
   bool first = true;
   for(int i = 0; i < count; i++) {
      StringTrimLeft(symbols[i]); StringTrimRight(symbols[i]);
      if(!SymbolInfoInteger(symbols[i], SYMBOL_SELECT)) continue;
      if(!first) json += ","; first = false;
      json += "\"" + symbols[i] + "\":" + DoubleToString(SymbolInfoDouble(symbols[i], SYMBOL_BID), (int)SymbolInfoInteger(symbols[i], SYMBOL_DIGITS));
   }
   json += "}}";
   int h = FileOpen(tickFileTemp, FILE_WRITE | FILE_ANSI | FILE_TXT);
   if(h != INVALID_HANDLE) {
      FileWriteString(h, json); FileClose(h);
      if(FileIsExist(tickFile)) FileDelete(tickFile);
      FileMove(tickFileTemp, 0, tickFile, 0);
   }
}

void ExportM5Bars() {
   static datetime lastExport = 0;
   if(TimeCurrent() - lastExport < 10) return;
   lastExport = TimeCurrent();

   string symbols[];
   int count = StringSplit(ExportSymbols, ',', symbols);
   string json = "{\"updated\":" + IntegerToString((int)lastExport) + ",\"symbols\":{";
   bool firstSym = true;
   for(int s = 0; s < count; s++) {
      StringTrimLeft(symbols[s]); StringTrimRight(symbols[s]);
      if(!SymbolInfoInteger(symbols[s], SYMBOL_SELECT)) continue;
      MqlRates rates[];
      if(CopyRates(symbols[s], PERIOD_M5, 0, 100, rates) <= 0) continue;
      if(!firstSym) json += ","; firstSym = false;
      json += "\"" + symbols[s] + "\":[";
      int digits = (int)SymbolInfoInteger(symbols[s], SYMBOL_DIGITS);
      for(int i = ArraySize(rates) - 1; i >= 0; i--) {
         if(i < ArraySize(rates) - 1) json += ",";
         json += StringFormat("{\"t\":%d,\"o\":%.*f,\"h\":%.*f,\"l\":%.*f,\"c\":%.*f}",
            (int)rates[i].time, digits, rates[i].open, digits, rates[i].high, digits, rates[i].low, digits, rates[i].close);
      }
      json += "]";
   }
   json += "}}";
   int h = FileOpen(m5BarsFileTemp, FILE_WRITE | FILE_ANSI | FILE_TXT);
   if(h != INVALID_HANDLE) {
      FileWriteString(h, json); FileClose(h);
      if(FileIsExist(m5BarsFile)) FileDelete(m5BarsFile);
      FileMove(m5BarsFileTemp, 0, m5BarsFile, 0);
   }
}

void BroadcastStatus() {
   static datetime lastBroadcast = 0;
   if(TimeCurrent() - lastBroadcast < 1) return;
   lastBroadcast = TimeCurrent();

   string json = "{\"updated\":" + IntegerToString((int)lastBroadcast) +
      ",\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) +
      ",\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) +
      ",\"trading_enabled\":" + (SystemState.tradingEnabled ? "true" : "false") +
      ",\"exposure_percent\":" + DoubleToString(CurrentExposurePercent(), 2) +
      ",\"exposure_lots\":" + DoubleToString(SystemState.totalExposureLots, 2) + ",\"positions\":[";
   int cnt = 0;
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER) {
         if(cnt > 0) json += ",";
         json += StringFormat("{\"ticket\":%d,\"symbol\":\"%s\",\"type\":\"%s\",\"volume\":%.2f,\"profit\":%.2f,\"price\":%.5f}",
            (long)ticket, PositionGetString(POSITION_SYMBOL),
            (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL"),
            PositionGetDouble(POSITION_VOLUME), PositionGetDouble(POSITION_PROFIT), PositionGetDouble(POSITION_PRICE_OPEN));
         cnt++;
      }
   }
   json += "]}";
   int h = FileOpen(statusFile, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE) { FileWriteString(h, json); FileClose(h); }
}

//============================ HUD (V6/V9 FUSION) ==================//
void UpdateHUD() {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double pnl = equity - balance;
   double dd = (SystemState.dailyHighWaterMark > 0) ? ((SystemState.dailyHighWaterMark - equity) / SystemState.dailyHighWaterMark) * 100.0 : 0;

   string modeStr = (EnableAIBridge && EnableNativeStrategy) ? "HYBRID" : (EnableAIBridge ? "AI BRIDGE" : "NATIVE");
   string statusStr = SystemState.tradingEnabled ? "🟢 HUNTING" : "🔴 HALTED";

   string hud = "";
   hud += "═══════════════════════════════════════\n";
   hud += "    SENTINEL V9 FUSION ULTIMATE        \n";
   hud += "═══════════════════════════════════════\n";
   hud += " STATUS:     " + statusStr + "\n";
   hud += " EQUITY:     " + DoubleToString(equity, 2) + " $\n";
   hud += " P&L DAY:    " + DoubleToString(pnl, 2) + " $\n";
   hud += " DD:         " + DoubleToString(dd, 2) + " %\n";
   hud += " EXPOSURE:   " + DoubleToString(SystemState.totalExposureLots, 2) + " Lots\n";
   hud += "---------------------------------------\n";
   hud += " MODE:       " + modeStr + "\n";
   hud += " LAST:       " + SystemState.lastAction + "\n";
   hud += " PATTERN:    " + SystemState.lastTudorPattern + "\n";
   hud += "═══════════════════════════════════════\n";

   Comment(hud);
}

void SaveState() {
   int h = FileOpen(watermarkFile, FILE_WRITE | FILE_BIN);
   if(h != INVALID_HANDLE) {
      FileWriteDouble(h, SystemState.dailyHighWaterMark);
      FileWriteInteger(h, (int)SystemState.tradingEnabled);
      FileWriteInteger(h, (int)SystemState.currentStrategy);
      FileClose(h);
   }
}

void LoadState() {
   int h = FileOpen(watermarkFile, FILE_READ | FILE_BIN);
   if(h != INVALID_HANDLE) {
      SystemState.dailyHighWaterMark = FileReadDouble(h);
      SystemState.tradingEnabled = (bool)FileReadInteger(h);
      SystemState.currentStrategy = (ENUM_TUDOR_STRATEGY)FileReadInteger(h);
      FileClose(h);
   } else {
      SystemState.tradingEnabled = true;
      SystemState.currentStrategy = ActiveStrategy;
   }
}

string ExtractJsonValue(string source, string key) {
   int key_pos = StringFind(source, "\"" + key + "\"");
   if(key_pos == -1) return "";
   int colon_pos = StringFind(source, ":", key_pos);
   if(colon_pos == -1) return "";
   int start = StringFind(source, "\"", colon_pos);
   if(start == -1) {
      start = colon_pos + 1;
      int end_comma = StringFind(source, ",", start);
      int end_brace = StringFind(source, "}", start);
      int end = (end_comma != -1 && end_brace != -1) ? (int)MathMin(end_comma, end_brace) : (end_comma != -1 ? end_comma : end_brace);
      if(end == -1) return "";
      return StringSubstr(source, start, end - start);
   }
   int end = StringFind(source, "\"", start + 1);
   if(end == -1) return "";
   return StringSubstr(source, start + 1, end - start - 1);
}
