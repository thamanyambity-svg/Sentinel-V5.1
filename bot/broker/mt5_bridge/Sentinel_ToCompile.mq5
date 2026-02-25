//+------------------------------------------------------------------+
//|                                            Sentinel_ToCompile.mq5 |
//|                                  Copyright 2026, Ambity Project   |
//|  VERSION 5.53 ALADDIN + DERIV + IFVG + TESTING MODE               |
//|  Compiler manuellement dans MetaEditor                            |
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "5.53"
#property strict

#include <Trade\Trade.mqh>

CTrade trade;

//--- CONSTANTS ---
input long   MAGIC_NUMBER = 65535;

//--- LOGGING LEVELS ---
enum ENUM_LOG_LEVEL {
   S_LOG_ERROR = 0,
   S_LOG_INFO  = 1,
   S_LOG_DEBUG = 2,
};

//--- TUDOR JONES STRATEGY TYPES ---
enum ENUM_TUDOR_STRATEGY {
   TUDOR_REVERSAL = 1,
   TUDOR_MACRO_TREND = 2,
   TUDOR_VOLATILITY_BREAKOUT = 3,
   TUDOR_RISK_PARITY = 4
};

//--- INPUTS ---
input group "=== SYSTEM SETTINGS ==="
input int            TimerSeconds   = 1;
input ENUM_LOG_LEVEL LogLevel       = S_LOG_INFO;

input group "=== TUDOR JONES SETTINGS ==="
input double         TudorRiskPercent      = 2.0;
input bool           EnableTudorStrategies  = true;
input ENUM_TUDOR_STRATEGY ActiveStrategy = TUDOR_REVERSAL;

input group "=== SECURITY & RISK ==="
input bool           TestingMode          = true;   // Désactive Kill Switch daily pour tester
input double         MaxDailyLoss         = 50.00;
input double         MaxDailyDrawdown     = 10.00;
input double         MaxLotSize           = 0.10;

input group "=== PILOT CONFIGURATION ==="
input bool           EnableScalper        = false;
input bool           EnableProfitProtector  = true;

input group "=== ALADDIN AI SETTINGS ==="
input bool           EnableAladdinAI   = true;
input double         MinAIConfidence   = 0.70;

input group "=== DERIV VOLATILITY INDICES ==="
input string         SymbolVol100     = "Volatility 100 Index";   // Deriv Volatility 100
input string         SymbolVol75      = "Volatility 75 Index";    // Deriv Volatility 75 (essayez R_75 si broker)

//--- GLOBAL STATE ---
struct SentinelStateStruct {
   double            dailyHighWaterMark;
   bool              tradingEnabled;
   bool              isBusy;
   datetime          lastErrorNotification;
   ENUM_TUDOR_STRATEGY currentStrategy;
   double            lastTudorSignalStrength;
   string            lastTudorPattern;
};

SentinelStateStruct SystemState;
string watermarkFile = "Sentinel_State.dat";
string tickFile = "ticks_v3.json";
string tickFileTemp = "ticks_v3_temp.json";
string m5BarsFile = "m5_bars.json";
string m5BarsFileTemp = "m5_bars_temp.json";

//--- PROTOTYPES ---
void  Processing();
void  S_Log(ENUM_LOG_LEVEL level, string method, string msg);
bool  CheckTradeResult(int retcode, string comment);
void  ScanForCommands();
void  ExecutePythonTrade(string json);
void  ExportTickData();
void  CheckRiskManagement();
void  LoadState();
void  SaveState();
void  ManageOpenPositions();
void  CloseAllPositions(string reason);
void  ProcessCommandFile(string path);
string ExtractJsonValue(string source, string key);
double CalculateTudorPositionSize(string symbol, double riskPercent, double stopLossPips);
bool   IsTudorPatternValid(string patternType, double signalStrength);
void   LogTudorSignal(ENUM_TUDOR_STRATEGY strategy, string pattern, double strength, string action);
void   ExecuteTudorTrade(string json);
void   BroadcastStatus();
void   ExportM5Bars();

