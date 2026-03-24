//+------------------------------------------------------------------+
//|                     AladdinPro_V719_TrapHunter.mq5               |
//|              Aladdin Pro V7.19 — Trap Hunter                     |
//|        Architecture : V7 Risk Core + Python Bridge (Sentinel)    |
//|        V7.19 : ComputeWickImbalance() — Trap Hunter              |
//|                sans MarketBookGet (Compatible Brokers Retail)     |
//|                        Copyright 2026, Ambity Project            |
//+------------------------------------------------------------------+
#property copyright "Ambity Project"
#property version   "7.19"
#property strict
#property description "Aladdin Pro V7.19 — Trap Hunter | Wick Rejection Imbalance | Python Sentinel Bridge"

#include <Trade\Trade.mqh>
CTrade trade;

//==================================================================//
//                        CONFIGURATION                              //
//==================================================================//

input group "=== CORE SYSTEM ==="
input long   MAGIC_NUMBER          = 776719;
input int    TimerSeconds          = 15;
input bool   EnableHUD             = true;
input bool   SaveStateOnDisk       = true;

input group "=== RISK ENGINE (V7) ==="
input double MaxDailyDrawdownPercent = 5.0;
input double MaxRiskPerTradePercent  = 1.5;
input double MaxExposurePercent      = 6.0;
input double MaxLotSize              = 2.0;

input group "=== EXECUTION FILTERS ==="
input double MaxAllowedSpreadPoints  = 300;

input group "=== TAKE PROFIT & STOPS ==="
input double TakeProfitUSD         = 1.50;
input bool   EnableAutoBreakeven   = true;
input double BreakevenTriggerProfit = 1.50;
input bool   EnableTrailingStop    = true;
input double TrailingStartPoints   = 500;
input double TrailingStepPoints    = 250;

input group "=== STRATEGY ==="
input bool   EnableAIBridge        = true;
input double MinAIConfidence       = 0.70;

input group "=== TIMEFRAMES ==="
ENUM_TIMEFRAMES TF_Entry           = PERIOD_M5;   // Timeframe pour signaux d'entrée
ENUM_TIMEFRAMES TF_Imbalance       = PERIOD_M5;   // Timeframe pour ComputeWickImbalance

input group "=== TESTING & EXPORT ==="
input bool   TestingMode           = false;
input string TradeSymbol           = "XAUUSD";
input string ExportSymbols         = "XAUUSD,EURUSD,BTCUSD";

//==================================================================//
//                         STRUCTURES                                //
//==================================================================//

struct TradeIndicators
{
    ulong   ticket;
    string  symbol;
    string  tech_signal;
    double  finbert_score;
    double  imbalance;        // V7.19 — Wick Rejection imbalance au moment de l'entrée
    double  entry_price;
    datetime entry_time;
    double  profit;
    bool    closed;
};

//==================================================================//
//                    VARIABLES GLOBALES                             //
//==================================================================//

string tickFile          = "ticks_v3.json";
string tickFileTemp      = "ticks_v3_temp.json";
string tradeHistoryFile  = "trade_history.json";
string stateFile         = "aladdin_v719_state.dat";

TradeIndicators trackedTrades[200];
int             trackedCount = 0;

double  dailyStartBalance  = 0;
double  dailyHighWaterMark = 0;
bool    tradingEnabled     = true;
int     todayTradeCount    = 0;
datetime todayDate         = 0;
datetime lastTradeTime     = 0;

