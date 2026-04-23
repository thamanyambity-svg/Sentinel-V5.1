//|         ARCHITECTURE : LE TRIUMVIRAT QUANTIQUE (V11.4)           |
//|    [VANGUARD: Sémantique] [NEXUS: Mémoire] [SOVEREIGN: Arbitre]  |
//|                 [APEX: ÉVOLUTION & AUTO-CORRECTION]              |
//|        >>>> MULTI-STRIKER : EXÉCUTION SIMULTANÉE <<<<            |
//+------------------------------------------------------------------+
#property copyright "Ambity Project"
#property version   "11.40"
#property strict

#include <Trade\Trade.mqh>
#include <Sentinel_Socket.mqh>

CTrade trade;

//==================================================================//
//                        CONFIGURATION                              //
//==================================================================//

input group "=== SYSTÈME MULTI-STRIKER (SÉCURISÉ) ==="
input long   BASE_MAGIC_NUMBER= 102796;    
input int    ScanIntervalSec  = 15;        // Respiration augmentée
input bool   ScanMarketWatch  = true;      
input int    MaxConcurrentPositions = 3;   // LIMITE CRUCIALE : Pas plus de 3 positions simultanées

input group "=== GOUVERNANCE DU RISQUE (CONSERVATEUR) ==="
input double RiskPerTrade     = 0.5;       // Risque divisé par 2
input double MAX_LOT_CAP      = 0.15;      // Cap drastique pour éviter les "scandales"
input double MaxDailyLossPerc = 3.0;       
input int    MaxTradesPerDay  = 20;        
input int    CooldownBetweenTrades = 60;   // 1 minute entre deux ouvertures globales
input int    SymbolCooldownMinutes = 60;   // 1 heure avant de retoucher le même symbole après clôture

input group "=== PARAMÈTRES SOVEREIGN ==="
input double SL_Multiplier    = 1.5;       
input double TP_Ratio         = 2.5;       
input double MinConsensus     = 2.0;       

//==================================================================//
//                   CONTEXTE TACTIQUE (POUR APEX)                   //
//==================================================================//
double current_spm = 0;
double current_prob = 0;
double current_imbalance = 0;
ulong  processed_history[50]; // Buffer pour éviter la répétition des feedbacks
int    processed_ptr = 0;
ulong  last_processed_ticket = 0;

//==================================================================//
//                        VARIABLES INTERNES                         //
//==================================================================//
int todayTradeCount = 0;
datetime todayDate = 0;
datetime lastTradeTime = 0;
double dailyStartBalance = 0;
string stateFile = "Sentinel_V11_Safe.dat";
long ActualMagicNumber = 0;

//==================================================================//
//                          INITIALISATION                           //
//==================================================================//
int OnInit()
{
   ActualMagicNumber = BASE_MAGIC_NUMBER;
   trade.SetExpertMagicNumber(ActualMagicNumber);
   trade.SetDeviationInPoints(50);
   
   uint filling=(uint)SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0) trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0) trade.SetTypeFilling(ORDER_FILLING_IOC);
   else trade.SetTypeFilling(ORDER_FILLING_RETURN);
   
   LoadState();
   dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   EventSetTimer(ScanIntervalSec);
   
   // --- ACTIVATION DE LA VISION QUANTUM (MARKET DEPTH) ---
   int total = SymbolsTotal(true);
   for(int i=0; i<total; i++) {
      string sym = SymbolName(i, true);
      if(SymbolInfoInteger(sym, SYMBOL_SELECT)) {
         MarketBookAdd(sym);
      }
   }
   
   Print("🌩️ SENTINEL V11.4 - MODE MULTI-STRIKER (LIQUIDITY AWARE) ACTIVÉ");
   Print("📡 Analyse et exécution simultanée avec Vision Bookmap intégrée.");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   SaveState();
   int total = SymbolsTotal(true);
   for(int i=0; i<total; i++) MarketBookRelease(SymbolName(i, true));
   Print("🛰️ SENTINEL : Systèmes mis en veille.");
}

void OnTimer()
{
   CheckDailyReset();
   if(!CheckDailyLimits()) return;
   
   CheckClosedTradesForApex();

   // --- VÉRIFICATION GLOBALE DE LA CAPACITÉ ---
   if(PositionsTotal() >= MaxConcurrentPositions) return;
   if(TimeCurrent() - lastTradeTime < CooldownBetweenTrades) return;

   int total = SymbolsTotal(true);
   for(int i=0; i<total; i++) 
   {
      string sym = SymbolName(i, true);
      if(!SymbolInfoInteger(sym, SYMBOL_SELECT)) continue;
      
      // Une seule position par actif
      if(IsPositionOpenOnSymbol(sym)) continue;
      
      // Vérification Cooldown par symbole après clôture
      if(IsSymbolInCooldown(sym)) continue;

      double risk_multiplier = 1.0;
      int signal = AnalyzeSymbolConsensus(sym, risk_multiplier);
      
      if(signal != 0) {
         ExecuteSymbolSignal(sym, signal, risk_multiplier);
         lastTradeTime = TimeCurrent();
         break; // Un seul trade par cycle OnTimer pour la stabilité
      }
      
      // Micro-pause pour la pile réseau
      Sleep(250);
   }
}

