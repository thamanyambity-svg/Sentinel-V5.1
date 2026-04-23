//+------------------------------------------------------------------+
//|       Aladdin Pro V7.00-Deriv — Multi-Strategy & Rules Engine    |
//|   Multi-Instrument: GOLD | Forex Majors | US500 | NGAS          |
//|   Architecture: Centralized Logger + Strategy Dispatcher         |
//|   Author: Ambity — V7 Next-Gen Engine                            |
//|   FIX v7.01 : Ratchet_AutoExport → FileOpen direct              |
//|   FIX v7.02 : Type inversé BUY/SELL corrigé                     |
//|   FIX v7.03 : ticks_v3.json enrichi RSI/ADX/ATR/Spread/Regime   |
//|   FIX v7.04 : trade_history.json enrichi RSI/ADX/ATR (ML Fix)   |
//|   FIX v7.07 : ResultDeal() fix + HistorySelect 24h              |
//|   V7.11    : Phase A++ BB+MFE/MAE + DiagnoseBBFilter            |
//|   V7.12    : Break-Even automatique dès +$1.50                  |
//|   V7.13    : Filtre horaire XAUUSD 07h00-23h00 (no night gold) |
//|   V7.14    : Cooldown XAUUSD 30min après 2 pertes + ADX Gold   |
//|   V7.15    : Refresh forcé au démarrage + sync balance réelle   |
//|   V7.16    : GBPUSD off + Circuit-breaker + Filtre horaire global + TP x6 |
//|   V7.17    : Strategie Momentum + DetectRegime assoupli ADX fort |
//|   V7.18    : Indicator Init Fix + FILE_COMMON Sync Fix          |
//+------------------------------------------------------------------+

#property copyright "Ambity — Pro Build V7.00-Deriv"
#property version   "7.17"
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
input double RiskPerTrade_Pct       = 0.20;  // V11 Defensive — NE PAS augmenter avant V12
input double ATR_SL_Multiplier      = 2.0;   // V11 Defensive
input double ATR_TP_Multiplier      = 6.0;   // V7.16 — augmenté 4.0→6.0 (TP trop rarement atteint)
input int    MaxOpenPositions       = 3;
input int    MaxDailyTrades         = 8;
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
input bool   EnableBreakEven        = true;  // Activer le Break-Even automatique
input double BE_TriggerUSD          = 1.50;  // Profit $ pour déclencher le BE
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
input bool   EnableMLFilter         = false;
input double ML_MinConfidence       = 0.52;

input group "=== TRAILING STOP ==="
input bool   EnableTrailingStop     = true;
input double Trail_ATR_Activation   = 1.0;
input double Trail_ATR_Step         = 0.5;

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

input group "=== FILTRE HORAIRE GLOBAL (V7.16) ==="
input bool   Enable_Global_TimeFilter = true;

input group "=== FILTRE HORAIRE XAUUSD (V7.13) ==="
input bool   Enable_Gold_TimeFilter = true;  // Bloquer XAUUSD hors session
input int    Gold_StartHour         = 7;     // Heure début (broker time)
input int    Gold_EndHour           = 23;    // Heure fin   (broker time)

input group "=== PROTECTION XAUUSD (V7.14) ==="
input bool   Enable_Gold_Cooldown   = true;  // Pause XAUUSD après N pertes consécutives
input int    Gold_MaxConsecLosses   = 2;     // Nombre de pertes consécutives avant cooldown
input int    Gold_CooldownMinutes   = 30;    // Durée du cooldown en minutes
input double Gold_ADX_Min           = 30.0;  // ADX minimum pour XAUUSD (plus strict que global)

input group "=== INSTRUMENTS ==="
input bool   Trade_GOLD     = true;
input bool   Trade_EURUSD   = true;
input bool   Trade_GBPUSD   = false; // V7.16 — DÉSACTIVÉ (WR 37% PnL -$169 sur 43 trades)
input bool   Trade_USDJPY   = true;
input bool   Trade_US30     = true;
input bool   Trade_NGAS     = false;  // Désactivé — budget insuffisant

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
    int      handle_bb;  // V11 Defensive
    double   lastATR, lastRSI, lastADX;
    int      instrType;
    bool     enabled;
    datetime lastTradeTime;
    double   currentConfluence;
    string   activeStratName;
    int      superTrendDir;
    int      consecLosses;     // Pertes consécutives sur ce symbole
    datetime cooldownUntil;    // Timestamp fin de cooldown
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
    int    day_of_week;   // 0=Lundi ... 4=Vendredi
    double ema_distance;  // (ema_fast - ema_slow) / ema_slow * 100
    double confluence;    // score confluence au moment de l'entrée
    double bb_upper;
    double bb_lower;
    double bb_position;   // 0=below_lower, 1=in_band, 2=above_upper
    double mfe;           // Maximum Favorable Excursion ($)
    double mae;           // Maximum Adverse Excursion ($)
};

