//+------------------------------------------------------------------+
//|                                                Sentinel_v4_7.mq5 |
//|                                  Copyright 2026, Ambity Project  |
//|                                       2-WAY SYNC (Read & Write)  |
//|                                    DEBUG & ROBUST JSON PARSER    |
//|                                    FULL RISK MANAGEMENT RESTORED |
//|                                    AUTO-RESET DEADLOCK FIXED     |
//|                                    INSTITUTIONAL REPORTING (NEW) |
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "4.70"
#include <Trade\Trade.mqh>

CTrade trade;

//--- Paramètres
input int TimerSeconds = 1;               // Fréquence de vérification (secondes)
input bool EnableLogs  = true;            // Logs détaillés
input bool DebugMode   = true;            // Debug Mode (Print Raw JSON)

//=== PARAMÈTRES DE SÉCURITÉ ===
input double MaxDailyLoss = 20.00;        // Limite Perte Jour ($20 sur $100)
input double MaxDailyDrawdown = 15.00;    // Drawdown journalier max (15%)
input int MaxConsecutiveLosses = 6;       // Stop après 6 défaites (Mode Observation)
input int EmergencyCooldownHours = 24;    // Désactivation après arrêt
input int DailyResetHour = 0;             // Heure de réinitialisation quotidienne (0-23)
input bool AllowManualOverride = true;    // Permettre reprise manuelle

// === OPTIMISATIONS FINALES (SENTINEL V4.8 - PROFIT MAXIMIZATION) ===
input group "=== PROFIT OPTIMIZATION SETTINGS ==="
input bool   EnableProfitProtector = true;     // Verrouiller automatiquement les petits gains
input double MinProfitToLock = 0.50;           // Profit minimum à garantir ($)
input double QuickProfitThreshold = 1.00;      // Seuil pour verrouillage agressif ($)
input bool   EnableTimeBasedExit = true;       // Fermer les trades stagnants
input int    MaxTradeDuration = 300;           // Durée max d'un trade (secondes)
input int    TightenAfterSeconds = 600;        // Resserrer SL après (secondes)
input bool   EnableAdaptiveLots = true;        // Ajuster taille selon performance
input double MaxLotMultiplier = 1.5;           // Multiplicateur max (150%)
input double MinLotMultiplier = 0.5;           // Multiplicateur min (50%)

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

// --- REPORTING STRUCTURES ---
struct TradeReport {
   long ticket;
   string symbol;
   ENUM_POSITION_TYPE type;
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

struct DailySummary {
   datetime date;
   int total_trades;
   int winning_trades;
   int losing_trades;
   double total_profit;
   double total_loss;
   double net_profit;
   double win_rate;
   double avg_win;
   double avg_loss;
   double profit_factor;
   double largest_win;
   double largest_loss;
};

TradeReport lastTradeReport;
DailySummary currentDailySummary;

//--- Function Prototypes
void LoadWatermarks();
void SaveWatermarks();
void CheckEmergencyStop();
void CheckDailyReset();
void ExecuteEmergencyStop();
void CancelAllPendingOrders();
void WriteEmergencyStatus();
bool CheckConsecutiveLosses(int maxLosses);
void ScanForCommands();
void ProcessCommandFile(string filepath);
void ExecuteTrade(string json);
void CloseSpecificTrade(string json);
void CloseAllPositions();
void ManageRisk();
void BroadcastStatus();
void GenerateDashboard();
string ExtractJsonValue(string source, string key);
// Reporting
void GenerateTradeReport(ulong ticket, string close_reason);
void GenerateTradeJSONReport();
void UpdateDailySummary();
void AdjustLotSizeBasedOnPerformance();
void OptimizeProfits();

//+------------------------------------------------------------------+
//| Initialisation                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(TimerSeconds);
   LoadWatermarks();
   Print("🏰 SENTINEL V4.7: REPORTING ENGINE ACTIVE");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   SaveWatermarks();
   FileDelete("status.json");
   Print("⚔️ SENTINEL: Arrêt.");
}

