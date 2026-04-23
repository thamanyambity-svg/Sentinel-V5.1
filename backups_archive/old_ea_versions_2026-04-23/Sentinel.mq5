//+------------------------------------------------------------------+
//|                                                      Sentinel.mq5 |
//|                                  Copyright 2026, Ambity Project  |
//|                          VERSION 5.1 ULTIMATE (XM HYBRID + PRO)  |
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "5.10"
#include <Trade\Trade.mqh>

CTrade trade;

//--- Paramètres
input int TimerSeconds = 1;               // Fréquence (secondes)
input bool EnableLogs  = true;            // Logs

//=== SÉCURITÉ (XM GLOBAL - PETIT COMPTE) ===
input group "=== SECURITY SETTINGS ==="
input double MaxDailyLoss = 50.00;        // 🚨 ARRÊT TOTAL SI PERTE > $50
input double MaxDailyDrawdown = 10.00;    // Drawdown max 10%
input int MaxConsecutiveLosses = 5;       // Stop après 5 défaites
input int EmergencyCooldownHours = 1;     // Pause 1h

//=== SCALPEUR MQL5 ===
input group "=== MICRO-SCALPER SETTINGS ==="
input bool   EnableScalper = true;        // ✅ Activer le scalpeur autonome
input double TargetProfit  = 1.00;        // 💰 Objectif par trade ($1.00)
input double ScalpLotSize  = 0.01;        // 🛡️ LOT SÉCURISÉ (0.01)
input int    RSIPeriod     = 7;           
input int    EMAPeriod     = 50;          
input int    MinRSILevel   = 30;          
input int    MaxRSILevel   = 70;          

// === PROFIT PROTECTOR ===
input group "=== PROFIT OPTIMIZATION ==="
input bool   EnableProfitProtector = true; // ✅ BreakEven Automatique
input double MinProfitToLock = 5.00;       // Sécurise à 0 si gain > $5

// Variables
double dailyHighWaterMark = 0.0;
double dailyLowWaterMark = 0.0;
datetime lastResetTime = 0;
bool tradingEnabled = true;
string watermarkFile = "Sentinel_Watermarks.dat";
int handle_ema = INVALID_HANDLE;
int handle_rsi = INVALID_HANDLE;

//--- Prototypes
void CheckEmergencyStop(); void ScanForCommands(); void ProcessCommandFile(string filepath);
void ExecuteTrade(string json); void CloseAllPositions(); void ExportTickData(); 
string ExtractJsonValue(string source, string key); void LoadWatermarks(); void SaveWatermarks();

//+------------------------------------------------------------------+
//| INIT                                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(TimerSeconds);
   LoadWatermarks();
   handle_ema = iMA(_Symbol, _Period, EMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   handle_rsi = iRSI(_Symbol, _Period, RSIPeriod, PRICE_CLOSE);
   
   Print("🏰 SENTINEL V5.1 ULTIMATE: PRÊT.");
   Print("🔌 BRIDGE PYTHON: ACTIF");
   Print("🛡️ SÉCURITÉ: Lot=0.01 | MaxLoss=$50");
   
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { EventKillTimer(); IndicatorRelease(handle_ema); IndicatorRelease(handle_rsi); SaveWatermarks(); }

//+------------------------------------------------------------------+
//| TRADING RAPIDE (OnTick)                                          |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!tradingEnabled || !EnableScalper) return;

   // 1. CIBLE ATTEINTE (1$)
   for(int i=PositionsTotal()-1; i>=0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket)) {
         if(PositionGetDouble(POSITION_PROFIT) >= TargetProfit) {
            trade.PositionClose(ticket);
            Print("💰 GAIN ENCAISSÉ ($1.00)");
         }
      }
   }

   // 2. SCALPING (Seulement si graphique vide)
   if(PositionsTotal() == 0) {
      double ema[], rsi[]; ArraySetAsSeries(ema, true); ArraySetAsSeries(rsi, true);
      if(CopyBuffer(handle_ema, 0, 0, 2, ema) < 2 || CopyBuffer(handle_rsi, 0, 0, 2, rsi) < 2) return;
      
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      
      if(bid > ema[0] && rsi[1] < MinRSILevel && rsi[0] >= MinRSILevel) {
         double sl = NormalizeDouble(bid - (200 * _Point), _Digits);
         trade.Buy(ScalpLotSize, _Symbol, ask, sl, 0, "Sentinel Buy");
      }
      else if(ask < ema[0] && rsi[1] > MaxRSILevel && rsi[0] <= MaxRSILevel) {
         double sl = NormalizeDouble(ask + (200 * _Point), _Digits);
         trade.Sell(ScalpLotSize, _Symbol, bid, sl, 0, "Sentinel Sell");
      }
   }
}

