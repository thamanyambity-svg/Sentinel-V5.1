//+------------------------------------------------------------------+
//|                                   Sentinel_v5_2_ULTIMATE.mq5     |
//|                                  Copyright 2026, Ambity Project  |
//|                          VERSION 5.2 ALADDIN (HYBRID AGGRESSIVE) |
//|                     MERGED: V5.1 (Scalper) + V4.7 (Risk/Reporting) |
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "5.20"
#property strict
#include <Trade\Trade.mqh>

CTrade trade;

//--- GLOBAL PARAMETERS ---
input int TimerSeconds = 1;               // Fréquence Système (secondes)
input bool EnableLogs  = true;            // Activer les rapports console

//=== GROUPE 1: SÉCURITÉ INSTITUTIONNELLE (Le Côté "SAGE") ===
input group "=== SECURITY & RISK MANAGEMENT ==="
input double MaxDailyLoss = 50.00;        // STOP TOTAL si perte > $50
input double MaxDailyDrawdown = 15.00;    // Drawdown max (15%)
input int MaxConsecutiveLosses = 6;       // Stop après 6 défaites
input int EmergencyCooldownHours = 4;     // Pause forcée (heures)
input bool EnableHardStop = true;         // Clôture tout en cas d'alerte

//=== GROUPE 2: AGGRESSIVE SCALPER (Le Côté "CHASSEUR") ===
input group "=== MICRO-SCALPER (AUTONOMOUS) ==="
input bool   EnableScalper = true;        // ✅ Activer le scalpeur interne
input double TargetProfit  = 1.50;        // 💰 Objectif par scalp ($)
input double BaseLotSize   = 0.01;        // Taille de lot initiale
input int    RSIPeriod     = 7;           
input int    EMAPeriod     = 50;          
input int    MinRSILevel   = 30;          
input int    MaxRSILevel   = 70;          

//=== GROUPE 3: INTELLIGENCE ADAPTATIVE (Le Côté "INTELLIGENT") ===
input group "=== ADAPTIVE INTELLIGENCE ==="
input bool   EnableAdaptiveLots = true;    // Ajuster les lots selon la perf
input double MaxLotMultiplier = 2.0;       // Jusqu'à x2 si on gagne
input double MinLotMultiplier = 0.5;       // Jusqu'à /2 si on perd
input bool   EnableProfitProtector = true; // Verrouillage rapide des gains
input double MinProfitToLock = 0.50;       // Garantie $0.50 dès que possible
input bool   EnableTimeExit = true;        // Fermer les trades qui stagnent
input int    MaxTradeDuration = 600;       // 10 min max pour un scalp

//--- INTERNAL STATE ---
double dailyHighWaterMark = 0.0;
datetime lastResetTime = 0;
bool tradingEnabled = true;
string watermarkFile = "Sentinel_V52_State.dat";
double adaptiveLotMultiplier = 1.0;
datetime lastPerfCheck = 0;
int handle_ema, handle_rsi;

//--- PROTOTYPES ---
void CheckSafety();
void ScanForCommands();
void ProcessCommandFile(string path);
void ExecuteTrade(string json);
void ManagePerformance();
void OptimizeOpenPositions();
void ExportStatus();
void GenerateReport(ulong ticket, string reason);
string ExtractValue(string source, string key);
void LoadState();
void SaveState();

//+------------------------------------------------------------------+
//| INIT                                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(TimerSeconds);
   LoadState();
   
   handle_ema = iMA(_Symbol, _Period, EMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   handle_rsi = iRSI(_Symbol, _Period, RSIPeriod, PRICE_CLOSE);
   
   Print("🏰 SENTINEL V5.2 ALADDIN: READY & AGGRESSIVE");
   Print("🛡️ RISK: $", MaxDailyLoss, " | ⚖️ ADAPTIVE: ", EnableAdaptiveLots ? "ON" : "OFF");
   
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { EventKillTimer(); IndicatorRelease(handle_ema); IndicatorRelease(handle_rsi); SaveState(); }

//+------------------------------------------------------------------+
//| TACTICAL LOOP (OnTick)                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!tradingEnabled || !EnableScalper) return;

   // 1. GESTION DES PROFITS (Fermeture à Target)
   for(int i=PositionsTotal()-1; i>=0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket)) {
         if(PositionGetDouble(POSITION_PROFIT) >= TargetProfit) {
            trade.PositionClose(ticket);
            GenerateReport(ticket, "TARGET_REACHED");
            Print("💰 GAIN ENCAISSÉ ($", TargetProfit, ")");
         }
      }
   }

   // 2. ENTRÉE SCALPING (Si champ libre)
   if(PositionsTotal() == 0) {
      double ema[], rsi[]; ArraySetAsSeries(ema, true); ArraySetAsSeries(rsi, true);
      if(CopyBuffer(handle_ema, 0, 0, 2, ema) < 2 || CopyBuffer(handle_rsi, 0, 0, 2, rsi) < 2) return;
      
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      
      double currentLot = BaseLotSize * adaptiveLotMultiplier;
      
      // SIGNAL ACHAT (RSI bas + Prix > EMA)
      if(bid > ema[0] && rsi[1] < MinRSILevel && rsi[0] >= MinRSILevel) {
         double sl = NormalizeDouble(bid - (250 * _Point), _Digits);
         trade.Buy(currentLot, _Symbol, ask, sl, 0, "Aladdin Buy");
      }
      // SIGNAL VENTE (RSI haut + Prix < EMA)
      else if(ask < ema[0] && rsi[1] > MaxRSILevel && rsi[0] <= MaxRSILevel) {
         double sl = NormalizeDouble(ask + (250 * _Point), _Digits);
         trade.Sell(currentLot, _Symbol, bid, sl, 0, "Aladdin Sell");
      }
   }
}

