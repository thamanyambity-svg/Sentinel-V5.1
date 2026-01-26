//+------------------------------------------------------------------+
//|                                                     Sentinel.mq5 |
//|                                  Copyright 2026, Ambity Project  |
//|                                    VERSION 4.71 PRO (HYBRID)     |
//|                                    ROBUSTNESS v4.7 + SCALPER 3.10|
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "4.71"
#include <Trade\Trade.mqh>

CTrade trade;

//--- Paramètres
input int TimerSeconds = 1;               // Fréquence de vérification (secondes)
input bool EnableLogs  = true;            // Logs détaillés
input bool DebugMode   = true;            // Debug Mode (Print Raw JSON)

//=== PARAMÈTRES DE SÉCURITÉ (AJUSTÉS POUR CAPITAL $10,000) ===
input double MaxDailyLoss = 50.00;       // Arrêt si perte > $50 (Pour petit compte)
input double MaxDailyDrawdown = 10.00;    // Drawdown max 10%
input int MaxConsecutiveLosses = 5;       // Stop après 5 défaites
input int EmergencyCooldownHours = 1;     // Pause de 1h après un arrêt (Plus rapide pour tests)
input int DailyResetHour = 0;             // Heure de réinitialisation quotidienne (0-23)
input bool AllowManualOverride = true;    // Permettre reprise manuelle

//--- Paramètres SCALPER (STANDARD - XM GLOBAL) ===
input group "=== MICRO-SCALPER SETTINGS ==="
input bool   EnableScalper = true;          // ACTIVER PAR DÉFAUT
input double TargetProfit  = 1.00;          // Profit cible par trade ($1.00)
input bool   EnableAIFilter = false;        // Activer le filtre AI de Python
input double ScalpLotSize  = 0.01;          // LOT DE SÉCURITÉ (0.01)
input int    RSIPeriod     = 7;             // Période RSI (Rapide)
input int    EMAPeriod     = 50;            // Filtre de tendance EMA
input int    MinRSILevel   = 30;            // Zone de survente Buy
input int    MaxRSILevel   = 70;            // Zone de surachat Sell

// === OPTIMISATIONS FINALES (SENTINEL v4.7 Robustness) ===
input group "=== PROFIT OPTIMIZATION SETTINGS ==="
input bool   EnableProfitProtector = true;     // Verrouiller automatiquement les petits gains
input double MinProfitToLock = 5.00;           // Sécuriser dès $5.00
input bool   EnableAdaptiveLots = false;       // DÉSACTIVÉ pour rester fixe

// Variables de sécurité & État
double dailyHighWaterMark = 0.0;
double dailyLowWaterMark = 0.0;
datetime lastResetTime = 0;
datetime lastDailyReset = 0;
bool tradingEnabled = true;
string emergencyReason = "";
string watermarkFile = "Sentinel_Watermarks.dat";

// Global handles pour indicateurs (Scalper)
int handle_ema = INVALID_HANDLE;
int handle_rsi = INVALID_HANDLE;

// Variables Performance
double adaptiveLotMultiplier = 1.0;
double referenceBalance = 0.0;
static int dailyTradesCount = 0;
static double dailyProfitTotal = 0.0;

//--- Prototypes
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
int GetAIConfirmation();
int GetPerfectEntrySignal();
void AdjustLotSizeBasedOnPerformance();
void OptimizeProfits();
void HandleBalanceChanges();
void ExportTickData();  // V5.1: Export live tick data for MT5DataClient

//+------------------------------------------------------------------+
//| Initialisation                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(TimerSeconds);
   LoadWatermarks();
   
   // Initialiser les indicateurs pour le scalping (V3.10 Ports)
   handle_ema = iMA(_Symbol, _Period, EMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   handle_rsi = iRSI(_Symbol, _Period, RSIPeriod, PRICE_CLOSE);
   
   Print("🏰 SENTINEL V4.71 PRO: HYBRID FORTERESSE ACTIVE");
   Print("⚠️ KILL SWITCH: Trading disabled if loss > $", MaxDailyLoss);
   if(EnableScalper) Print("🎯 SCALPER MODE: Active (Target: $", TargetProfit, ")");
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Nettoyage                                                        |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   IndicatorRelease(handle_ema);
   IndicatorRelease(handle_rsi);
   SaveWatermarks();
   FileDelete("status.json");
   Print("⚔️ SENTINEL PRO: Arrêt propre.");
}

