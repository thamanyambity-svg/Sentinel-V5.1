//+------------------------------------------------------------------+
//|                                                Sentinel_v4_7_FIXED.mq5 |
//|                                  Copyright 2026, Ambity Project  |
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "4.73"
#include <Trade\Trade.mqh>

CTrade trade;

//--- Paramètres
input int TimerSeconds = 1;
input bool EnableLogs  = true;
input bool DebugMode   = true;

input double MaxDailyLoss = 20.00;
input double MaxDailyDrawdown = 15.00;
input int MaxConsecutiveLosses = 6;
input int EmergencyCooldownHours = 24;
input int DailyResetHour = 0;
input bool AllowManualOverride = true;

// === OPTIMISATIONS FINALES ===
input group "=== PROFIT OPTIMIZATION SETTINGS ==="
input bool   EnableProfitProtector = true;
input double MinProfitToLock = 0.50;
input double QuickProfitThreshold = 1.00;
input bool   EnableTimeBasedExit = false;
input int    MaxTradeDuration = 300;
input int    TightenAfterSeconds = 600;
input bool   EnableAdaptiveLots = true;
input double MaxLotMultiplier = 1.5;
input double MinLotMultiplier = 0.5;

// === VALIDATION MATHÉMATIQUE ===
input group "=== ENTRY VALIDATION ==="
input bool   EnableEMAFilter = true;     // Activer filtre de tendance EMA
input int    EMA_Fast_Period = 20;       // Période EMA rapide
input int    EMA_Slow_Period = 50;       // Période EMA lente

// Variables de sécurité
double dailyHighWaterMark = 0.0;
double dailyLowWaterMark = 0.0;
datetime lastResetTime = 0;
datetime lastDailyReset = 0;
bool tradingEnabled = true;
string emergencyReason = "";
string watermarkFile = "Sentinel_Watermarks.dat";

// === VARIABLES D'OPTIMISATION ===
double adaptiveLotMultiplier = 1.0;
datetime lastPerformanceCheck = 0;
double referenceBalance = 0.0;

// --- REPORTING STRUCTURES ---
struct TradeReport {
   long ticket;
   string symbol;
   long type;  // Utiliser long au lieu de ENUM_POSITION_TYPE
   double volume;
   double entry_price;
   double exit_price;
   double profit;
   double commission;
   double swap;
   double net_profit;
   datetime entry_time;
   datetime exit_time;
   double used_margin;
   double free_margin_before;
   double free_margin_after;
   double balance_before;
   double balance_after;
   string close_reason; 
};

TradeReport lastTradeReport;

// FORWARD DECLARATIONS
void ExecuteEmergencyStop();
void CancelAllPendingOrders();
void WriteEmergencyStatus();
bool CheckConsecutiveLosses(int maxLosses);
void ScanForCommands();
void ProcessCommandFile(string filepath);
void ExecuteTrade(string json);
void CloseSpecificTrade(string json);
void CloseSpecificTrade(long ticket);
void CloseAllPositions();
void ManageRisk();
void BroadcastStatus();
void GenerateDashboard();
string ExtractJsonValue(string source, string key);
void GenerateTradeReport(ulong ticket, string close_reason);
void GenerateTradeJSONReport();
void UpdateDailySummary();
void AdjustLotSizeBasedOnPerformance();
void OptimizeProfits();
void CheckDailyReset();
void SaveWatermarks();
void LoadWatermarks();
bool ValidateEMAEntry(string symbol, string type);

//+------------------------------------------------------------------+
//| Initialisation                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(TimerSeconds);
   
   // Charger les watermarks depuis un fichier
   LoadWatermarks();
   
   // Initialisation Optimisation
   adaptiveLotMultiplier = 1.0;
   if(EnableAdaptiveLots) referenceBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   lastPerformanceCheck = TimeCurrent();
   
   Print("🏰 SENTINEL V4.7 FIXED Initialisé");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   SaveWatermarks();
}