void OnTimer()
{
   CheckEmergencyStop();
   
   // FIX DEADLOCK: Always scan for commands (like RESET_RISK) even if stopped
   ScanForCommands();
   
   if(!tradingEnabled) 
   { 
      BroadcastStatus(); 
      GenerateDashboard(); 
      return; 
   }
   
   ManageRisk();
   
   // V4.8 OPTIMIZATIONS
   AdjustLotSizeBasedOnPerformance();
   OptimizeProfits();
   
   BroadcastStatus();
   GenerateDashboard();
}

void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
    // Detect Closed Trade (Deal Entry Out)
    if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
    {
        long deal_entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
        if(deal_entry == DEAL_ENTRY_OUT)
        {
            ulong ticket = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
            string symbol = HistoryDealGetString(trans.deal, DEAL_SYMBOL);
            double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
            Print("📊 TRADE CLOSED: Ticket #", ticket, " Symbol: ", symbol, " Profit: ", profit);
            
            // Determine reason (approximate)
            string reason = "MANUAL"; 
            string comment = HistoryDealGetString(trans.deal, DEAL_COMMENT);
            if (StringFind(comment, "sl") >= 0) reason = "STOP_LOSS";
            if (StringFind(comment, "tp") >= 0) reason = "TAKE_PROFIT";
            if (!tradingEnabled) reason = "EMERGENCY_STOP";
            
            GenerateTradeReport(ticket, reason);
        }
    }
}

//=== FONCTION D'ARRÊT D'URGENCE RENFORCÉE ===
void CheckEmergencyStop()
{
   if(!tradingEnabled)
   {
      if(TimeCurrent() - lastResetTime > EmergencyCooldownHours * 3600)
      {
         tradingEnabled = true;
         emergencyReason = "";
         dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
         dailyLowWaterMark = dailyHighWaterMark;
         SaveWatermarks();
         Print("🔄 TRADING RE-ENABLED after cooldown period");
      }
      return;
   }
   
   CheckDailyReset();
   
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   if(currentEquity > dailyHighWaterMark) 
   {
      dailyHighWaterMark = currentEquity;
      SaveWatermarks();
   }
   
   if(currentEquity < dailyLowWaterMark) 
   {
      dailyLowWaterMark = currentEquity;
      SaveWatermarks();
   }
   
   double dailyDrawdownVal = dailyHighWaterMark - currentEquity;
   double dailyDrawdownPct = 0.0;
   
   if(dailyHighWaterMark > 0.0000001) 
   {
      dailyDrawdownPct = ((dailyHighWaterMark - currentEquity) / dailyHighWaterMark) * 100;
   }
   
   if(dailyDrawdownVal > MaxDailyLoss && MaxDailyLoss > 0)
   {
      emergencyReason = "Absolute loss limit exceeded: $" + DoubleToString(dailyDrawdownVal, 2);
      ExecuteEmergencyStop();
      return;
   }
   
   if(dailyDrawdownPct > MaxDailyDrawdown && MaxDailyDrawdown > 0)
   {
      emergencyReason = "Daily drawdown limit exceeded: " + DoubleToString(dailyDrawdownPct, 1) + "%";
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

void CheckDailyReset()
{
   if(TimeCurrent() - lastDailyReset >= 86400) // 24h reset
   {
       dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
       dailyLowWaterMark = dailyHighWaterMark;
       lastDailyReset = TimeCurrent();
       SaveWatermarks();
       Print("📅 Daily reset (24h elapsed) at " + TimeToString(TimeCurrent()));
   }
}

void ExecuteEmergencyStop()
{
   Print("🚨🚨🚨 EMERGENCY STOP TRIGGERED! 🚨🚨🚨");
   Print("REASON: " + emergencyReason);
   CloseAllPositions();
   CancelAllPendingOrders();
   tradingEnabled = false;
   lastResetTime = TimeCurrent();
   WriteEmergencyStatus();
   GenerateDashboard();
   Print("⚠️ TRADING DISABLED until " + TimeToString(lastResetTime + EmergencyCooldownHours*3600));
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
      
      Print("💾 Watermarks loaded: High=$" + DoubleToString(dailyHighWaterMark, 2));
   }
   else
   {
      dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
      dailyLowWaterMark = dailyHighWaterMark;
      lastResetTime = TimeCurrent();
      lastDailyReset = TimeCurrent();
      Print("💾 New watermarks initialized");
   }
}

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
      if (totalHistory - i > 20) break; 
   }
   return false;
}

