//+------------------------------------------------------------------+
//|                                        Sentinel_V10_COMBAT.mq5   |
//|                                  Copyright 2026, Ambity Project  |
//|          VERSION 10 - COMBAT EDITION (Volatility 100 Index)      |
//|                                                                  |
//|  PRINCIPES:                                                      |
//|  1. Trade activement mais intelligemment                         |
//|  2. 3 stratégies votent ensemble (consensus)                     |
//|  3. Stop Loss TOUJOURS présent                                   |
//|  4. Lots proportionnels au solde                                 |
//|  5. Maximum 1 position à la fois                                 |
//+------------------------------------------------------------------+
#property copyright "Ambity Project"
#property version   "10.00"
#property strict

#include <Trade\Trade.mqh>
#include <Sentinel_Socket.mqh> // Communication REST vers le Cerveau Python

CTrade trade;

//==================================================================//
//                        CONFIGURATION                              //
//==================================================================//

input group "=== SYSTÈME ==="
input long   BASE_MAGIC_NUMBER= 101010;    // Magic de base (sera mixé avec le symbole)
input int    ScanIntervalSec  = 10;        // Scanner toutes les 10 secondes
input bool   EnableLogs       = true;

input group "=== GESTION DU RISQUE ==="
input double RiskPerTrade     = 2.0;       // % du solde risqué par trade
input double MaxDailyLossPerc = 8.0;       // Stop journalier (% du solde)
input int    MaxTradesPerDay  = 30;        // Limite journalière
input int    CooldownSeconds  = 120;       // 2 min entre chaque trade

input group "=== STRATÉGIE ==="
input int    EMA_Fast_Period  = 8;         // EMA rapide
input int    EMA_Slow_Period  = 21;        // EMA lente
input int    RSI_Period       = 14;        // RSI
input int    BreakoutBars     = 20;        // Nombre de barres pour le breakout
input int    Macro_EMA_Period = 50;        // Filtre Macro-Tendance (M5)
input double MinConsensus     = 2.0;       // Minimum 2 stratégies d'accord sur 3
input double SL_Multiplier    = 0.3;       // SL ULTRA-SERRÉ (0.3x ATR)
input double TP_Ratio         = 4.0;       // TP = 4x SL pour compenser le SL serré

//==================================================================//
//                        VARIABLES INTERNES                         //
//==================================================================//

int handle_ema_fast, handle_ema_slow, handle_rsi, handle_atr, handle_ema_macro;
int todayTradeCount = 0;
datetime todayDate = 0;
datetime lastTradeTime = 0;
double dailyStartBalance = 0;
bool tradingEnabled = true;
string stateFile = "Sentinel_V10_State.dat";
long ActualMagicNumber = 0;
string GLOBAL_LOSS_VAR_NAME = "Sentinel_V10_GlobalLoss";

