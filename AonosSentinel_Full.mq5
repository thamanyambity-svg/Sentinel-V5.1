//+------------------------------------------------------------------+

//|                        Sentinel_V12_IMPROVED.mq5                  |

//|         V12 - OBJECTIF 9/10 : entrées ultra-sélectives            |

//|         Consensus total + alignement EMAs + zone RSI + proba haute|

//+------------------------------------------------------------------+

#property copyright "Ambity Project"

#property version   "12.10"

#property strict



#include <Trade\Trade.mqh>

#include <Sentinel_Socket.mqh>



CTrade trade;



// ExtractJSONValue fourni par Sentinel_Socket.mqh

void SendFeedbackToServer(ulong order_ticket, string sym, string type, double profit, double spm, double prob, double imbalance) {

   return;  // Optionnel : décommenter WebRequest si endpoint /feedback existe

}



//==================================================================//

//                        CONFIGURATION                              //

//==================================================================//



input group "=== SYSTÈME MULTI-STRIKER (SÉCURISÉ) ==="

input long   BASE_MAGIC_NUMBER   = 102796;

input int    ScanIntervalSec    = 15;

input bool   ScanMarketWatch    = true;

input int    MaxConcurrentPositions = 3;



input group "=== GOUVERNANCE DU RISQUE (OBJECTIF 9/10) ==="

input double RiskPerTrade       = 0.5;

input double MAX_LOT_CAP        = 0.15;

input double MaxDailyLossPerc   = 3.0;

input int    MaxTradesPerDay     = 10;     // Moins de trades = seulement les meilleurs

input int    CooldownBetweenTrades = 300;  // 5 min entre deux ouvertures

input int    SymbolCooldownMinutes = 120;  // 2 h avant de retoucher le même symbole



input group "=== SOVEREIGN 9/10 (CONSENSUS TOTAL) ==="

input double SL_Multiplier      = 1.5;

input double TP_Ratio           = 3.5;     // Laisser courir les gains

input double MinConsensus       = 3.0;     // 3/3 : les 3 critères doivent être d'accord

input double MinProbability     = 0.70;     // Serveur très confiant (70 % min)

input int    RSI_BuyMax         = 65;      // BUY uniquement si RSI <= 65 (pas suracheté)

input int    RSI_BuyMin         = 45;      // BUY si RSI >= 45 (momentum haussier)

input int    RSI_SellMin        = 35;      // SELL uniquement si RSI >= 35 (pas survendu)

input int    RSI_SellMax        = 55;      // SELL si RSI <= 55 (momentum baissier)

input bool   RequireEmaStack    = true;    // BUY: EMA8>EMA21>EMA50 | SELL: EMA8<EMA21<EMA50



//==================================================================//

//                   CONTEXTE TACTIQUE (POUR APEX)                   //

//==================================================================//

double current_spm = 0;

double current_prob = 0;

double current_imbalance = 0;

ulong  processed_history[50];

int    processed_ptr = 0;

ulong  last_processed_ticket = 0;



//==================================================================//

//                        VARIABLES INTERNES                         //

//==================================================================//

int todayTradeCount = 0;

datetime todayDate = 0;

datetime lastTradeTime = 0;

double dailyStartBalance = 0;

string stateFile = "Sentinel_V12_Safe.dat";

long ActualMagicNumber = 0;



//==================================================================//

//                          INITIALISATION                           //

//==================================================================//

int OnInit()