//=== GESTION DES COMMANDES (ROBUST - READ FIX + DEADLOCK FIX) ===
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
   // [FIX] BINARY READ for Wine/Mac Compatibility
   int handle = FileOpen(filepath, FILE_READ|FILE_BIN);
   
   if(handle == INVALID_HANDLE) 
   {
       Print("❌ FAILED TO OPEN FILE: ", filepath);
       return;
   }

   uchar buffer[];
   long size = FileSize(handle);
   if (size > 0) FileReadArray(handle, buffer);
   FileClose(handle);

   // Convert raw bytes to string (Try UTF-8 first)
   string json_content = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_UTF8);
   
   if (StringLen(json_content) == 0 && size > 0)
   {
       json_content = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_ACP); // ANSI Fallback
   }

   if (EnableLogs || DebugMode) Print("📩 RAW CONTENT: ", json_content);

   string action = ExtractJsonValue(json_content, "action");
   if (DebugMode) Print("🔍 PARSED ACTION: [", action, "]");
   
   if (action == "TRADE") 
   {
       if(tradingEnabled) ExecuteTrade(json_content);
       else Print("⛔ Ignored TRADE: Bot is in Emergency Stop.");
   }
   else if (action == "CLOSE") CloseSpecificTrade(json_content);
   else if (action == "CLOSE_ALL") CloseAllPositions();
   else if (action == "EMERGENCY_STOP") ExecuteEmergencyStop();
   else if (action == "RESET_RISK") { 
       tradingEnabled = true; 
       emergencyReason = ""; 
       dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY); 
       dailyLowWaterMark = dailyHighWaterMark;
       SaveWatermarks();
       Print("♻️ RISK METRICS RESET by Command"); 
   }
   else if (action == "RESUME_TRADING") { tradingEnabled=true; Print("🔄 RESUMED"); }
   else if (action == "STATUS") { BroadcastStatus(); }
   else Print("⚠️ UNKNOWN ACTION: ", action);
      
   // Retry Deletion Logic (Fixes File Locking on Wine)
   int attempts = 0;
   while(!FileDelete(filepath) && attempts < 5)
   {
       Sleep(100);
       attempts++;
   }
   
   if(attempts >= 5) 
   {
       Print("❌ DEADLOCK: Could not delete ", filepath, " - Renaming to .err");
       string errPath = filepath + ".err";
       FileMove(filepath, 0, errPath, FILE_REWRITE);
   }
   else if(attempts > 0)
   {
       Print("⚠️ Cleaned up ", filepath, " after ", attempts, " retries.");
   }
}