//==================================================================//
//                          INITIALISATION                           //
//==================================================================//
int OnInit()
{
   // Générer un Magic Number unique pour ce symbole
   ActualMagicNumber = GenerateMagicNumber(_Symbol, BASE_MAGIC_NUMBER);
   trade.SetExpertMagicNumber(ActualMagicNumber);
   trade.SetDeviationInPoints(50);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   
   handle_ema_fast = iMA(_Symbol, PERIOD_M1, EMA_Fast_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_ema_slow = iMA(_Symbol, PERIOD_M1, EMA_Slow_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_rsi      = iRSI(_Symbol, PERIOD_M5, RSI_Period, PRICE_CLOSE);
   handle_atr      = iATR(_Symbol, PERIOD_M5, 14);
   handle_ema_macro= iMA(_Symbol, PERIOD_M5, Macro_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   
   if(handle_ema_fast == INVALID_HANDLE || handle_ema_slow == INVALID_HANDLE || 
      handle_rsi == INVALID_HANDLE || handle_atr == INVALID_HANDLE || 
      handle_ema_macro == INVALID_HANDLE)
   {
      Print("❌ ERREUR CRITIQUE: Impossible de charger les indicateurs");
      return(INIT_FAILED);
   }
   
   LoadState();
   dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   EventSetTimer(ScanIntervalSec);
   
   Print("═══════════════════════════════════════════");
   Print("  ⚔️ SENTINEL V10 COMBAT - OPÉRATIONNEL");
   Print("  📊 Symbole: ", _Symbol);
   Print("  💰 Solde: $", DoubleToString(dailyStartBalance, 2));
   Print("  🎯 Risque/trade: ", RiskPerTrade, "%");
   Print("  🛡️ Stop journalier: ", MaxDailyLossPerc, "%");
   Print("  ⏱️ Scan: toutes les ", ScanIntervalSec, "s");
   Print("═══════════════════════════════════════════");
   
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   IndicatorRelease(handle_ema_fast);
   IndicatorRelease(handle_ema_slow);
   IndicatorRelease(handle_rsi);
   IndicatorRelease(handle_atr);
   IndicatorRelease(handle_ema_macro);
   SaveState();
   Comment("");
}

//==================================================================//
//                     BOUCLE PRINCIPALE (OnTimer)                   //
//==================================================================//
void OnTimer()
{
   // 1. RESET JOURNALIER
   CheckDailyReset();
   
   // 2. VÉRIFIER LES LIMITES
   if(!CheckDailyLimits()) return;
   
   // 3. GÉRER LA POSITION OUVERTE (Trailing)
   if(HasOpenPosition())
   {
      ManagePosition();
   }
   else if(tradingEnabled)
   {
      // 4. CHERCHER UN SIGNAL (seulement si pas de position)
      if(IsCooldownOver() && IsMarketOpen())
      {
         double dynamic_multiplier = 1.0;
         int signal = AnalyzeConsensus(dynamic_multiplier);
         if(signal != 0)
         {
            ExecuteSignal(signal, dynamic_multiplier);
         }
      }
   }
   
   // 5. METTRE À JOUR LE DASHBOARD
   UpdateDashboard();
   BroadcastStatus();
}

//==================================================================//
//                   SYSTÈME DE CONSENSUS (3 VOTES + IA)             //
//==================================================================//
int AnalyzeConsensus(double &out_multiplier)
{
   out_multiplier = 1.0;
   // Récupérer les données
   double ema_fast[], ema_slow[], rsi[], atr[], ema_macro[];
   ArraySetAsSeries(ema_fast, true);
   ArraySetAsSeries(ema_slow, true);
   ArraySetAsSeries(rsi, true);
   ArraySetAsSeries(atr, true);
   ArraySetAsSeries(ema_macro, true);
   
   if(CopyBuffer(handle_ema_fast, 0, 0, 3, ema_fast) < 3) return 0;
   if(CopyBuffer(handle_ema_slow, 0, 0, 3, ema_slow) < 3) return 0;
   if(CopyBuffer(handle_rsi,      0, 0, 3, rsi)      < 3) return 0;
   if(CopyBuffer(handle_atr,      0, 0, 2, atr)      < 2) return 0;
   if(CopyBuffer(handle_ema_macro,0, 0, 2, ema_macro)< 2) return 0;
   
   // Vérifier que l'ATR est suffisant (marché actif)
   if(atr[0] < _Point * 10)
   {
      if(EnableLogs) Print("💤 Marché trop calme (ATR trop bas)");
      return 0;
   }
   
   double buyVotes = 0;
   double sellVotes = 0;
   
   //--- STRATÉGIE 1: EMA CROSSOVER (Tendance) ---
   // EMA rapide au-dessus de la lente = haussier
   bool ema_bullish = (ema_fast[0] > ema_slow[0]);
   bool ema_bearish = (ema_fast[0] < ema_slow[0]);
   // Bonus si le cross vient de se produire
   bool ema_just_crossed_up   = (ema_fast[0] > ema_slow[0] && ema_fast[1] <= ema_slow[1]);
   bool ema_just_crossed_down = (ema_fast[0] < ema_slow[0] && ema_fast[1] >= ema_slow[1]);
   
   if(ema_bullish) buyVotes += (ema_just_crossed_up ? 1.0 : 0.6);
   if(ema_bearish) sellVotes += (ema_just_crossed_down ? 1.0 : 0.6);
   
   //--- STRATÉGIE 2: RSI MOMENTUM ---
   // RSI > 50 = momentum haussier, < 50 = baissier
   // Bonus si RSI sort d'une zone extrême (reversal)
   if(rsi[0] > 50 && rsi[0] < 75)
   {
      buyVotes += (rsi[1] < 30 ? 1.0 : 0.5);  // Rebond de survente = fort signal
   }
   if(rsi[0] < 50 && rsi[0] > 25)
   {
      sellVotes += (rsi[1] > 70 ? 1.0 : 0.5);  // Chute de surachat = fort signal
   }
   
   //--- STRATÉGIE 3: BREAKOUT (Cassure de range) ---
   double highestHigh = 0, lowestLow = 999999;
   double close[];
   ArraySetAsSeries(close, true);
   if(CopyClose(_Symbol, PERIOD_M1, 1, BreakoutBars, close) < BreakoutBars) return 0;
   
   for(int i = 0; i < BreakoutBars; i++)
   {
      if(close[i] > highestHigh) highestHigh = close[i];
      if(close[i] < lowestLow) lowestLow = close[i];
   }
   
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double range = highestHigh - lowestLow;
   
   if(range > 0)
   {
      // Cassure au-dessus du range
      if(currentPrice > highestHigh)
      {
         buyVotes += 1.0;
      }
      // Cassure en dessous du range
      else if(currentPrice < lowestLow)
      {
         sellVotes += 1.0;
      }
   }
   
   //--- FILTRE MACRO & VALIDATION MOMENTUM (La 'Baguette Magique') ---
   bool is_macro_bullish = (currentPrice > ema_macro[0]);
   bool is_macro_bearish = (currentPrice < ema_macro[0]);
   
   if(buyVotes >= MinConsensus && buyVotes > sellVotes)
   {
      // 1. Appel au Serveur Cognitif (Python AI)
      if(EnableLogs) Print("⏳ Interrogation du Cerveau Python (FinBERT + PyTorch) pour le signal BUY...");
      string ai_response = SendToCognitiveServer("EVALUATE", _Symbol, "BUY");
      
      if(StringLen(ai_response) > 0)
      {
         // 🔄 INVERSION MAGIQUE: L'IA peut décider que c'est un SELL !
         if(StringFind(ai_response, "\"cognitive_decision\":\"SELL\"") >= 0) {
            if(EnableLogs) Print("🔄 INVERSION IA: Signal technique BUY → SELL filtré par le Cerveau.");
            out_multiplier = 0.5;
            return -1; // Force SELL
         }
         
         if(StringFind(ai_response, "\"cognitive_decision\":\"IGNORE\"") >= 0) {
            if(EnableLogs) Print("🛑 VETO DE L'IA: Trade BUY censuré.");
            return 0; 
         }
         
         // Extraction du multiplicateur
         if(StringFind(ai_response, "\"dynamic_lot_multiplier\":0.5") >= 0) out_multiplier = 0.5;
         else if(StringFind(ai_response, "\"dynamic_lot_multiplier\":1.0") >= 0) out_multiplier = 1.0;
         
         if(EnableLogs) Print("✅ FEU VERT DE L'IA: Trade BUY autorisé (", DoubleToString(out_multiplier, 1), "x)");
         return 1;
      } 
      
      Print("⚠️ Serveur IA muet. Trade BUY bloqué par sécurité.");
      return 0; 
   }
   
   if(sellVotes >= MinConsensus && sellVotes > buyVotes)
   {
      // 1. Appel au Serveur Cognitif (Python AI)
      if(EnableLogs) Print("⏳ Interrogation du Cerveau Python (FinBERT + PyTorch) pour le signal SELL...");
      string ai_response = SendToCognitiveServer("EVALUATE", _Symbol, "SELL");
      
      if(StringLen(ai_response) > 0)
      {
         // 🔄 INVERSION MAGIQUE: L'IA peut décider que c'est un BUY !
         if(StringFind(ai_response, "\"cognitive_decision\":\"BUY\"") >= 0) {
            if(EnableLogs) Print("🔄 INVERSION IA: Signal technique SELL → BUY filtré par le Cerveau.");
            out_multiplier = 0.5;
            return 1; // Force BUY
         }

         if(StringFind(ai_response, "\"cognitive_decision\":\"IGNORE\"") >= 0) {
            if(EnableLogs) Print("🛑 VETO DE L'IA: Trade SELL censuré.");
            return 0; 
         }
         
         if(StringFind(ai_response, "\"dynamic_lot_multiplier\":0.5") >= 0) out_multiplier = 0.5;
         else if(StringFind(ai_response, "\"dynamic_lot_multiplier\":1.0") >= 0) out_multiplier = 1.0;
         
         if(EnableLogs) Print("✅ FEU VERT DE L'IA: Trade SELL autorisé (", DoubleToString(out_multiplier, 1), "x)");
         return -1;
      }

      Print("⚠️ Serveur IA muet. Trade SELL bloqué par sécurité.");
      return 0;
   }
   
   return 0; // PAS DE SIGNAL
}

//==================================================================//
//                     EXÉCUTION DU TRADE                            //
//==================================================================//
void ExecuteSignal(int signal, double risk_multiplier = 1.0)
{
   // 1. VÉRIFIER QUE LE MARCHÉ EST BIEN OUVERT
   if(!IsMarketOpen())
   {
      Print("⏸️ ORDRE REJETÉ: Le marché ", _Symbol, " est fermé.");
      return;
   }
   
   // 2. CALCULER LE STOP LOSS (basé sur ATR)
   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(handle_atr, 0, 0, 1, atr) < 1) return;
   
   double slDistance = atr[0] * SL_Multiplier;
   
   // Minimum SL = 50 points pour éviter les "invalid stops"
   double minStopPoints = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(minStopPoints == 0) minStopPoints = 50 * _Point;
   // Ajouter une marge de sécurité
   minStopPoints += 20 * _Point;
   
   if(slDistance < minStopPoints)
      slDistance = minStopPoints;
   
   // 2. CALCULER LE TAKE PROFIT
   double tpDistance = slDistance * TP_Ratio;
   
   // 3. CALCULER LA TAILLE DE POSITION (Appliquée par le multiplicateur de risque IA)
   double lot = CalculateLotSize(slDistance) * risk_multiplier;
   
   // S'assurer qu'on reste au-dessus du lot minimum du broker
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(lot < minLot && lot > 0) lot = minLot;
   
   if(lot <= 0)
   {
      Print("❌ Lot calculé = 0. Solde insuffisant.");
      return;
   }
   
   // 4. PRIX D'ENTRÉE, SL, TP
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = 0, tp = 0;
   bool result = false;
   
   if(signal == 1) // BUY
   {
      sl = NormalizeDouble(ask - slDistance, _Digits);
      tp = NormalizeDouble(ask + tpDistance, _Digits);
      result = trade.Buy(lot, _Symbol, ask, sl, tp, "V10 COMBAT BUY");
   }
   else if(signal == -1) // SELL
   {
      sl = NormalizeDouble(bid + slDistance, _Digits);
      tp = NormalizeDouble(bid - tpDistance, _Digits);
      result = trade.Sell(lot, _Symbol, bid, sl, tp, "V10 COMBAT SELL");
   }
   
   // 5. VÉRIFIER LE RÉSULTAT
   if(result)
   {
      todayTradeCount++;
      lastTradeTime = TimeCurrent();
      SaveState();
      
      string dir = (signal == 1) ? "BUY" : "SELL";
      Print("⚔️ TRADE EXÉCUTÉ: ", dir, " ", DoubleToString(lot, 2), " lots");
      Print("   SL: ", DoubleToString(sl, _Digits), " | TP: ", DoubleToString(tp, _Digits));
      Print("   R:R = 1:", DoubleToString(TP_Ratio, 1));
      Print("   Trades aujourd'hui: ", todayTradeCount, "/", MaxTradesPerDay);
   }
   else
   {
      uint retcode = trade.ResultRetcode();
      Print("❌ ÉCHEC TRADE (Code ", retcode, "): ", trade.ResultComment());
      
      // NE PAS retenter sans SL. JAMAIS.
      if(retcode == 10016) // Invalid stops
      {
         Print("⚠️ Stops invalides. Le broker refuse le SL/TP. On attend.");
         Print("   SL Distance: ", DoubleToString(slDistance/_Point, 0), " points");
         Print("   Min Stop Level: ", SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL));
      }
   }
}

//==================================================================//
//                   CALCUL TAILLE DE POSITION                       //
//==================================================================//
double CalculateLotSize(double slDistance)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * (RiskPerTrade / 100.0);
   
   // Valeur d'un tick
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(tickValue <= 0 || tickSize <= 0 || slDistance <= 0)
      return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   
   double slTicks = slDistance / tickSize;
   double lot = riskAmount / (slTicks * tickValue);
   
   // Normaliser
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lot = MathMax(minLot, MathMin(maxLot, lot));
   lot = MathFloor(lot / lotStep) * lotStep;
   
   return NormalizeDouble(lot, 2);
}

