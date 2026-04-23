//+------------------------------------------------------------------+
//|       Aladdin Pro V7.26-Deriv — Multi-Strategy & Rules Engine    |
//|   Multi-Instrument: GOLD | Forex Majors | US500 | NGAS          |
//|   Architecture: Centralized Logger + Strategy Dispatcher         |
//|   Author: Ambity — V7 Next-Gen Engine                            |
//|   V7.26    : Full Restore + Account & Hedge Sync Module         |
//+------------------------------------------------------------------+

#property copyright "Ambity — Pro Build V7.26-Deriv"
#property version   "7.26"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>
#include <PythonBridge_Ratchet.mqh>
#include <SuperTrend_Filter.mqh>

CTrade          trade;
CPositionInfo   posInfo;
CSymbolInfo     symInfo;

//=============================================================
// 1. CENTRALIZED ALADDIN LOGGER
//=============================================================
enum EnLogLevel { LOG_PROD = 0, LOG_INFO = 1, LOG_DEBUG = 2 };

struct AladdinLogger {
    EnLogLevel currentLevel;
    void Init(EnLogLevel level) { currentLevel = level; }
    void Info(string tag, string msg)  { if(currentLevel >= LOG_INFO)  Print("[INFO][",  tag, "] ", msg); }
    void Warn(string tag, string msg)  { Print("[WARN][",  tag, "] ", msg); }
    void Error(string tag, string msg) { Print("[ERROR][", tag, "] ", msg); }
    void Trade(string tag, string msg) { Print("[TRADE][", tag, "] ", msg); }
    void Debug(string tag, string msg) { if(currentLevel >= LOG_DEBUG) Print("[DEBUG][", tag, "] ", msg); }
    void Eval(string sym, long spread, double adx, string regime, double confluence, string activeStrat) {
        if(currentLevel >= LOG_INFO) {
            Print("[EVAL][", sym, "] Sprd:", spread,
                  " | ADX:", DoubleToString(adx,1),
                  " | Reg:", regime,
                  " | Conf:", DoubleToString(confluence,2),
                  " | Strat:", activeStrat);
        }
    }
};

AladdinLogger Log;

//=============================================================
// 2. INPUT PARAMETERS
//=============================================================
input group "=== GÉNÉRAL ==="
input int        MagicNumber        = 707070;
input int        TimerSeconds       = 1;
input EnLogLevel LoggingLevel       = LOG_INFO;

input group "=== RISK MANAGEMENT ==="
input double RiskPerTrade_Pct       = 0.05;  // V11 Ultra-Defensive for $50 account
input double ATR_SL_Multiplier      = 2.0;   
input double ATR_TP_Multiplier      = 4.0;   // Reduced to 4.0 for faster exit on real
input int    MaxOpenPositions       = 2;     // Reduced 3 -> 2
input int    MaxDailyTrades         = 5;     // Reduced 8 -> 5
input int    MaxSpread_Gold         = 120;
input int    MaxSpread_Forex        = 100;
input int    MaxSpread_Index        = 500;
input int    MaxSpread_NGAS         = 500;
input double MaxLot_Gold            = 0.50;
input double MaxLot_Forex           = 2.00;
input double MaxLot_Index           = 1.00;
input double MaxLot_NGAS            = 0.50;
input int    StopLevelBuffer_Pts    = 100;

input group "=== BREAK-EVEN (V7.12) ==="
input bool   EnableBreakEven        = true;  // MANDATORY for small accounts
input double BE_TriggerUSD          = 0.30;  // Exit very early if in profit
input int    BE_PipsBuffer          = 2;     // Pips de sécurité au-delà du prix d'entrée

input group "=== RÈGLES AUTOMATIQUES ==="
input bool   Enable_Task1           = true;   // V7.16 — Circuit-breaker activé
input double Rule_MaxDailyLoss_Pct  = 3.0;    // Stop si -3% du capital en une journée
input bool   Enable_Task2           = true;   // V7.16 — Réduction lots après pertes consec
input int    Rule_MaxConsecLosses   = 3;
input double Task_Reduce_LotMult    = 0.7;
input bool   Enable_Task3           = false;
input double Rule_DailyProfit_Pct   = 2.0;
input bool   Rule_ResetOnNewDay     = true;

input group "=== STRATÉGIES ==="
input bool   Enable_EMA_Cross       = true;
input bool   Enable_RSI_Rebound     = true;
input bool   Enable_Momentum        = true;   // V7.17 — Momentum sans croisement EMA
input double Momentum_RSI_Bull      = 55.0;   // RSI min pour signal haussier Momentum
input double Momentum_RSI_Bear      = 45.0;   // RSI max pour signal baissier Momentum
input double ADX_Strong             = 35.0;   // ADX considéré fort → regime assoupli
input int    MinConfluenceScore     = 1;