void ExecuteTrade(string json)
{
   string symbol = ExtractJsonValue(json, "symbol");
   string type   = ExtractJsonValue(json, "type");
   double baseVolume = StringToDouble(ExtractJsonValue(json, "volume"));
   double volume = baseVolume;
   
   if(EnableAdaptiveLots) {
       volume = baseVolume * adaptiveLotMultiplier;
       // Clamp to permitted limits
       if(volume < SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN)) volume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
       if(volume > SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX)) volume = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
       
       double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
       if(step > 0) volume = MathRound(volume/step)*step;
   }
   
   double sl     = StringToDouble(ExtractJsonValue(json, "sl"));
   double tp     = StringToDouble(ExtractJsonValue(json, "tp"));
   string comment = ExtractJsonValue(json, "comment");
   
   if (StringReplace(symbol, "\"", "") < 0) Print("StringReplace warning fix");
   
   if (DebugMode) Print("🚀 EXEC: ", type, " ", volume, " ", symbol, " SL:", sl, " TP:", tp);

   double price = 0.0;
   
   if(!SymbolInfoDouble(symbol, SYMBOL_BID, price))
   {
       int err = GetLastError();
       if (err == ERR_UNKNOWN_SYMBOL) Print("❌ SYMBOL ERROR: ", symbol, " does not exist in Market Watch.");
       else Print("❌ SYMBOL ERROR: ", symbol, " not found or no tick. Err:", err);
       return;
   }
   
   if (type == "BUY") 
   {
      price = SymbolInfoDouble(symbol, SYMBOL_ASK);
      if(!trade.Buy(volume, symbol, price, sl, tp, comment))
         Print("❌ BUY ERROR: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
      else
         Print("✅ BUY SUCCESS: #", trade.ResultOrder());
   }
   else if (type == "SELL") 
   {
      price = SymbolInfoDouble(symbol, SYMBOL_BID);
      if(!trade.Sell(volume, symbol, price, sl, tp, comment))
         Print("❌ SELL ERROR: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
      else
         Print("✅ SELL SUCCESS: #", trade.ResultOrder());
   }
}

void CloseSpecificTrade(string json)
{
   long ticket = StringToInteger(ExtractJsonValue(json, "ticket"));
   if (ticket > 0) trade.PositionClose(ticket);
}

void CloseAllPositions()
{
   for(int i=PositionsTotal()-1; i>=0; i--) trade.PositionClose(PositionGetTicket(i));
   Print("⚠️ CLOSE ALL");
}

string ExtractJsonValue(string source, string key)
{
   int key_pos = StringFind(source, "\"" + key + "\"");
   if(key_pos == -1) return "";
   
   int colon_pos = StringFind(source, ":", key_pos);
   if(colon_pos == -1) return "";
   
   int start = -1;
   bool is_string = false;
   
   for(int i = colon_pos + 1; i < StringLen(source); i++)
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
       for(int i = start; i < StringLen(source); i++) {
           ushort c = StringGetCharacter(source, i);
           if(c == '\"') break; 
           result += StringFormat("%c", c);
       }
   }
   else
   {
       for(int i = start; i < StringLen(source); i++) {
           ushort c = StringGetCharacter(source, i);
           if(c == ',' || c == '}' || c == ']' || c == ' ' || c == '\n' || c == '\r') break;
           result += StringFormat("%c", c);
       }
   }
   return result;
}

//=== GESTION DU RISQUE (LE GRIMPEUR) ===
void ManageRisk()
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      
      long type = PositionGetInteger(POSITION_TYPE);
      double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      string symbol = PositionGetString(POSITION_SYMBOL);

      double symPoint = SymbolInfoDouble(symbol, SYMBOL_POINT);
      if(symPoint == 0) continue; 

      double Rope_Length = 300 * symPoint;

      double new_sl = 0.0;
      bool update_needed = false;
      
      if(type == POSITION_TYPE_BUY)
      {
         double potential_sl = current_price - Rope_Length;
         if(potential_sl > sl || sl == 0) { new_sl = potential_sl; update_needed = true; }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double potential_sl = current_price + Rope_Length;
         if(potential_sl < sl || sl == 0) { new_sl = potential_sl; update_needed = true; }
      }
        
      if(update_needed)
      {
         double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
         if (tick_size > 0)
         {
             new_sl = NormalizeDouble(MathRound(new_sl/tick_size)*tick_size, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS));
             if (MathAbs(new_sl - sl) > symPoint) 
             {
                 trade.PositionModify(ticket, new_sl, tp);
             }
         }
      }
   }
}

void BroadcastStatus()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   string json = "{ \"updated\": " + IntegerToString(TimeCurrent()) + 
                 ", \"balance\": " + DoubleToString(balance, 2) + 
                 ", \"equity\": " + DoubleToString(equity, 2) + 
                 ", \"trading_enabled\": " + (tradingEnabled ? "true" : "false") +
                 ", \"emergency_reason\": \"" + emergencyReason + "\"" +
                 ", \"positions\": [";
   
   int total = PositionsTotal();
   int count = 0;
   for(int i=0; i<total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0)
      {
         if(count > 0) json += ",";
         json += StringFormat("{\"ticket\": %d, \"symbol\": \"%s\", \"vol\": %.2f, \"profit\": %.2f, \"price\": %.5f}", 
                              ticket, PositionGetString(POSITION_SYMBOL), PositionGetDouble(POSITION_VOLUME), PositionGetDouble(POSITION_PROFIT), PositionGetDouble(POSITION_PRICE_OPEN));
         count++;
      }
   }
   json += "] }";
   
   int handle = FileOpen("status.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle != INVALID_HANDLE) { FileWrite(handle, json); FileClose(handle); }
}