//+------------------------------------------------------------------+
//| INIT                                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MAGIC_NUMBER);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFilling(ORDER_FILLING_IOC);

   EventSetTimer(TimerSeconds);
   LoadState();

   SystemState.isBusy = false;
   SystemState.currentStrategy = ActiveStrategy;
   SystemState.lastTudorSignalStrength = 0;
   SystemState.lastTudorPattern = "";

   if(SystemState.dailyHighWaterMark == 0)
      SystemState.dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);

   // Force Volatility 100 & 75 dans Market Watch
   if(!SymbolSelect(SymbolVol100, true))  Print("⚠️ SymbolVol100 non trouvé: ", SymbolVol100);
   if(!SymbolSelect(SymbolVol75, true))   Print("⚠️ SymbolVol75 non trouvé: ", SymbolVol75, " (essayez R_75 si broker Deriv)");

   // DIAGNOSTIC: où l'EA lit les commandes (à comparer avec MT5_FILES_PATH du bot Python)
   string dataPath = TerminalInfoString(TERMINAL_DATA_PATH);
   Print("📂 EA FILES PATH (copier dans .env MT5_FILES_PATH si différent): ", dataPath + "MQL5\\Files");
   if(TestingMode && !SystemState.tradingEnabled) {
      SystemState.tradingEnabled = true;
      SaveState();
      Print("📂 tradingEnabled: was false -> forced true (TestingMode)");
   } else
      Print("📂 tradingEnabled: ", (SystemState.tradingEnabled ? "true" : "false"));

   Print("🏰 SENTINEL V5.53 ALADDIN + DERIV Volatility + IFVG M5 (TestingMode=" + (TestingMode ? "ON" : "OFF") + "): INITIALIZED");

   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
   EventKillTimer();
   SaveState();
}

//+------------------------------------------------------------------+
//| MAIN TIMER LOOP                                                  |
//+------------------------------------------------------------------+
void OnTimer()
{
   if(SystemState.isBusy) return;
   SystemState.isBusy = true;
   Processing();
   SystemState.isBusy = false;
}

//+------------------------------------------------------------------+
//| SAFE PROCESSING LOGIC                                            |
//+------------------------------------------------------------------+
void Processing()
{
   CheckRiskManagement();
   BroadcastStatus();
   if(SystemState.tradingEnabled) {
      ScanForCommands();
      ExportTickData();
      ExportM5Bars();
      ManageOpenPositions();
   }
}

//+------------------------------------------------------------------+
//| COMMAND HANDLER                                                  |
//+------------------------------------------------------------------+
void ScanForCommands() {
   string filename;
   long handle = FileFindFirst("Command\\*.json", filename);
   int count = 0;
   if(handle != INVALID_HANDLE) {
      do {
         ProcessCommandFile("Command\\" + filename);
         count++;
      } while(FileFindNext(handle, filename));
      FileFindClose(handle);
      if(count > 0 && LogLevel >= S_LOG_INFO)
         Print("📥 Processed ", count, " command(s)");
   }
}

void ProcessCommandFile(string path) {
   int h = FileOpen(path, FILE_READ|FILE_BIN);
   if(h == INVALID_HANDLE) {
      S_Log(S_LOG_ERROR, "ProcessCmd", "Failed to open: " + path);
      return;
   }
   ulong fsize = FileSize(h);
   uchar buffer[];
   ArrayResize(buffer, (int)fsize);
   FileReadArray(h, buffer);
   FileClose(h);

   string json = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_UTF8);
   if(LogLevel >= S_LOG_DEBUG) S_Log(S_LOG_DEBUG, "CMD", "Received: " + json);

   string action = ExtractJsonValue(json, "action");
   if(EnableTudorStrategies && StringFind(action, "TUDOR_") == 0) ExecuteTudorTrade(json);
   else if(action == "TRADE") ExecutePythonTrade(json);
   else if(action == "CLOSE_ALL") CloseAllPositions("Panic Button");
   else if(action == "RESET_RISK") {
      SystemState.tradingEnabled = true;
      SystemState.dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
      SaveState();
      S_Log(S_LOG_INFO, "Risk", "Risk constraints reset.");
   }
   FileDelete(path);
}