void OnTimer()
{
   // Vérifier l'arrêt d'urgence
   if(!tradingEnabled) 
   { 
      long cooldownSeconds = (long)EmergencyCooldownHours * 3600L;
      if(TimeCurrent() - lastResetTime > cooldownSeconds)
      {
         tradingEnabled = true;
         emergencyReason = "";
         dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
         dailyLowWaterMark = dailyHighWaterMark;
         Print("🔄 TRADING RE-ENABLED after cooldown period");
      }
      BroadcastStatus();
      GenerateDashboard(); // RESTORED
      return;
   }
   
   // Scanner les commandes
   ScanForCommands();
   
   // ÉTAPE 4 : OPTIMISATIONS (Restaurées)
   if(EnableAdaptiveLots) AdjustLotSizeBasedOnPerformance();
   if(EnableProfitProtector || EnableTimeBasedExit) OptimizeProfits();
   
   // Gestion des risques
   ManageRisk();
   
   // Vérifier les pertes quotidiennes
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   if(currentEquity > dailyHighWaterMark) 
      dailyHighWaterMark = currentEquity;
   
   if(currentEquity < dailyLowWaterMark) 
      dailyLowWaterMark = currentEquity;
   
   double dailyDrawdownVal = dailyHighWaterMark - currentEquity;
   
   if(dailyDrawdownVal > MaxDailyLoss && MaxDailyLoss > 0)
   {
      emergencyReason = "Absolute loss limit exceeded: $" + DoubleToString(dailyDrawdownVal, 2);
      ExecuteEmergencyStop();
      return;
   }
   
   BroadcastStatus();
   GenerateDashboard(); // RESTORED
}

void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
    if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
    {
        long deal_entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
        if(deal_entry == DEAL_ENTRY_OUT)
        {
            ulong ticket = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
            string reason = "MANUAL";
             string comment = HistoryDealGetString(trans.deal, DEAL_COMMENT);
            if (StringFind(comment, "sl") >= 0) reason = "STOP_LOSS";
            if (StringFind(comment, "tp") >= 0) reason = "TAKE_PROFIT";
            if (!tradingEnabled) reason = "EMERGENCY_STOP";
            
            GenerateTradeReport(ticket, reason);
        }
    }
}

void CheckEmergencyStop()
{
   if(!tradingEnabled) 
   { 
      long cooldownSeconds = (long)EmergencyCooldownHours * 3600L;
      if(TimeCurrent() - lastResetTime > cooldownSeconds)
      {
         tradingEnabled = true;
         emergencyReason = "";
         dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
         dailyLowWaterMark = dailyHighWaterMark;
         Print("🔄 TRADING RE-ENABLED after cooldown period");
      }
      return;
   }
   
   CheckDailyReset();
   
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   if(currentEquity > dailyHighWaterMark) {
      dailyHighWaterMark = currentEquity;
      SaveWatermarks();
   }
   
   if(currentEquity < dailyLowWaterMark) {
      dailyLowWaterMark = currentEquity;
      SaveWatermarks();
   }
   
   double dailyDrawdownVal = dailyHighWaterMark - currentEquity;
   
   if(dailyDrawdownVal > MaxDailyLoss && MaxDailyLoss > 0)
   {
      emergencyReason = "Absolute loss limit exceeded: $" + DoubleToString(dailyDrawdownVal, 2);
      ExecuteEmergencyStop();
      return;
   }
   
   if(CheckConsecutiveLosses(MaxConsecutiveLosses))
   {
      emergencyReason = IntegerToString(MaxConsecutiveLosses) + " consecutive losses detected";
      ExecuteEmergencyStop();
      return;
   }
}

void ExecuteEmergencyStop()
{
   Print("🚨 EMERGENCY STOP: " + emergencyReason);
   CloseAllPositions();
   CancelAllPendingOrders();
   tradingEnabled = false;
   lastResetTime = TimeCurrent();
   WriteEmergencyStatus();
}

void CheckDailyReset()
{
   MqlDateTime currentTime, lastResetTimeStruct;
   TimeToStruct(TimeCurrent(), currentTime);
   TimeToStruct(lastDailyReset, lastResetTimeStruct);
   
   if(currentTime.day != lastResetTimeStruct.day)
   {
      if(currentTime.hour >= DailyResetHour)
      {
          dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
          dailyLowWaterMark = dailyHighWaterMark;
          lastDailyReset = TimeCurrent();
          SaveWatermarks();
          Print("📅 Daily reset at " + TimeToString(TimeCurrent()));
      }
   }
}

// === GESTION DES POSITIONS ===
void CloseAllPositions()
{
   int total = PositionsTotal();
   for(int i=total-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0) trade.PositionClose(ticket);
   }
   Print("⚠️ " + IntegerToString(total) + " positions closed");
}