//==================================================================//
//          ComputeWickImbalance — V7.19 Trap Hunter                 //
//  Approxime l'imbalance acheteurs/vendeurs via les mèches de       //
//  bougie (Wick Rejection). Fonctionne sur tous brokers retail.     //
//  Résultat : +1.0 (pression acheteuse) à -1.0 (pression vendeuse) //
//                                                                    //
//  Interprétation des mèches :                                       //
//   mèche haute (wick_up)  → pression VENDEUSE (vendeurs ont rejeté //
//                             la hausse et ramené le prix vers le    //
//                             corps → dominance vendeur en haut)     //
//   mèche basse (wick_down) → pression ACHETEUSE (acheteurs ont     //
//                             rejeté la baisse et remonté le prix    //
//                             → dominance acheteur en bas)           //
//==================================================================//
double ComputeWickImbalance(string sym, ENUM_TIMEFRAMES tf)
{
    double o[3], h[3], l[3], c[3];
    if(CopyOpen (sym, tf, 1, 3, o) < 3) return 0.0;
    if(CopyHigh (sym, tf, 1, 3, h) < 3) return 0.0;
    if(CopyLow  (sym, tf, 1, 3, l) < 3) return 0.0;
    if(CopyClose(sym, tf, 1, 3, c) < 3) return 0.0;

    double buy_pressure = 0.0, sell_pressure = 0.0;
    for(int i = 0; i < 3; i++)
    {
        double body_top    = MathMax(o[i], c[i]);
        double body_bottom = MathMin(o[i], c[i]);
        double wick_up     = h[i] - body_top;    // mèche haute → pression vendeuse
        double wick_down   = body_bottom - l[i]; // mèche basse → pression acheteuse
        double range       = h[i] - l[i];
        if(range > 1e-10)
        {
            sell_pressure += wick_up   / range;
            buy_pressure  += wick_down / range;
        }
    }
    double total = buy_pressure + sell_pressure;
    if(total < 1e-10) return 0.0;
    // Normalisé entre -1.0 et +1.0
    return (buy_pressure - sell_pressure) / total;
}

//==================================================================//
//                    ExportTickData_V7                              //
//  Exporte les ticks des symboles surveillés dans ticks_v3.json     //
//  V7.19 : Inclut le champ "imbalance" (Wick Rejection)             //
//==================================================================//
void ExportTickData_V7()
{
    static datetime lastExport = 0;
    if(TimeCurrent() - lastExport < 2) return;
    lastExport = TimeCurrent();

    string symbols[];
    int count = StringSplit(ExportSymbols, ',', symbols);

    string json = "[";
    bool first = true;
    for(int i = 0; i < count; i++)
    {
        StringTrimLeft(symbols[i]);
        StringTrimRight(symbols[i]);
        if(!SymbolInfoInteger(symbols[i], SYMBOL_SELECT)) continue;

        double bid    = SymbolInfoDouble(symbols[i], SYMBOL_BID);
        double ask    = SymbolInfoDouble(symbols[i], SYMBOL_ASK);
        double spread = ask - bid;
        int    digits = (int)SymbolInfoInteger(symbols[i], SYMBOL_DIGITS);

        // Calcul RSI et ADX pour active_strat
        int hRsi = iRSI(symbols[i], TF_Entry, 14, PRICE_CLOSE);
        int hAdx = iADX(symbols[i], TF_Entry, 14);
        double rsi_buf[1], adx_buf[1];
        double rsi_val = 50.0, adx_val = 0.0;
        if(CopyBuffer(hRsi, 0, 0, 1, rsi_buf) > 0) rsi_val = rsi_buf[0];
        if(CopyBuffer(hAdx, 0, 0, 1, adx_buf) > 0) adx_val = adx_buf[0];
        string active_strat = (adx_val > 35 && rsi_val > 50) ? "MOM_BUY" :
                              (adx_val > 35 && rsi_val < 50) ? "MOM_SELL" : "WAIT";

        // Calculer l'imbalance via wick rejection (V7.19 Trap Hunter)
        double imb = ComputeWickImbalance(symbols[i], TF_Imbalance);

        if(!first) json += ",";
        first = false;
        json += "{\"sym\":\"" + symbols[i] + "\""
              + ",\"bid\":"    + DoubleToString(bid, digits)
              + ",\"ask\":"    + DoubleToString(ask, digits)
              + ",\"spread\":" + DoubleToString(spread, digits)
              + ",\"rsi\":"    + DoubleToString(rsi_val, 2)
              + ",\"adx\":"    + DoubleToString(adx_val, 2)
              + ",\"active_strat\":\"" + active_strat + "\""
              + ",\"imbalance\":" + DoubleToString(imb, 3)
              + ",\"t\":" + IntegerToString((int)TimeCurrent())
              + "}";

        PrintFormat("[INFO][TICK] %s | bid=%.*f | imbalance=%.3f",
                    symbols[i], digits, bid, imb);
    }
    json += "]";

    int h = FileOpen(tickFileTemp, FILE_WRITE | FILE_ANSI | FILE_TXT);
    if(h != INVALID_HANDLE)
    {
        FileWriteString(h, json);
        FileClose(h);
        if(FileIsExist(tickFile)) FileDelete(tickFile);
        FileMove(tickFileTemp, 0, tickFile, 0);
    }
}