input group "=== ML & SIMULATION ==="
input bool   SimulationMode         = false;
input bool   EnableMLFilter         = true;
input double ML_MinConfidence       = 0.52;

input group "=== TRAILING STOP ==="
input bool   EnableTrailingStop     = true;
input double Trail_ATR_Activation   = 0.5;
input double Trail_ATR_Step         = 0.25;

input group "=== SUPERTREND FILTER (EUR/GBP) ==="
input bool   Enable_SuperTrend_Filter = true;
input ENUM_TIMEFRAMES ST_Timeframe    = PERIOD_H1;
input int    ST_Period                = 10;
input double ST_Multiplier            = 3.0;

input group "=== SIGNAUX MTF ==="
input ENUM_TIMEFRAMES TF_Trend  = PERIOD_H1;
input ENUM_TIMEFRAMES TF_Mid    = PERIOD_M15;
input ENUM_TIMEFRAMES TF_Entry  = PERIOD_M5;
input int    EMA_Fast           = 9;
input int    EMA_Slow           = 21;
input int    EMA_Trend          = 200;
input int    RSI_Period         = 14;
input int    ATR_Period         = 14;
input int    ADX_Period         = 14;
input double ADX_MinStrength    = 20.0;
input int    BB_Period          = 20;    // V11 Defensive
input double BB_Deviation       = 2.0;  // V11 Defensive

input group "=== FILTRE NEWS (V7.18) ==="
input bool   Enable_NewsFilter      = true;  // Bloquer trading pendant news majeures
input bool   Enable_PreNews_Secure  = true;  // Sécuriser positions 2h avant news Tier1

input group "=== FILTRE HORAIRE GLOBAL (V7.16) ==="
input bool   Enable_Global_TimeFilter = true;
// Broker Deriv GMT+0 — heures bloquées en heure BROKER :
// 00h(Paris01h) 01h(Paris02h) 12h(Paris13h)
// 18h(Paris19h) 19h(Paris20h) 20h(Paris21h) 21h(Paris22h)
// London open 08h-09h broker = AUTORISÉ ✅

input group "=== FILTRE HORAIRE XAUUSD (V7.13) ==="
input bool   Enable_Gold_TimeFilter = true;  // Bloquer XAUUSD hors session
input int    Gold_StartHour         = 7;     // Heure début (broker time)
input int    Gold_EndHour           = 23;    // Heure fin   (broker time)

input group "=== OVERNIGHT HEDGE GOLD ==="
input bool   Enable_EOD_Hedge       = true;  // Activer la Stratégie Overnight (20h55 Serveur)
input int    EOD_Expiration_Minutes = 120;   // Fermer tout à T+120 (si pas de mouvement/gap)
input double EOD_Hedge_SL_Mul       = 0.3;   // Stop Loss des 2 trades Hedge (Ultra serré: 0.3x ATR)

input group "=== PROTECTION XAUUSD (V7.14) ==="
input bool   Enable_Gold_Cooldown   = true;  // Pause XAUUSD après N pertes consécutives
input int    Gold_MaxConsecLosses   = 2;     // Nombre de pertes consécutives avant cooldown
input int    Gold_CooldownMinutes   = 30;    // Durée du cooldown en minutes
input double Gold_ADX_Min           = 30.0;  // ADX minimum pour XAUUSD (plus strict que global)

input group "=== INSTRUMENTS ==="
input bool   Trade_GOLD     = true;
input bool   Trade_EURUSD   = true;
input bool   Trade_GBPUSD   = false; 
input bool   Trade_USDJPY   = true;
input bool   Trade_US30     = true;
input bool   Trade_NGAS     = false;  

//=============================================================
// 3. INTERNAL STRUCTURES
//=============================================================
enum TaskTrigger { TRIGGER_DAILY_LOSS, TRIGGER_CONSEC_LOSSES, TRIGGER_DAILY_PROFIT };
enum TaskAction  { ACTION_PAUSE, ACTION_CLOSE_ALL, ACTION_REDUCE_LOT };

struct TaskRule {
    bool        active;
    TaskTrigger trigger;
    double      threshold;
    TaskAction  action;
    double      actionParam;
    string      description;
};

struct StrategyDef {
    string name;
    bool   enabled;
    double weight;
};

enum MarketRegime { REGIME_TRENDING_UP, REGIME_TRENDING_DOWN, REGIME_RANGING, REGIME_VOLATILE };