void CloseSpecificTrade(long ticket)
{
   if(ticket > 0) trade.PositionClose(ticket);
}

void CloseSpecificTrade(string json)
{
   long ticket = StringToInteger(ExtractJsonValue(json, "ticket"));
   CloseSpecificTrade(ticket); 
}

//=== GESTION DES COMMANDES ===
void ScanForCommands()
{
   string search_path = "Command\\*.json";
   string filename;
   long search_handle = FileFindFirst(search_path, filename);

   if(search_handle != INVALID_HANDLE)
   {
      do { ProcessCommandFile("Command\\" + filename); }
      while(FileFindNext(search_handle, filename));
      FileFindClose(search_handle);
   }
}

void ProcessCommandFile(string filepath)
{
   int handle = FileOpen(filepath, FILE_READ|FILE_BIN);
   if(handle == INVALID_HANDLE) return;

   uchar buffer[];
   long size = FileSize(handle);
   if (size > 0) FileReadArray(handle, buffer);
   FileClose(handle);

   string json_content = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_UTF8);
   
   // Traiter les commandes
   string action = ExtractJsonValue(json_content, "action");
   
   if (action == "TRADE") 
   {
       ExecuteTrade(json_content);
   }
   else if(StringFind(json_content, "RESET_RISK") >= 0 || action == "RESET_RISK")
   {
      tradingEnabled = true;
      emergencyReason = "";
      dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
      dailyLowWaterMark = dailyHighWaterMark;
      Print("♻️ RISK METRICS RESET");
   }
   else if (action == "EMERGENCY_STOP")
   {
      emergencyReason = "External Command";
      ExecuteEmergencyStop();
   }
   else if (action == "CLOSE") CloseSpecificTrade(json_content);
   else if (action == "CLOSE_ALL") CloseAllPositions();
   
   FileDelete(filepath);
}

void ExecuteTrade(string json)
{
   string symbol = ExtractJsonValue(json, "symbol");
   string type   = ExtractJsonValue(json, "type");
   double baseVolume = StringToDouble(ExtractJsonValue(json, "volume"));
   double volume = baseVolume;
   
   // ADAPTIVE LOTS IMPLEMENTATION
   if(EnableAdaptiveLots) {
       volume = baseVolume * adaptiveLotMultiplier;
       // Clamp to permitted limits
       double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
       double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
       if(volume < minLot) volume = minLot;
       if(volume > maxLot) volume = maxLot;
       
       double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
       if(step > 0) volume = MathRound(volume/step)*step;
   }
   
   // === MINIMUM TRADE VALUE CHECK ($3 USD) ===
   double currentPrice = 0;
   if (type == "BUY") currentPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
   else currentPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
   
   double tradeValue = volume * currentPrice;
   double MIN_TRADE_USD = 3.0;
   
   if(tradeValue < MIN_TRADE_USD)
   {
      Print("❌ TRADE REJECTED: $", DoubleToString(tradeValue, 2), " < minimum $", DoubleToString(MIN_TRADE_USD, 2));
      Print("   Symbol: ", symbol, ", Volume: ", volume, ", Price: ", currentPrice);
      return;
   }
   
   // === VALIDATION EMA TREND ===
   if(EnableEMAFilter)
   {
      if(!ValidateEMAEntry(symbol, type))
      {
         Print("❌ TRADE REJECTED: EMA Trend does not confirm ", type, " direction");
         Print("   Symbol: ", symbol, " | Check EMA(", EMA_Fast_Period, ") vs EMA(", EMA_Slow_Period, ")");
         return;
      }
   }
   
   // Nettoyer le symbole
   StringReplace(symbol, "\"", "");
   
   double price = 0;
   
   if (type == "BUY") 
   {
      price = SymbolInfoDouble(symbol, SYMBOL_ASK);
      if(!trade.Buy(volume, symbol, price, 0, 0, "Sentinel"))
         Print("❌ BUY ERROR: ", trade.ResultRetcodeDescription());
      else
         Print("✅ BUY SUCCESS: ", symbol, " | $", DoubleToString(tradeValue, 2));
   }
   else if (type == "SELL") 
   {
      price = SymbolInfoDouble(symbol, SYMBOL_BID);
      if(!trade.Sell(volume, symbol, price, 0, 0, "Sentinel"))
         Print("❌ SELL ERROR: ", trade.ResultRetcodeDescription());
      else
         Print("✅ SELL SUCCESS: ", symbol, " | $", DoubleToString(tradeValue, 2));
   }
}