//+------------------------------------------------------------------+
//| High Frequency Tick Loop (V3.10 Scalper Logic)                   |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!tradingEnabled || !EnableScalper) return;

   // 1. RECOLTE (HARVEST) : Sortie immédiate si profit cible atteint ($1.00)
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         double currentProfit = PositionGetDouble(POSITION_PROFIT);
         if(currentProfit >= TargetProfit) 
         {
            if(trade.PositionClose(ticket))
               Print("💰 GAIN SCELLÉ: +", currentProfit, " USD (Scalp Target)");
         }
      }
   }

   // 2. SNIPER : Entrée si aucune position
   if(PositionsTotal() == 0)
   {
      int signal = GetPerfectEntrySignal();
      
      // Filtre AI (Optionnel)
      if(EnableAIFilter && signal != 0)
      {
         int ai_confirm = GetAIConfirmation();
         if(ai_confirm != 0 && ai_confirm != signal)
         {
            if(EnableLogs) Print("🛡️ SCALPER: Signal rejeté par l'IA (Signal: ", signal, " vs AI: ", ai_confirm, ")");
            signal = 0;
         }
      }

      if(signal != 0)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double price = (signal == 1) ? ask : bid;
         double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
         double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
         double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         int stopsLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
         
         // 0. Normalisation du Volume (CRITIQUE pour Volatility 100 1s)
         double min_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double max_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
         double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         
         double final_lots = ScalpLotSize;
         
         // Ajustement au Step
         if(step_vol > 0)
         {
            final_lots = MathRound(final_lots / step_vol) * step_vol;
         }
         
         // Bornage Min/Max
         if(final_lots < min_vol) final_lots = min_vol;
         if(final_lots > max_vol) final_lots = max_vol;
         
         final_lots = NormalizeDouble(final_lots, 2); // 2 décimales max pour les lots
         
         // 1. Calcul de la distance souhaitée ($0.50 de risque)
         // Note: On utilise final_lots pour le calcul
         double dist_in_ticks = 0.50 / (final_lots * tickValue);
         double sl_dist = dist_in_ticks * tickSize;
         
         // 2. Vérification des contraintes du courtier (Distance MINIMALE)
         int freezeLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
         double min_dist_points = (MathMax(stopsLevel, freezeLevel) + 20) * point; // Marge de 20 points au-dessus du max
         if(sl_dist < min_dist_points) sl_dist = min_dist_points;

         // 3. Calcul final du SL avec forçage de direction
         // CRITIQUE: Pour un BUY, le SL est calculé par rapport au BID. Pour un SELL, par rapport à l'ASK.
         double sl = (signal == 1) ? (bid - sl_dist) : (ask + sl_dist);
         
         // Normalisation du SL
         sl = NormalizeDouble(sl, _Digits);
         
         // Log Debug pour identifier les blocages
         Print("📡 DEBUG SL: ", _Symbol, " Sig=", signal, " Prc=", price, " SL=", sl, " Dist=", sl_dist, " MinDist=", min_dist_points);
         
         if(signal == 1) // BUY
         {
            if(trade.Buy(final_lots, _Symbol, ask, sl, 0, "Sentinel Sniper BUY"))
               Print("🎯 SNIPER: BUY @ ", ask, " SL: ", sl, " Lots: ", final_lots);
            else
               Print("❌ BUY FAILED (", _Symbol, "): Err=", GetLastError(), " Ask=", ask, " SL=", sl);
         }
         else if(signal == -1) // SELL
         {
            if(trade.Sell(final_lots, _Symbol, bid, sl, 0, "Sentinel Sniper SELL"))
               Print("🎯 SNIPER: SELL @ ", bid, " SL: ", sl, " Lots: ", final_lots);
            else
               Print("❌ SELL FAILED (", _Symbol, "): Err=", GetLastError(), " Bid=", bid, " SL=", sl);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Boucle Principale (Timer)                                        |
//+------------------------------------------------------------------+
void OnTimer()
{
   CheckEmergencyStop();
   
   // FIX DEADLOCK: Always scan for commands
   ScanForCommands();
   
   if(!tradingEnabled) 
   { 
      BroadcastStatus(); 
      GenerateDashboard(); 
      return; 
   }
   
   ManageRisk();
   
   if(EnableAdaptiveLots) AdjustLotSizeBasedOnPerformance();
   if(EnableProfitProtector) OptimizeProfits();
   
   BroadcastStatus();
   ExportTickData();  // V5.1: Export live tick data for Python bot
   GenerateDashboard();
}

//=== FONCTION D'ARRÊT D'URGENCE RENFORCÉE (v4.7 Robustness) ===
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
   HandleBalanceChanges();
   
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(currentEquity > dailyHighWaterMark) { dailyHighWaterMark = currentEquity; SaveWatermarks(); }
   if(currentEquity < dailyLowWaterMark) { dailyLowWaterMark = currentEquity; SaveWatermarks(); }
   
   double dailyDrawdownVal = dailyHighWaterMark - currentEquity;
   double dailyDrawdownPct = (dailyHighWaterMark > 0.000001) ? ((dailyHighWaterMark - currentEquity) / dailyHighWaterMark) * 100 : 0;
   
   if(dailyDrawdownVal > MaxDailyLoss && MaxDailyLoss > 0)
   {
      emergencyReason = "Absolute loss limit exceeded: $" + DoubleToString(dailyDrawdownVal, 2);
      ExecuteEmergencyStop();
   }
   else if(dailyDrawdownPct > MaxDailyDrawdown && MaxDailyDrawdown > 0)
   {
      emergencyReason = "Daily drawdown limit exceeded: " + DoubleToString(dailyDrawdownPct, 1) + "%";
      ExecuteEmergencyStop();
   }
   else if(CheckConsecutiveLosses(MaxConsecutiveLosses))
   {
      emergencyReason = IntegerToString(MaxConsecutiveLosses) + " consecutive losses detected";
      ExecuteEmergencyStop();
   }
}

void CheckDailyReset()
{
   MqlDateTime currentTime, lastResetTimeStruct;
   TimeToStruct(TimeCurrent(), currentTime);
   TimeToStruct(lastDailyReset, lastResetTimeStruct);
   if(currentTime.day != lastResetTimeStruct.day && currentTime.hour >= DailyResetHour)
   {
       dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY);
       dailyLowWaterMark = dailyHighWaterMark;
       lastDailyReset = TimeCurrent();
       SaveWatermarks();
       Print("📅 Daily reset at " + TimeToString(TimeCurrent()));
   }
}