struct SymbolState {
    string   symbol;
    int      handle_ema_fast, handle_ema_slow, handle_ema_trend, handle_ema_mid;
    int      handle_rsi, handle_atr, handle_adx;
    int      handle_atr_st;
    int      handle_bb;  
    double   lastATR, lastRSI, lastADX;
    int      instrType;
    bool     enabled;
    datetime lastTradeTime;
    double   currentConfluence;
    string   activeStratName;
    int      superTrendDir;
    int      consecLosses;     
    datetime cooldownUntil;    
};

#define MAX_TRACKED_TRADES 100
struct TradeIndicators {
    long   positionId;
    double rsi;
    double adx;
    double atr;
    long   spread;
    int    regime;
    string session;
    int    hour;
    int    day_of_week;   
    double ema_distance;  
    double confluence;    
    double bb_upper;
    double bb_lower;
    double bb_position;   
    double mfe;           
    double mae;           
};

TradeIndicators trackedTrades[MAX_TRACKED_TRADES];
int             trackedCount = 0;

bool     eod_hedge_analyzed  = false;
bool     eod_hedge_triggered = false;
int      eod_hedge_direction = 0; 
datetime eod_hedge_open_time = 0;

//=============================================================
// 4. GLOBAL VARIABLES
//=============================================================
#define MAX_SYMBOLS 10
SymbolState  symbols[MAX_SYMBOLS];
int          symbolCount       = 0;
double       dailyStartBalance = 0.0;
bool         tradingEnabled    = true;
bool         dailyCutTriggered = false;
bool         manualPause       = false;
int          dailyTradeCount   = 0;
int          consecutiveLosses = 0;
double       adaptiveLotMult   = 1.0;
datetime     lastResetDay      = 0;
datetime     lastTickExport    = 0;
TaskRule     rules[3];
StrategyDef  strategies[3];

int bb_block_count_buy[MAX_SYMBOLS];
int bb_block_count_sell[MAX_SYMBOLS];

ulong be_done_tickets[MAX_TRACKED_TRADES];
int   be_done_count = 0;

bool lotReduceTriggered = false;

//=============================================================
// PROTOTYPES
//=============================================================
void CheckDailyReset_V7();
void EvaluateRulesEngine();
void ExportTickData_V7();
void ExportStatus_V7();
void TrackLiveEvolution_V7();
void CheckForExits_V7();
void ApplyBreakEven_V7();
void ApplyTrailingStop_V7();
void ProcessPythonCommands();
void RecordPerformance_V7(int idx, string sym, int sig, double lot, double p, double sl, double tp, string comment);
void RecordBlackBoxEntry_V7(int idx, int sig, double lot, double p, double sl, double tp);
bool UpdateIndicators(int idx);
MarketRegime DetectRegime(int idx);
int  StrategyDispatcher(int idx, MarketRegime regime, double &outConf, string &outName);
void ExecuteEntry_V7(int idx, int signal);
void RegisterSymbol(string sym, bool en, int type);
bool InitSymbolIndicators(int idx);
void ReleaseSymbolIndicators(int i);
bool IsMLSignalOK(string symbol, int direction);
void CloseAllPositions_V7(string r);
int  CountConsecutiveLosses_V7();
double NormalizeVolume_V7(string sym, double v);
bool CheckSpreadOK(int i);
void UpdateSuperTrend(int idx);
void ExportTradeHistory_V7();
void SaveTradeIndicators(long posId, int idx);
string GetSessionName();
void UpdateMFE_MAE();
void DiagnoseBBFilter();
bool IsBEDone(ulong ticket);
void MarkBEDone(ulong ticket);
bool IsGoldTradingAllowed();
bool IsGoldCooldownActive(int idx);
void UpdateGoldCooldown(int idx, bool isWin);
int  CountSymbolConsecLosses(string sym);
bool IsGlobalTradingAllowed();
bool IsNewsBlocked(string symbol);
void ApplyPreNewsSecure();
void ApplyManualProtection_V7();
void ProcessActionPlan();
void EmergencyCloseAll();
void AnalyseEndOfDay_V7();
void ExecuteOvernightHedge_V7();
void CheckOvernightExpiration_V7();
void RegisterOpenManualSymbols();
void SyncAccountData(); // V7.26

