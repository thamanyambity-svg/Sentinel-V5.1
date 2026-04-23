//+------------------------------------------------------------------+
//|                                           Sentinel_V6_SNIPER.mq5 |
//|                                  Copyright 2026, Ambity Project  |
//|                  VERSION 6.0 - THE SNIPER (Smart & Selective)    |
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "6.00"
#property strict
#include <Trade\Trade.mqh>

CTrade trade;

//=== CONFIGURATION SNIPER ===
input group "=== SNIPER SETTINGS ==="
input double RiskPercent = 2.0;           // Risque par trade (% du capital)
input double RiskRewardRatio = 3.0;       // Take Profit = 3x Stop Loss
input int MaxTradesPerDay = 2;            // Maximum 2 trades/jour
input bool EnableTrailing = true;         // Trailing Stop activé

input group "=== TECHNICAL INDICATORS ==="
input int EMA_Fast = 50;                  // EMA Rapide (Tendance court terme)
input int EMA_Slow = 200;                 // EMA Lente (Tendance long terme)
input int RSI_Period = 14;                // RSI Standard
input int RSI_Neutral_Min = 45;           // Zone neutre RSI (évite les pièges)
input int RSI_Neutral_Max = 55;

input group "=== RISK MANAGEMENT ==="
input double MaxDailyLoss = 100.00;       // Stop journalier ($)
input int MinPipsBetweenTrades = 50;      // Distance minimum entre 2 trades

//=== VARIABLES GLOBALES ===
int handle_ema_fast, handle_ema_slow, handle_rsi;
int tradesCountToday = 0;
datetime lastTradeTime = 0;
double dailyStartBalance = 0;
bool tradingEnabled = true;
string stateFile = "Sentinel_V6_State.dat";