//+------------------------------------------------------------------+
//| Broadcast Status                                                 |
//+------------------------------------------------------------------+
void BroadcastStatus()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   string json = "{ \"updated\": " + IntegerToString((int)TimeCurrent()) + 
                 ", \"balance\": " + DoubleToString(balance, 2) + 
                 ", \"equity\": " + DoubleToString(equity, 2) + 
                 ", \"trading_enabled\": " + (tradingEnabled ? "true" : "false") +
                 ", \"emergency_reason\": \"" + emergencyReason + "\" }";
   
   int handle = FileOpen("status.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle != INVALID_HANDLE) 
   { 
      FileWrite(handle, json); 
      FileClose(handle); 
   }
}

void WriteEmergencyStatus()
{
   int handle = FileOpen("status.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle != INVALID_HANDLE)
   {
      string json = "{ \"emergency\": true, \"reason\": \"" + emergencyReason + "\", \"trading_enabled\": false }";
      FileWrite(handle, json);
      FileClose(handle);
   }
}

void GenerateDashboard()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   int positions = PositionsTotal();
   
   string html = "<!DOCTYPE html><html><head><title>Sentinel Dashboard</title>";
   html += "<meta http-equiv='refresh' content='5'><style>body{font-family:sans-serif;background:#0f172a;color:#f1f5f9;padding:20px}table{width:100%;border-collapse:collapse}th,td{padding:8px;border-bottom:1px solid #333}.profit{color:#10b981}.loss{color:#ef4444}</style></head><body>";
   html += "<h1>🏰 SENTINEL V4.7 FIXED</h1>";
   html += "<p>Balance: $" + DoubleToString(balance, 2) + " | Equity: $" + DoubleToString(equity, 2) + "</p>";
   
   if(positions > 0)
   {
      html += "<table><tr><th>Symbol</th><th>Type</th><th>Vol</th><th>Profit</th></tr>";
      for(int i=0; i<positions; i++)
      {
          ulong ticket = PositionGetTicket(i);
          if(ticket > 0)
          {
             string type = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? "BUY" : "SELL";
             double profit = PositionGetDouble(POSITION_PROFIT);
             html += "<tr><td>"+PositionGetString(POSITION_SYMBOL)+"</td><td>"+type+"</td><td>"+DoubleToString(PositionGetDouble(POSITION_VOLUME),2)+"</td><td class='"+(profit>=0?"profit":"loss")+"'>$"+DoubleToString(profit,2)+"</td></tr>";
          }
      }
      html += "</table>";
   }
   else html += "<p>No active positions.</p>";
   html += "</body></html>";
   
   int handle = FileOpen("dashboard.html", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle != INVALID_HANDLE) { FileWrite(handle, html); FileClose(handle); }
}

void GenerateTradeReport(ulong ticket, string close_reason)
{
   if(!HistorySelectByPosition(ticket)) return;
   
   // Simplification pour rapport JSON rapide
   string json = "{";
   json += "\"event_type\": \"TRADE_CLOSED\",";
   json += "\"ticket\": " + IntegerToString(ticket) + ",";
   json += "\"reason\": \"" + close_reason + "\",";
   json += "\"timestamp\": " + IntegerToString((int)TimeCurrent());
   json += "}";
   
   string filename = "trade_report_" + IntegerToString(ticket) + ".json";
   int handle = FileOpen(filename, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle != INVALID_HANDLE) { FileWrite(handle, json); FileClose(handle); }
   
   UpdateDailySummary();
}

void GenerateTradeJSONReport()
{
   // Helper function not strictly needed if GenerateTradeReport does the work directly
}

void UpdateDailySummary()
{
   static int dailyTradesCount = 0;
   static double dailyProfitTotal = 0;
   dailyTradesCount++;
   // Note: In simplified version, we just print
   Print("📈 Daily Stats: Trades=", dailyTradesCount, " Profit=$", DoubleToString(dailyProfitTotal, 2));
}

// === STEP 3: OPTIMISATIONS FINANCIÈRES ===