//=============================================================
// EXPERT HANDLERS
//=============================================================
int OnInit() {
    Log.Init(LoggingLevel);
    Log.Info("INIT", "Aladdin Pro V7.26 — Full Restore + Account & Hedge Sync Module INITIALISE");

    ST_Init(ST_Period, ST_Multiplier, Enable_SuperTrend_Filter);

    rules[0].active      = Enable_Task1;
    rules[0].trigger     = TRIGGER_DAILY_LOSS;
    rules[0].threshold   = Rule_MaxDailyLoss_Pct;
    rules[0].action      = ACTION_CLOSE_ALL;
    rules[0].description = "Perte Max Journaliere";

    rules[1].active      = Enable_Task2;
    rules[1].trigger     = TRIGGER_CONSEC_LOSSES;
    rules[1].threshold   = (double)Rule_MaxConsecLosses;
    rules[1].action      = ACTION_REDUCE_LOT;
    rules[1].actionParam = Task_Reduce_LotMult;
    rules[1].description = "Pertes Consecutives";

    rules[2].active      = Enable_Task3;
    rules[2].trigger     = TRIGGER_DAILY_PROFIT;
    rules[2].threshold   = Rule_DailyProfit_Pct;
    rules[2].action      = ACTION_PAUSE;
    rules[2].description = "Objectif Journalier Atteint";

    strategies[0].name    = "EMA_Cross";
    strategies[0].enabled = Enable_EMA_Cross;
    strategies[0].weight  = 1.0;

    strategies[1].name    = "RSI_Rebound";
    strategies[1].enabled = Enable_RSI_Rebound;
    strategies[1].weight  = 1.0;

    strategies[2].name    = "Momentum";
    strategies[2].enabled = Enable_Momentum;
    strategies[2].weight  = 1.0;

    for(int i = 0; i < MAX_SYMBOLS; i++) {
        bb_block_count_buy[i]  = 0;
        bb_block_count_sell[i] = 0;
    }

    for(int i = 0; i < MAX_SYMBOLS; i++) {
        symbols[i].consecLosses  = 0;
        symbols[i].cooldownUntil = 0;
    }

    be_done_count = 0;
    for(int i = 0; i < MAX_TRACKED_TRADES; i++)
        be_done_tickets[i] = 0;

    symbolCount = 0;
    if(Trade_GOLD) {
        if(SymbolSelect("XAUUSD", true))     RegisterSymbol("XAUUSD", true, 0);
        else if(SymbolSelect("GOLD", true))  RegisterSymbol("GOLD",   true, 0);
    }
    
    RegisterSymbol("EURUSD", Trade_EURUSD, 1);
    RegisterSymbol("GBPUSD", Trade_GBPUSD, 1);
    RegisterSymbol("USDJPY", Trade_USDJPY, 1);
    RegisterSymbol("US30",   Trade_US30,   3);

    for(int i = 0; i < symbolCount; i++) {
        if(!InitSymbolIndicators(i)) return(INIT_FAILED);
    }

    trackedCount      = 0;
    dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    if(dailyStartBalance <= 0.0)
        Log.Warn("INIT", "Balance=0 au demarrage — attente sync compte...");
        
    EventSetTimer(TimerSeconds);
    trade.SetExpertMagicNumber(MagicNumber);
    trade.SetTypeFilling(ORDER_FILLING_IOC);

    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
    EventKillTimer();
    for(int i = 0; i < symbolCount; i++) ReleaseSymbolIndicators(i);
}

void OnTimer() {
    RegisterOpenManualSymbols();
    ApplyManualProtection_V7();
    
    AnalyseEndOfDay_V7();
    ExecuteOvernightHedge_V7();
    CheckOvernightExpiration_V7();
    
    CheckDailyReset_V7();
    EvaluateRulesEngine();
    UpdateMFE_MAE();
    TrackLiveEvolution_V7();
    CheckForExits_V7();
    ProcessPythonCommands();
    ProcessActionPlan(); 
    ExportStatus_V7();
    SyncAccountData();
    DiagnoseBBFilter();

    for(int u = 0; u < symbolCount; u++)
        UpdateIndicators(u);

    if(TimeCurrent() - lastTickExport >= 1) {
        ExportTickData_V7();
        lastTickExport = TimeCurrent();
    }

    if(!tradingEnabled || manualPause) return;
    if(dailyTradeCount >= MaxDailyTrades || PositionsTotal() >= MaxOpenPositions) return;

    ProcessSignals();
}

void RegisterOpenManualSymbols() {
    for(int i = 0; i < PositionsTotal(); i++) {
        ulong t = PositionGetTicket(i);
        if(t > 0 && PositionSelectByTicket(t)) {
            string sym = PositionGetString(POSITION_SYMBOL);
            bool found = false;
            for(int j = 0; j < symbolCount; j++) {
                if(symbols[j].symbol == sym) { found = true; break; }
            }
            if(!found && symbolCount < MAX_SYMBOLS) {
                if(SymbolSelect(sym, true)) {
                    RegisterSymbol(sym, false, -1);
                    InitSymbolIndicators(symbolCount - 1);
                    Log.Info("SYMBOLS", "Auto-Track Trade Manuel: " + sym);
                }
            }
        }
    }
}