//+------------------------------------------------------------------+
//| TUDOR TRADE                                                      |
//+------------------------------------------------------------------+
void ExecuteTudorTrade(string json) {
   string strategyType = ExtractJsonValue(json, "strategy");
   string symbol = ExtractJsonValue(json, "symbol");
   string type = ExtractJsonValue(json, "type");
   double signalStrength = StringToDouble(ExtractJsonValue(json, "signal_strength"));
   string pattern = ExtractJsonValue(json, "pattern");
   double stopLossPips = StringToDouble(ExtractJsonValue(json, "stop_loss_pips"));
   string aiRiskStr = ExtractJsonValue(json, "ai_risk_multiplier");
   string aiConfStr = ExtractJsonValue(json, "ai_confidence_score");

   double aiRiskMultiplier = 1.0;
   double aiConfidence = 1.0;
   if(EnableAladdinAI) {
      if(aiRiskStr != "") aiRiskMultiplier = StringToDouble(aiRiskStr);
      if(aiConfStr != "") aiConfidence = StringToDouble(aiConfStr);
      if(aiConfidence < MinAIConfidence) {
         S_Log(S_LOG_INFO, "AladdinAI", "🛑 Rejected Conf=" + DoubleToString(aiConfidence,2));
         return;
      }
   }

   ENUM_TUDOR_STRATEGY strategy = TUDOR_REVERSAL;
   if(strategyType == "TUDOR_MACRO") strategy = TUDOR_MACRO_TREND;
   else if(strategyType == "TUDOR_VOLATILITY") strategy = TUDOR_VOLATILITY_BREAKOUT;
   else if(strategyType == "TUDOR_RISK_PARITY") strategy = TUDOR_RISK_PARITY;

   if(!IsTudorPatternValid(pattern, signalStrength)) return;

   double currentRiskPercent = TudorRiskPercent;
   if(EnableAladdinAI) {
      currentRiskPercent = TudorRiskPercent * aiRiskMultiplier;
      currentRiskPercent = MathMax(0.1, MathMin(10.0, currentRiskPercent));
   }

   double volume = CalculateTudorPositionSize(symbol, currentRiskPercent, stopLossPips);
   if(StringFind(symbol, "Volatility") >= 0 && volume < 0.5) volume = 0.5;
   // Vol 75: plafonner à 0.5 max (contrat énorme, éviter pertes explosives)
   if(StringFind(symbol, "Volatility 75") >= 0 && volume > 0.5) volume = 0.5;
   LogTudorSignal(strategy, pattern, signalStrength, type);
   SystemState.lastTudorSignalStrength = signalStrength;
   SystemState.lastTudorPattern = pattern;

   double sl = 0, tp = 0;
   if(stopLossPips > 0) {
      long digits = SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double pointsPerPip = (digits == 3 || digits == 5) ? 10 : 1;
      double slDistancePoints = stopLossPips * pointsPerPip * point;
      // retcode 10016 = Invalid stops: respecter la distance min broker (SYMBOL_TRADE_STOPS_LEVEL)
      long stopsLevel = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double minDist = (double)stopsLevel * point;
      if(minDist > 0 && slDistancePoints < minDist) slDistancePoints = minDist;
      // Arrondir le prix SL au step du symbole
      double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickSize <= 0) tickSize = point;
      bool ok = false;
      if(type == "BUY") {
         double askPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
         sl = askPrice - slDistancePoints;
         sl = MathFloor(sl / tickSize) * tickSize;
         if(sl >= askPrice) sl = askPrice - minDist;
         if(sl < askPrice) ok = trade.Buy(volume, symbol, askPrice, sl, tp, "Aladdin " + pattern);
      } else if(type == "SELL") {
         double bidPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
         sl = bidPrice + slDistancePoints;
         sl = MathCeil(sl / tickSize) * tickSize;
         if(sl <= bidPrice) sl = bidPrice + minDist;
         if(sl > bidPrice) ok = trade.Sell(volume, symbol, bidPrice, sl, tp, "Aladdin " + pattern);
      }
      bool usedFallback = false;
      // Vol 75: NE JAMAIS ouvrir sans SL (contrat énorme, pertes >600$)
      bool allowNoSL = (StringFind(symbol, "Volatility 75") < 0);
      if(!ok && trade.ResultRetcode() == 10016 && allowNoSL) {
         // Fallback: ouvrir SANS SL uniquement pour Vol 100 (risque maîtrisé)
         if(type == "BUY") ok = trade.Buy(volume, symbol, SymbolInfoDouble(symbol, SYMBOL_ASK), 0, 0, "Aladdin " + pattern);
         else if(type == "SELL") ok = trade.Sell(volume, symbol, SymbolInfoDouble(symbol, SYMBOL_BID), 0, 0, "Aladdin " + pattern);
         if(ok) { usedFallback = true; Print("✅ Trade sent (sans SL): ", type, " ", symbol, " vol=", volume); }
      } else if(!ok && trade.ResultRetcode() == 10016 && !allowNoSL)
         Print("❌ Vol 75: Refus d'ouvrir sans SL (risque trop élevé)");
      if(!ok) Print("❌ Trade failed: ", type, " ", symbol, " vol=", volume, " retcode=", trade.ResultRetcode(), " ", trade.ResultComment());
      else if(!usedFallback && LogLevel >= S_LOG_INFO) Print("✅ Trade sent: ", type, " ", symbol, " vol=", volume);
   }
}