void AdjustLotSizeBasedOnPerformance()
{
    static datetime lastCheck = 0;
    if(TimeCurrent() - lastCheck < 3600) return; // Check hourly
    
    double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    if(referenceBalance == 0.0) referenceBalance = currentBalance;
    
    double ratio = currentBalance / referenceBalance;
    
    if(ratio < 0.95) 
    {
        adaptiveLotMultiplier = MathMax(MinLotMultiplier, 0.7);
    }
    else if(ratio > 1.05) 
    {
        adaptiveLotMultiplier = MathMin(MaxLotMultiplier, 1.1);
    }
    else adaptiveLotMultiplier = 1.0;
    
    lastCheck = TimeCurrent();
    
    // Reset reference daily
    if(TimeCurrent() - lastPerformanceCheck > 86400)
    {
        referenceBalance = currentBalance;
        lastPerformanceCheck = TimeCurrent();
    }
}

void OptimizeProfits()
{
    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket <= 0) continue;
        
        double profit = PositionGetDouble(POSITION_PROFIT);
        double sl = PositionGetDouble(POSITION_SL);
        datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
        int duration = (int)(TimeCurrent() - openTime);
        
        // Profit Protector
        if(EnableProfitProtector && profit >= MinProfitToLock && sl == 0) // Only if no SL yet
        {
            double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            long type = PositionGetInteger(POSITION_TYPE);
            
            double newSL = openPrice; // Breakeven
            
            double currentTP = PositionGetDouble(POSITION_TP);
            
            trade.PositionModify(ticket, newSL, currentTP);
            Print("🛡️ PROFIT PROTECTOR: Secured trade #", ticket);
        }
        
        // Time Exit (Optional)
        if(EnableTimeBasedExit && duration > MaxTradeDuration && profit > 0)
        {
             Print("⏰ TIME EXIT: Closing trade #", ticket, " after ", duration, "s");
             trade.PositionClose(ticket);
        }
    }
}

void ManageRisk()
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      
      string symbol = PositionGetString(POSITION_SYMBOL);
      long type = PositionGetInteger(POSITION_TYPE);
      double sl = PositionGetDouble(POSITION_SL);
      double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
      
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double ropeLength = 300 * point; // 300 points
      
      double newSl = 0;
      
      if(type == POSITION_TYPE_BUY)
      {
         newSl = currentPrice - ropeLength;
         if(newSl > sl || sl == 0)
         {
            trade.PositionModify(ticket, newSl, PositionGetDouble(POSITION_TP));
         }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         newSl = currentPrice + ropeLength;
         if(newSl < sl || sl == 0)
         {
            trade.PositionModify(ticket, newSl, PositionGetDouble(POSITION_TP));
         }
      }
   }
}

void SaveWatermarks()
{
   int handle = FileOpen(watermarkFile, FILE_WRITE | FILE_BIN);
   if(handle != INVALID_HANDLE)
   {
      FileWriteDouble(handle, dailyHighWaterMark);
      FileWriteDouble(handle, dailyLowWaterMark);
      FileWriteLong(handle, lastResetTime);
      FileWriteLong(handle, lastDailyReset);
      FileClose(handle);
   }
}

void LoadWatermarks()
{
   int handle = FileOpen(watermarkFile, FILE_READ | FILE_BIN);
   if(handle != INVALID_HANDLE)
   {
      dailyHighWaterMark = FileReadDouble(handle);
      dailyLowWaterMark = FileReadDouble(handle);
      lastResetTime = (datetime)FileReadLong(handle);
      lastDailyReset = (datetime)FileReadLong(handle);
      FileClose(handle);
   }
   else
   {
      dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
      dailyLowWaterMark = dailyHighWaterMark;
      lastResetTime = TimeCurrent();
      lastDailyReset = TimeCurrent();
   }
}

string ExtractJsonValue(string source, string key)
{
   int key_pos = StringFind(source, "\"" + key + "\"");
   if(key_pos == -1) return "";
   
   int colon_pos = StringFind(source, ":", key_pos);
   if(colon_pos == -1) return "";
   
   int start = -1;
   bool is_string = false;
   
   // PROTECTION: Vérification des limites
   int sourceLen = StringLen(source);
   for(int i = colon_pos + 1; i < sourceLen; i++)
   {
       ushort c = StringGetCharacter(source, i);
       if(c == ' ' || c == '\t' || c == '\n' || c == '\r') continue;
       if(c == '\"') { start = i + 1; is_string = true; break; } 
       if((c >= '0' && c <= '9') || c == '-' || c == '.') { start = i; break; } 
       if(c == 't' || c == 'f') { start = i; break; } 
       if(c == '}' || c == ']') return ""; 
   }
   
   if(start == -1) return "";
   
   string result = "";
   
   if(is_string)
   {
       for(int i = start; i < sourceLen; i++) {
           ushort c = StringGetCharacter(source, i);
           if(c == '\"') break; 
           result += StringFormat("%c", c);
       }
   }
   else
   {
       for(int i = start; i < sourceLen; i++) {
           ushort c = StringGetCharacter(source, i);
           if(c == ',' || c == '}' || c == ']' || c == ' ' || c == '\n' || c == '\r') break;
           result += StringFormat("%c", c);
       }
   }
   return result;
}