//=== GESTION DES MOUVEMENTS DE FONDS (ANTI-FAUX POSITIFS) ===
void HandleBalanceChanges()
{
   if(!HistorySelect(lastDailyReset, TimeCurrent())) return;
   
   double totalBalanceOps = 0;
   int total = HistoryDealsTotal();
   
   for(int i = 0; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long type = HistoryDealGetInteger(ticket, DEAL_TYPE);
         if(type == DEAL_TYPE_BALANCE || type == DEAL_TYPE_CREDIT)
         {
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            totalBalanceOps += profit;
         }
      }
   }
   
   if(MathAbs(totalBalanceOps) > 0.001)
   {
      // Un mouvement de fond a été détecté depuis le dernier reset
      // On ajuste les Watermarks pour compenser
      dailyHighWaterMark += totalBalanceOps;
      dailyLowWaterMark += totalBalanceOps;
      
      // On reset l'historique pour ne pas compter deux fois (en avançant lastDailyReset ou via une autre méthode)
      // Note: Plus simple, on met à jour les watermarks et on log
      Print("🏦 [CAPITAL] Mouvement détecté: $", totalBalanceOps, ". Watermarks ajustés.");
      SaveWatermarks();
      
      // On force un refresh de l'équité de base pour éviter le déclenchement immédiat
      // si le retrait a fait plonger l'équité sous le LowWaterMark
   }
}