//+------------------------------------------------------------------+
//| INIT                                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   // Initialiser les indicateurs
   handle_ema_fast = iMA(_Symbol, PERIOD_M15, EMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
   handle_ema_slow = iMA(_Symbol, PERIOD_M15, EMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
   handle_rsi = iRSI(_Symbol, PERIOD_M5, RSI_Period, PRICE_CLOSE);
   
   if(handle_ema_fast == INVALID_HANDLE || handle_ema_slow == INVALID_HANDLE || handle_rsi == INVALID_HANDLE) {
      Print("❌ ERREUR: Impossible de charger les indicateurs");
      return(INIT_FAILED);
   }
   
   LoadState();
   dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   Print("🎯 SENTINEL V6.0 SNIPER: Prêt au combat");
   Print("📊 Stratégie: Multi-Timeframe | R:R 1:", RiskRewardRatio);
   Print("🛡️ Protection: Max ", MaxTradesPerDay, " trades/jour | Stop à $", MaxDailyLoss);
   
   EventSetTimer(60); // Check toutes les 60 secondes (pas besoin de spam)
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { 
   EventKillTimer(); 
   SaveState();
   IndicatorRelease(handle_ema_fast);
   IndicatorRelease(handle_ema_slow);
   IndicatorRelease(handle_rsi);
}

//+------------------------------------------------------------------+
//| TIMER - ANALYSE STRATEGIQUE                                      |
//+------------------------------------------------------------------+
void OnTimer()
{
   // 1. CHECK DAILY RESET
   CheckDailyReset();
   
   // 2. RISK MANAGEMENT
   if(!CheckRiskLimits()) return;
   
   // 3. SCAN FOR OPPORTUNITY (seulement si pas de position)
   if(PositionsTotal() == 0 && tradingEnabled) {
      AnalyzeMarket();
   }
   
   // 4. MANAGE OPEN POSITIONS
   ManageOpenPositions();
   
   // 5. EXPORT STATUS
   ExportStatus();
}

//+------------------------------------------------------------------+
//| ANALYSE DE MARCHE (MULTI-TIMEFRAME)                              |
//+------------------------------------------------------------------+
void AnalyzeMarket()
{
   // Vérifier les limites de trading
   if(tradesCountToday >= MaxTradesPerDay) {
      Print("⏸️ Limite journalière atteinte (", tradesCountToday, "/", MaxTradesPerDay, ")");
      return;
   }
   
   // Buffer pour les indicateurs
   double ema_fast[], ema_slow[], rsi[];
   ArraySetAsSeries(ema_fast, true);
   ArraySetAsSeries(ema_slow, true);
   ArraySetAsSeries(rsi, true);
   
   // Copier les données (M15 pour les EMAs, M5 pour RSI)
   if(CopyBuffer(handle_ema_fast, 0, 0, 3, ema_fast) < 3) return;
   if(CopyBuffer(handle_ema_slow, 0, 0, 3, ema_slow) < 3) return;
   if(CopyBuffer(handle_rsi, 0, 0, 3, rsi) < 3) return;
   
   // === RÈGLE 1: TENDANCE CLAIRE (EMA Alignment) ===
   bool trend_bullish = (ema_fast[0] > ema_slow[0]) && (ema_fast[1] > ema_slow[1]);
   bool trend_bearish = (ema_fast[0] < ema_slow[0]) && (ema_fast[1] < ema_slow[1]);
   
   if(!trend_bullish && !trend_bearish) {
      Print("💤 Pas de tendance claire (EMAs non alignées)");
      return;
   }
   
   // === RÈGLE 2: RSI EN ZONE NEUTRE (pas en extrême) ===
   bool rsi_neutral = (rsi[0] > RSI_Neutral_Min && rsi[0] < RSI_Neutral_Max);
   
   if(!rsi_neutral) {
      Print("⚠️ RSI en zone extrême (", DoubleToString(rsi[0], 1), ") - Risque de retournement");
      return;
   }
   
   // === RÈGLE 3: CONFIRMATION PRICE ACTION ===
   double current_price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   // SIGNAL D'ACHAT
   if(trend_bullish && current_price > ema_fast[0]) {
      double sl = CalculateStopLoss(ORDER_TYPE_BUY);
      double tp = CalculateTakeProfit(ORDER_TYPE_BUY, sl);
      ExecuteTrade(ORDER_TYPE_BUY, sl, tp);
   }
   // SIGNAL DE VENTE
   else if(trend_bearish && current_price < ema_fast[0]) {
      double sl = CalculateStopLoss(ORDER_TYPE_SELL);
      double tp = CalculateTakeProfit(ORDER_TYPE_SELL, sl);
      ExecuteTrade(ORDER_TYPE_SELL, sl, tp);
   }
}

//+------------------------------------------------------------------+
//| CALCUL STOP LOSS (Basé sur ATR ou distance fixe)                 |
//+------------------------------------------------------------------+
double CalculateStopLoss(ENUM_ORDER_TYPE type)
{
   double atr_distance = 150 * _Point; // 150 pips par défaut
   double current_price = (type == ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   if(type == ORDER_TYPE_BUY)
      return NormalizeDouble(current_price - atr_distance, _Digits);
   else
      return NormalizeDouble(current_price + atr_distance, _Digits);
}

//+------------------------------------------------------------------+
//| CALCUL TAKE PROFIT (R:R Ratio)                                   |
//+------------------------------------------------------------------+
double CalculateTakeProfit(ENUM_ORDER_TYPE type, double sl)
{
   double current_price = (type == ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl_distance = MathAbs(current_price - sl);
   double tp_distance = sl_distance * RiskRewardRatio;
   
   if(type == ORDER_TYPE_BUY)
      return NormalizeDouble(current_price + tp_distance, _Digits);
   else
      return NormalizeDouble(current_price - tp_distance, _Digits);
}

//+------------------------------------------------------------------+
//| EXECUTION TRADE                                                   |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double sl, double tp)
{
   double lot = CalculateLotSize(sl);
   double price = (type == ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   string type_str = (type == ORDER_TYPE_BUY) ? "BUY" : "SELL";
   
   bool result = false;
   if(type == ORDER_TYPE_BUY)
      result = trade.Buy(lot, _Symbol, price, sl, tp, "Sniper " + type_str);
   else
      result = trade.Sell(lot, _Symbol, price, sl, tp, "Sniper " + type_str);
   
   if(result) {
      tradesCountToday++;
      lastTradeTime = TimeCurrent();
      Print("🎯 SNIPER SHOT: ", type_str, " | Lot: ", lot, " | SL: ", sl, " | TP: ", tp);
      Print("📊 R:R = 1:", RiskRewardRatio, " | Trades Today: ", tradesCountToday, "/", MaxTradesPerDay);
   } else {
      Print("❌ Échec trade: ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| CALCUL TAILLE POSITION (Risk Management)                         |
//+------------------------------------------------------------------+
double CalculateLotSize(double sl)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (RiskPercent / 100.0);
   
   double current_price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl_distance = MathAbs(current_price - sl);
   
   if(sl_distance == 0) return 0.01;
   
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(tick_value == 0 || tick_size == 0) return 0.01;
   
   double point_value = tick_value / tick_size;
   double lot = risk_amount / (sl_distance / _Point * point_value);
   
   // Normaliser et limiter
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lot = MathMax(min_lot, MathMin(max_lot, lot));
   lot = MathRound(lot / lot_step) * lot_step;
   
   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| GESTION POSITIONS OUVERTES (Trailing Stop)                       |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   if(!EnableTrailing) return;
   
   for(int i = PositionsTotal()-1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      
      double profit = PositionGetDouble(POSITION_PROFIT);
      double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
      double current_sl = PositionGetDouble(POSITION_SL);
      double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
      ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      
      // Trailing seulement si en profit
      if(profit > 5.0) {
         double new_sl = 0;
         double trail_distance = 100 * _Point; // 100 pips trailing
         
         if(pos_type == POSITION_TYPE_BUY) {
            new_sl = current_price - trail_distance;
            if(new_sl > current_sl && new_sl < current_price) {
               trade.PositionModify(ticket, NormalizeDouble(new_sl, _Digits), PositionGetDouble(POSITION_TP));
               Print("📈 Trailing BUY: Nouveau SL = ", new_sl);
            }
         } else {
            new_sl = current_price + trail_distance;
            if((current_sl == 0 || new_sl < current_sl) && new_sl > current_price) {
               trade.PositionModify(ticket, NormalizeDouble(new_sl, _Digits), PositionGetDouble(POSITION_TP));
               Print("📉 Trailing SELL: Nouveau SL = ", new_sl);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| VERIFICATION LIMITES                                              |
//+------------------------------------------------------------------+
bool CheckRiskLimits()
{
   double current_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double daily_loss = dailyStartBalance - current_balance;
   
   if(daily_loss > MaxDailyLoss) {
      Print("🚨 STOP JOURNALIER: Perte de $", daily_loss, " atteinte");
      tradingEnabled = false;
      for(int i=PositionsTotal()-1; i>=0; i--) {
         trade.PositionClose(PositionGetTicket(i));
      }
      return false;
   }
   
   return tradingEnabled;
}

//+------------------------------------------------------------------+
//| RESET JOURNALIER                                                  |
//+------------------------------------------------------------------+
void CheckDailyReset()
{
   static datetime last_date = 0;
   datetime current_date = TimeCurrent() - (TimeCurrent() % 86400); // Minuit UTC
   
   if(current_date != last_date && last_date != 0) {
      tradesCountToday = 0;
      dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      tradingEnabled = true;
      Print("📅 NOUVEAU JOUR: Compteurs réinitialisés");
   }
   
   last_date = current_date;
}

//+------------------------------------------------------------------+
//| EXPORT STATUS                                                     |
//+------------------------------------------------------------------+
void ExportStatus()
{
   string json = "{";
   json += "\"time\":" + IntegerToString(TimeCurrent()) + ",";
   json += "\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
   json += "\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   json += "\"positions\":" + IntegerToString(PositionsTotal()) + ",";
   json += "\"trades_today\":" + IntegerToString(tradesCountToday) + ",";
   json += "\"trading\":" + (tradingEnabled ? "true" : "false");
   json += "}";
   
   int h = FileOpen("status.json", FILE_WRITE|FILE_ANSI|FILE_TXT);
   if(h != INVALID_HANDLE) {
      FileWriteString(h, json);
      FileClose(h);
   }
}

void SaveState()
{
   int h = FileOpen(stateFile, FILE_WRITE|FILE_BIN);
   if(h != INVALID_HANDLE) {
      FileWriteInteger(h, tradesCountToday);
      FileWriteDouble(h, dailyStartBalance);
      FileClose(h);
   }
}

void LoadState()
{
   int h = FileOpen(stateFile, FILE_READ|FILE_BIN);
   if(h != INVALID_HANDLE) {
      tradesCountToday = FileReadInteger(h);
      dailyStartBalance = FileReadDouble(h);
      FileClose(h);
   } else {
      tradesCountToday = 0;
      dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   }
}