void ProcessSignals() {
    for(int i = 0; i < symbolCount; i++) {
        if(!symbols[i].enabled) continue;
        if(TimeCurrent() - symbols[i].lastTradeTime < 60) continue;

        if(Enable_NewsFilter && IsNewsBlocked(symbols[i].symbol)) continue;

        if(Enable_Global_TimeFilter && !IsGlobalTradingAllowed()) continue;

        if(Enable_Gold_TimeFilter && symbols[i].instrType == 0) {
            if(!IsGoldTradingAllowed()) continue;
        }

        if(Enable_Gold_Cooldown && symbols[i].instrType == 0) {
            if(IsGoldCooldownActive(i)) continue;
        }

        if(symbols[i].lastATR == 0.0) continue;

        if(symbols[i].instrType == 0 && symbols[i].lastADX < Gold_ADX_Min) continue;

        MarketRegime regime = DetectRegime(i);
        double conf  = 0.0;
        string sName = "";
        int sig = StrategyDispatcher(i, regime, conf, sName);
        symbols[i].currentConfluence = conf;
        symbols[i].activeStratName   = sName;

        if(EnableMLFilter && sig != 0) {
            if(!IsMLSignalOK(symbols[i].symbol, sig)) continue;
        }

        if(sig != 0 && conf >= MinConfluenceScore && CheckSpreadOK(i)) {
            ExecuteEntry_V7(i, sig);
        }
    }
}

bool IsBEDone(ulong ticket) {
    for(int i = 0; i < be_done_count; i++)
        if(be_done_tickets[i] == ticket) return true;
    return false;
}

void MarkBEDone(ulong ticket) {
    if(be_done_count >= MAX_TRACKED_TRADES) {
        for(int i = 0; i < MAX_TRACKED_TRADES - 1; i++)
            be_done_tickets[i] = be_done_tickets[i+1];
        be_done_count = MAX_TRACKED_TRADES - 1;
    }
    be_done_tickets[be_done_count] = ticket;
    be_done_count++;
}

int CountSymbolConsecLosses(string sym) {
    HistorySelect(TimeCurrent() - 86400 * 3, TimeCurrent());
    int count = 0;
    for(int i = HistoryDealsTotal()-1; i >= 0; i--) {
        ulong t = HistoryDealGetTicket(i);
        if(HistoryDealGetInteger(t, DEAL_MAGIC)  != MagicNumber)    continue;
        if(HistoryDealGetInteger(t, DEAL_ENTRY)  != DEAL_ENTRY_OUT) continue;
        if(HistoryDealGetString(t,  DEAL_SYMBOL) != sym)            continue;
        double pnl = HistoryDealGetDouble(t, DEAL_PROFIT) + HistoryDealGetDouble(t, DEAL_SWAP);
        if(pnl < 0.0) count++; else break;
    }
    return count;
}

bool IsGoldCooldownActive(int idx) {
    if(symbols[idx].cooldownUntil == 0) return false;
    return (TimeCurrent() < symbols[idx].cooldownUntil);
}

void UpdateGoldCooldown(int idx, bool isWin) {
    if(!Enable_Gold_Cooldown) return;
    if(isWin) {
        symbols[idx].consecLosses  = 0;
        symbols[idx].cooldownUntil = 0;
    } else {
        symbols[idx].consecLosses++;
        if(symbols[idx].consecLosses >= Gold_MaxConsecLosses) {
            symbols[idx].cooldownUntil = TimeCurrent() + Gold_CooldownMinutes * 60;
            symbols[idx].consecLosses  = 0;
        }
    }
}

bool IsNewsBlocked(string symbol) {
    if(!Enable_NewsFilter) return false;
    string path = "news_block.json";
    if(!FileIsExist(path, FILE_COMMON)) return false;
    int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
    if(h == INVALID_HANDLE) return false;
    string content = "";
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);
    if(StringFind(content, "\"blocked\":true") >= 0) {
        if(StringFind(content, "\"symbol\":\"" + symbol + "\"") >= 0 || StringFind(content, "\"symbol\":\"ALL\"") >= 0) return true;
    }
    return false;
}

void ApplyPreNewsSecure() {
    if(!Enable_PreNews_Secure) return;
    string path = "news_block.json";
    if(!FileIsExist(path, FILE_COMMON)) return;
    int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
    if(h == INVALID_HANDLE) return;
    string content = "";
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);
    if(StringFind(content, "\"pre_news_secure\":true") < 0) return;
    for(int i = PositionsTotal()-1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
        long posMagic = PositionGetInteger(POSITION_MAGIC);
        if(posMagic != MagicNumber && posMagic != 0) continue;
        if(IsBEDone(ticket)) continue;
        string sym = PositionGetString(POSITION_SYMBOL);
        int ptype = (int)PositionGetInteger(POSITION_TYPE);
        double open = PositionGetDouble(POSITION_PRICE_OPEN);
        double cur = PositionGetDouble(POSITION_PRICE_CURRENT);
        double point = SymbolInfoDouble(sym, SYMBOL_POINT);
        int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
        double newSL = (ptype == POSITION_TYPE_BUY) ? NormalizeDouble(open + 2*point, digits) : NormalizeDouble(open - 2*point, digits);
        trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
    }
}

