//+------------------------------------------------------------------+
//|                                                Sentinel_v4_4.mq5 |
//|                                  Copyright 2026, Ambity Project  |
//|                                       2-WAY SYNC (Read & Write)  |
//|                                    DEBUG & ROBUST JSON PARSER    |
//|                                    FULL RISK MANAGEMENT RESTORED |
//|                                    ATR TRAILING + SMART EXEC     |
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "4.40"
#include <Trade\Trade.mqh>

CTrade trade;

//--- Paramètres
input int TimerSeconds = 1;               // Fréquence de vérification (secondes)
input bool EnableLogs  = true;            // Logs détaillés
input bool DebugMode   = true;            // Debug Mode (Print Raw JSON)

//=== PARAMÈTRES DE SÉCURITÉ ===
input double MaxDailyLoss = 300.00;       // ARRÊT ABSOLU si perte > $300.00
input double MaxDailyDrawdown = 5.00;     // Drawdown journalier max (%)
input int EmergencyCooldownHours = 24;    // Désactivation après arrêt
input int DailyResetHour = 0;             // Heure de réinitialisation quotidienne (0-23)
input bool AllowManualOverride = true;    // Permettre reprise manuelle

//=== PARAMÈTRES ATR (NOUVEAU V4.0) ===
input bool   UseATR_Trailing = true;     // [V4] Activer le trailing stop dynamique
input int    ATR_Period = 14;            // [V4] Période de l'ATR
input double ATR_Multiplier = 2.0;       // [V4] Multiplicateur pour la distance du SL

// Variables de sécurité
double dailyHighWaterMark = 0.0;
double dailyLowWaterMark = 0.0;
datetime lastResetTime = 0;
datetime lastDailyReset = 0;
bool tradingEnabled = true;
string emergencyReason = "";
string watermarkFile = "Sentinel_Watermarks.dat";

//+------------------------------------------------------------------+
//| Initialisation                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(TimerSeconds);
   LoadWatermarks();
   Print("🏰 SENTINEL V4.4: FULL ARMOR + ATR TRAILING");
   Print("⚠️ KILL SWITCH: Trading disabled if loss > $", MaxDailyLoss);
   if(UseATR_Trailing) Print("🧗 ATR Trailing: ACTIVE (Per:", ATR_Period, " Mul:", ATR_Multiplier, ")");
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
   if(!tradingEnabled) { BroadcastStatus(); GenerateDashboard(); return; }
   
   ScanForCommands();
   ManageRisk();
   BroadcastStatus();
   GenerateDashboard();
}

//=== FONCTION D'ARRÊT D'URGENCE RENFORCÉE (Restored from v3.10) ===
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
   
   if(dailyHighWaterMark > 0) 
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
   
   if(CheckConsecutiveLosses(3))
   {
      emergencyReason = "3 consecutive losses detected";
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

//=== GESTION DES COMMANDES (ROBUST) ===
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
    else 
    { 
        if(DebugMode && GetLastError() != 5018) // 5018 = ERR_FILE_NOT_EXIST which is normal
           Print("ℹ️ No commands found (or FileFindFirst error: ", GetLastError(), ")"); 
    }
}

void ProcessCommandFile(string filepath)
{
   // FIXED: Try UTF-8 first, then fallback to ANSI
   int handle = FileOpen(filepath, FILE_READ|FILE_TXT|CP_UTF8); 
   if(handle == INVALID_HANDLE) 
   {
      if(DebugMode) Print("⚠️ Failed to open as UTF-8: ", filepath, " (Error: ", GetLastError(), "). Retrying ANSI...");
      handle = FileOpen(filepath, FILE_READ|FILE_TXT|CP_ACP); // Fallback ANSI
      if (handle == INVALID_HANDLE) {
          Print("❌ CRITICAL: FAILED TO OPEN FILE IN ANY CODEPAGE: ", filepath, " Error: ", GetLastError());
          return;
      }
   }

   string json_content = "";
   while(!FileIsEnding(handle)) json_content += FileReadString(handle);
   FileClose(handle);

   if (EnableLogs || DebugMode) Print("📩 RAW CONTENT: ", json_content);

   string action = ExtractJsonValue(json_content, "action");
   if (DebugMode) Print("🔍 PARSED ACTION: [", action, "]");
   
   if (action == "TRADE") ExecuteTrade(json_content);
   else if (action == "CLOSE") CloseSpecificTrade(json_content);
   else if (action == "CLOSE_ALL") CloseAllPositions();
   else if (action == "EMERGENCY_STOP") ExecuteEmergencyStop();
   else if (action == "RESUME_TRADING") { tradingEnabled=true; Print("🔄 RESUMED"); }
   else if (action == "STATUS") { BroadcastStatus(); }
   else Print("⚠️ UNKNOWN ACTION: ", action);
      
   if(!FileDelete(filepath)) Print("❌ FAILED TO DELETE: ", filepath);
}