void ExecuteEmergencyStop()
{
   Print("🚨🚨🚨 EMERGENCY STOP TRIGGERED! 🚨🚨🚨 REASON: " + emergencyReason);
   CloseAllPositions();
   CancelAllPendingOrders();
   tradingEnabled = false;
   lastResetTime = TimeCurrent();
   WriteEmergencyStatus();
   GenerateDashboard();
   Print("⚠️ TRADING DISABLED until " + TimeToString(lastResetTime + EmergencyCooldownHours*3600));
}

//=== PERSISTANCE ===
void SaveWatermarks()
{
   int handle = FileOpen(watermarkFile, FILE_WRITE | FILE_BIN);
   if(handle != INVALID_HANDLE) { FileWriteDouble(handle, dailyHighWaterMark); FileWriteDouble(handle, dailyLowWaterMark); FileWriteLong(handle, lastResetTime); FileWriteLong(handle, lastDailyReset); FileClose(handle); }
}

void LoadWatermarks()
{
   int handle = FileOpen(watermarkFile, FILE_READ | FILE_BIN);
   if(handle != INVALID_HANDLE) { dailyHighWaterMark = FileReadDouble(handle); dailyLowWaterMark = FileReadDouble(handle); lastResetTime = (datetime)FileReadLong(handle); lastDailyReset = (datetime)FileReadLong(handle); FileClose(handle); }
   else { dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY); dailyLowWaterMark = dailyHighWaterMark; lastResetTime = TimeCurrent(); lastDailyReset = TimeCurrent(); }
}

void CancelAllPendingOrders()
{
   for(int i = OrdersTotal()-1; i >= 0; i--) { ulong ticket = OrderGetTicket(i); if(ticket > 0) trade.OrderDelete(ticket); }
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
         if (HistoryDealGetInteger(ticket, DEAL_TIME) < lastResetTime) break;
         if (HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT)
         { 
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            if (profit < -0.01) { consecutiveLosses++; if(consecutiveLosses >= maxLosses) return true; }
            else if (profit > 0.00) return false;
         }
      }
      if (totalHistory - i > 20) break; 
   }
   return false;
}

//=== GESTION DES COMMANDES (Robust v4.7 Mode) ===
void ScanForCommands()
{
   string search_path = "Command\\*.json"; string filename; long search_handle = FileFindFirst(search_path, filename);
   if(search_handle != INVALID_HANDLE) { do { ProcessCommandFile("Command\\" + filename); } while(FileFindNext(search_handle, filename)); FileFindClose(search_handle); }
}

void ProcessCommandFile(string filepath)
{
   int handle = FileOpen(filepath, FILE_READ|FILE_BIN);
   if(handle == INVALID_HANDLE) return;
   uchar buffer[]; FileReadArray(handle, buffer); FileClose(handle);
   string json_content = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_UTF8);
   if (StringLen(json_content) == 0) json_content = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_ACP);

   string action = ExtractJsonValue(json_content, "action");
   if (action == "TRADE") { if(tradingEnabled) ExecuteTrade(json_content); }
   else if (action == "CLOSE") CloseSpecificTrade(json_content);
   else if (action == "CLOSE_ALL") CloseAllPositions();
   else if (action == "EMERGENCY_STOP") ExecuteEmergencyStop();
   else if (action == "RESET_RISK") { tradingEnabled = true; emergencyReason = ""; dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY); dailyLowWaterMark = dailyHighWaterMark; SaveWatermarks(); Print("♻️ RISK RESET"); }
   else if (action == "RESUME_TRADING") { tradingEnabled=true; Print("🔄 RESUMED"); }
   else if (action == "STATUS") { BroadcastStatus(); }
      
   int attempts = 0; while(!FileDelete(filepath) && attempts < 5) { Sleep(100); attempts++; }
}