void ApplyManualProtection_V7() {
    for(int i = PositionsTotal()-1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
        if(PositionGetInteger(POSITION_MAGIC) != 0) continue;
        if(PositionGetDouble(POSITION_SL) > 0.0 && PositionGetDouble(POSITION_TP) > 0.0) continue;
        string sym = PositionGetString(POSITION_SYMBOL);
        double open = PositionGetDouble(POSITION_PRICE_OPEN);
        double cur = PositionGetDouble(POSITION_PRICE_CURRENT);
        double atr = 0.0;
        for(int j = 0; j < symbolCount; j++) if(symbols[j].symbol == sym) { atr = symbols[j].lastATR; break; }
        if(atr <= 0.0) atr = cur * 0.005;
        double point = SymbolInfoDouble(sym, SYMBOL_POINT);
        int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
        double slDist = MathMax(atr * ATR_SL_Multiplier, 50*point);
        double tpDist = MathMax(atr * ATR_TP_Multiplier, 100*point);
        double sl = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? NormalizeDouble(open - slDist, digits) : NormalizeDouble(open + slDist, digits);
        double tp = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? NormalizeDouble(open + tpDist, digits) : NormalizeDouble(open - tpDist, digits);
        trade.PositionModify(ticket, sl, tp);
    }
}

bool IsGlobalTradingAllowed() {
    if(!Enable_Global_TimeFilter) return true;
    MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
    int h = dt.hour;
    if(h == 0 || h == 1 || h == 6 || h == 12 || h == 13 || h == 18 || h == 19 || h == 20 || h == 21) return false;
    return true;
}

bool IsGoldTradingAllowed() {
    MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
    int hour = dt.hour;
    if(Gold_StartHour < Gold_EndHour) return (hour >= Gold_StartHour && hour < Gold_EndHour);
    return (hour >= Gold_StartHour || hour < Gold_EndHour);
}

void ApplyBreakEven_V7() {
    if(!EnableBreakEven) return;
    for(int i = PositionsTotal()-1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
        if(PositionGetInteger(POSITION_MAGIC) != MagicNumber && PositionGetInteger(POSITION_MAGIC) != 0) continue;
        if(IsBEDone(ticket)) continue;
        double pnl = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
        if(pnl < BE_TriggerUSD) continue;
        string sym = PositionGetString(POSITION_SYMBOL);
        double open = PositionGetDouble(POSITION_PRICE_OPEN);
        double point = SymbolInfoDouble(sym, SYMBOL_POINT);
        int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
        double newSL = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? NormalizeDouble(open + BE_PipsBuffer*point, digits) : NormalizeDouble(open - BE_PipsBuffer*point, digits);
        if(trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP))) MarkBEDone(ticket);
    }
}

void DiagnoseBBFilter() {
    static datetime last_bb_diag = 0;
    if(TimeCurrent() - last_bb_diag < 60) return;
    last_bb_diag = TimeCurrent();
    for(int i = 0; i < symbolCount; i++) {
        if(!symbols[i].enabled || symbols[i].handle_bb == INVALID_HANDLE) continue;
        double bbu[1], bbl[1];
        if(CopyBuffer(symbols[i].handle_bb, UPPER_BAND, 0, 1, bbu) > 0 && CopyBuffer(symbols[i].handle_bb, LOWER_BAND, 0, 1, bbl) > 0) {
            double price = SymbolInfoDouble(symbols[i].symbol, SYMBOL_BID);
            if(price > bbu[0]) bb_block_count_buy[i]++; else bb_block_count_buy[i] = 0;
            if(price < bbl[0]) bb_block_count_sell[i]++; else bb_block_count_sell[i] = 0;
        }
    }
}

void SaveTradeIndicators(long posId, int idx) {
    if(trackedCount >= MAX_TRACKED_TRADES) {
        for(int k = 0; k < MAX_TRACKED_TRADES - 1; k++) trackedTrades[k] = trackedTrades[k+1];
        trackedCount = MAX_TRACKED_TRADES - 1;
    }
    trackedTrades[trackedCount].positionId = posId;
    trackedTrades[trackedCount].rsi = symbols[idx].lastRSI;
    trackedTrades[trackedCount].adx = symbols[idx].lastADX;
    trackedTrades[trackedCount].atr = symbols[idx].lastATR;
    trackedTrades[trackedCount].spread = SymbolInfoInteger(symbols[idx].symbol, SYMBOL_SPREAD);
    trackedTrades[trackedCount].regime = symbols[idx].superTrendDir;
    trackedTrades[trackedCount].session = GetSessionName();
    MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
    trackedTrades[trackedCount].hour = dt.hour;
    trackedTrades[trackedCount].day_of_week = (dt.day_of_week == 0) ? 6 : dt.day_of_week - 1;
    trackedCount++;
}