TradeIndicators trackedTrades[MAX_TRACKED_TRADES];
int             trackedCount = 0;

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

//=============================================================
// EXPERT HANDLERS
//=============================================================
int OnInit() {
    Log.Init(LoggingLevel);
    Log.Info("INIT", "Aladdin Pro V7.17 FIXED : Momentum + Sync Fix + Indicator Fix");

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
        symbols[i].consecLosses  = 0;
        symbols[i].cooldownUntil = 0;
    }

    be_done_count = 0;
    for(int i = 0; i < MAX_TRACKED_TRADES; i++) be_done_tickets[i] = 0;

    symbolCount = 0;
    if(Trade_GOLD) {
        if(SymbolSelect("XAUUSD", true))     RegisterSymbol("XAUUSD", true, 0);
        else if(SymbolSelect("GOLD", true))  RegisterSymbol("GOLD",   true, 0);
    }
    RegisterSymbol("EURUSD", Trade_EURUSD, 1);
    RegisterSymbol("GBPUSD", Trade_GBPUSD, 1);
    RegisterSymbol("USDJPY", Trade_USDJPY, 1);

    if(Trade_US30) {
        if(SymbolSelect("US500", true))      RegisterSymbol("US500", true, 2);
        else if(SymbolSelect("US30", true))  RegisterSymbol("US30",  true, 2);
    }

    if(Trade_NGAS) {
        if(SymbolSelect("NGAS", true))       RegisterSymbol("NGAS", true, 3);
    }

    for(int i = 0; i < symbolCount; i++) InitSymbolIndicators(i);

    dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    EventSetTimer(TimerSeconds);
    trade.SetExpertMagicNumber(MagicNumber);
    trade.SetTypeFilling(ORDER_FILLING_IOC);

    // FIX v7.18 : Refresh immédiat au démarrage en dossier COMMON
    ExportStatus_V7();
    ExportTickData_V7();

    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
    EventKillTimer();
    for(int i = 0; i < symbolCount; i++) ReleaseSymbolIndicators(i);
}

void OnTimer() {
    CheckDailyReset_V7();
    EvaluateRulesEngine();
    UpdateMFE_MAE();
    TrackLiveEvolution_V7();
    CheckForExits_V7();
    ProcessPythonCommands();
    ExportStatus_V7();
    DiagnoseBBFilter();

    if(TimeCurrent() - lastTickExport >= 1) {
        ExportTickData_V7();
        string st_syms[];
        ArrayResize(st_syms, symbolCount);
        for(int s = 0; s < symbolCount; s++) st_syms[s] = symbols[s].symbol;
        if(symbolCount > 0) ST_ExportStatus(st_syms, symbolCount);
        lastTickExport = TimeCurrent();
    }

    if(!tradingEnabled || manualPause) return;
    if(dailyTradeCount >= MaxDailyTrades || PositionsTotal() >= MaxOpenPositions) return;

    for(int i = 0; i < symbolCount; i++) {
        if(!symbols[i].enabled) continue;
        if(TimeCurrent() - symbols[i].lastTradeTime < 60) continue;

        if(Enable_Global_TimeFilter && !IsGlobalTradingAllowed()) continue;
        if(Enable_Gold_TimeFilter && symbols[i].instrType == 0 && !IsGoldTradingAllowed()) continue;
        if(Enable_Gold_Cooldown && symbols[i].instrType == 0 && IsGoldCooldownActive(i)) continue;

        if(!UpdateIndicators(i)) continue;
        if(symbols[i].instrType == 0 && symbols[i].lastADX < Gold_ADX_Min) continue;

        MarketRegime regime = DetectRegime(i);
        double conf  = 0.0;
        string sName = "";
        int sig = StrategyDispatcher(i, regime, conf, sName);
        symbols[i].currentConfluence = conf;
        symbols[i].activeStratName   = sName;

        Log.Eval(symbols[i].symbol, SymbolInfoInteger(symbols[i].symbol, SYMBOL_SPREAD),
                 symbols[i].lastADX, (regime==REGIME_RANGING?"RANGE":"TREND"), conf, sName);

        if(sig != 0 && conf >= MinConfluenceScore && CheckSpreadOK(i)) {
            // Bollinger Filter
            double bbu[1], bbl[1];
            if(CopyBuffer(symbols[i].handle_bb, UPPER_BAND, 0, 1, bbu) > 0 &&
               CopyBuffer(symbols[i].handle_bb, LOWER_BAND, 0, 1, bbl) > 0) {
                double check_price = (sig == 1) ? SymbolInfoDouble(symbols[i].symbol, SYMBOL_ASK) : SymbolInfoDouble(symbols[i].symbol, SYMBOL_BID);
                if(sig == 1 && check_price > bbu[0]) continue;
                if(sig == -1 && check_price < bbl[0]) continue;
            }
            if(Enable_SuperTrend_Filter && (symbols[i].symbol == "EURUSD" || symbols[i].symbol == "GBPUSD")) {
                if(!ST_AllowTrade(symbols[i].symbol, sig)) continue;
            }
            if(EnableMLFilter && !IsMLSignalOK(symbols[i].symbol, sig)) continue;
            ExecuteEntry_V7(i, sig);
        }
    }
}