void ExecuteTrade(string json)
{
   // 1. EXTRACTION
   string symbol = ExtractJsonValue(json, "symbol"); 
   string type = ExtractJsonValue(json, "type");
   string s_vol = ExtractJsonValue(json, "volume");
   string s_sl = ExtractJsonValue(json, "sl");
   string s_tp = ExtractJsonValue(json, "tp");
   string comment = ExtractJsonValue(json, "comment"); 
   
   // 2. CLEANUP & NORMALIZATION
   StringReplace(symbol, "\"", ""); StringTrimLeft(symbol); StringTrimRight(symbol);
   StringReplace(type, "\"", ""); StringTrimLeft(type); StringTrimRight(type);
   
   double volume = StringToDouble(s_vol);
   double sl = StringToDouble(s_sl);
   double tp = StringToDouble(s_tp);
   
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   if(sl > 0) sl = NormalizeDouble(sl, digits);
   if(tp > 0) tp = NormalizeDouble(tp, digits);
   
   // Apply Adaptive Multiplier if enabled
   if(EnableAdaptiveLots) volume *= adaptiveLotMultiplier;
   
   // 3. DEBUG LOG
   Print("📝 EXECUTING: [", type, "] on [", symbol, "] Vol=", volume, " SL=", sl, " TP=", tp);

   // 4. EXECUTION
   trade.SetExpertMagicNumber(123456); 
   trade.SetDeviationInPoints(30); // Allow some slippage to avoid "Price Changed" errors
   
   bool res = false;
   double price = 0;
   
   if (type == "BUY") 
   {
       price = SymbolInfoDouble(symbol, SYMBOL_ASK);
       res = trade.Buy(volume, symbol, price, sl, tp, comment);
       
       // Handle Error 4756 or general failure: try without SL/TP and modify after
       if(!res)
       {
          Print("⚠️ Initial BUY failed (Err: ", GetLastError(), "). Retrying without SL/TP...");
          res = trade.Buy(volume, symbol, price, 0, 0, comment);
          if(res)
          {
             ulong ticket = trade.ResultOrder(); // Get ticket from result
             if(ticket > 0 && (sl > 0 || tp > 0))
             {
                Sleep(200); // Wait a bit for server to register position
                if(PositionSelectByTicket(ticket))
                   trade.PositionModify(ticket, sl, tp);
             }
          }
       }
   }
   else if (type == "SELL") 
   {
       price = SymbolInfoDouble(symbol, SYMBOL_BID);
       res = trade.Sell(volume, symbol, price, sl, tp, comment);
       
       if(!res)
       {
          Print("⚠️ Initial SELL failed (Err: ", GetLastError(), "). Retrying without SL/TP...");
          res = trade.Sell(volume, symbol, price, 0, 0, comment);
          if(res)
          {
             ulong ticket = trade.ResultOrder();
             if(ticket > 0 && (sl > 0 || tp > 0))
             {
                Sleep(200);
                if(PositionSelectByTicket(ticket))
                   trade.PositionModify(ticket, sl, tp);
             }
          }
       }
   }
   else
   {
       Print("❌ UNKNOWN TYPE: '", type, "'");
       return;
   }
   
   if(!res) Print("❌ TRADE FAILED: Final Error=", GetLastError());
}

void CloseSpecificTrade(string json)
{
   long ticket = StringToInteger(ExtractJsonValue(json, "ticket"));
   if (ticket > 0) trade.PositionClose(ticket);
}

void CloseAllPositions()
{
   for(int i=PositionsTotal()-1; i>=0; i--) trade.PositionClose(PositionGetTicket(i));
}