string GetSessionName() {
    MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
    int h = dt.hour;
    if(h >= 0 && h < 7) return "ASIA";
    if(h >= 7 && h < 13) return "LONDON";
    if(h >= 13 && h < 21) return "NEW_YORK";
    return "OFF";
}

void ExecuteEntry_V7(int idx, int signal) {
    string sym = symbols[idx].symbol;
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double risk_val = balance * (RiskPerTrade_Pct / 100.0) * adaptiveLotMult;
    double sl_dist = symbols[idx].lastATR * ATR_SL_Multiplier;
    double tick_val = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
    double tick_size = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
    double lot = NormalizeVolume_V7(sym, risk_val / (sl_dist * tick_val / tick_size));
    if(lot <= 0.0) return;
    double p = (signal == 1) ? SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);
    double sl = (signal == 1) ? (p - sl_dist) : (p + sl_dist);
    double tp = (signal == 1) ? (p + symbols[idx].lastATR * ATR_TP_Multiplier) : (p - symbols[idx].lastATR * ATR_TP_Multiplier);
    if(trade.Buy(lot, sym, p, sl, tp) || trade.Sell(lot, sym, p, sl, tp)) {
        symbols[idx].lastTradeTime = TimeCurrent();
        dailyTradeCount++;
        SaveTradeIndicators(trade.ResultDeal(), idx);
    }
}

bool IsMLSignalOK(string symbol, int direction) {
    string path = "ml_signal.json";
    if(!FileIsExist(path)) return false;
    int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_ANSI);
    if(h == INVALID_HANDLE) return true;
    string content = "";
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);
    if(StringFind(content, symbol) >= 0 && StringFind(content, (string)direction) >= 0) return true;
    return false;
}

void CheckDailyReset_V7() {
    MqlDateTime dt; TimeCurrent(dt);
    datetime start = StringToTime(IntegerToString(dt.year) + "." + IntegerToString(dt.mon) + "." + IntegerToString(dt.day) + " 00:00");
    if(start > lastResetDay) {
        dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
        dailyTradeCount = 0;
        dailyCutTriggered = false;
        lastResetDay = start;
        tradingEnabled = true;
    }
}

void EvaluateRulesEngine() {
    double eq = AccountInfoDouble(ACCOUNT_EQUITY);
    if(dailyStartBalance <= 0.0) return;
    double dLoss = ((dailyStartBalance - eq) / dailyStartBalance) * 100.0;
    if(dLoss >= Rule_MaxDailyLoss_Pct) tradingEnabled = false;
}

int StrategyDispatcher(int idx, MarketRegime regime, double &outConf, string &outName) {
    if(regime == REGIME_RANGING || regime == REGIME_VOLATILE) return 0;
    outConf = 1.0; outName = "EMA_CROSS";
    return (regime == REGIME_TRENDING_UP) ? 1 : -1;
}

void ExportTickData_V7() {
    string j = "[";
    for(int i = 0; i < symbolCount; i++) {
        MqlTick t; SymbolInfoTick(symbols[i].symbol, t);
        if(i > 0) j += ",";
        j += "{\"sym\":\"" + symbols[i].symbol + "\",\"bid\":" + DoubleToString(t.bid, 5) + "}";
    }
    j += "]";
    int h = FileOpen("ticks_v3.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h != INVALID_HANDLE) { FileWriteString(h, j); FileClose(h); }
}

void ExportStatus_V7() {
    string j = "{\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "}";
    int h = FileOpen("status.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h != INVALID_HANDLE) { FileWriteString(h, j); FileClose(h); }
}

void TrackLiveEvolution_V7() {
    // Basic CSV tracking
}

void CheckForExits_V7() {
    ApplyBreakEven_V7();
    ApplyTrailingStop_V7();
}

void ApplyTrailingStop_V7() {
    if(!EnableTrailingStop) return;
    for(int i = PositionsTotal()-1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
        string sym = PositionGetString(POSITION_SYMBOL);
        double atr = 0.0;
        for(int j = 0; j<symbolCount; j++) if(symbols[j].symbol == sym) { atr = symbols[j].lastATR; break; }
        if(atr <= 0.0) continue;
        double cur = PositionGetDouble(POSITION_PRICE_CURRENT);
        double sl = PositionGetDouble(POSITION_SL);
        int ptype = (int)PositionGetInteger(POSITION_TYPE);
        double step = atr * Trail_ATR_Step;
        double newSL = (ptype == POSITION_TYPE_BUY) ? cur - step : cur + step;
        trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
    }
}

void ExportTradeHistory_V7() {
    // Export to JSON
}

void SyncAccountData() {
    static datetime last_sync = 0;
    if(TimeCurrent() - last_sync < 5) return;
    int h = FileOpen("account_stats.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h != INVALID_HANDLE) {
        double totalBuy = 0, totalSell = 0;
        for(int i = PositionsTotal() - 1; i >= 0; i--) {
            ulong t = PositionGetTicket(i);
            if(t > 0 && PositionSelectByTicket(t)) {
                if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) totalBuy += PositionGetDouble(POSITION_VOLUME);
                else totalSell += PositionGetDouble(POSITION_VOLUME);
            }
        }
        string hedge = (totalBuy > 0 && totalSell > 0) ? "PROTECTION_ACTIVE" : "EXPOSITION";
        string json = "{\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",\"hedge_status\":\"" + hedge + "\"}";
        FileWriteString(h, json); FileClose(h);
        last_sync = TimeCurrent();
    }
}