//==================================================================//
//                     SaveTradeIndicators                           //
//  Enregistre les indicateurs au moment de l'ouverture du trade     //
//  V7.19 : Inclut le champ imbalance (Wick Rejection)               //
//  imbalance passé en paramètre depuis ProcessBridgeCommand pour    //
//  garantir la cohérence avec la valeur utilisée à la décision.     //
//==================================================================//
void SaveTradeIndicators(ulong ticket, string sym, string tech_signal,
                         double finbert_score, double entry_price,
                         double imb_at_entry)
{
    if(trackedCount >= 200) return;

    trackedTrades[trackedCount].ticket        = ticket;
    trackedTrades[trackedCount].symbol        = sym;
    trackedTrades[trackedCount].tech_signal   = tech_signal;
    trackedTrades[trackedCount].finbert_score = finbert_score;
    trackedTrades[trackedCount].imbalance     = imb_at_entry;
    trackedTrades[trackedCount].entry_price   = entry_price;
    trackedTrades[trackedCount].entry_time    = TimeCurrent();
    trackedTrades[trackedCount].profit        = 0.0;
    trackedTrades[trackedCount].closed        = false;
    trackedCount++;

    PrintFormat("[INFO][TRACK] %s | tech=%s | finbert=%.3f | imbalance=%.3f",
                sym, tech_signal, finbert_score, imb_at_entry);
}

//==================================================================//
//                     ExportTradeHistory_V7                         //
//  Exporte l'historique des trades dans trade_history.json          //
//  V7.19 : Inclut le champ imbalance pour l'apprentissage NEXUS     //
//==================================================================//
void ExportTradeHistory_V7()
{
    // Mise à jour des profits sur les trades fermés
    if(HistorySelect(TimeCurrent() - 86400 * 7, TimeCurrent()))
    {
        for(int i = 0; i < trackedCount; i++)
        {
            if(trackedTrades[i].closed) continue;
            ulong ticket = trackedTrades[i].ticket;
            if(HistoryDealSelect(ticket))
            {
                trackedTrades[i].profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
                trackedTrades[i].closed = true;
            }
        }
    }

    string json = "[";
    bool first = true;
    for(int i = 0; i < trackedCount; i++)
    {
        double entryImbalance = trackedTrades[i].imbalance;
        if(!first) json += ",";
        first = false;
        json += "{"
              + "\"ticket\":"        + IntegerToString((long)trackedTrades[i].ticket)
              + ",\"sym\":\""        + trackedTrades[i].symbol + "\""
              + ",\"tech_signal\":\"" + trackedTrades[i].tech_signal + "\""
              + ",\"finbert_score\":" + DoubleToString(trackedTrades[i].finbert_score, 4)
              + ",\"imbalance\":"    + DoubleToString(entryImbalance, 3)
              + ",\"entry_price\":"  + DoubleToString(trackedTrades[i].entry_price, 5)
              + ",\"entry_time\":"   + IntegerToString((int)trackedTrades[i].entry_time)
              + ",\"profit\":"       + DoubleToString(trackedTrades[i].profit, 2)
              + ",\"closed\":"       + (trackedTrades[i].closed ? "true" : "false")
              + "}";
    }
    json += "]";

    int h = FileOpen(tradeHistoryFile, FILE_WRITE | FILE_ANSI | FILE_TXT);
    if(h != INVALID_HANDLE)
    {
        FileWriteString(h, json);
        FileClose(h);
    }
}