// === VALIDATION MATHÉMATIQUE : EMA TREND FILTER ===

bool ValidateEMAEntry(string symbol, string type)
{
   // Calculate EMA Fast and EMA Slow on current timeframe
   double ema_fast = iMA(symbol, PERIOD_CURRENT, EMA_Fast_Period, 0, MODE_EMA, PRICE_CLOSE);
   double ema_slow = iMA(symbol, PERIOD_CURRENT, EMA_Slow_Period, 0, MODE_EMA, PRICE_CLOSE);
   
   if(ema_fast == 0 || ema_slow == 0)
   {
      Print("⚠️ EMA Calculation Error for ", symbol);
      return true; // Allow trade if indicator fails (safety)
   }
   
   // Get current values
   double ema_fast_values[], ema_slow_values[];
   ArraySetAsSeries(ema_fast_values, true);
   ArraySetAsSeries(ema_slow_values, true);
   
   if(CopyBuffer(ema_fast, 0, 0, 1, ema_fast_values) <= 0 ||
      CopyBuffer(ema_slow, 0, 0, 1, ema_slow_values) <= 0)
   {
      Print("⚠️ Failed to copy EMA buffers for ", symbol);
      return true; // Allow trade if data unavailable
   }
   
   double current_ema_fast = ema_fast_values[0];
   double current_ema_slow = ema_slow_values[0];
   
   // BUY: Require uptrend (EMA_fast > EMA_slow)
   if(type == "BUY")
   {
      if(current_ema_fast > current_ema_slow)
      {
         Print("✅ EMA Trend CONFIRMED for BUY (EMA", EMA_Fast_Period, "=", current_ema_fast, " > EMA", EMA_Slow_Period, "=", current_ema_slow, ")");
         return true;
      }
      else
      {
         Print("⚠️ EMA Trend UNFAVORABLE for BUY (EMA", EMA_Fast_Period, "=", current_ema_fast, " <= EMA", EMA_Slow_Period, "=", current_ema_slow, ")");
         return false;
      }
   }
   // SELL: Require downtrend (EMA_fast < EMA_slow)
   else if(type == "SELL")
   {
      if(current_ema_fast < current_ema_slow)
      {
         Print("✅ EMA Trend CONFIRMED for SELL (EMA", EMA_Fast_Period, "=", current_ema_fast, " < EMA", EMA_Slow_Period, "=", current_ema_slow, ")");
         return true;
      }
      else
      {
         Print("⚠️ EMA Trend UNFAVORABLE for SELL (EMA", EMA_Fast_Period, "=", current_ema_fast, " >= EMA", EMA_Slow_Period, "=", current_ema_slow, ")");
         return false;
      }
   }
   
   return true; // Default allow if type unknown
}

// === HELPER FUNCTIONS (MISSING) ===

void CancelAllPendingOrders()
{
   for(int i = OrdersTotal()-1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0) trade.OrderDelete(ticket);
   }
}

bool CheckConsecutiveLosses(int maxLosses)
{
   int consecutiveLosses = 0;
   HistorySelect(0, TimeCurrent());
   int totalHistory = HistoryDealsTotal();
   
   for(int i = totalHistory-1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long dealTime = HistoryDealGetInteger(ticket, DEAL_TIME);
         if (dealTime < lastResetTime) break;
         
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if (entry == DEAL_ENTRY_OUT)
         { 
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            if (profit < -0.01) 
            {
               consecutiveLosses++;
               if(consecutiveLosses >= maxLosses) 
               {
                  Print("📉 Consecutive losses: " + IntegerToString(consecutiveLosses));
                  return true;
               }
            }
            else if (profit > 0.00) return false; // Win breaks chain
         }
      }
      if (totalHistory - i > 20) break; // Check only last 20 trades
   }
   return false;
}