//==================================================================//
//                   ANALYSE TECHNIQUE PAR SYMBOLE                   //
//==================================================================//
int AnalyzeSymbolConsensus(string sym, double &out_multiplier)
{
   out_multiplier = 1.0;
   
   int hFast = iMA(sym, PERIOD_CURRENT, 8, 0, MODE_EMA, PRICE_CLOSE);
   int hSlow = iMA(sym, PERIOD_CURRENT, 21, 0, MODE_EMA, PRICE_CLOSE);
   int hRsi  = iRSI(sym, PERIOD_CURRENT, 14, PRICE_CLOSE);
   int hMacro= iMA(sym, PERIOD_CURRENT, 50, 0, MODE_EMA, PRICE_CLOSE);
   
   double ema8[], ema21[], rsi[], ema50[];
   ArraySetAsSeries(ema8, true); ArraySetAsSeries(ema21, true);
   ArraySetAsSeries(rsi, true); ArraySetAsSeries(ema50, true);

   if(CopyBuffer(hFast, 0, 0, 2, ema8) < 2) return 0;
   if(CopyBuffer(hSlow, 0, 0, 2, ema21) < 2) return 0;
   if(CopyBuffer(hRsi, 0, 0, 2, rsi) < 2) return 0;
   if(CopyBuffer(hMacro,0, 0, 2, ema50) < 2) return 0;

   double buyVotes = 0, sellVotes = 0;
   double price = SymbolInfoDouble(sym, SYMBOL_BID);

   if(ema8[0] > ema21[0]) buyVotes += 1.0; else sellVotes += 1.0;
   if(rsi[0] > 50) buyVotes += 0.5; else sellVotes += 0.5;
   if(price > ema50[0]) buyVotes += 1.0; else sellVotes += 1.0;

   if(buyVotes >= MinConsensus || sellVotes >= MinConsensus) {
      string techSig = (buyVotes >= MinConsensus) ? "BUY" : "SELL";
      
      string response = SendToCognitiveServer("EVALUATE", sym, techSig);
      if(response == "") return 0; // Erreur serveur
      
      string decision = ExtractJSONValue(response, "decision");
      out_multiplier = StringToDouble(ExtractJSONValue(response, "lot_multiplier"));
      current_prob = StringToDouble(ExtractJSONValue(response, "probability"));
      current_spm = StringToDouble(ExtractJSONValue(response, "spm_score"));
      current_imbalance = StringToDouble(ExtractJSONValue(response, "imbalance"));
      
      if(decision == "IGNORE") return 0;
      
      if(out_multiplier < 0.1) out_multiplier = 0.1;
      return (decision == "BUY") ? 1 : -1;
   }
   return 0;
}

//==================================================================//
//                     EXÉCUTION PAR SYMBOLE                         //
//==================================================================//
void ExecuteSymbolSignal(string sym, int signal, double risk_multiplier = 1.0)
{
   int hAtr = iATR(sym, PERIOD_CURRENT, 14);
   double atr_val[]; ArraySetAsSeries(atr_val, true);
   if(CopyBuffer(hAtr, 0, 0, 1, atr_val) < 1) return;
   
   // --- CALCUL SÉCURISÉ DES STOPS ---
   double stopLevel = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) * SymbolInfoDouble(sym, SYMBOL_POINT);
   double spread = SymbolInfoDouble(sym, SYMBOL_ASK) - SymbolInfoDouble(sym, SYMBOL_BID);
   double minReqDist = stopLevel + spread + (30 * SymbolInfoDouble(sym, SYMBOL_POINT)); 
   
   double slDist = atr_val[0] * SL_Multiplier;
   if(slDist < minReqDist) slDist = minReqDist;
   double tpDist = slDist * TP_Ratio;
   
   double lot = CalculateSymbolLotSize(sym, slDist) * risk_multiplier;
   
   // --- SÉCURITÉ ABSOLUE : CAP DUR À 0.15 ---
   // On ignore l'input utilisateur s'il est trop haut pour éviter les "scandales"
   double final_cap = MathMin(MAX_LOT_CAP, 0.15); 
   if(lot > final_cap) lot = final_cap;

   double price = (signal == 1) ? SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);
   double sl = (signal == 1) ? price - slDist : price + slDist;
   double tp = (signal == 1) ? price + tpDist : price - tpDist;

   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);

   if((signal == 1 && trade.Buy(lot, sym, price, sl, tp, "SENTINEL MULTI")) || 
      (signal == -1 && trade.Sell(lot, sym, price, sl, tp, "SENTINEL MULTI")))
   {
      last_processed_ticket = trade.ResultOrder();
      Print("⚖️ MULTI-STRIKER EXEC : ", sym, " (", lot, " lots)");
      todayTradeCount++; lastTradeTime = TimeCurrent(); SaveState();
      ExportStatusToFile(); // Mise à jour immédiate
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
    
    // --- NORMALISATION STRICTE XM ---
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
   if(HistorySelect(TimeCurrent()-86400, TimeCurrent())) {
      for(int i=HistoryDealsTotal()-1; i>=0; i--) {
         ulong ticket = HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == ActualMagicNumber && HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT) {
            ulong order_ticket = (ulong)HistoryDealGetInteger(ticket, DEAL_ORDER);
            
            // Vérification si déjà traité via le buffer circulaire
            bool already_done = false;
            for(int j=0; j<50; j++) if(processed_history[j] == order_ticket) { already_done = true; break; }
            
            if(order_ticket != 0 && !already_done) {
               double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
               string sym = HistoryDealGetString(ticket, DEAL_SYMBOL);
               string type = (HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_SELL) ? "BUY" : "SELL";
               
               SendFeedbackToServer(order_ticket, sym, type, profit, current_spm, current_prob, current_imbalance);
               
               // Enregistrement dans l'historique circulaire
               processed_history[processed_ptr] = order_ticket;
               processed_ptr = (processed_ptr + 1) % 50;
               
               ExportStatusToFile();
               break; 
            }
         }
      }
   }
}