void GenerateDashboard()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double freeMargin = AccountInfoDouble(ACCOUNT_FREEMARGIN);
   int positions = PositionsTotal();
   
   string html = "<!DOCTYPE html><html><head><title>Sentinel V4.7 Dashboard</title>";
   html += "<style>body { font-family: sans-serif; background: #0f172a; color: #f1f5f9; padding: 20px; } table { width: 100%; border-collapse: collapse; } th, td { padding: 8px; border-bottom: 1px solid #333; } .profit { color: #10b981; } .loss { color: #ef4444; }</style></head><body>";
   
   html += "<h1>🏰 SENTINEL V4.7</h1>";
   html += "<p>Balance: " + DoubleToString(balance, 2) + " | Equity: " + DoubleToString(equity, 2) + " | Status: " + (tradingEnabled?"ACTIVE":"DISABLED") + "</p>";
   
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
             html += "<tr><td>"+PositionGetString(POSITION_SYMBOL)+"</td><td>"+type+"</td><td>"+DoubleToString(PositionGetDouble(POSITION_VOLUME),2)+"</td><td class='"+(profit>=0?"profit":"loss")+"'>"+DoubleToString(profit,2)+"</td></tr>";
          }
      }
      html += "</table>";
   }
   else html += "<p>No active positions.</p>";
   
   html += "</body></html>";
   
   int handle = FileOpen("dashboard.html", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle != INVALID_HANDLE) { FileWrite(handle, html); FileClose(handle); }
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

// === REPORTING ENGINE: GENERATE JSON (NATIVE) ===
void GenerateTradeReport(ulong position_id, string close_reason)
{
   if(!HistorySelectByPosition(position_id))
   {
      Print("❌ Failed to select history for position ", position_id);
      return;
   }
   
   int deals = HistoryDealsTotal();
   ulong entry_deal_ticket = 0;
   ulong exit_deal_ticket = 0;
   
   // Find ENTRY_IN and ENTRY_OUT deals
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_IN) entry_deal_ticket = ticket;
         else if(entry == DEAL_ENTRY_OUT) exit_deal_ticket = ticket;
      }
   }
   
   if(entry_deal_ticket == 0 || exit_deal_ticket == 0)
   {
      Print("⚠️ Cannot find both deals for pos ", position_id, ". In: ", entry_deal_ticket, " Out: ", exit_deal_ticket);
      return;
   }
   
   // CORRECT DATA MAPPING
   lastTradeReport.ticket = (long)position_id;
   lastTradeReport.symbol = HistoryDealGetString(exit_deal_ticket, DEAL_SYMBOL);
   lastTradeReport.type   = (ENUM_POSITION_TYPE)HistoryDealGetInteger(entry_deal_ticket, DEAL_TYPE); 
   lastTradeReport.volume = HistoryDealGetDouble(entry_deal_ticket, DEAL_VOLUME);
   
   lastTradeReport.entry_price = HistoryDealGetDouble(entry_deal_ticket, DEAL_PRICE); // Correct Entry Price
   lastTradeReport.entry_time  = (datetime)HistoryDealGetInteger(entry_deal_ticket, DEAL_TIME);
   
   lastTradeReport.exit_price  = HistoryDealGetDouble(exit_deal_ticket, DEAL_PRICE);
   lastTradeReport.exit_time   = (datetime)HistoryDealGetInteger(exit_deal_ticket, DEAL_TIME);
   
   lastTradeReport.profit     = HistoryDealGetDouble(exit_deal_ticket, DEAL_PROFIT);
   lastTradeReport.commission = HistoryDealGetDouble(exit_deal_ticket, DEAL_COMMISSION);
   lastTradeReport.swap       = HistoryDealGetDouble(exit_deal_ticket, DEAL_SWAP);
   lastTradeReport.net_profit = lastTradeReport.profit + lastTradeReport.commission + lastTradeReport.swap;
   
   lastTradeReport.close_reason = close_reason;
   lastTradeReport.balance_after = AccountInfoDouble(ACCOUNT_BALANCE);
   lastTradeReport.balance_before = lastTradeReport.balance_after - lastTradeReport.net_profit;
   
   GenerateTradeJSONReport();
   UpdateDailySummary();
}