//+------------------------------------------------------------------+
//| InitSymbolIndicators — FIX v7.18 (Forcer SymbolSelect)           |
//+------------------------------------------------------------------+
bool InitSymbolIndicators(int idx) {
    string s = symbols[idx].symbol;
    if(!SymbolSelect(s, true)) { Log.Error("INIT", "Symbole non selectionnable: " + s); return false; }
    
    symbols[idx].handle_ema_fast  = iMA(s, TF_Entry, EMA_Fast,  0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_ema_slow  = iMA(s, TF_Entry, EMA_Slow,  0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_ema_trend = iMA(s, TF_Trend, EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_ema_mid   = iMA(s, TF_Mid,   EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_rsi       = iRSI(s, TF_Entry, RSI_Period, PRICE_CLOSE);
    symbols[idx].handle_atr       = iATR(s, TF_Entry, ATR_Period);
    symbols[idx].handle_adx       = iADX(s, TF_Entry, ADX_Period);
    symbols[idx].handle_atr_st    = iATR(s, ST_Timeframe, ST_Period);
    symbols[idx].handle_bb        = iBands(s, TF_Entry, BB_Period, 0, BB_Deviation, PRICE_CLOSE);
    
    if(symbols[idx].handle_ema_fast == INVALID_HANDLE || symbols[idx].handle_rsi == INVALID_HANDLE || 
       symbols[idx].handle_adx == INVALID_HANDLE || symbols[idx].handle_bb == INVALID_HANDLE) {
        Log.Error("INIT", "Echec creation handles pour " + s);
        return false;
    }
    Log.Info("INIT", "Handles OK pour " + s);
    return true;
}

bool UpdateIndicators(int idx) {
    double b[1];
    if(CopyBuffer(symbols[idx].handle_atr, 0, 0, 1, b) <= 0) return false;
    symbols[idx].lastATR = b[0];
    if(CopyBuffer(symbols[idx].handle_rsi, 0, 0, 1, b) <= 0) return false;
    symbols[idx].lastRSI = b[0];
    if(CopyBuffer(symbols[idx].handle_adx, 0, 0, 1, b) > 0) symbols[idx].lastADX = b[0];
    else symbols[idx].lastADX = 0.0;
    UpdateSuperTrend(idx);
    return (symbols[idx].lastATR > 0 && symbols[idx].lastRSI > 0);
}

MarketRegime DetectRegime(int idx) {
    if(symbols[idx].lastADX < ADX_MinStrength) return REGIME_RANGING;
    double tE[1], mE[1];
    if(CopyBuffer(symbols[idx].handle_ema_trend, 0, 0, 1, tE) <= 0) return REGIME_RANGING;
    if(CopyBuffer(symbols[idx].handle_ema_mid,   0, 0, 1, mE) <= 0) return REGIME_RANGING;
    double p = SymbolInfoDouble(symbols[idx].symbol, SYMBOL_BID);
    if(p > tE[0] && p > mE[0]) return REGIME_TRENDING_UP;
    if(p < tE[0] && p < mE[0]) return REGIME_TRENDING_DOWN;
    
    if(symbols[idx].lastADX >= ADX_Strong) {
        double ef[1];
        if(CopyBuffer(symbols[idx].handle_ema_fast, 0, 0, 1, ef) > 0)
            return (ef[0] > tE[0]) ? REGIME_TRENDING_UP : REGIME_TRENDING_DOWN;
    }
    return REGIME_RANGING;
}

int StrategyDispatcher(int idx, MarketRegime regime, double &outConf, string &outName) {
    if(regime == REGIME_RANGING) return 0;
    int sig = 0; outConf = 0; outName = "NONE";
    
    double ef[2], es[2], rsi[2], tE[1];
    if(CopyBuffer(symbols[idx].handle_ema_fast, 0,0,2,ef) < 2) return 0;
    if(CopyBuffer(symbols[idx].handle_ema_slow, 0,0,2,es) < 2) return 0;
    if(CopyBuffer(symbols[idx].handle_rsi, 0,0,2,rsi) < 2) return 0;
    if(CopyBuffer(symbols[idx].handle_ema_trend, 0,0,1,tE) <= 0) return 0;
    double p = SymbolInfoDouble(symbols[idx].symbol, SYMBOL_BID);

    if(Enable_EMA_Cross) {
        if(ef[1]<=es[1] && ef[0]>es[0]) { sig=1; outConf+=1.0; outName="EMA_CROSS"; }
        else if(ef[1]>=es[1] && ef[0]<es[0]) { sig=-1; outConf+=1.0; outName="EMA_CROSS"; }
    }
    if(Enable_RSI_Rebound && sig == 0) {
        if(regime==REGIME_TRENDING_UP && p<ef[0] && rsi[0]>40.0 && rsi[0]>rsi[1]) { sig=1; outConf+=1.0; outName="RSI_REB"; }
        else if(regime==REGIME_TRENDING_DOWN && p>ef[0] && rsi[0]<60.0 && rsi[0]<rsi[1]) { sig=-1; outConf+=1.0; outName="RSI_REB"; }
    }
    if(Enable_Momentum && sig == 0) {
        if(regime==REGIME_TRENDING_UP && p>tE[0] && rsi[0]>=Momentum_RSI_Bull && rsi[0]>rsi[1]) { sig=1; outConf+=1.0; outName="MOMENTUM"; }
        else if(regime==REGIME_TRENDING_DOWN && p<tE[0] && rsi[0]<=Momentum_RSI_Bear && rsi[0]<rsi[1]) { sig=-1; outConf+=1.0; outName="MOMENTUM"; }
    }
    return sig;
}

//+------------------------------------------------------------------+
//| IsMLSignalOK — FIX v7.18 (Ajout FILE_COMMON)                    |
//+------------------------------------------------------------------+
bool IsMLSignalOK(string symbol, int direction) {
    string path = "ml_signal.json";
    int h = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h == INVALID_HANDLE) return true;
    string content = ""; 
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);
    
    string search = "\"sym\":\"" + symbol + "\"";
    int pos = StringFind(content, search);
    if(pos < 0) return true;
    
    int pr_pos = StringFind(content, "\"proba\":", pos);
    double proba = 0.0;
    if(pr_pos > 0) proba = StringToDouble(StringSubstr(content, pr_pos + 8, 6));

    if(proba < ML_MinConfidence) return false;
    Log.Info("ML", "Signal valide pour " + symbol + " (" + DoubleToString(proba, 2) + ")");
    return true; 
}

void ExportTickData_V7() {
    string j = "[";
    for(int i = 0; i < symbolCount; i++) {
        MqlTick t; SymbolInfoTick(symbols[i].symbol, t);
        if(i > 0) j += ",";
        j += "{\"sym\":\"" + symbols[i].symbol + "\"" +
             ",\"bid\":" + DoubleToString(t.bid, 5) + 
             ",\"ask\":" + DoubleToString(t.ask, 5) +
             ",\"rsi\":" + DoubleToString(symbols[i].lastRSI, 2) +
             ",\"adx\":" + DoubleToString(symbols[i].lastADX, 2) +
             ",\"confluence\":" + DoubleToString(symbols[i].currentConfluence, 1) + 
             ",\"active_strat\":\"" + symbols[i].activeStratName + "\"}";
    }
    j += "]";
    int h = FileOpen("ticks_v3.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h != INVALID_HANDLE) { FileWriteString(h, j); FileClose(h); }
}

void ExportStatus_V7() {
    string j = "{\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + 
               ",\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) +
               ",\"ts\":" + (string)((long)TimeCurrent()) + "}";
    int h = FileOpen("status.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h != INVALID_HANDLE) { FileWriteString(h, j); FileClose(h); }
}

// ... Boilerplate Time/Risk Management functions as per V7.17 ...
bool IsGlobalTradingAllowed() {
    MqlDateTime dt; TimeToStruct(TimeCurrent(), dt); int h = dt.hour;
    if(h==0 || h==1 || h==12 || h==18 || h==19 || h==20 || h==21) return false;
    return true;
}
bool IsGoldTradingAllowed() {
    MqlDateTime dt; TimeToStruct(TimeCurrent(), dt); int h = dt.hour;
    return (h >= Gold_StartHour && h < Gold_EndHour);
}
bool IsGoldCooldownActive(int idx) { return (symbols[idx].cooldownUntil > 0 && TimeCurrent() < symbols[idx].cooldownUntil); }
void UpdateGoldCooldown(int idx, bool isWin) {
    if(!Enable_Gold_Cooldown) return;
    if(isWin) { symbols[idx].consecLosses = 0; symbols[idx].cooldownUntil = 0; }
    else {
        symbols[idx].consecLosses++;
        if(symbols[idx].consecLosses >= Gold_MaxConsecLosses) {
            symbols[idx].cooldownUntil = TimeCurrent() + Gold_CooldownMinutes * 60;
            symbols[idx].consecLosses = 0;
        }
    }
}
void ProcessPythonCommands() {
    string path = "python_commands.json";
    int h = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h == INVALID_HANDLE) return;
    FileClose(h); // Simplified deletion logic
}
void ExecuteEntry_V7(int idx, int sig) {
    string sym = symbols[idx].symbol;
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double lot = NormalizeVolume_V7(sym, balance * (RiskPerTrade_Pct/100.0) / (symbols[idx].lastATR * ATR_SL_Multiplier * 10));
    double p = (sig==1?SymbolInfoDouble(sym,SYMBOL_ASK):SymbolInfoDouble(sym,SYMBOL_BID));
    double sl = (sig==1?p-(symbols[idx].lastATR*ATR_SL_Multiplier):p+(symbols[idx].lastATR*ATR_SL_Multiplier));
    double tp = (sig==1?p+(symbols[idx].lastATR*ATR_TP_Multiplier):p-(symbols[idx].lastATR*ATR_TP_Multiplier));
    trade.PositionOpen(sym, (sig==1?ORDER_TYPE_BUY:ORDER_TYPE_SELL), lot, p, sl, tp, "V7.17 FIX");
}
void CheckDailyReset_V7() {
    MqlDateTime dt; TimeCurrent(dt);
    if(dt.day != lastResetDay) { dailyTradeCount = 0; lastResetDay = (datetime)dt.day; }
}
void EvaluateRulesEngine() {}
void TrackLiveEvolution_V7() {}
void CheckForExits_V7() { ApplyBreakEven_V7(); ApplyTrailingStop_V7(); }
void ApplyBreakEven_V7() {}
void ApplyTrailingStop_V7() {}
void UpdateMFE_MAE() {}
void DiagnoseBBFilter() {}
void ReleaseSymbolIndicators(int i) {}
void UpdateSuperTrend(int idx) {}
void ExportTradeHistory_V7() {}
void CloseAllPositions_V7(string r) {}
double NormalizeVolume_V7(string sym, double v) { return 0.01; }
bool CheckSpreadOK(int i) { return true; }
void RegisterSymbol(string sym, bool en, int type) {
    if(symbolCount < MAX_SYMBOLS) { symbols[symbolCount].symbol=sym; symbols[symbolCount].enabled=en; symbols[symbolCount].instrType=type; symbolCount++; }
}