//==================================================================//
//               GESTION DE LA POSITION OUVERTE                      //
//==================================================================//
void ManagePosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != ActualMagicNumber) continue;
      
      double profit     = PositionGetDouble(POSITION_PROFIT);
      double openPrice  = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL  = PositionGetDouble(POSITION_SL);
      double currentTP  = PositionGetDouble(POSITION_TP);
      double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      
      double slDistance = MathAbs(openPrice - currentSL);
      
      // Récupérer le niveau minimal vital pour ajuster les stops
      double symbol_stoplevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
      if (symbol_stoplevel == 0) symbol_stoplevel = 50 * _Point;
      
      // BREAKEVEN : Quand le profit atteint 1x le SL, on déplace le SL au prix d'entrée
      if(profit > 0 && slDistance > 0)
      {
         double profitDistance = 0;
         if(posType == POSITION_TYPE_BUY)
            profitDistance = currentPrice - openPrice;
         else
            profitDistance = openPrice - currentPrice;
         
         // Si le profit dépasse 1x le SL initial → Breakeven
         if(profitDistance >= slDistance)
         {
            double newSL = 0;
            if(posType == POSITION_TYPE_BUY && currentSL < openPrice)
            {
               newSL = openPrice + (10 * _Point); // Petit profit garanti
               trade.PositionModify(ticket, NormalizeDouble(newSL, _Digits), currentTP);
               Print("🛡️ BREAKEVEN activé sur ticket #", ticket);
            }
            else if(posType == POSITION_TYPE_SELL && (currentSL > openPrice || currentSL == 0))
            {
               newSL = openPrice - (10 * _Point);
               trade.PositionModify(ticket, NormalizeDouble(newSL, _Digits), currentTP);
               Print("🛡️ BREAKEVEN activé sur ticket #", ticket);
            }
         }
         
         // TRAILING ADAPTATIF BASÉ SUR VOLATILITÉ: Si le profit dépasse 1x le SL (plus agressif pour couper l'anomalie tôt)
         if(profitDistance >= slDistance * 1.5 && profitDistance > 10 * _Point)
         {
            // Récupérer la volatilité immédiate pour le trailing
            double atr_trail[];
            ArraySetAsSeries(atr_trail, true);
            if(CopyBuffer(handle_atr, 0, 0, 1, atr_trail) > 0)
            {
               double trailDistance = atr_trail[0] * 1.2; // Trail plus large → laisse le trade courir vers le TP
               if(trailDistance < symbol_stoplevel) trailDistance = symbol_stoplevel + 20 * _Point;
               
               double newSL2 = 0;
            
            if(posType == POSITION_TYPE_BUY)
            {
               newSL2 = currentPrice - trailDistance;
               if(newSL2 > currentSL)
               {
                  trade.PositionModify(ticket, NormalizeDouble(newSL2, _Digits), currentTP);
                  Print("📈 TRAILING: SL déplacé à ", DoubleToString(newSL2, _Digits));
               }
            }
            else if(posType == POSITION_TYPE_SELL)
            {
               newSL2 = currentPrice + trailDistance;
               if(newSL2 < currentSL || currentSL == 0)
               {
                  trade.PositionModify(ticket, NormalizeDouble(newSL2, _Digits), currentTP);
                  Print("📉 TRAILING: SL déplacé à ", DoubleToString(newSL2, _Digits));
               }
            }
         }
      }
      }
   }
}