{

   ActualMagicNumber = BASE_MAGIC_NUMBER;

   trade.SetExpertMagicNumber(ActualMagicNumber);

   trade.SetDeviationInPoints(50);



   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);

   if((filling & SYMBOL_FILLING_FOK) != 0) trade.SetTypeFilling(ORDER_FILLING_FOK);

   else if((filling & SYMBOL_FILLING_IOC) != 0) trade.SetTypeFilling(ORDER_FILLING_IOC);

   else trade.SetTypeFilling(ORDER_FILLING_RETURN);



   LoadState();

   dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);

   EventSetTimer(ScanIntervalSec);



   int total = SymbolsTotal(true);

   for(int i = 0; i < total; i++) {

      string sym = SymbolName(i, true);

      if(SymbolInfoInteger(sym, SYMBOL_SELECT)) MarketBookAdd(sym);

   }



   Print("🎯 SENTINEL V12 - OBJECTIF 9/10 (ENTRÉES ULTRA-SÉLECTIVES)");

   Print("📡 Consensus=", MinConsensus, "/3 | Proba>=", MinProbability, " | TP=", TP_Ratio, " | Cooldown=", CooldownBetweenTrades, "s");

   return(INIT_SUCCEEDED);

}



void OnDeinit(const int reason)

{

   EventKillTimer();

   SaveState();

   int total = SymbolsTotal(true);

   for(int i = 0; i < total; i++) MarketBookRelease(SymbolName(i, true));

   Print("🛰️ SENTINEL V12 : Arrêt propre.");

}



void OnTimer()

{

   CheckDailyReset();

   if(!CheckDailyLimits()) return;



   CheckClosedTradesForApex();



   // EXPORT LIVE TICK DATA FOR PYTHON BOT

   ExportTicksToFile();
   
   // EXPORT STATUS (HEARTBEAT) FOR PYTHON BOT
   
   ExportStatusToFile();



   if(PositionsTotal() >= MaxConcurrentPositions) return;

   if(TimeCurrent() - lastTradeTime < CooldownBetweenTrades) return;



   int total = SymbolsTotal(true);

   for(int i = 0; i < total; i++) {

      string sym = SymbolName(i, true);

      if(!SymbolInfoInteger(sym, SYMBOL_SELECT)) continue;

      if(IsPositionOpenOnSymbol(sym)) continue;

      if(IsSymbolInCooldown(sym)) continue;



      double risk_multiplier = 1.0;

      int signal = AnalyzeSymbolConsensus(sym, risk_multiplier);



      if(signal != 0) {

         ExecuteSymbolSignal(sym, signal, risk_multiplier);

         lastTradeTime = TimeCurrent();

         break;

      }

      Sleep(250);

   }

}



//==================================================================//

//                   ANALYSE 9/10 : CONSENSUS TOTAL + ZONES RSI       //

//==================================================================//

int AnalyzeSymbolConsensus(string sym, double &out_multiplier)