//=== LOGIQUE SNIPER EMA+RSI (v3.10 Port) ===
int GetPerfectEntrySignal()
{
   double ema_buffer[]; double rsi_buffer[]; ArraySetAsSeries(ema_buffer, true); ArraySetAsSeries(rsi_buffer, true);
   if(CopyBuffer(handle_ema, 0, 0, 2, ema_buffer) < 2) return 0;
   if(CopyBuffer(handle_rsi, 0, 0, 2, rsi_buffer) < 2) return 0;
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(currentPrice > ema_buffer[0] && rsi_buffer[1] < MinRSILevel && rsi_buffer[0] >= MinRSILevel) return 1; // BUY
   if(currentPrice < ema_buffer[0] && rsi_buffer[1] > MaxRSILevel && rsi_buffer[0] <= MaxRSILevel) return -1; // SELL
   return 0;
}

int GetAIConfirmation()
{
   int handle = FileOpen("ai_bias.json", FILE_READ|FILE_BIN); if(handle == INVALID_HANDLE) return 0;
   uchar buffer[]; FileReadArray(handle, buffer); FileClose(handle);
   string json = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_UTF8);
   string bias = ExtractJsonValue(json, "signal");
   if(bias == "BUY") return 1; if(bias == "SELL") return -1;
   return 0;
}

//=== FONCTIONS AVANCÉES v4.7 ===
void AdjustLotSizeBasedOnPerformance()
{
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   if(referenceBalance == 0.0) referenceBalance = currentBalance;
   double ratio = currentBalance / referenceBalance;
   if(ratio < 0.95) adaptiveLotMultiplier = 0.8;
   else if(ratio > 1.05) adaptiveLotMultiplier = 1.2;
   else adaptiveLotMultiplier = 1.0;
}

void OptimizeProfits()
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      double profit = PositionGetDouble(POSITION_PROFIT);
      if(profit >= MinProfitToLock)
      {
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         trade.PositionModify(ticket, openPrice, PositionGetDouble(POSITION_TP));
      }
   }
}

void ManageRisk() { /* Trailing Stop logic if needed */ }

void BroadcastStatus()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   int posCount = PositionsTotal();
   double totalProfit = 0;
   
   string posJson = "[";
   for(int i = 0; i < posCount; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionSelectByTicket(ticket))
      {
         double profit = PositionGetDouble(POSITION_PROFIT);
         totalProfit += profit;
         posJson += "{\"ticket\":" + IntegerToString(ticket) + 
                    ",\"symbol\":\"" + PositionGetString(POSITION_SYMBOL) + "\"" +
                    ",\"profit\":" + DoubleToString(profit, 2) + 
                    ",\"price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), _Digits) + 
                    ",\"volume\":" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + 
                    ",\"type\":\"" + (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"BUY":"SELL") + "\"}";
         if(i < posCount - 1) posJson += ",";
      }
   }
   posJson += "]";

   string json = "{";
   json += "\"updated\":" + IntegerToString(TimeCurrent()) + ",";
   json += "\"balance\":" + DoubleToString(balance, 2) + ",";
   json += "\"equity\":" + DoubleToString(equity, 2) + ",";
   json += "\"trading_enabled\":" + (tradingEnabled?"true":"false") + ",";
   json += "\"positions\":" + posJson + "";
   json += "}";
   
   int handle = FileOpen("status.json", FILE_WRITE|FILE_ANSI|FILE_TXT);
   if(handle != INVALID_HANDLE)
   {
      FileWriteString(handle, json);
      FileClose(handle);
   }
}

void WriteEmergencyStatus()
{
   int handle = FileOpen("status.json", FILE_WRITE|FILE_BIN);
   if(handle != INVALID_HANDLE)
   {
      string json = "{ \"emergency\": true, \"reason\": \"" + emergencyReason + "\", ";
      json += "\"trading_enabled\": false, ";
      json += "\"triggered\": \"" + TimeToString(lastResetTime) + "\", ";
      json += "\"updated\": " + IntegerToString(TimeCurrent()) + " }";
      FileWrite(handle, json);
      FileClose(handle);
   }
}