//==================================================================//
//                      VÉRIFICATIONS                                //
//==================================================================//

bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         if(PositionGetInteger(POSITION_MAGIC) == ActualMagicNumber)
            return true;
   }
   return false;
}

bool IsCooldownOver()
{
   return (TimeCurrent() - lastTradeTime >= CooldownSeconds);
}

bool CheckDailyLimits()
{
   // Vérifier le nombre de trades
   if(todayTradeCount >= MaxTradesPerDay)
   {
      if(tradingEnabled)
         Print("⏸️ Limite de ", MaxTradesPerDay, " trades/jour atteinte");
      tradingEnabled = false;
      return false;
   }
   
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   // AUTO-RESET SI DÉPÔT DÉTECTÉ (ex: tes +10 USD)
   if(currentBalance > dailyStartBalance + 5.0)
   {
      Print("💰 DÉPÔT DÉTECTÉ: Réinitialisation des limites (Ancien: $", DoubleToString(dailyStartBalance, 2), " -> Nouveau: $", DoubleToString(currentBalance, 2), ")");
      dailyStartBalance = currentBalance;
      if(GlobalVariableCheck(GLOBAL_LOSS_VAR_NAME)) GlobalVariableSet(GLOBAL_LOSS_VAR_NAME, 0);
      todayTradeCount = 0;
   }

   double localLoss = dailyStartBalance - currentBalance;
   
   // GESTION DU STOP JOURNALIER GLOBAL (Multi-Charts)
   double globalLoss = 0;
   if(GlobalVariableCheck(GLOBAL_LOSS_VAR_NAME)) {
       globalLoss = GlobalVariableGet(GLOBAL_LOSS_VAR_NAME);
   }
   
   // Si notre perte locale est plus grande que la globale (on a contribué à la chute), on met à jour
   if(localLoss > globalLoss) {
       GlobalVariableSet(GLOBAL_LOSS_VAR_NAME, localLoss);
       globalLoss = localLoss;
   }
   
   double maxLoss = AccountInfoDouble(ACCOUNT_EQUITY) > 0 ? (AccountInfoDouble(ACCOUNT_EQUITY) + localLoss) * (MaxDailyLossPerc / 100.0) : dailyStartBalance * (MaxDailyLossPerc / 100.0);
   
   if(globalLoss >= maxLoss && maxLoss > 0)
   {
      if(tradingEnabled)
         Print("🚨 STOP JOURNALIER GLOBAL: Perte totale de $", DoubleToString(globalLoss, 2),
               " (limite: $", DoubleToString(maxLoss, 2), ")");
      tradingEnabled = false;
      
      // Fermer toute position ouverte
      CloseAllPositions("Daily Loss Limit");
      return false;
   }
   
   tradingEnabled = true;
   return true;
}