{

   out_multiplier = 1.0;



   int hFast  = iMA(sym, PERIOD_CURRENT, 8, 0, MODE_EMA, PRICE_CLOSE);

   int hSlow  = iMA(sym, PERIOD_CURRENT, 21, 0, MODE_EMA, PRICE_CLOSE);

   int hRsi   = iRSI(sym, PERIOD_CURRENT, 14, PRICE_CLOSE);

   int hMacro = iMA(sym, PERIOD_CURRENT, 50, 0, MODE_EMA, PRICE_CLOSE);



   double ema8[], ema21[], rsi[], ema50[];

   ArraySetAsSeries(ema8, true);  ArraySetAsSeries(ema21, true);

   ArraySetAsSeries(rsi, true);  ArraySetAsSeries(ema50, true);



   if(CopyBuffer(hFast, 0, 0, 2, ema8)  < 2) return 0;

   if(CopyBuffer(hSlow, 0, 0, 2, ema21) < 2) return 0;

   if(CopyBuffer(hRsi, 0, 0, 2, rsi)   < 2) return 0;

   if(CopyBuffer(hMacro, 0, 0, 2, ema50) < 2) return 0;



   double buyVotes = 0, sellVotes = 0;

   double price = SymbolInfoDouble(sym, SYMBOL_BID);

   double rsiVal = rsi[0];



   // Vote 1 : court terme (EMA8 vs EMA21)

   if(ema8[0] > ema21[0]) buyVotes += 1.0; else sellVotes += 1.0;

   // Vote 2 : momentum (RSI)

   if(rsiVal > 50) buyVotes += 1.0; else sellVotes += 1.0;

   // Vote 3 : tendance macro (prix vs EMA50)

   if(price > ema50[0]) buyVotes += 1.0; else sellVotes += 1.0;



   // --- OBJECTIF 9/10 : consensus total (3/3) uniquement ---

   if(buyVotes < MinConsensus && sellVotes < MinConsensus) return 0;



   // --- Alignement des EMAs (tendance claire) ---

   if(RequireEmaStack) {

      if(buyVotes >= MinConsensus) {

         if(ema8[0] <= ema21[0] || ema21[0] <= ema50[0]) return 0;  // Pas de stack haussier

      }

      if(sellVotes >= MinConsensus) {

         if(ema8[0] >= ema21[0] || ema21[0] >= ema50[0]) return 0;  // Pas de stack baissier

      }

   }



   // --- Zone RSI : ne pas acheter suracheté, ne pas vendre survendu ---

   if(buyVotes >= MinConsensus) {

      if(rsiVal < RSI_BuyMin || rsiVal > RSI_BuyMax) return 0;   // BUY seulement RSI 45-65

   }

   if(sellVotes >= MinConsensus) {

      if(rsiVal < RSI_SellMin || rsiVal > RSI_SellMax) return 0;  // SELL seulement RSI 35-55

   }



   string techSig = (buyVotes >= MinConsensus) ? "BUY" : "SELL";



   string response = SendToCognitiveServer("EVALUATE", sym, techSig);

   if(response == "") return 0;



   string decision = ExtractJSONValue(response, "decision");

   out_multiplier = StringToDouble(ExtractJSONValue(response, "lot_multiplier"));

   current_prob   = StringToDouble(ExtractJSONValue(response, "probability"));

   current_spm    = StringToDouble(ExtractJSONValue(response, "spm_score"));

   current_imbalance = StringToDouble(ExtractJSONValue(response, "imbalance"));



   if(decision == "IGNORE") return 0;

   if(current_prob > 0 && current_prob < MinProbability) return 0;  // Confiance 70 % min



   if(out_multiplier < 0.1) out_multiplier = 0.1;

   return (decision == "BUY") ? 1 : -1;

}



//==================================================================//

//                     EXÉCUTION PAR SYMBOLE                         //

//==================================================================//

void ExecuteSymbolSignal(string sym, int signal, double risk_multiplier = 1.0)

{

   int hAtr = iATR(sym, PERIOD_CURRENT, 14);

   double atr_val[]; ArraySetAsSeries(atr_val, true);

   if(CopyBuffer(hAtr, 0, 0, 1, atr_val) < 1) return;



   double stopLevel = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) * SymbolInfoDouble(sym, SYMBOL_POINT);

   double spread   = SymbolInfoDouble(sym, SYMBOL_ASK) - SymbolInfoDouble(sym, SYMBOL_BID);

   double minReqDist = stopLevel + spread + (30 * SymbolInfoDouble(sym, SYMBOL_POINT));



   double slDist = atr_val[0] * SL_Multiplier;

   if(slDist < minReqDist) slDist = minReqDist;

   double tpDist = slDist * TP_Ratio;



   double lot = CalculateSymbolLotSize(sym, slDist) * risk_multiplier;



   double final_cap = MathMin(MAX_LOT_CAP, 0.15);

   if(lot > final_cap) lot = final_cap;



   double price = (signal == 1) ? SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);

   double sl = (signal == 1) ? price - slDist : price + slDist;

   double tp = (signal == 1) ? price + tpDist : price - tpDist;



   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);

   sl = NormalizeDouble(sl, digits);

   tp = NormalizeDouble(tp, digits);



   string comment = "SENTINEL V12 9/10";

   if((signal == 1 && trade.Buy(lot, sym, price, sl, tp, comment)) ||

      (signal == -1 && trade.Sell(lot, sym, price, sl, tp, comment)))

   {

      last_processed_ticket = trade.ResultOrder();

      Print("⚖️ V12 EXEC : ", sym, " ", (signal == 1 ? "BUY" : "SELL"), " (", lot, " lots)");

      todayTradeCount++; lastTradeTime = TimeCurrent(); SaveState();

      ExportStatusToFile();

   }

}