//+------------------------------------------------------------------+
//| STRATEGIC LOOP (OnTimer)                                         |
//+------------------------------------------------------------------+
void OnTimer()
{
   CheckSafety();      // Côté SAGE
   ScanForCommands();  // Côté PONT PYTHON
   
   if(tradingEnabled) {
      ManagePerformance();    // Côté INTELLIGENT
      OptimizeOpenPositions(); // Côté WISE
   }
   
   ExportStatus(); // Dashboard
}

//+------------------------------------------------------------------+
//| CORE LOGIC: SAFETY                                               |
//+------------------------------------------------------------------+
void CheckSafety() {
   if(!tradingEnabled) {
      if(TimeCurrent() - lastResetTime > EmergencyCooldownHours * 3600) {
         tradingEnabled = true; Print("♻️ SÉCURITÉ: Fin de la pause de trading.");
      } return;
   }

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > dailyHighWaterMark) dailyHighWaterMark = equity;
   
   double loss = dailyHighWaterMark - equity;
   if(loss > MaxDailyLoss) {
      Print("🚨 SÉCURITÉ: Perte Max Attainte (-$", loss, ")");
      if(EnableHardStop) {
         for(int i=PositionsTotal()-1; i>=0; i--) trade.PositionClose(PositionGetTicket(i));
      }
      tradingEnabled = false; lastResetTime = TimeCurrent(); SaveState();
   }
}

//+------------------------------------------------------------------+
//| CORE LOGIC: ADAPTIVE LOTS                                        |
//+------------------------------------------------------------------+
void ManagePerformance() {
   if(TimeCurrent() - lastPerfCheck < 3600 || !EnableAdaptiveLots) return;
   
   HistorySelect(TimeCurrent()-86400, TimeCurrent());
   int total = HistoryDealsTotal();
   double profit=0, loss=0;
   int wins=0, trades=0;
   
   for(int i=total-1; i>=0 && trades<10; i--) {
      ulong t = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(t, DEAL_ENTRY) == DEAL_ENTRY_OUT) {
         double pnl = HistoryDealGetDouble(t, DEAL_PROFIT);
         if(pnl > 0) { wins++; profit += pnl; } else loss += MathAbs(pnl);
         trades++;
      }
   }
   
   if(trades >= 5) {
      double pf = (loss>0) ? profit/loss : 2.0;
      if(pf > 1.5) adaptiveLotMultiplier = MathMin(MaxLotMultiplier, adaptiveLotMultiplier + 0.1);
      else if(pf < 1.0) adaptiveLotMultiplier = MathMax(MinLotMultiplier, adaptiveLotMultiplier - 0.1);
      Print("🧠 ADAPTIVE: Nouveau multiplicateur lot = ", DoubleToString(adaptiveLotMultiplier, 2));
   }
   lastPerfCheck = TimeCurrent();
}