void ExecutePythonTrade(string json) {
   string symbol = ExtractJsonValue(json, "symbol");
   string type = ExtractJsonValue(json, "type");
   double volume = StringToDouble(ExtractJsonValue(json, "volume"));
   if(volume > MaxLotSize) volume = MaxLotSize;
   if(!SystemState.tradingEnabled) return;
   if(type == "BUY") trade.Buy(volume, symbol, SymbolInfoDouble(symbol, SYMBOL_ASK));
   else if(type == "SELL") trade.Sell(volume, symbol, SymbolInfoDouble(symbol, SYMBOL_BID));
}

double CalculateTudorPositionSize(string symbol, double riskPercent, double stopLossPips) {
   if(stopLossPips <= 0) return 0.01;
   double accountEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = accountEquity * riskPercent / 100.0;
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue == 0 || tickSize == 0) return 0.01;
   long digits = SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double pointsPerPip = (digits == 2 || digits == 3) ? 1 : 10;
   double pointValue = tickValue / tickSize;
   double pipValue = pointValue * pointsPerPip;
   double volume = riskAmount / (stopLossPips * pipValue);
   double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   volume = MathMax(minLot, MathMin(maxLot, volume));
   volume = MathRound(volume / lotStep) * lotStep;
   return volume;
}

bool IsTudorPatternValid(string pattern, double strength) {
   return (StringLen(pattern) >= 3 && strength >= 0.6);
}

void LogTudorSignal(ENUM_TUDOR_STRATEGY strategy, string pattern, double strength, string action) {
   S_Log(S_LOG_INFO, "TudorSignal", "[" + pattern + "] " + action);
}

void ManageOpenPositions() {
   if(!EnableProfitProtector) return;
   for(int i=PositionsTotal()-1; i>=0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i)) && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER) {
         double profit = PositionGetDouble(POSITION_PROFIT);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double sl = PositionGetDouble(POSITION_SL);
         if(profit >= 5.0 && MathAbs(sl - openPrice) > _Point)
            trade.PositionModify(PositionGetInteger(POSITION_TICKET), openPrice, 0);
      }
   }
}

void CheckRiskManagement() {
   if(!SystemState.tradingEnabled) return;
   if(TestingMode) return;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > SystemState.dailyHighWaterMark) SystemState.dailyHighWaterMark = equity;
   double drawdown = SystemState.dailyHighWaterMark - equity;
   if(drawdown > MaxDailyLoss) {
      CloseAllPositions("Hard Stop");
      SystemState.tradingEnabled = false;
      SaveState();
   }
}

void ExportTickData() {
   string symbols[];
   ArrayResize(symbols, 6);
   symbols[0] = SymbolVol100;
   symbols[1] = SymbolVol75;
   symbols[2] = "EURUSD";
   symbols[3] = "GOLD";
   symbols[4] = "BTCUSD";
   symbols[5] = "ETHUSD";

   double totalPnL = 0;
   for(int i=PositionsTotal()-1; i>=0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i)) && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
         totalPnL += PositionGetDouble(POSITION_PROFIT);
   }

   string json = "{\"t\":" + IntegerToString(TimeCurrent()) +
                 ",\"account_pnl\":" + DoubleToString(totalPnL, 2) +
                 ",\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) +
                 ",\"strategy\":\"" + EnumToString(SystemState.currentStrategy) + "\"" +
                 ",\"last_pattern\":\"" + SystemState.lastTudorPattern + "\"" +
                 ",\"signal_strength\":" + DoubleToString(SystemState.lastTudorSignalStrength, 2) +
                 ",\"ticks\":{";
   bool firstTick = true;
   for(int i=0; i<ArraySize(symbols); i++) {
      if(!SymbolInfoInteger(symbols[i], SYMBOL_SELECT)) continue;
      if(!firstTick) json += ",";
      firstTick = false;
      json += "\"" + symbols[i] + "\":" + DoubleToString(SymbolInfoDouble(symbols[i], SYMBOL_BID), (int)SymbolInfoInteger(symbols[i], SYMBOL_DIGITS));
   }
   json += "}}";

   int h = FileOpen(tickFileTemp, FILE_WRITE|FILE_ANSI|FILE_TXT);
   if(h != INVALID_HANDLE) {
      FileWriteString(h, json);
      FileClose(h);
      if(FileIsExist(tickFile) && !FileDelete(tickFile)) return;
      FileMove(tickFileTemp, 0, tickFile, 0);
   }
}