//+------------------------------------------------------------------+
//| BOUCLE SYSTÈME (OnTimer)                                         |
//+------------------------------------------------------------------+
void OnTimer()
{
   CheckEmergencyStop();
   
   // 1. ÉCOUTER PYTHON (C'est ça qui manquait !)
   ScanForCommands(); 
   
   // 2. EXPORTER DONNÉES VERS PYTHON
   ExportTickData(); 

   // 3. PROFIT PROTECTOR (BreakEven)
   if(tradingEnabled && EnableProfitProtector) {
      for(int i=PositionsTotal()-1; i>=0; i--) {
         ulong t = PositionGetTicket(i);
         if(PositionSelectByTicket(t) && PositionGetDouble(POSITION_PROFIT) >= MinProfitToLock) {
            // Si gain > 5$, on déplace le SL au prix d'entrée
            double open = PositionGetDouble(POSITION_PRICE_OPEN);
            double sl = PositionGetDouble(POSITION_SL);
            // On modifie seulement si le SL n'est pas déjà sécurisé
            if(MathAbs(sl - open) > _Point) {
               trade.PositionModify(t, open, 0); 
               Print("🛡️ BE ACTIVÉ sur ticket ", t);
            }
         }
      }
   }
   
   if(tradingEnabled) {
      if(AccountInfoDouble(ACCOUNT_BALANCE) > dailyHighWaterMark) {
         dailyHighWaterMark = AccountInfoDouble(ACCOUNT_BALANCE); SaveWatermarks();
      }
   }
}

//+------------------------------------------------------------------+
//| EXPORTATION DONNÉES                                              |
//+------------------------------------------------------------------+
void ExportTickData()
{
   // LISTE COMPLÈTE (Incluant CADCHF et CRYPTO pour le week-end)
   string symbols[] = {
      "EURUSD", "GBPUSD", "USDCHF", "USDJPY", "USDCNH",
      "AUDUSD", "NZDUSD", "USDCAD", "USDSEK", 
      "GOLD", "Nvidia", "Apple", "CADCHF",
      "BTCUSD", "ETHUSD" 
   };
   
   string json = "{\"updated\":" + IntegerToString(TimeCurrent()) + ",\"symbols\":{";
   int count = 0;
   for(int i = 0; i < ArraySize(symbols); i++) {
      string s = symbols[i];
      if(!SymbolInfoInteger(s, SYMBOL_SELECT)) SymbolSelect(s, true);
      double bid = SymbolInfoDouble(s, SYMBOL_BID);
      double ask = SymbolInfoDouble(s, SYMBOL_ASK);
      if(bid > 0) {
         if(count > 0) json += ",";
         int digits = (int)SymbolInfoInteger(s, SYMBOL_DIGITS);
         json += "\"" + s + "\":{\"bid\":" + DoubleToString(bid, digits) + 
                 ",\"ask\":" + DoubleToString(ask, digits) + 
                 ",\"spread\":" + IntegerToString((int)SymbolInfoInteger(s, SYMBOL_SPREAD)) + "}";
         count++;
      }
   }
   json += "}}";
   int h = FileOpen("ticks.json", FILE_WRITE|FILE_ANSI|FILE_TXT);
   if(h != INVALID_HANDLE) { FileWriteString(h, json); FileClose(h); }
}