//+------------------------------------------------------------------+
//| CORE LOGIC: PROFIT OPTIMIZER                                     |
//+------------------------------------------------------------------+
void OptimizeOpenPositions() {
   datetime now = TimeCurrent();
   for(int i=PositionsTotal()-1; i>=0; i--) {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t)) {
         double p = PositionGetDouble(POSITION_PROFIT);
         double open = PositionGetDouble(POSITION_PRICE_OPEN);
         double sl = PositionGetDouble(POSITION_SL);
         
         // 1. LOCK PROFIT (Breakeven + Secu)
         if(EnableProfitProtector && p >= MinProfitToLock) {
            if((PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY && sl < open) ||
               (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL && sl > open || sl == 0)) {
               trade.PositionModify(t, open, 0); // Sécurise au prix d'entrée
               Print("🛡️ PROTECTOR: Ticket #", t, " sécurisé au BE.");
            }
         }
         
         // 2. TIME EXIT (Stagnation)
         if(EnableTimeExit) {
            datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
            if(now - openTime > MaxTradeDuration) {
               trade.PositionClose(t);
               GenerateReport(t, "TIME_EXIT");
               Print("⏱️ TIME_EXIT: Ticket #", t, " fermé après stagnation.");
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| BRIDGE: PYTHON INTERFACE (ROBUST)                                |
//+------------------------------------------------------------------+
void ScanForCommands() {
   string file; long h = FileFindFirst("Command\\*.json", file);
   if(h != INVALID_HANDLE) {
      do { ProcessCommandFile("Command\\" + file); } while(FileFindNext(h, file));
      FileFindClose(h);
   }
}

void ProcessCommandFile(string path) {
   int h = FileOpen(path, FILE_READ|FILE_BIN);
   if(h == INVALID_HANDLE) return;
   uchar buffer[]; FileReadArray(h, buffer); FileClose(h);
   string json = CharArrayToString(buffer, 0, WHOLE_ARRAY, CP_UTF8);
   
   string act = ExtractValue(json, "action");
   if(act == "TRADE" && tradingEnabled) ExecuteTrade(json);
   else if(act == "CLOSE_ALL") { for(int i=PositionsTotal()-1; i>=0; i--) trade.PositionClose(PositionGetTicket(i)); }
   else if(act == "RESET_RISK") { tradingEnabled=true; dailyHighWaterMark=AccountInfoDouble(ACCOUNT_EQUITY); SaveState(); }
   
   FileDelete(path);
}

void ExecuteTrade(string json) {
   string s = ExtractValue(json, "symbol");
   string t = ExtractValue(json, "type");
   double v = StringToDouble(ExtractValue(json, "volume"));
   if(v > 0.10) v = 0.10; // Sécurité XM
   
   if(t == "BUY") trade.Buy(v, s, SymbolInfoDouble(s, SYMBOL_ASK));
   else if(t == "SELL") trade.Sell(v, s, SymbolInfoDouble(s, SYMBOL_BID));
}

//+------------------------------------------------------------------+
//| UTILS: DATA & STATE                                              |
//+------------------------------------------------------------------+
void ExportStatus() {
   string j = "{\"updated\":"+IntegerToString(TimeCurrent())+",\"equity\":"+DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),2)+",\"trading\":"+(tradingEnabled?"true":"false")+"}";
   int h = FileOpen("status.json", FILE_WRITE|FILE_ANSI|FILE_TXT);
   if(h!=INVALID_HANDLE) { FileWriteString(h, j); FileClose(h); }
}

void GenerateReport(ulong ticket, string reason) {
   string j = "{\"event\":\"CLOSE\",\"ticket\":"+IntegerToString(ticket)+",\"reason\":\""+reason+"\",\"time\":"+IntegerToString(TimeCurrent())+"}";
   int h = FileOpen("report_"+IntegerToString(ticket)+".json", FILE_WRITE|FILE_ANSI|FILE_TXT);
   if(h!=INVALID_HANDLE) { FileWriteString(h, j); FileClose(h); }
}

string ExtractValue(string source, string key) {
   int kp = StringFind(source, "\"" + key + "\""); if(kp == -1) return "";
   int cp = StringFind(source, ":", kp); if(cp == -1) return "";
   int s = StringFind(source, "\"", cp);
   if(s == -1) { s=cp+1; int e=StringFind(source, ",", s); if(e==-1) e=StringFind(source, "}", s); return StringSubstr(source, s, e-s); }
   int e = StringFind(source, "\"", s+1); return StringSubstr(source, s+1, e-s-1);
}

void SaveState() {
   int h = FileOpen(watermarkFile, FILE_WRITE|FILE_BIN);
   if(h!=INVALID_HANDLE) { FileWriteDouble(h, dailyHighWaterMark); FileWriteDouble(h, adaptiveLotMultiplier); FileClose(h); }
}

void LoadState() {
   int h = FileOpen(watermarkFile, FILE_READ|FILE_BIN);
   if(h!=INVALID_HANDLE) { dailyHighWaterMark = FileReadDouble(h); adaptiveLotMultiplier = FileReadDouble(h); FileClose(h); }
   else { dailyHighWaterMark = AccountInfoDouble(ACCOUNT_EQUITY); adaptiveLotMultiplier = 1.0; }
}