void GenerateTradeJSONReport()
{
   // Safe String Construction for JSON
   string json = "{";
   json += "\"event_type\": \"TRADE_CLOSED\",";
   json += "\"timestamp\": " + IntegerToString(TimeCurrent()) + ",";
   json += "\"trade\": {";
   json += "\"ticket\": " + IntegerToString(lastTradeReport.ticket) + ",";
   json += "\"symbol\": \"" + lastTradeReport.symbol + "\",";
   json += "\"reason\": \"" + lastTradeReport.close_reason + "\",";
   // Add PnL details for the Python reporter
   json += "\"net_profit\": " + DoubleToString(lastTradeReport.net_profit, 2) + ","; 
   json += "\"balance_after\": " + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2);
   json += "}"; // End trade
   json += "}"; // End root
   
   string filename = "trade_report_" + IntegerToString(lastTradeReport.ticket) + ".json";
   int handle = FileOpen(filename, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle != INVALID_HANDLE)
   {
      FileWrite(handle, json);
      FileClose(handle);
      Print("📝 REPORT SAVED: ", filename);
   }
}

void UpdateDailySummary()
{
    // Minimal daily summary update placeholder
    // Real implementation requires history scan
}

//+------------------------------------------------------------------+
//| AJUSTEMENT DYNAMIQUE DES LOTS                                    |
//+------------------------------------------------------------------+
void AdjustLotSizeBasedOnPerformance() {
   if(TimeCurrent() - lastPerformanceCheck < 3600) return;
   
   if(!EnableAdaptiveLots) {
      adaptiveLotMultiplier = 1.0;
      return;
   }
   
   int totalTrades = 0;
   int winningTrades = 0;
   double totalProfit = 0;
   double totalLoss = 0;
   double maxWin = 0;
   double maxLoss = 0;
   
   HistorySelect(TimeCurrent() - 86400, TimeCurrent()); 
   int historyTotal = HistoryDealsTotal();
   
   for(int i = historyTotal-1; i >= MathMax(0, historyTotal-20); i--) {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0) {
         long dealType = HistoryDealGetInteger(ticket, DEAL_TYPE);
         long dealEntry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         
         if((dealType == DEAL_TYPE_BUY || dealType == DEAL_TYPE_SELL) && dealEntry == DEAL_ENTRY_OUT) {
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            double commission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
            double swap = HistoryDealGetDouble(ticket, DEAL_SWAP);
            double netProfit = profit + commission + swap;
            
            if(netProfit != 0) {
               totalTrades++;
               totalProfit += netProfit;
               
               if(netProfit > 0) {
                  winningTrades++;
                  if(netProfit > maxWin) maxWin = netProfit;
               } else {
                  totalLoss += MathAbs(netProfit);
                  if(netProfit < maxLoss) maxLoss = netProfit;
               }
            }
         }
      }
   }
   
   if(totalTrades >= 5) {
      double winRate = (double)winningTrades / totalTrades;
      double avgProfit = totalProfit / totalTrades;
      double profitFactor = (totalLoss > 0) ? (totalProfit - totalLoss) / totalLoss : 999;
      
      Print("[ADAPTIVE LOTS] Stats: WR " + DoubleToString(winRate*100,1) + "% PF " + DoubleToString(profitFactor,2));
      
      if(winRate < 0.3 || avgProfit < -0.5 || profitFactor < 0.5) {
         adaptiveLotMultiplier = MinLotMultiplier * 0.8;
         Print("📉 Performance critique -> Lots " + DoubleToString(adaptiveLotMultiplier*100, 0) + "%");
      } else if(winRate < 0.4 || avgProfit < 0 || profitFactor < 1.0) {
         adaptiveLotMultiplier = MinLotMultiplier; // Reduced
      } else if(winRate > 0.7 && avgProfit > 1.0 && profitFactor > 2.0) {
         adaptiveLotMultiplier = MaxLotMultiplier;
      } else if(winRate > 0.6 && avgProfit > 0.5 && profitFactor > 1.5) {
         adaptiveLotMultiplier = 1.2;
      } else {
         adaptiveLotMultiplier = 1.0;
      }
      
      adaptiveLotMultiplier = MathMin(adaptiveLotMultiplier, MaxLotMultiplier);
      adaptiveLotMultiplier = MathMax(adaptiveLotMultiplier, MinLotMultiplier * 0.5);
      
   } else {
      adaptiveLotMultiplier = 1.0;
   }
   
   lastPerformanceCheck = TimeCurrent();
}