void ExecuteTrade(string json)
{
   string symbol = ExtractJsonValue(json, "symbol");
   string type   = ExtractJsonValue(json, "type");
   double volume = StringToDouble(ExtractJsonValue(json, "volume"));
   double sl     = StringToDouble(ExtractJsonValue(json, "sl"));
   double tp     = StringToDouble(ExtractJsonValue(json, "tp"));
   string comment = ExtractJsonValue(json, "comment");
   
   StringReplace(symbol, "\"", ""); 
   
   if (DebugMode) Print("🚀 EXEC: ", type, " ", volume, " ", symbol, " SL:", sl, " TP:", tp);

   double price = 0.0;
   
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
   // [V4] SMART EXECUTION (LIMIT ORDERS)
   else if (type == "BUY_LIMIT" || type == "SELL_LIMIT")
   {
       price = StringToDouble(ExtractJsonValue(json, "price")); // Try to get price from JSON
       
       if(price <= 0) // Si prix non spécifié, calculer un prix passif intelligent
       {
           double spread = SymbolInfoInteger(symbol, SYMBOL_SPREAD) * Point();
           if(type == "BUY_LIMIT") price = SymbolInfoDouble(symbol, SYMBOL_BID) + (spread * 0.3); // Légèrement au-dessus du Bid (agressif mais passif)
           if(type == "SELL_LIMIT") price = SymbolInfoDouble(symbol, SYMBOL_ASK) - (spread * 0.3); // Légèrement en-dessous de l'Ask
       }
       
       // Normalize price
       double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
       price = NormalizeDouble(MathRound(price/tick_size)*tick_size, _Digits);

       if(type == "BUY_LIMIT") {
           if(!trade.BuyLimit(volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment))
               Print("❌ BUYLIMIT ERROR: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
           else
               Print("✅ BUYLIMIT PLACED: #", trade.ResultOrder(), " @ ", price);
       }
       else {
           if(!trade.SellLimit(volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment))
               Print("❌ SELLLIMIT ERROR: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
           else
               Print("✅ SELLLIMIT PLACED: #", trade.ResultOrder(), " @ ", price);
       }
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

//=== NEW ROBUST PARSER ===
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
           result += ShortToString(c);
       }
   }
   else
   {
       for(int i = start; i < StringLen(source); i++) {
           ushort c = StringGetCharacter(source, i);
           if(c == ',' || c == '}' || c == ']' || c == ' ' || c == '\n' || c == '\r') break;
           result += ShortToString(c);
       }
   }
   return result;
}

//=== GESTION DU RISQUE (LE GRIMPEUR + ATR) ===
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

      double risk_distance = 300 * Point(); // Valeur par défaut (fallback)
      
      // [V4] CALCUL DYNAMIQUE ATR
      if(UseATR_Trailing)
      {
          int atr_handle = iATR(symbol, PERIOD_CURRENT, ATR_Period);
          if(atr_handle != INVALID_HANDLE)
          {
              double atr_buffer[];
              ArraySetAsSeries(atr_buffer, true);
              if(CopyBuffer(atr_handle, 0, 0, 1, atr_buffer) > 0)
              {
                  risk_distance = atr_buffer[0] * ATR_Multiplier;
              }
              IndicatorRelease(atr_handle);
          }
      }

      double new_sl = 0.0;
      bool update_needed = false;
      
      if(type == POSITION_TYPE_BUY)
      {
         double potential_sl = current_price - risk_distance;
         if(potential_sl > sl || sl == 0) { new_sl = potential_sl; update_needed = true; }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double potential_sl = current_price + risk_distance;
         if(potential_sl < sl || sl == 0) { new_sl = potential_sl; update_needed = true; }
      }
        
      if(update_needed)
      {
         double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
         new_sl = NormalizeDouble(MathRound(new_sl/tick_size)*tick_size, _Digits);
         // Filter minor updates (only if change is > small diff)
         if (MathAbs(new_sl - sl) > Point()) 
         {
             trade.PositionModify(ticket, new_sl, tp);
             // Print("🧗 Grimpeur (ATR): SL Moved to ", new_sl);
         }
      }
   }
}

//=== RAPPORT DE SITUATION JSON ===
void BroadcastStatus()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   string json = "{ \"updated\": " + IntegerToString(TimeCurrent()) + ", \"balance\": " + DoubleToString(balance, 2) + 
                 ", \"equity\": " + DoubleToString(equity, 2) + ", \"positions\": [";
   
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

//=== GENERATION DASHBOARD ===
void GenerateDashboard()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double freeMargin = AccountInfoDouble(ACCOUNT_FREEMARGIN);
   int positions = PositionsTotal();
   
   string html = "<!DOCTYPE html><html><head><title>Sentinel V4.4 Dashboard</title>";
   html += "<style>body { font-family: sans-serif; background: #0f172a; color: #f1f5f9; padding: 20px; } table { width: 100%; border-collapse: collapse; } th, td { padding: 8px; border-bottom: 1px solid #333; } .profit { color: #10b981; } .loss { color: #ef4444; }</style></head><body>";
   
   html += "<h1>🏰 SENTINEL V4.4</h1>";
   html += "<p>Balance: " + DoubleToString(balance, 2) + " | Equity: " + DoubleToString(equity, 2) + " | Status: " + (tradingEnabled?"ACTIVE":"DISABLED") + "</p>";
   html += "<p>ATR Trailing: " + (UseATR_Trailing ? "ON" : "OFF") + "</p>";
   
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