bool IsSymbolInCooldown(string sym)
{
   if(HistorySelect(TimeCurrent() - (SymbolCooldownMinutes * 60), TimeCurrent())) {
      for(int i=HistoryDealsTotal()-1; i>=0; i--) {
         ulong ticket = HistoryDealGetTicket(i);
         if(HistoryDealGetString(ticket, DEAL_SYMBOL) == sym && HistoryDealGetInteger(ticket, DEAL_MAGIC) == ActualMagicNumber) {
            return true; // Trop tôt pour re-trader ce symbole
         }
      }
   }
   return false;
}

bool IsPositionOpenOnSymbol(string sym) { 
   for(int i=PositionsTotal()-1; i>=0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i))) {
         if(PositionGetInteger(POSITION_MAGIC) == ActualMagicNumber && PositionGetString(POSITION_SYMBOL) == sym) return true;
      }
   }
   return false; 
}

bool CheckDailyLimits() {
   if(AccountInfoDouble(ACCOUNT_BALANCE) < dailyStartBalance * (1.0 - MaxDailyLossPerc/100.0)) return false;
   if(todayTradeCount >= MaxTradesPerDay) return false;
   return true;
}

void CheckDailyReset() {
   datetime today = TimeCurrent() - (TimeCurrent() % 86400);
   if(today != todayDate) { todayTradeCount = 0; dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE); todayDate = today; SaveState(); }
}

void SaveState() { int h = FileOpen(stateFile, FILE_WRITE|FILE_BIN); if(h != INVALID_HANDLE) { FileWriteInteger(h, todayTradeCount); FileWriteDouble(h, dailyStartBalance); FileWriteInteger(h, (int)todayDate); FileClose(h); }}
void LoadState() { int h = FileOpen(stateFile, FILE_READ|FILE_BIN); if(h != INVALID_HANDLE) { todayTradeCount = FileReadInteger(h); dailyStartBalance = FileReadDouble(h); todayDate = (datetime)FileReadInteger(h); FileClose(h); }}

//+------------------------------------------------------------------+
//| Exportation du statut pour le Moniteur Telegram/Discord          |
//+------------------------------------------------------------------+
void ExportStatusToFile()
{
   string filename = "status.json";
   int h = FileOpen(filename, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   
   string json = "{";
   json += StringFormat("\"balance\":%.2f,", AccountInfoDouble(ACCOUNT_BALANCE));
   json += StringFormat("\"equity\":%.2f,", AccountInfoDouble(ACCOUNT_EQUITY));
   json += StringFormat("\"trades_today\":%d,", todayTradeCount);
   json += "\"positions\":[";
   
   bool first = true;
   for(int i=0; i<PositionsTotal(); i++) {
      if(PositionSelectByTicket(PositionGetTicket(i))) {
         if(PositionGetInteger(POSITION_MAGIC) == ActualMagicNumber) {
            if(!first) json += ",";
            json += "{";
            json += StringFormat("\"ticket\":%lld,", PositionGetInteger(POSITION_TICKET));
            json += StringFormat("\"symbol\":\"%s\",", PositionGetString(POSITION_SYMBOL));
            json += StringFormat("\"type\":\"%s\",", (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"BUY":"SELL"));
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