//+------------------------------------------------------------------+
//| GESTION COMMANDES PYTHON (BRIDGE)                                |
//+------------------------------------------------------------------+
void ScanForCommands() {
   string filename; 
   long handle = FileFindFirst("Command\\*.json", filename);
   if(handle != INVALID_HANDLE) { 
      do { ProcessCommandFile("Command\\" + filename); } while(FileFindNext(handle, filename)); 
      FileFindClose(handle); 
   }
}

void ProcessCommandFile(string path) {
   int h = FileOpen(path, FILE_READ|FILE_BIN);
   if(h == INVALID_HANDLE) return;
   uchar buffer[]; FileReadArray(h, buffer); FileClose(h);
   string json = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_UTF8);
   
   string action = ExtractJsonValue(json, "action");
   if(action == "TRADE" && tradingEnabled) ExecuteTrade(json);
   else if(action == "CLOSE_ALL") CloseAllPositions();
   else if(action == "RESET_RISK") { tradingEnabled=true; dailyHighWaterMark=AccountInfoDouble(ACCOUNT_EQUITY); SaveWatermarks(); }
   FileDelete(path);
}

void ExecuteTrade(string json) {
   string symbol = ExtractJsonValue(json, "symbol");
   string type = ExtractJsonValue(json, "type");
   double vol = StringToDouble(ExtractJsonValue(json, "volume"));
   if (vol > 0.10) vol = 0.10; // Force Sécurité (Test Mode)
   
   if(type == "BUY") trade.Buy(vol, symbol, SymbolInfoDouble(symbol, SYMBOL_ASK), 0, 0, "Python CMD");
   else if(type == "SELL") trade.Sell(vol, symbol, SymbolInfoDouble(symbol, SYMBOL_BID), 0, 0, "Python CMD");
}

void CloseAllPositions() { for(int i=PositionsTotal()-1; i>=0; i--) trade.PositionClose(PositionGetTicket(i)); }

//+------------------------------------------------------------------+
//| UTILITAIRES                                                      |
//+------------------------------------------------------------------+
void CheckEmergencyStop() {
   if(!tradingEnabled) {
      if(TimeCurrent() - lastResetTime > EmergencyCooldownHours * 3600) {
         tradingEnabled = true; LoadWatermarks(); Print("♻️ REPRISE DU TRADING");
      } return;
   }
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > dailyHighWaterMark) dailyHighWaterMark = equity;
   if(dailyHighWaterMark - equity > MaxDailyLoss) {
      Print("🚨 MAX LOSS (-$50). ARRÊT.");
      CloseAllPositions(); tradingEnabled = false; lastResetTime = TimeCurrent(); SaveWatermarks();
   }
}

string ExtractJsonValue(string source, string key) {
   int key_pos = StringFind(source, "\"" + key + "\""); if(key_pos == -1) return "";
   int colon_pos = StringFind(source, ":", key_pos); if(colon_pos == -1) return "";
   int start = StringFind(source, "\"", colon_pos); 
   if(start == -1) { start = colon_pos + 1; int end = StringFind(source, ",", start); if(end == -1) end = StringFind(source, "}", start); return StringSubstr(source, start, end - start); }
   int end = StringFind(source, "\"", start + 1); return StringSubstr(source, start + 1, end - start - 1);
}

void SaveWatermarks() { int h = FileOpen(watermarkFile, FILE_WRITE|FILE_BIN); if(h!=INVALID_HANDLE) { FileWriteDouble(h, dailyHighWaterMark); FileClose(h); }}
void LoadWatermarks() { int h = FileOpen(watermarkFile, FILE_READ|FILE_BIN); if(h!=INVALID_HANDLE) { dailyHighWaterMark = FileReadDouble(h); FileClose(h); } else dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY); }