void CheckDailyReset()
{
   datetime currentDate = TimeCurrent() - (TimeCurrent() % 86400);
   
   if(currentDate != todayDate)
   {
      if(todayDate != 0)
      {
         Print("📅 NOUVEAU JOUR | Trades hier: ", todayTradeCount,
               " | Balance: $", DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2));
      }
      todayTradeCount = 0;
      dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      tradingEnabled = true;
      todayDate = currentDate;
      
      // Reset Global Variable Loss for the new day
      if(GlobalVariableCheck(GLOBAL_LOSS_VAR_NAME)) {
          GlobalVariableSet(GLOBAL_LOSS_VAR_NAME, 0);
      }
      
      SaveState();
   }
}

void CloseAllPositions(string reason)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         if(PositionGetInteger(POSITION_MAGIC) == ActualMagicNumber)
         {
            trade.PositionClose(ticket);
            Print("🔒 Position fermée (", reason, ") Ticket #", ticket);
         }
   }
}

//==================================================================//
//                        DASHBOARD HUD                              //
//==================================================================//
void UpdateDashboard()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnl     = equity - balance;
   double dailyPnL = balance - dailyStartBalance;
   
   string status = tradingEnabled ? "🟢 ACTIVE" : "🔴 STOP";
   string posInfo = HasOpenPosition() ? "⚔️ EN COMBAT" : "👁️ EN VEILLE";
   
   string hud = "\n";
   hud += "══════════════════════════════════\n";
   hud += "   SENTINEL V10 COMBAT EDITION   \n";
   hud += "══════════════════════════════════\n";
   hud += " Status:    " + status + "\n";
   hud += " Position:  " + posInfo + "\n";
   hud += " Balance:   $" + DoubleToString(balance, 2) + "\n";
   hud += " P&L Jour:  $" + DoubleToString(dailyPnL, 2) + "\n";
   hud += " Trades:    " + IntegerToString(todayTradeCount) + "/" + IntegerToString(MaxTradesPerDay) + "\n";
   hud += " Cooldown:  " + (IsCooldownOver() ? "Prêt" : "Attente") + "\n";
   hud += "══════════════════════════════════\n";
   
   Comment(hud);
}