void GenerateDashboard()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   int positions = PositionsTotal();
   
   string html = "<!DOCTYPE html><html><head><title>Sentinel PRO Dashboard</title>";
   html += "<style>body { font-family: sans-serif; background: #0f172a; color: #f1f5f9; padding: 20px; } .profit { color: #10b981; } .loss { color: #ef4444; }</style></head><body>";
   html += "<h1>🏰 SENTINEL V4.71 PRO</h1>";
   html += "<p>Equity: $" + DoubleToString(equity, 2) + " | Balance: $" + DoubleToString(balance, 2) + "</p>";
   html += "<p>Status: " + (tradingEnabled?"🟢 ACTIVE":"🔴 DISABLED") + "</p>";
   if(!tradingEnabled) html += "<p style='color:#ef4444'>Reason: " + emergencyReason + "</p>";
   html += "</body></html>";
   
   int handle = FileOpen("dashboard.html", FILE_WRITE|FILE_BIN);
   if(handle != INVALID_HANDLE) { FileWrite(handle, html); FileClose(handle); }
}

string ExtractJsonValue(string source, string key)
{
   int key_pos = StringFind(source, "\"" + key + "\""); if(key_pos == -1) return "";
   int colon_pos = StringFind(source, ":", key_pos); if(colon_pos == -1) return "";
   int start = -1; bool is_string = false;
   for(int i = colon_pos + 1; i < StringLen(source); i++) {
      ushort c = StringGetCharacter(source, i); if(c == ' ' || c == '\t' || c == '\n') continue;
      if(c == '\"') { start = i + 1; is_string = true; break; } 
      if((c >= '0' && c <= '9') || c == '-' || c == '.') { start = i; break; } 
      if(c == 't' || c == 'f') { start = i; break; } 
      if(c == '}' || c == ']') return ""; 
   }
   if(start == -1) return "";
   string result = "";
   if(is_string) { for(int i = start; i < StringLen(source); i++) { ushort c = StringGetCharacter(source, i); if(c == '\"') break; result += StringFormat("%c", c); } }
   else { for(int i = start; i < StringLen(source); i++) { ushort c = StringGetCharacter(source, i); if(c == ',' || c == '}' || c == ']' || c == ' ' || c == '\n') break; result += StringFormat("%c", c); } }
   return result;
}

//+------------------------------------------------------------------+
//| Export Live Tick Data for Python MT5DataClient (V5.1)           |
//+------------------------------------------------------------------+
void ExportTickData()
{
   // List of all monitored symbols for the bot
   string symbols[] = {
      "EURUSD", "GBPUSD", "USDCHF", "USDJPY", "USDCNH",
      "AUDUSD", "NZDUSD", "USDCAD", "USDSEK", 
      "GOLD", "Nvidia", "Apple"
   };
   
   string json = "{";
   json += "\"updated\":" + IntegerToString(TimeCurrent()) + ",";
   json += "\"symbols\":{";
   
   int validCount = 0;
   for(int i = 0; i < ArraySize(symbols); i++)
   {
      string symbol = symbols[i];
      if(!SymbolInfoInteger(symbol, SYMBOL_SELECT)) { SymbolSelect(symbol, true); Sleep(100); }
      
      double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      int spread = (int)SymbolInfoInteger(symbol, SYMBOL_SPREAD);
      int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      
      if(bid > 0 && ask > 0)
      {
         if(validCount > 0) json += ",";
         json += "\"" + symbol + "\":{";
         json += "\"bid\":" + DoubleToString(bid, digits) + ",";
         json += "\"ask\":" + DoubleToString(ask, digits) + ",";
         json += "\"spread\":" + IntegerToString(spread) + ",";
         json += "\"previous_close\":" + DoubleToString(iClose(symbol, PERIOD_D1, 1), digits) + ",";
         json += "\"time\":" + IntegerToString(TimeCurrent());
         json += "}";
         validCount++;
      }
   }
   
   json += "}}";
   
   // Write to ticks.json
   int handle = FileOpen("ticks.json", FILE_WRITE|FILE_ANSI|FILE_TXT);
   if(handle != INVALID_HANDLE)
   {
      FileWriteString(handle, json);
      FileClose(handle);
   }
   else
   {
      Print("❌ Failed to write ticks.json: Error ", GetLastError());
   }
}

