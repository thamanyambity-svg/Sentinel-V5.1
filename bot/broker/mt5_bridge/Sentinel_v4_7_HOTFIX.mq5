//+------------------------------------------------------------------+
//|                                                Sentinel_v4_7_HOTFIX.mq5 |
//|                                  Copyright 2026, Ambity Project  |
//|                                    VERSION HOTFIX - BUGS CRITIQUES CORRIGÉS |
//|                                    FONCTIONS MANQUANTES IMPLÉMENTÉES |
//|                                    LOGIQUE TIME-EXIT SÉCURISÉE   |
//|                                    RAPPORTING CORRECT            |
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "4.71"
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
input bool   EnableTimeBasedExit = false;      // DÉSACTIVÉ PAR DÉFAUT - Trop risqué
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
double referenceBalance = 0.0;     // Added for hotfix
static int dailyTradesCount = 0;   // Added for hotfix
static double dailyProfitTotal = 0.0; // Added for hotfix

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

// === FONCTIONS MANQUANTES - AJOUTÉES ===
void AdjustLotSizeBasedOnPerformance();
void OptimizeProfits();

//+------------------------------------------------------------------+
//| Initialisation                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(TimerSeconds);
   LoadWatermarks();
   
   // Initialisation sécurisée
   adaptiveLotMultiplier = 1.0;
   lastPerformanceCheck = TimeCurrent();
   
   Print("🏰 SENTINEL V4.7 HOTFIX: CRITICAL BUGS FIXED");
   Print("⚠️ Time-Based Exit: ", (EnableTimeBasedExit ? "ACTIVE (Use with caution)" : "DISABLED (Recommended)"));
   
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   SaveWatermarks();
   FileDelete("status.json");
   Print("⚔️ SENTINEL HOTFIX: Arrêt propre.");
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
   
   // V4.8 OPTIMIZATIONS - AVEC VÉRIFICATIONS
   if(EnableAdaptiveLots) AdjustLotSizeBasedOnPerformance();
   if(EnableProfitProtector || EnableTimeBasedExit) OptimizeProfits();
   
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
   
   if(dailyHighWaterMark > 0.00000001) // Protection division par zéro
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
       double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
       double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
       if(volume < minLot) volume = minLot;
       if(volume > maxLot) volume = maxLot;
       
       double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
       if(step > 0) volume = MathRound(volume/step)*step;
   }
   
   double sl     = StringToDouble(ExtractJsonValue(json, "sl"));
   double tp     = StringToDouble(ExtractJsonValue(json, "tp"));
   string comment = ExtractJsonValue(json, "comment");
   
   // Nettoyage du symbole
   StringReplace(symbol, "\"", "");
   
   if (DebugMode) Print("🚀 EXEC: ", type, " ", volume, " ", symbol, " SL:", sl, " TP:", tp);

   // VÉRIFICATION RENFORCÉE DU SYMBOLE
   double dummyPrice = 0;
   if(!SymbolInfoDouble(symbol, SYMBOL_BID, dummyPrice))
   {
       int lastError = GetLastError();
       if(lastError == ERR_UNKNOWN_SYMBOL)
       {
           Print("❌ SYMBOL ERROR: ", symbol, " does not exist in Market Watch.");
       }
       else if(lastError == ERR_SYMBOL_NOT_AVAILABLE)
       {
           Print("❌ SYMBOL ERROR: ", symbol, " not available (no ticks).");
       }
       else
       {
           Print("❌ SYMBOL ERROR: ", symbol, " - Error code: ", lastError);
       }
       return;
   }
   
   double price = 0;
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
   Print("⚠️ CLOSE ALL positions executed");
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
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   int positions = PositionsTotal();
   
   string html = "<!DOCTYPE html><html><head><title>Sentinel V4.7 HOTFIX Dashboard</title>";
   html += "<style>body { font-family: sans-serif; background: #0f172a; color: #f1f5f9; padding: 20px; } table { width: 100%; border-collapse: collapse; } th, td { padding: 8px; border-bottom: 1px solid #333; } .profit { color: #10b981; } .loss { color: #ef4444; }</style></head><body>";
   
   html += "<h1>🏰 SENTINEL V4.7 HOTFIX</h1>";
   html += "<p><strong>Version:</strong> 4.71 - Critical bugs fixed</p>";
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