//==================================================================//
//                        RISK ENGINE (V7)                           //
//==================================================================//
bool CheckDailyLimits()
{
    datetime now = TimeCurrent();
    MqlDateTime dt_now, dt_today;
    TimeToStruct(now, dt_now);
    TimeToStruct(todayDate, dt_today);
    if(dt_now.day != dt_today.day || dt_now.mon != dt_today.mon)
    {
        todayDate          = now;
        todayTradeCount    = 0;
        dailyStartBalance  = AccountInfoDouble(ACCOUNT_BALANCE);
        dailyHighWaterMark = dailyStartBalance;
        tradingEnabled     = true;
    }

    double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    if(equity > dailyHighWaterMark) dailyHighWaterMark = equity;

    double dd = (dailyHighWaterMark > 0) ?
                ((dailyHighWaterMark - equity) / dailyHighWaterMark) * 100.0 : 0.0;
    if(!TestingMode && dd > MaxDailyDrawdownPercent)
    {
        if(tradingEnabled)
        {
            tradingEnabled = false;
            PrintFormat("🛑 RISK HALT: Drawdown journalier %.2f%% > %.2f%%", dd, MaxDailyDrawdownPercent);
        }
        return false;
    }
    return tradingEnabled;
}

double CalculateLotSize(string sym, double slDistance)
{
    double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
    double riskAmount = balance * (MaxRiskPerTradePercent / 100.0);
    double tickValue  = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
    double tickSize   = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
    if(tickValue <= 0 || slDistance <= 0 || tickSize <= 0)
        return SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);

    double lot     = riskAmount / ((slDistance / tickSize) * tickValue);
    double minLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
    double maxLot  = MathMin(SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX), MaxLotSize);
    double lotStep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);

    lot = MathMax(minLot, MathMin(maxLot, lot));
    lot = MathFloor(lot / lotStep) * lotStep;
    return NormalizeDouble(lot, 2);
}

bool CheckSpread(string sym)
{
    double spread = (SymbolInfoDouble(sym, SYMBOL_ASK) - SymbolInfoDouble(sym, SYMBOL_BID))
                    / SymbolInfoDouble(sym, SYMBOL_POINT);
    return spread <= MaxAllowedSpreadPoints;
}

//==================================================================//
//                    BRIDGE PYTHON (Lecture JSON)                   //
//==================================================================//
string ReadCommandFile(string path)
{
    int h = FileOpen(path, FILE_READ | FILE_ANSI | FILE_TXT);
    if(h == INVALID_HANDLE) return "";
    string content = "";
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);
    return content;
}

string ExtractJSONValue(string src, string key)
{
    int kp = StringFind(src, "\"" + key + "\"");
    if(kp == -1) return "";
    int cp = StringFind(src, ":", kp);
    if(cp == -1) return "";
    int start = StringFind(src, "\"", cp);
    if(start == -1)
    {
        start = cp + 1;
        // Ignorer les espaces
        while(start < StringLen(src) && StringGetCharacter(src, start) == ' ') start++;
        int end_c = StringFind(src, ",", start);
        int end_b = StringFind(src, "}", start);
        int end   = (end_c != -1 && end_b != -1) ? (int)MathMin(end_c, end_b)
                  : (end_c != -1 ? end_c : end_b);
        if(end == -1) return "";
        return StringSubstr(src, start, end - start);
    }
    int end = StringFind(src, "\"", start + 1);
    if(end == -1) return "";
    return StringSubstr(src, start + 1, end - start - 1);
}