//+------------------------------------------------------------------+
//| GESTION DES PROFITS OPTIMISÉE                                    |
//+------------------------------------------------------------------+
void OptimizeProfits() {
   if(!EnableProfitProtector && !EnableTimeBasedExit) return;
   
   for(int i = PositionsTotal()-1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      
      string symbol = PositionGetString(POSITION_SYMBOL);
      double profit = PositionGetDouble(POSITION_PROFIT);
      double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      long type = PositionGetInteger(POSITION_TYPE);
      datetime positionTime = (datetime)PositionGetInteger(POSITION_TIME);
      int positionDuration = (int)(TimeCurrent() - positionTime);
      
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      
      // 1. PROFIT PROTECTOR
      if(EnableProfitProtector) {
         // Rule 1: Secure Min Profit
         if(profit > MinProfitToLock && positionDuration > 30) {
            double safetyPrice;
            if(type == POSITION_TYPE_BUY) safetyPrice = openPrice + (point * 2);
            else safetyPrice = openPrice - (point * 2);
            
            bool shouldUpdate = false;
            if(type == POSITION_TYPE_BUY && safetyPrice > currentSL) shouldUpdate = true;
            else if(type == POSITION_TYPE_SELL && safetyPrice < currentSL) shouldUpdate = true;
            
            if(shouldUpdate && currentSL != safetyPrice) {
               trade.PositionModify(ticket, safetyPrice, currentTP);
               Print("🛡️ Profit Protector: SL Secured");
            }
         }
         
         // Rule 2: Lock Gains (Quick Profit)
         if(profit > QuickProfitThreshold) {
            double lockPrice;
            double lockDistance = 10.0 * point;
            
            if(type == POSITION_TYPE_BUY) {
               lockPrice = currentPrice - lockDistance;
               if(lockPrice < openPrice + (point * 2)) lockPrice = openPrice + (point * 2);
            } else {
               lockPrice = currentPrice + lockDistance;
               if(lockPrice > openPrice - (point * 2)) lockPrice = openPrice - (point * 2);
            }
            
            bool updateLock = false;
            if(type == POSITION_TYPE_BUY && lockPrice > currentSL) updateLock = true;
            else if(type == POSITION_TYPE_SELL && lockPrice < currentSL) updateLock = true;
            
            if(updateLock) {
               trade.PositionModify(ticket, lockPrice, currentTP);
               Print("💰 Profit Lock: " + DoubleToString(profit, 2));
            }
         }
      }
      
      // 2. TIME-BASED EXIT
      if(EnableTimeBasedExit) {
         // Rule 1: Close Stagnant (No SL Only)
         if(positionDuration > MaxTradeDuration && MathAbs(profit) < 0.20 && currentSL == 0) {
            trade.PositionClose(ticket);
            Print("⏰ Time Exit: Stagnant (No SL)");
            continue;
         }
         
         // Rule 2: Tighten SL
         if(positionDuration > TightenAfterSeconds && currentSL != 0) {
            double tightSL;
            double tightDistance = 3.0 * point;
            if(type == POSITION_TYPE_BUY) tightSL = currentPrice - tightDistance;
            else tightSL = currentPrice + tightDistance;
            
            bool improve = false;
            if(type == POSITION_TYPE_BUY && tightSL > currentSL) improve = true;
            else if(type == POSITION_TYPE_SELL && tightSL < currentSL) improve = true;
            
            if(improve) {
               trade.PositionModify(ticket, tightSL, currentTP);
               Print("⏳ Time Tightening: SL Adjustment");
            }
         }
      }
   }
}