void CloseAllPositions(string reason) {
   for(int i=PositionsTotal()-1; i>=0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
         trade.PositionClose(ticket);
   }
}

void ExportM5Bars() {
   string syms[];
   ArrayResize(syms, 2);
   syms[0] = SymbolVol100;
   syms[1] = SymbolVol75;
   string json = "{\"updated\":" + IntegerToString(TimeCurrent()) + ",\"symbols\":{";
   bool firstSym = true;
   for(int s=0; s<ArraySize(syms); s++) {
      if(!SymbolInfoInteger(syms[s], SYMBOL_SELECT)) continue;
      MqlRates rates[];
      int copied = CopyRates(syms[s], PERIOD_M5, 0, 100, rates);
      if(copied <= 0) continue;
      if(!firstSym) json += ",";
      firstSym = false;
      json += "\"" + syms[s] + "\":[";
      int digits = (int)SymbolInfoInteger(syms[s], SYMBOL_DIGITS);
      for(int i=copied-1; i>=0; i--) {
         if(i < copied-1) json += ",";
         json += StringFormat("{\"t\":%d,\"o\":%.*f,\"h\":%.*f,\"l\":%.*f,\"c\":%.*f}",
             (int)rates[i].time, digits, rates[i].open, digits, rates[i].high,
             digits, rates[i].low, digits, rates[i].close);
      }
      json += "]";
   }
   json += "}}";
   int h = FileOpen(m5BarsFileTemp, FILE_WRITE|FILE_ANSI|FILE_TXT);
   if(h != INVALID_HANDLE) {
      FileWriteString(h, json);
      FileClose(h);
      if(FileIsExist(m5BarsFile)) FileDelete(m5BarsFile);
      FileMove(m5BarsFileTemp, 0, m5BarsFile, 0);
   }
}

void BroadcastStatus() {
   string json = "{\"updated\":" + IntegerToString(TimeCurrent()) +
                 ",\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) +
                 ",\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) +
                 ",\"trading_enabled\":" + (SystemState.tradingEnabled ? "true" : "false") +
                 ",\"positions\":[";
   int count = 0;
   for(int i=0; i<PositionsTotal(); i++) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER) {
         if(count > 0) json += ",";
         json += StringFormat("{\"ticket\":%d,\"symbol\":\"%s\",\"type\":\"%s\",\"volume\":%.2f,\"profit\":%.2f,\"price\":%.5f}",
             (long)ticket, PositionGetString(POSITION_SYMBOL),
             (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? "BUY" : "SELL"),
             PositionGetDouble(POSITION_VOLUME), PositionGetDouble(POSITION_PROFIT), PositionGetDouble(POSITION_PRICE_OPEN));
         count++;
      }
   }
   json += "]}";
   int h = FileOpen("status.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h != INVALID_HANDLE) { FileWriteString(h, json); FileClose(h); }
}

void S_Log(ENUM_LOG_LEVEL level, string method, string msg) {
   if(level <= LogLevel) Print("[" + method + "] " + msg);
}

void SaveState() {
   int h = FileOpen(watermarkFile, FILE_WRITE|FILE_BIN);
   if(h != INVALID_HANDLE) {
      FileWriteDouble(h, SystemState.dailyHighWaterMark);
      FileWriteInteger(h, (int)SystemState.tradingEnabled);
      FileWriteInteger(h, (int)SystemState.currentStrategy);
      FileClose(h);
   }
}

void LoadState() {
   int h = FileOpen(watermarkFile, FILE_READ|FILE_BIN);
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
   int key_pos = StringFind(source, "\"" + key + "\""); if(key_pos == -1) return "";
   int colon_pos = StringFind(source, ":", key_pos); if(colon_pos == -1) return "";
   int start = StringFind(source, "\"", colon_pos);
   if(start == -1) {
      start = colon_pos + 1;
      int end_comma = StringFind(source, ",", start);
      int end_brace = StringFind(source, "}", start);
      int end = (end_comma != -1 && end_brace != -1) ? MathMin(end_comma, end_brace) : (end_comma != -1 ? end_comma : end_brace);
      if(end == -1) return "";
      return StringSubstr(source, start, end - start);
   }
   int end = StringFind(source, "\"", start + 1);
   if(end == -1) return "";
   return StringSubstr(source, start + 1, end - start - 1);
}