//==================================================================//

//              LOT SIZE ROBUSTE (SPÉCIAL XM)                        //

//==================================================================//

double CalculateSymbolLotSize(string sym, double slDistance)

{

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);

   double riskAmount = balance * (RiskPerTrade / 100.0);

   double tickValue = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);

   double tickSize  = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);



   if(tickValue <= 0 || slDistance <= 0) return SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);



   double lot = riskAmount / ((slDistance / tickSize) * tickValue);



   double minLot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);

   double maxLot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);

   double lotStep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);



   lot = MathMax(minLot, MathMin(maxLot, lot));

   lot = MathFloor(lot / lotStep) * lotStep;



   return NormalizeDouble(lot, 2);

}



//==================================================================//

//                     OUTILS ET GESTION                             //

//==================================================================//

void CheckClosedTradesForApex()

{

   if(!HistorySelect(TimeCurrent() - 86400, TimeCurrent())) return;

   for(int i = HistoryDealsTotal() - 1; i >= 0; i--) {

      ulong ticket = HistoryDealGetTicket(i);

      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != ActualMagicNumber) continue;

      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;



      ulong order_ticket = (ulong)HistoryDealGetInteger(ticket, DEAL_ORDER);



      bool already_done = false;

      for(int j = 0; j < 50; j++) if(processed_history[j] == order_ticket) { already_done = true; break; }



      if(order_ticket != 0 && !already_done) {

         double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);

         string sym = HistoryDealGetString(ticket, DEAL_SYMBOL);

         string type = (HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_SELL) ? "BUY" : "SELL";



         SendFeedbackToServer(order_ticket, sym, type, profit, current_spm, current_prob, current_imbalance);



         processed_history[processed_ptr] = order_ticket;

         processed_ptr = (processed_ptr + 1) % 50;



         ExportStatusToFile();

         break;

      }

   }

}



bool IsSymbolInCooldown(string sym)

{

   if(!HistorySelect(TimeCurrent() - (SymbolCooldownMinutes * 60), TimeCurrent())) return false;

   for(int i = HistoryDealsTotal() - 1; i >= 0; i--) {

      ulong ticket = HistoryDealGetTicket(i);

      if(HistoryDealGetString(ticket, DEAL_SYMBOL) == sym && HistoryDealGetInteger(ticket, DEAL_MAGIC) == ActualMagicNumber)

         return true;

   }

   return false;

}



bool IsPositionOpenOnSymbol(string sym)

{

   for(int i = PositionsTotal() - 1; i >= 0; i--) {

      if(PositionSelectByTicket(PositionGetTicket(i))) {

         if(PositionGetInteger(POSITION_MAGIC) == ActualMagicNumber && PositionGetString(POSITION_SYMBOL) == sym)

            return true;

      }

   }

   return false;

}



bool CheckDailyLimits()

{

   if(AccountInfoDouble(ACCOUNT_BALANCE) < dailyStartBalance * (1.0 - MaxDailyLossPerc / 100.0)) return false;

   if(todayTradeCount >= MaxTradesPerDay) return false;

   return true;

}



void CheckDailyReset()

{

   datetime today = TimeCurrent() - (TimeCurrent() % 86400);

   if(today != todayDate) {

      todayTradeCount = 0;

      dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);

      todayDate = today;

      SaveState();

   }

}



void SaveState()