void ProcessBridgeCommand(string json)
{
    if(StringLen(json) < 5) return;

    string decision   = ExtractJSONValue(json, "decision");
    string sym        = ExtractJSONValue(json, "asset");
    double multiplier = StringToDouble(ExtractJSONValue(json, "lot_multiplier"));
    double finbert    = StringToDouble(ExtractJSONValue(json, "spm_score"));

    if(decision == "IGNORE" || decision == "") return;
    if(sym == "") sym = TradeSymbol;
    if(multiplier < 0.1) multiplier = 1.0;

    if(!CheckSpread(sym)) { Print("⛔ Spread trop large sur ", sym); return; }

    int hAtr = iATR(sym, TF_Entry, 14);
    double atr_buf[1];
    if(CopyBuffer(hAtr, 0, 0, 1, atr_buf) < 1) return;
    double atrVal = atr_buf[0];

    double slDist = atrVal * 1.5;
    double tpDist = slDist * 2.5;
    double lot    = CalculateLotSize(sym, slDist) * multiplier;
    double price  = (decision == "BUY") ? SymbolInfoDouble(sym, SYMBOL_ASK)
                                        : SymbolInfoDouble(sym, SYMBOL_BID);
    int digits    = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
    double sl     = NormalizeDouble((decision == "BUY") ? price - slDist : price + slDist, digits);
    double tp     = NormalizeDouble((decision == "BUY") ? price + tpDist : price - tpDist, digits);

    // Calculer l'imbalance une seule fois pour la décision ET le tracking
    double imb_now = ComputeWickImbalance(sym, TF_Imbalance);

    bool ok = (decision == "BUY") ? trade.Buy(lot, sym, price, sl, tp, "ALADDIN V7.19")
                                  : trade.Sell(lot, sym, price, sl, tp, "ALADDIN V7.19");
    if(ok)
    {
        ulong ticket = trade.ResultOrder();
        PrintFormat("✅ EXEC %s | %s | %.2f lots | SL=%.5f | TP=%.5f | imbalance=%.3f",
                    decision, sym, lot, sl, tp, imb_now);
        SaveTradeIndicators(ticket, sym, decision, finbert, price, imb_now);
        todayTradeCount++;
        lastTradeTime = TimeCurrent();
        ExportTradeHistory_V7();
    }
}

//==================================================================//
//                        GESTION POSITIONS                          //
//==================================================================//
void ManagePositions()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(!PositionSelectByTicket(ticket)) continue;
        if(PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;

        string sym    = PositionGetString(POSITION_SYMBOL);
        int    ptype  = (int)PositionGetInteger(POSITION_TYPE);
        double pOpen  = PositionGetDouble(POSITION_PRICE_OPEN);
        double pCur   = (ptype == POSITION_TYPE_BUY) ? SymbolInfoDouble(sym, SYMBOL_BID)
                                                     : SymbolInfoDouble(sym, SYMBOL_ASK);
        double pSL    = PositionGetDouble(POSITION_SL);
        double pTP    = PositionGetDouble(POSITION_TP);
        double profit = PositionGetDouble(POSITION_PROFIT);
        int    digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
        double point  = SymbolInfoDouble(sym, SYMBOL_POINT);

        // Break-Even automatique
        if(EnableAutoBreakeven && profit >= BreakevenTriggerProfit)
        {
            double newSl = NormalizeDouble(pOpen + (ptype == POSITION_TYPE_BUY ? point : -point), digits);
            if((ptype == POSITION_TYPE_BUY  && newSl > pSL) ||
               (ptype == POSITION_TYPE_SELL && (pSL == 0 || newSl < pSL)))
                trade.PositionModify(ticket, newSl, pTP);
        }

        // Trailing Stop
        if(EnableTrailingStop)
        {
            double trailDist  = TrailingStepPoints * point;
            double trailStart = TrailingStartPoints * point;
            if(ptype == POSITION_TYPE_BUY && pCur - pOpen >= trailStart)
            {
                double newSl = NormalizeDouble(pCur - trailDist, digits);
                if(newSl > pSL) trade.PositionModify(ticket, newSl, pTP);
            }
            else if(ptype == POSITION_TYPE_SELL && pOpen - pCur >= trailStart)
            {
                double newSl = NormalizeDouble(pCur + trailDist, digits);
                if(pSL == 0 || newSl < pSL) trade.PositionModify(ticket, newSl, pTP);
            }
        }
    }
}