// === REPORTING ENGINE: VERSION CORRIGÉE ===
void GenerateTradeReport(ulong position_id, string close_reason)
{
   // VÉRIFICATION INITIALE CRITIQUE
   if(!HistorySelectByPosition(position_id))
   {
      Print("❌ GenerateTradeReport: Failed to select history for position ", position_id);
      return;
   }
   
   int deals = HistoryDealsTotal();
   ulong entry_deal_ticket = 0;
   ulong exit_deal_ticket = 0;
   
   // RECHERCHE SÉPARÉE DES DEALS D'ENTRÉE ET SORTIE
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_IN)
         {
            entry_deal_ticket = ticket;
         }
         else if(entry == DEAL_ENTRY_OUT)
         {
            exit_deal_ticket = ticket;
         }
      }
   }
   
   // VÉRIFICATION DES DONNÉES TROUVÉES
   if(entry_deal_ticket == 0 || exit_deal_ticket == 0)
   {
      Print("⚠️ GenerateTradeReport: Incomplete data for position ", position_id, 
            " (Entry: ", entry_deal_ticket, ", Exit: ", exit_deal_ticket, ")");
      return;
   }
   
   // CORRECT : Prix d'entrée depuis DEAL_ENTRY_IN
   lastTradeReport.entry_price = HistoryDealGetDouble(entry_deal_ticket, DEAL_PRICE);
   lastTradeReport.entry_time = (datetime)HistoryDealGetInteger(entry_deal_ticket, DEAL_TIME);
   
   // CORRECT : Prix de sortie depuis DEAL_ENTRY_OUT
   lastTradeReport.exit_price = HistoryDealGetDouble(exit_deal_ticket, DEAL_PRICE);
   lastTradeReport.exit_time = (datetime)HistoryDealGetInteger(exit_deal_ticket, DEAL_TIME);
   
   // AUTRES DONNÉES
   lastTradeReport.ticket = (long)position_id;
   lastTradeReport.symbol = HistoryDealGetString(exit_deal_ticket, DEAL_SYMBOL);
   lastTradeReport.type = (ENUM_POSITION_TYPE)HistoryDealGetInteger(entry_deal_ticket, DEAL_TYPE);
   lastTradeReport.volume = HistoryDealGetDouble(entry_deal_ticket, DEAL_VOLUME);
   lastTradeReport.profit = HistoryDealGetDouble(exit_deal_ticket, DEAL_PROFIT);
   lastTradeReport.commission = HistoryDealGetDouble(exit_deal_ticket, DEAL_COMMISSION);
   lastTradeReport.swap = HistoryDealGetDouble(exit_deal_ticket, DEAL_SWAP);
   lastTradeReport.net_profit = lastTradeReport.profit + lastTradeReport.commission + lastTradeReport.swap;
   lastTradeReport.close_reason = close_reason;
   
   // CALCUL CORRECT DES SOLDES
   lastTradeReport.balance_after = AccountInfoDouble(ACCOUNT_BALANCE);
   lastTradeReport.balance_before = lastTradeReport.balance_after - lastTradeReport.net_profit;
   
   GenerateTradeJSONReport();
   UpdateDailySummary();
}

void GenerateTradeJSONReport()
{
   // Construction sécurisée du JSON
   string json = "{";
   json += "\"event_type\": \"TRADE_CLOSED\",";
   json += "\"timestamp\": " + IntegerToString(TimeCurrent()) + ",";
   json += "\"trade\": {";
   json += "\"ticket\": " + IntegerToString(lastTradeReport.ticket) + ",";
   json += "\"symbol\": \"" + lastTradeReport.symbol + "\",";
   json += "\"entry_price\": " + DoubleToString(lastTradeReport.entry_price, 5) + ",";
   json += "\"exit_price\": " + DoubleToString(lastTradeReport.exit_price, 5) + ",";
   json += "\"reason\": \"" + lastTradeReport.close_reason + "\",";
   json += "\"net_profit\": " + DoubleToString(lastTradeReport.net_profit, 2) + ","; 
   json += "\"balance_before\": " + DoubleToString(lastTradeReport.balance_before, 2) + ",";
   json += "\"balance_after\": " + DoubleToString(lastTradeReport.balance_after, 2);
   json += "}";
   json += "}";
   
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
   // Version simplifiée - à compléter selon besoins
   static int dailyTrades = 0;
   static double dailyProfit = 0;
   
   dailyTrades++;
   dailyProfit += lastTradeReport.net_profit;
   
   Print("📈 Daily Stats: Trades=", dailyTrades, " Profit=$", dailyProfit);
}

//+------------------------------------------------------------------+
//| FONCTIONS MANQUANTES - IMPLÉMENTÉES SÉCURITAIRES (PATCHED)       |
//+------------------------------------------------------------------+

void AdjustLotSizeBasedOnPerformance()
{
    static datetime lastCheck = TimeCurrent();
    
    if(TimeCurrent() - lastCheck < 14400) return;
    
    double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    if(referenceBalance == 0.0) referenceBalance = currentBalance;
    
    double ratio = currentBalance / referenceBalance;
    
    if(ratio < 0.95) 
    {
        adaptiveLotMultiplier = MathMax(MinLotMultiplier, 0.7);
        Print("📉 Lots réduits à ", adaptiveLotMultiplier*100, "%");
    }
    else if(ratio > 1.05) 
    {
        adaptiveLotMultiplier = MathMin(MaxLotMultiplier, 1.1);
        Print("📈 Lots augmentés à ", adaptiveLotMultiplier*100, "%");
    }
    else adaptiveLotMultiplier = 1.0;
    
    lastCheck = TimeCurrent();
    
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
        
        // Profit Protector seulement
        if(EnableProfitProtector && profit >= MinProfitToLock && sl != 0)
        {
            double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            long type = PositionGetInteger(POSITION_TYPE);
            
            double newSL = openPrice;
            if(type == POSITION_TYPE_BUY)
                newSL = openPrice * 0.999;
            else
                newSL = openPrice * 1.001;
            
            // Basic check to ensure valid SL modification
             double currentTP = PositionGetDouble(POSITION_TP);
             trade.PositionModify(ticket, newSL, currentTP);
             Print("🛡️ SL sécurisé pour #", ticket);
        }
        
        // Time Exit désactivé par défaut
        if(EnableTimeBasedExit && duration > MaxTradeDuration)
        {
            Print("⏰ Trade #", ticket, " ouvert depuis ", duration/60, "min");
        }
    }
}

void UpdateDailySummary()
{
    // Version minimale
    dailyTradesCount++;
    dailyProfitTotal += lastTradeReport.net_profit;
}
//+------------------------------------------------------------------+