{

   int h = FileOpen(stateFile, FILE_WRITE | FILE_BIN);

   if(h != INVALID_HANDLE) {

      FileWriteInteger(h, todayTradeCount);

      FileWriteDouble(h, dailyStartBalance);

      FileWriteInteger(h, (int)todayDate);

      FileClose(h);

   }

}



void LoadState()

{

   int h = FileOpen(stateFile, FILE_READ | FILE_BIN);

   if(h != INVALID_HANDLE) {

      todayTradeCount = FileReadInteger(h);

      dailyStartBalance = FileReadDouble(h);

      todayDate = (datetime)FileReadInteger(h);

      FileClose(h);

   }

}



void ExportStatusToFile()

{

   int h = FileOpen("status.json", FILE_WRITE | FILE_TXT | FILE_ANSI);

   if(h == INVALID_HANDLE) return;



   string json = "{";

   json += StringFormat("\"balance\":%.2f,", AccountInfoDouble(ACCOUNT_BALANCE));

   json += StringFormat("\"equity\":%.2f,", AccountInfoDouble(ACCOUNT_EQUITY));

   json += StringFormat("\"trades_today\":%d,", todayTradeCount);

   json += "\"positions\":[";



   bool first = true;

   for(int i = 0; i < PositionsTotal(); i++) {

      if(PositionSelectByTicket(PositionGetTicket(i))) {

         if(PositionGetInteger(POSITION_MAGIC) == ActualMagicNumber) {

            if(!first) json += ",";

            json += "{";

            json += StringFormat("\"ticket\":%lld,", PositionGetInteger(POSITION_TICKET));

            json += StringFormat("\"symbol\":\"%s\",", PositionGetString(POSITION_SYMBOL));

            json += StringFormat("\"type\":\"%s\",", (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL"));

            json += StringFormat("\"volume\":%.2f,", PositionGetDouble(POSITION_VOLUME));

            json += StringFormat("\"price\":%.5f,", PositionGetDouble(POSITION_PRICE_OPEN));

            json += StringFormat("\"profit\":%.2f", PositionGetDouble(POSITION_PROFIT));

            json += "}";

            first = false;

         }

      }

   }

   json += "]}";



   FileWriteString(h, json);

   FileClose(h);

}



//==================================================================//
//              EXPORT LIVE TICK & CANDLE DATA FOR PYTHON            //
//==================================================================//
void ExportTicksToFile()
{
   int h = FileOpen("ticks_v3.json", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE) return;

   string json = "{";
   json += StringFormat("\"t\":%lld,", TimeCurrent());
   json += "\"ticks\":{";

   int total = SymbolsTotal(true);
   bool first = true;

   for(int i = 0; i < total; i++) {
      string sym = SymbolName(i, true);
      if(!SymbolInfoInteger(sym, SYMBOL_SELECT)) continue;

      double price = SymbolInfoDouble(sym, SYMBOL_BID);
      if(price > 0) {
         if(!first) json += ",";
         
         // Fetch last 3 M5 candles for Price Action
         MqlRates rates[];
         ArraySetAsSeries(rates, true);
         string m5_data = "[]";
         
         if(CopyRates(sym, PERIOD_M5, 0, 3, rates) == 3) {
             m5_data = StringFormat("[{\"o\":%f,\"h\":%f,\"l\":%f,\"c\":%f}, {\"o\":%f,\"h\":%f,\"l\":%f,\"c\":%f}, {\"o\":%f,\"h\":%f,\"l\":%f,\"c\":%f}]",
                 rates[2].open, rates[2].high, rates[2].low, rates[2].close,
                 rates[1].open, rates[1].high, rates[1].low, rates[1].close,
                 rates[0].open, rates[0].high, rates[0].low, rates[0].close
             );
         }
         
         json += StringFormat("\"%s\":{\"bid\":%.5f, \"m5\":%s}", sym, price, m5_data);
         first = false;
      }
   }
   json += "}}";

   FileWriteString(h, json);
   FileClose(h);
}