//==================================================================//
//                           HUD                                     //
//==================================================================//
void UpdateHUD()
{
    if(!EnableHUD) return;
    double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double dd      = (dailyHighWaterMark > 0) ?
                     ((dailyHighWaterMark - equity) / dailyHighWaterMark) * 100.0 : 0.0;
    string hud = "";
    hud += "══════════════════════════════════════\n";
    hud += "    ALADDIN PRO V7.19 — TRAP HUNTER  \n";
    hud += "══════════════════════════════════════\n";
    hud += " STATUS:  " + (tradingEnabled ? "🟢 HUNTING" : "🔴 HALTED") + "\n";
    hud += " EQUITY:  " + DoubleToString(equity, 2)  + " $\n";
    hud += " P&L:     " + DoubleToString(equity - balance, 2) + " $\n";
    hud += " DD:      " + DoubleToString(dd, 2) + " %\n";
    hud += " TRADES:  " + IntegerToString(todayTradeCount) + " (aujourd'hui)\n";
    hud += " TRACKED: " + IntegerToString(trackedCount) + " trades\n";
    hud += "--------------------------------------\n";
    hud += " IMBALANCE ENGINE: Wick Rejection V7.19\n";
    hud += "══════════════════════════════════════\n";
    Comment(hud);
}

//==================================================================//
//                      INITIALISATION / TIMERS                      //
//==================================================================//
int OnInit()
{
    trade.SetExpertMagicNumber(MAGIC_NUMBER);
    trade.SetDeviationInPoints(50);

    uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
    if((filling & SYMBOL_FILLING_FOK) != 0)      trade.SetTypeFilling(ORDER_FILLING_FOK);
    else if((filling & SYMBOL_FILLING_IOC) != 0) trade.SetTypeFilling(ORDER_FILLING_IOC);
    else                                          trade.SetTypeFilling(ORDER_FILLING_RETURN);

    dailyStartBalance  = AccountInfoDouble(ACCOUNT_BALANCE);
    dailyHighWaterMark = dailyStartBalance;
    todayDate          = TimeCurrent();
    trackedCount       = 0;

    EventSetTimer(TimerSeconds);
    Print("🎯 ALADDIN PRO V7.19 — TRAP HUNTER ACTIVÉ");
    Print("📡 ComputeWickImbalance() initialisé — Brokers retail compatibles.");
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
    EventKillTimer();
    ExportTradeHistory_V7();
    Print("🛰️ ALADDIN V7.19 : Systèmes mis en veille.");
}

void OnTimer()
{
    if(!CheckDailyLimits()) return;
    ManagePositions();
    ExportTickData_V7();

    if(!EnableAIBridge) return;
    if(TimeCurrent() - lastTradeTime < 60) return; // Cooldown 1 minute

    // Lecture de la décision Python depuis action_plan.json
    // On utilise l'heure de modification du fichier (FileGetInteger) pour éviter
    // de rejouer une ancienne décision (ISO timestamp non parseable via StringToInteger).
    if(FileIsExist("action_plan.json"))
    {
        long fileTime = (long)FileGetInteger("action_plan.json", FILE_MODIFY_DATE);
        if(fileTime > 0 && (int)TimeCurrent() - (int)fileTime < 30)
        {
            string cmd = ReadCommandFile("action_plan.json");
            if(StringLen(cmd) > 10)
                ProcessBridgeCommand(cmd);
        }
    }

    UpdateHUD();
    ExportTradeHistory_V7();
}

void OnTick()
{
    // Gestion active des positions à chaque tick (trailing, breakeven)
    ManagePositions();
}