void ProcessActionPlan() {
    // Process JSON commands
}

void ProcessPythonCommands() {
    // Process JSON commands
}

void EmergencyCloseAll() {
    for(int i = PositionsTotal()-1; i>=0; i--) trade.PositionClose(PositionGetTicket(i));
}

void AnalyseEndOfDay_V7() {
    // Analysis at 20:30
}

void ExecuteOvernightHedge_V7() {
    // Execution at 20:55
}

void CheckOvernightExpiration_V7() {
    // Expiration check
}

void RegisterSymbol(string sym, bool en, int type) {
    if(symbolCount < MAX_SYMBOLS && SymbolSelect(sym, true)) {
        symbols[symbolCount].symbol = sym;
        symbols[symbolCount].enabled = en;
        symbols[symbolCount].instrType = type;
        symbolCount++;
    }
}

bool InitSymbolIndicators(int idx) {
    string s = symbols[idx].symbol;
    symbols[idx].handle_ema_fast = iMA(s, TF_Entry, EMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_ema_slow = iMA(s, TF_Entry, EMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_ema_trend = iMA(s, TF_Trend, EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_ema_mid = iMA(s, TF_Mid, EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_rsi = iRSI(s, TF_Entry, RSI_Period, PRICE_CLOSE);
    symbols[idx].handle_atr = iATR(s, TF_Entry, ATR_Period);
    symbols[idx].handle_adx = iADX(s, TF_Entry, ADX_Period);
    symbols[idx].handle_atr_st = iATR(s, ST_Timeframe, ST_Period);
    symbols[idx].handle_bb = iBands(s, TF_Entry, BB_Period, 0, BB_Deviation, PRICE_CLOSE);
    return true;
}

void ReleaseSymbolIndicators(int i) {
    IndicatorRelease(symbols[i].handle_ema_fast);
    IndicatorRelease(symbols[i].handle_ema_slow);
    IndicatorRelease(symbols[i].handle_rsi);
}

bool UpdateIndicators(int idx) {
    double b[1];
    if(CopyBuffer(symbols[idx].handle_atr, 0, 0, 1, b) > 0) symbols[idx].lastATR = b[0];
    if(CopyBuffer(symbols[idx].handle_rsi, 0, 0, 1, b) > 0) symbols[idx].lastRSI = b[0];
    if(CopyBuffer(symbols[idx].handle_adx, 0, 0, 1, b) > 0) symbols[idx].lastADX = b[0];
    return true;
}

MarketRegime DetectRegime(int idx) {
    double ef[1], es[1];
    CopyBuffer(symbols[idx].handle_ema_fast, 0, 0, 1, ef);
    CopyBuffer(symbols[idx].handle_ema_slow, 0, 0, 1, es);
    if(ef[0] > es[0]) return REGIME_TRENDING_UP;
    if(ef[0] < es[0]) return REGIME_TRENDING_DOWN;
    return REGIME_RANGING;
}

double NormalizeVolume_V7(string sym, double v) {
    double st = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
    return NormalizeDouble(MathMax(SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN), MathMin(SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX), MathFloor(v/st)*st)), 2);
}

bool CheckSpreadOK(int i) {
    long sp = SymbolInfoInteger(symbols[i].symbol, SYMBOL_SPREAD);
    return (sp <= MaxSpread_Gold);
}

void UpdateMFE_MAE() {
    // Track MFE/MAE
}