//==================================================================//
//                    BRIDGE PYTHON (status.json)                     //
//==================================================================//
void BroadcastStatus()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   
 // Infos position globale (même un autre bot)
   string posJson = "[]";
   if(PositionsTotal() > 0)
   {
      posJson = "[";
      int count = 0;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         ulong ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(ticket)) // On envoie toutes les positions pour le webhook
         {
            if(count > 0) posJson += ",";
            posJson += StringFormat(
               "{\"ticket\":%d,\"symbol\":\"%s\",\"type\":\"%s\",\"volume\":%.2f,\"profit\":%.2f,\"price\":%.5f,\"magic\":%d}",
               (long)ticket,
               PositionGetString(POSITION_SYMBOL),
               (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL"),
               PositionGetDouble(POSITION_VOLUME),
               PositionGetDouble(POSITION_PROFIT),
               PositionGetDouble(POSITION_PRICE_OPEN),
               PositionGetInteger(POSITION_MAGIC));
            count++;
         }
      }
      posJson += "]";
   }
   
   string json = "{";
   json += "\"version\":\"V10_COMBAT\",";
   json += "\"updated\":" + IntegerToString(TimeCurrent()) + ",";
   json += "\"balance\":" + DoubleToString(balance, 2) + ",";
   json += "\"equity\":" + DoubleToString(equity, 2) + ",";
   json += "\"trades_today\":" + IntegerToString(todayTradeCount) + ",";
   json += "\"trading_enabled\":" + (tradingEnabled ? "true" : "false") + ",";
   json += "\"exposure_lots\":" + DoubleToString(GetTotalLots(), 2) + ",";
   json += "\"positions\":" + posJson;
   json += "}";
   
   int h = FileOpen("status.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h != INVALID_HANDLE) { FileWriteString(h, json); FileClose(h); }
}

double GetTotalLots()
{
   double total = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         if(PositionGetInteger(POSITION_MAGIC) == ActualMagicNumber)
            total += PositionGetDouble(POSITION_VOLUME);
   }
   return total;
}

//==================================================================//
//                      ÉTAT PERSISTANT                               //
//==================================================================//
void SaveState()
{
   int h = FileOpen(stateFile, FILE_WRITE|FILE_BIN);
   if(h != INVALID_HANDLE)
   {
      FileWriteInteger(h, todayTradeCount);
      FileWriteDouble(h, dailyStartBalance);
      FileWriteInteger(h, (int)tradingEnabled);
      FileWriteInteger(h, (int)todayDate);
      FileClose(h);
   }
}

void LoadState()
{
   int h = FileOpen(stateFile, FILE_READ|FILE_BIN);
   if(h != INVALID_HANDLE)
   {
      todayTradeCount   = FileReadInteger(h);
      dailyStartBalance = FileReadDouble(h);
      tradingEnabled    = (bool)FileReadInteger(h);
      todayDate         = (datetime)FileReadInteger(h);
      FileClose(h);
   }
   else
   {
      todayTradeCount = 0;
      dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      tradingEnabled = true;
      todayDate = TimeCurrent() - (TimeCurrent() % 86400);
   }
}

//==================================================================//
//                 OUTILS MULTI-ACTIFS (HEURES/MAGICS)               //
//==================================================================//
long GenerateMagicNumber(string symbol, long baseMagic)
{
   long hash = 0;
   int len = StringLen(symbol);
   for(int i=0; i<len; i++) {
      hash = hash + StringGetCharacter(symbol, i);
   }
   return baseMagic + hash;
}

bool IsMarketOpen()
{
   datetime time_start, time_end;
   datetime time_current = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(time_current, dt);
   
   // Check if trading is allowed for the symbol today
   if(SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)dt.day_of_week, 0, time_start, time_end))
   {
      // Calculate current time of day in seconds
      int current_time_sec = (int)(time_current % 86400); 
      
      // Start and End time are in seconds since midnight
      if(current_time_sec >= time_start && current_time_sec <= time_end)
         return true;
   }
   
   return false;
}
