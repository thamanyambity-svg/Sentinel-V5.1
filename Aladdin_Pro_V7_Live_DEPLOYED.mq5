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
//|   V7.18    : News filter + Fix circuit-breaker + 07h/13h off + Momentum EURUSD off |
//|   V7.18b   : Fix definitif circuit-breaker boucle (lotReduceTriggered flag)        |
//|   V7.20    : Trailing GOLD-TIGHT (ATR*0.10 activation, *0.07 step)               |
//|   V7.21    : ApplyManualProtection_V7 (SL/TP auto trades manuels)                |
//|   V7.22    : OVERNIGHT HEDGE GOLD (3 dominants + 2 hedges @20h55 GMT+0)          |
//|   V7.25    : NIGHT FIX — Trailing inclus trades EOD Hedge                    |
//|             : TP = 15xATR (filet), SL = 1.5xATR (respiration)               |
//|             : Lots EOD = 0.20% risque réel (fin du lot fixe 0.01)           |
//|             : Ratchet Audit connecté aux trades Overnight                    |
//+------------------------------------------------------------------+

#property copyright "Ambity — Pro Build V7.00-Deriv"
#property version   "7.25"
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
input double ATR_TP_Multiplier      = 12.0;  // V7.25+: Harmonisé (Large TP + Trailing Exit)
input int    MaxOpenPositions       = 5;     // V7.25+: Mode Demo (Multi-trades actif)
input int    MaxDailyTrades         = 15;    // V7.25+: Plus d'opportunites
input int    MaxSpread_Gold         = 120;
input int    MaxSpread_Forex        = 100;
input int    MaxSpread_Index        = 250;   // V7.25+: Plus strict (500 -> 250)
input int    MaxSpread_NGAS         = 500;
input double MaxLot_Gold            = 0.50;
input double MaxLot_Forex           = 2.00;
input double MaxLot_Index           = 1.00;
input double MaxLot_NGAS            = 0.50;
input int    StopLevelBuffer_Pts    = 100;

input group "=== BREAK-EVEN (V7.12) ==="
input bool   EnableBreakEven        = true;  // Activer le Break-Even automatique
input double BE_TriggerUSD          = 5.00;  // V7.25+: Profit $ min pour déclencher le BE (évite le bruit)
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
input bool   EnableMLFilter         = true;  // V7.25+: Veto IA obligatoire
input double ML_MinConfidence       = 0.75;  // V7.25+: Exigence Sniper (0.75 = 75%)

input group "=== TRAILING STOP ==="
input bool   EnableTrailingStop     = true;
input double Trail_ATR_Activation   = 0.15;  // V7.25+: Plus réactif (0.5 -> 0.15)
input double Trail_ATR_Step         = 0.10;  // V7.25+: Plus serré (0.25 -> 0.10)
input bool   USE_RATCHET_ENGINE     = false; // V7.24 Phase A (Disabled by default)

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
input bool   Enable_Global_TimeFilter = false;
// Broker Deriv GMT+0 — heures bloquées en heure BROKER :
// 00h(Paris01h) 01h(Paris02h) 12h(Paris13h)
// 18h(Paris19h) 19h(Paris20h) 20h(Paris21h) 21h(Paris22h)
// London open 08h-09h broker = AUTORISÉ ✅

input group "=== FILTRE HORAIRE XAUUSD (V7.13) ==="
input bool   Enable_Gold_TimeFilter = false;  // Bloquer XAUUSD hors session
input int    Gold_StartHour         = 7;     // Heure début (broker time)
input int    Gold_EndHour           = 23;    // Heure fin   (broker time)

input group "=== PROTECTION XAUUSD (V7.14) ==="
input bool   Enable_Gold_Cooldown   = true;  // Pause XAUUSD après N pertes consécutives
input int    Gold_MaxConsecLosses   = 2;     // Nombre de pertes consécutives avant cooldown
input int    Gold_CooldownMinutes   = 30;    // Durée du cooldown en minutes
input double Gold_ADX_Min           = 30.0;  // ADX minimum pour XAUUSD (plus strict que global)

input group "=== OVERNIGHT HEDGE GOLD (V7.22) ==="
input bool   Enable_EOD_Hedge        = true;  // Activer la strategie Overnight
input int    EOD_Hour                = 20;    // Heure declenchement (broker GMT+0)
input int    EOD_Minute              = 55;    // Minute declenchement
input double EOD_Dominant_Lot        = 0.01;  // Lot par trade dominant
input double EOD_Hedge_Lot           = 0.01;  // Lot par trade hedge
input int    EOD_Dominant_Count      = 3;     // Nombre de trades dominants
input int    EOD_Hedge_Count         = 2;     // V7.21: 3+2 Asymétrique
input double EOD_Dominant_SL_ATR     = 1.5;   // SL Dominant = 1.5 * ATR
input double EOD_Dominant_TP_ATR     = 4.0;   // TP Dominant = 4.0 * ATR
input double EOD_Hedge_SL_ATR        = 0.3;   // SL Hedge = 0.3 * ATR (Serré)
input double EOD_Hedge_TP_ATR        = 0.5;   // TP Hedge = 0.5 * ATR (Scalp)
input int    EOD_MagicOffset         = 100;   // Magic = MagicNumber + offset (isolation)
input bool   EOD_Alert_Popup         = true;  // Pop-up MT5 a l'execution

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
    // ── V7.14 : Cooldown par symbole ──
    int      consecLosses;     // Pertes consécutives sur ce symbole
    datetime cooldownUntil;    // Timestamp fin de cooldown
};

//=============================================================
// 3b. INSTITUTIONAL RATCHET STATE (V7.24)
//=============================================================
#define MAX_TRACKED_TRADES 100
struct TradeRiskState {
    long   positionId;
    double initialRiskUSD;       // 1R Immutable
    double initialRiskDistance;  // Distance SL initiale en points
    double entryFill;            // Prix d'exécution réel (VWAP si multi-fill)
    double slippage;             // Écart (Requested - Filled) en points
    double lockedFloorR;         // Dernier palier R verrouillé (ex: 0.5, 1.0)
    double highestLockedFloorR;  // Audit: Plus haut palier atteint
    double highestProfitR;       // MFE en unités R
    double maxDrawdownR;         // MAE en unités R
    int    ratchetStage;         // 0=None, 1=0.5R, 2=1.0R, etc.
    datetime lastRatchetUpdate;  // Timestamp dernier mouvement cliquet
    
    // Audit Shadow (Phase B)
    double virtualExitR;         // Niveau R de sortie si le ratchet était actif
    bool   isVirtualClosed;      // Flag pour marquer la sortie simulée
    
    // Heritage indicateurs pour ML/Audit
    double rsi;
    double adx;
    double atr;
    long   spread;
    int    regime;
    string session;
    int    hour;
    int    day_of_week;
    double confluence;
    bool   partial_done;
    double ema_distance;
    
    // UI compatibility (V7.22 Legacy)
    double bb_upper;
    double bb_lower;
    double bb_position;
    double mfe;
    double mae;
};

TradeRiskState trackedTrades[MAX_TRACKED_TRADES];
int            trackedCount = 0;

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

//=============================================================
// 3c. RATCHET PROFILES (V7.24 Phase B)
//=============================================================
struct RatchetProfile {
    string symbol;
    double activationR;
    double trailGapR;
    double locks[5];
    int    lockCount;
};

RatchetProfile profileGold;
RatchetProfile profileDefault;

// V7.22 — Overnight Hedge state
bool     eod_hedge_triggered_today = false;
datetime eod_last_trigger_day      = 0;
int      eod_handle_ema_fast_h1    = INVALID_HANDLE;
int      eod_handle_ema_slow_h1    = INVALID_HANDLE;
string   eod_gold_symbol           = ""; // "XAUUSD" ou "GOLD" selon broker

// BB Diagnostic counters (V7.11)
int bb_block_count_buy[MAX_SYMBOLS];
int bb_block_count_sell[MAX_SYMBOLS];

// Break-Even tracking — évite de modifier plusieurs fois le même ticket (V7.12)
ulong be_done_tickets[MAX_TRACKED_TRADES];
int   be_done_count = 0;

// V7.18b FIX — circuit-breaker lot reduce flag
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
void ApplyScalingOut_V7();
void ProcessPythonCommands();
void RecordPerformance_V7(int idx, string sym, int sig, double lot, double p, double sl, double tp, string comment);
void RecordBlackBoxEntry_V7(int idx, int sig, double lot, double p, double sl, double tp);
void SaveTradeRiskState(long posId, int idx, double requestedPrice, double slAtEntry);
void ApplyRatchetProfitLocks_V7();
void InitRatchetProfiles_V7();
bool UpdateIndicators(int idx);
MarketRegime DetectRegime(int idx);
int  StrategyDispatcher(int idx, MarketRegime regime, double &outConf, string &outName);
void ExecuteEntry_V7(int idx, int signal, double lot_mult=1.0, double sl_mult=0.0, double tp_mult=0.0);
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
void ExecuteOvernightHedge_V7();
void SyncDailyTradeCount_V7();
int  GetGoldSymbolIdx();

//=============================================================
// EXPERT HANDLERS
//=============================================================
int OnInit() {
    Log.Init(LoggingLevel);
    Log.Info("INIT", "Aladdin Pro V7.18b — Fix CB boucle definitif + News Filter + 07h/13h off INITIALISE");

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

    // Initialiser cooldown par symbole (V7.14)
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
        else Log.Warn("INIT", "Or non disponible (XAUUSD/GOLD introuvable)");
    }
    RegisterSymbol("EURUSD", Trade_EURUSD, 1);
    RegisterSymbol("GBPUSD", Trade_GBPUSD, 1);
    RegisterSymbol("USDJPY", Trade_USDJPY, 1);

    if(Trade_US30) {
        if(SymbolSelect("US500", true))      RegisterSymbol("US500", true, 2);
        else if(SymbolSelect("US30", true))  RegisterSymbol("US30",  true, 2);
    }

    /* 
    // DESACTIVE V7.25+ : Trop imprévisible (Synthetics)
    if(SymbolSelect("Volatility 100 Index", true)) {
        RegisterSymbol("Volatility 100 Index", true, 2);
    }
    */

    if(Trade_NGAS) {
        if(SymbolSelect("NGAS", true))       RegisterSymbol("NGAS", true, 3);
        else Log.Warn("INIT", "NGAS non disponible sur ce broker");
    }

    for(int i = 0; i < symbolCount; i++) {
        if(!InitSymbolIndicators(i)) return(INIT_FAILED);
    }

    trackedCount      = 0;
    dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    // V7.20 FIX: Si le terminal n'a pas encore synchro le compte, on retry dans OnTimer
    if(dailyStartBalance <= 0.0)
        Log.Warn("INIT", "Balance=0 au demarrage — attente sync compte...");
    EventSetTimer(TimerSeconds);
    trade.SetExpertMagicNumber(MagicNumber);
    trade.SetTypeFilling(ORDER_FILLING_IOC);

    // ── V7.15 : Refresh forcé au démarrage ──
    // Écriture immédiate de status.json avec la vraie balance
    // Sans attendre le premier OnTimer()
    double realBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    double realEquity  = AccountInfoDouble(ACCOUNT_EQUITY);
    string initStatus  = "{\"balance\":"  + DoubleToString(realBalance, 2) +
                         ",\"equity\":"   + DoubleToString(realEquity,  2) +
                         ",\"trading\":"  + "true" +
                         ",\"ts\":"       + (string)((long)TimeCurrent()) +
                         ",\"version\":\"7.15\"" +
                         ",\"positions\":[]}";
    int fInit = FileOpen("status.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(fInit != INVALID_HANDLE) { FileWriteString(fInit, initStatus); FileClose(fInit); }

    // Écriture immédiate de ticks_v3.json avec prix actuels
    string initTicks = "[";
    for(int i = 0; i < symbolCount; i++) {
        MqlTick tk;
        SymbolInfoTick(symbols[i].symbol, tk);
        if(i > 0) initTicks += ",";
        initTicks += "{\"sym\":\"" + symbols[i].symbol + "\"" +
                     ",\"bid\":"   + DoubleToString(tk.bid, 5) +
                     ",\"ask\":"   + DoubleToString(tk.ask, 5) +
                     ",\"rsi\":0,\"adx\":0,\"atr\":0" +
                     ",\"spread\":" + (string)SymbolInfoInteger(symbols[i].symbol, SYMBOL_SPREAD) +
                     ",\"regime\":0,\"ema_fast\":0,\"ema_slow\":0" +
                     ",\"confluence\":0,\"active_strat\":\"INIT\"}";
    }
    initTicks += "]";
    int fTicks = FileOpen("ticks_v3.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(fTicks != INVALID_HANDLE) { FileWriteString(fTicks, initTicks); FileClose(fTicks); }

    Log.Info("INIT", "V7.15 — Balance reelle au demarrage: $" + DoubleToString(realBalance, 2));
    Log.Info("INIT", "V7.15 — Equity reelle au demarrage:  $" + DoubleToString(realEquity,  2));
    Log.Info("INIT", "V7.15 — status.json et ticks_v3.json ecrits immediatement");

    InitRatchetProfiles_V7(); // V7.24 Phase B
    CheckDailyReset_V7();
    SyncDailyTradeCount_V7(); // V7.25+: Récupère les trades déjà faits aujourd'hui dans l'historique
    
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
    EventKillTimer();
    for(int i = 0; i < symbolCount; i++) ReleaseSymbolIndicators(i);
    // V7.22 — liberer handles EOD Hedge
    if(eod_handle_ema_fast_h1 != INVALID_HANDLE) IndicatorRelease(eod_handle_ema_fast_h1);
    if(eod_handle_ema_slow_h1 != INVALID_HANDLE) IndicatorRelease(eod_handle_ema_slow_h1);
}

void OnTimer() {
    CheckDailyReset_V7();
    EvaluateRulesEngine();

    // ── V7.25+ : UpdateIndicators EN PREMIER ──────────────────────────────────
    // ATR/RSI/ADX doivent être frais AVANT CheckForExits, Trailing et Ratchet.
    // Un ATR périmé = un Trailing Stop mal calibré.
    for(int u = 0; u < symbolCount; u++)
        UpdateIndicators(u);

    UpdateMFE_MAE();
    TrackLiveEvolution_V7();
    CheckForExits_V7();            // Trailing Stop + Ratchet + Break-Even
    ExecuteOvernightHedge_V7();    // EOD Hedge @ 20h55 GMT+0
    ProcessPythonCommands();
    ProcessActionPlan();
    ExportStatus_V7();
    DiagnoseBBFilter();
    OnTimerTrading();

    if(TimeCurrent() - lastTickExport >= 1) {
        ExportTickData_V7();
        string st_syms[];
        ArrayResize(st_syms, symbolCount);
        for(int s = 0; s < symbolCount; s++) st_syms[s] = symbols[s].symbol;
        if(symbolCount > 0) ST_ExportStatus(st_syms, symbolCount);
        lastTickExport = TimeCurrent();
    }
}

//+------------------------------------------------------------------+
//| OnTradeTransaction : Détection instantanée des fermetures        |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
    // Quand un deal est ajouté à l'historique
    if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
    {
        if(HistoryDealSelect(trans.deal))
        {
            long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
            // Si c'est une sortie de position
            if(entry == DEAL_ENTRY_OUT)
            {
                Log.Info("EVENT", "Fermeture detectee — Mise à jour Dashboard immédiate");
                ExportTradeHistory_V7();
                ExportStatus_V7();
            }
        }
    }
}

void OnTimerTrading() {
    if(!tradingEnabled || manualPause) return;
    if(dailyTradeCount >= MaxDailyTrades) return;

    for(int i = 0; i < symbolCount; i++) {
        if(!symbols[i].enabled) continue;
        if(TimeCurrent() - symbols[i].lastTradeTime < 60) continue;

        // ── V14/V23 : Limite de positions PAR instrument ──
        if(CountPositionsBySymbol(symbols[i].symbol) >= MaxOpenPositions) continue;

        // ── V7.18 : Filtre News — bloquer si news_block.json indique blocked ──
        if(Enable_NewsFilter && IsNewsBlocked(symbols[i].symbol)) {
            Log.Debug("NEWS", symbols[i].symbol + " bloque par news majeure");
            continue;
        }
        if(Enable_Global_TimeFilter && !IsGlobalTradingAllowed()) {
            MqlDateTime _dth; TimeToStruct(TimeCurrent(), _dth);
            Log.Debug("GLOBAL_TIME", symbols[i].symbol +
                      " heure " + (string)_dth.hour + "h bloquee (heure non rentable)");
            continue;
        }

        // ── V7.13 : Filtre horaire XAUUSD — pas de trading la nuit ──
        if(Enable_Gold_TimeFilter && symbols[i].instrType == 0) {
            if(!IsGoldTradingAllowed()) {
                Log.Debug("GOLD_TIME", symbols[i].symbol +
                          " hors plage horaire (" +
                          (string)Gold_StartHour + "h-" +
                          (string)Gold_EndHour + "h) — skipped");
                continue;
            }
        }

        // ── V7.14 : Cooldown XAUUSD après N pertes consécutives ──
        if(Enable_Gold_Cooldown && symbols[i].instrType == 0) {
            if(IsGoldCooldownActive(i)) {
                int remaining = (int)(symbols[i].cooldownUntil - TimeCurrent()) / 60;
                Log.Debug("GOLD_CD", symbols[i].symbol +
                          " cooldown actif — encore " + (string)remaining + "min");
                continue;
            }
        }

        // Indicateurs déjà mis à jour en haut de OnTimer()
        // Vérifier quand même que les données sont valides
        if(symbols[i].lastATR == 0.0) continue;

        // ── V7.14 : ADX minimum spécifique XAUUSD ──
        if(symbols[i].instrType == 0 && symbols[i].lastADX < Gold_ADX_Min) {
            Log.Debug("GOLD_ADX", symbols[i].symbol +
                      " ADX=" + DoubleToString(symbols[i].lastADX, 1) +
                      " < Gold_ADX_Min=" + DoubleToString(Gold_ADX_Min, 1) +
                      " — skipped");
            continue;
        }

        MarketRegime regime = DetectRegime(i);
        double conf  = 0.0;
        string sName = "";

        int sig = StrategyDispatcher(i, regime, conf, sName);
        symbols[i].currentConfluence = conf;
        symbols[i].activeStratName   = sName;

        string regStr = (regime==REGIME_TRENDING_UP)  ? "TREND_UP" :
                        (regime==REGIME_TRENDING_DOWN) ? "TREND_DN" :
                        (regime==REGIME_RANGING)       ? "RANGE"    : "VOLATILE";

        Log.Eval(symbols[i].symbol,
                 SymbolInfoInteger(symbols[i].symbol, SYMBOL_SPREAD),
                 symbols[i].lastADX, regStr, conf, sName);

        if(EnableMLFilter && sig != 0) {
            if(!IsMLSignalOK(symbols[i].symbol, sig)) continue;
        }

        if(sig != 0 && conf >= MinConfluenceScore && CheckSpreadOK(i)) {
            // Filtre Bollinger Defensif V11
            double bbu[1], bbl[1];
            if(CopyBuffer(symbols[i].handle_bb, UPPER_BAND, 0, 1, bbu) > 0 &&
               CopyBuffer(symbols[i].handle_bb, LOWER_BAND, 0, 1, bbl) > 0) {
                double check_price = (sig == 1) ?
                    SymbolInfoDouble(symbols[i].symbol, SYMBOL_ASK) :
                    SymbolInfoDouble(symbols[i].symbol, SYMBOL_BID);
                if(sig == 1 && check_price > bbu[0]) {
                    Log.Eval(symbols[i].symbol, 0, 0, "BB_BLOCKED", 0, "Bloque Bollinger Extreme (Achat)");
                    continue;
                }
                if(sig == -1 && check_price < bbl[0]) {
                    Log.Eval(symbols[i].symbol, 0, 0, "BB_BLOCKED", 0, "Bloque Bollinger Extreme (Vente)");
                    continue;
                }
            }

            // SuperTrend uniquement sur EURUSD et GBPUSD
            if(Enable_SuperTrend_Filter &&
               (symbols[i].symbol == "EURUSD" || symbols[i].symbol == "GBPUSD")) {
                if(!ST_AllowTrade(symbols[i].symbol, sig)) {
                    Log.Eval(symbols[i].symbol, 0, 0, "ST_BLOCKED", 0, "Bloque SuperTrend");
                    continue;
                }
            }
            ExecuteEntry_V7(i, sig);
        }
    }
}

//=============================================================
// 5. BREAK-EVEN (V7.12)
//=============================================================

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

//+------------------------------------------------------------------+
//| CountSymbolConsecLosses — V7.14                                  |
//| Compte les pertes consécutives récentes sur un symbole donné     |
//+------------------------------------------------------------------+
int CountSymbolConsecLosses(string sym) {
    HistorySelect(TimeCurrent() - 86400 * 3, TimeCurrent());
    int count = 0;
    for(int i = HistoryDealsTotal()-1; i >= 0; i--) {
        ulong t = HistoryDealGetTicket(i);
        if(HistoryDealGetInteger(t, DEAL_MAGIC)  != MagicNumber)    continue;
        if(HistoryDealGetInteger(t, DEAL_ENTRY)  != DEAL_ENTRY_OUT) continue;
        if(HistoryDealGetString(t,  DEAL_SYMBOL) != sym)            continue;
        double pnl = HistoryDealGetDouble(t, DEAL_PROFIT)
                   + HistoryDealGetDouble(t, DEAL_SWAP);
        if(pnl < 0.0) count++;
        else          break;  // Série interrompue par un gain
    }
    return count;
}

//+------------------------------------------------------------------+
//| IsGoldCooldownActive — V7.14                                     |
//| Retourne true si XAUUSD est en période de cooldown               |
//+------------------------------------------------------------------+
bool IsGoldCooldownActive(int idx) {
    if(symbols[idx].cooldownUntil == 0) return false;
    return (TimeCurrent() < symbols[idx].cooldownUntil);
}

//+------------------------------------------------------------------+
//| UpdateGoldCooldown — V7.14                                       |
//| Appelé à chaque clôture XAUUSD — met à jour le compteur         |
//+------------------------------------------------------------------+
void UpdateGoldCooldown(int idx, bool isWin) {
    if(!Enable_Gold_Cooldown) return;

    if(isWin) {
        // Gain → reset compteur
        if(symbols[idx].consecLosses > 0) {
            Log.Info("GOLD_CD", symbols[idx].symbol +
                     " Gain — reset compteur pertes (" +
                     (string)symbols[idx].consecLosses + " -> 0)");
        }
        symbols[idx].consecLosses  = 0;
        symbols[idx].cooldownUntil = 0;
    } else {
        // Perte → incrémenter + vérifier seuil
        symbols[idx].consecLosses++;
        Log.Warn("GOLD_CD", symbols[idx].symbol +
                 " Perte #" + (string)symbols[idx].consecLosses +
                 " consecutive");

        if(symbols[idx].consecLosses >= Gold_MaxConsecLosses) {
            symbols[idx].cooldownUntil = TimeCurrent() + Gold_CooldownMinutes * 60;
            symbols[idx].consecLosses  = 0;  // Reset pour le prochain cycle
            Log.Warn("GOLD_CD", symbols[idx].symbol +
                     " COOLDOWN ACTIVE " + (string)Gold_CooldownMinutes + "min" +
                     " — reprise a " +
                     TimeToString(symbols[idx].cooldownUntil, TIME_MINUTES));
        }
    }
}

//+------------------------------------------------------------------+
//| IsNewsBlocked — V7.18                                            |
//| Lit news_block.json généré par Antigravity/Python               |
//| Format : {"blocked":true,"symbol":"EURUSD","mins_until":45}     |
//+------------------------------------------------------------------+
bool IsNewsBlocked(string symbol) {
    if(!Enable_NewsFilter) return false;
    string path = "news_block.json";
    if(!FileIsExist(path, FILE_COMMON)) return false;

    int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
    if(h == INVALID_HANDLE) return false;

    string content = "";
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);

    // Si blocked global
    if(StringFind(content, "\"blocked\":true") >= 0) {
        // Vérifier si ce symbole est concerné
        int symPos = StringFind(content, "\"symbol\":\"" + symbol + "\"");
        int allPos = StringFind(content, "\"symbol\":\"ALL\"");
        if(symPos >= 0 || allPos >= 0) return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| ApplyPreNewsSecure — V7.18                                       |
//| Si pre_news_secure=true → forcer BE + resserrer trailing        |
//+------------------------------------------------------------------+
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

    // Forcer Break-Even sur toutes les positions ouvertes
    for(int i = PositionsTotal()-1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(!PositionSelectByTicket(ticket)) continue;
        // V7.25+: Sécurise TOUTES les positions (EA, Manuel, EOD, Python)
        // Aucun filtre Magic Number — Protection universelle avant news
        if(IsBEDone(ticket)) continue;

        string sym   = PositionGetString(POSITION_SYMBOL);
        int    ptype = (int)PositionGetInteger(POSITION_TYPE);
        double open  = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl    = PositionGetDouble(POSITION_SL);
        double tp    = PositionGetDouble(POSITION_TP);
        double cur   = PositionGetDouble(POSITION_PRICE_CURRENT);
        double pnl   = PositionGetDouble(POSITION_PROFIT);
        int    digits= (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
        double point = SymbolInfoDouble(sym, SYMBOL_POINT);
        double stopLevel = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) * point;

        // Forcer BE même si profit < BE_TriggerUSD
        double newSL = 0.0;
        if(ptype == POSITION_TYPE_BUY) {
            newSL = NormalizeDouble(open + 2*point, digits);
            if(sl >= newSL || (cur - newSL) < stopLevel) continue;
        } else if(ptype == POSITION_TYPE_SELL) {
            newSL = NormalizeDouble(open - 2*point, digits);
            if(sl > 0 && sl <= newSL || (newSL - cur) < stopLevel) continue;
        } else continue;

        if(trade.PositionModify(ticket, newSL, tp)) {
            MarkBEDone(ticket);
            Log.Warn("PRE_NEWS", sym + " BE force avant news" +
                     " PnL=$" + DoubleToString(pnl, 2));
        }
    }
}

void ApplyManualProtection_V7() {
    for(int i = PositionsTotal()-1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(!PositionSelectByTicket(ticket)) continue;

        long posMagic = PositionGetInteger(POSITION_MAGIC);
        if(posMagic != 0) continue;

        double sl = PositionGetDouble(POSITION_SL);
        double tp = PositionGetDouble(POSITION_TP);
        if(sl > 0.0 && tp > 0.0) continue;

        string sym   = PositionGetString(POSITION_SYMBOL);
        int    ptype = (int)PositionGetInteger(POSITION_TYPE);
        double open  = PositionGetDouble(POSITION_PRICE_OPEN);
        double cur   = PositionGetDouble(POSITION_PRICE_CURRENT);
        double atr   = 0.0;

        for(int j = 0; j < symbolCount; j++) {
            if(symbols[j].symbol == sym) {
                atr = symbols[j].lastATR;
                break;
            }
        }
        if(atr <= 0.0) continue;

        int    digits    = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
        double point     = SymbolInfoDouble(sym, SYMBOL_POINT);
        double stopLevel = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) * point;
        double buffer    = StopLevelBuffer_Pts * point;
        double slDist    = MathMax(atr * ATR_SL_Multiplier, stopLevel + buffer);
        double tpDist    = MathMax(atr * ATR_TP_Multiplier, stopLevel + buffer);
        double newSL     = sl;
        double newTP     = tp;

        if(ptype == POSITION_TYPE_BUY) {
            if(newSL <= 0.0) {
                newSL = NormalizeDouble(MathMin(open - slDist, cur - stopLevel - buffer), digits);
            }
            if(newTP <= 0.0 || newTP <= cur + stopLevel) {
                newTP = NormalizeDouble(MathMax(open + tpDist, cur + stopLevel + buffer), digits);
            }
        }
        else if(ptype == POSITION_TYPE_SELL) {
            if(newSL <= 0.0) {
                newSL = NormalizeDouble(MathMax(open + slDist, cur + stopLevel + buffer), digits);
            }
            if(newTP <= 0.0 || newTP >= cur - stopLevel) {
                newTP = NormalizeDouble(MathMin(open - tpDist, cur - stopLevel - buffer), digits);
            }
        }
        else continue;

        if(trade.PositionModify(ticket, newSL, newTP)) {
            Log.Warn("MANUAL_PROTECT", sym +
                     " protection auto SL=" + DoubleToString(newSL, digits) +
                     " TP=" + DoubleToString(newTP, digits));
        }
    }
}

//+------------------------------------------------------------------+
//| V7.22 — OVERNIGHT HEDGE GOLD                                     |
//| Declenche a EOD_Hour:EOD_Minute broker GMT+0 (1 fois par jour)   |
//| Direction : EMA_fast > EMA_slow sur H1 GOLD → BUY dominants      |
//|             EMA_fast < EMA_slow sur H1 GOLD → SELL dominants     |
//| 3 dominants (TP=4xATR, SL=1.5xATR) + 2 hedges sens oppose        |
//|                            (TP=0.5xATR, SL=0.3xATR)              |
//| Magic distinct = MagicNumber + EOD_MagicOffset (isole du reste)  |
//+------------------------------------------------------------------+
int GetGoldSymbolIdx() {
    for(int i = 0; i < symbolCount; i++) {
        string s = symbols[i].symbol;
        if(s == "XAUUSD" || s == "GOLD" || s == "XAUUSDm") return i;
    }
    return -1;
}

void ExecuteOvernightHedge_V7() {
    if(!Enable_EOD_Hedge)              return;
    if(eod_hedge_triggered_today)      return;

    // Fenetre de declenchement : [EOD_Hour:EOD_Minute ; +4 min]
    MqlDateTime dt;
    TimeCurrent(dt);
    int nowMin   = dt.hour * 60 + dt.min;
    int triggMin = EOD_Hour * 60 + EOD_Minute;
    if(nowMin < triggMin || nowMin > triggMin + 4) return;

    // Localisation du symbole GOLD dispo sur le broker
    int gidx = GetGoldSymbolIdx();
    if(gidx < 0) {
        Log.Warn("EOD_HEDGE", "GOLD/XAUUSD introuvable, skip");
        eod_hedge_triggered_today = true; // evite spam
        return;
    }
    string sym = symbols[gidx].symbol;
    if(!SymbolSelect(sym, true)) { Log.Warn("EOD_HEDGE", "SymbolSelect KO " + sym); return; }

    // Lazy-init des handles EMA H1 (fast/slow) dedies
    if(eod_handle_ema_fast_h1 == INVALID_HANDLE || eod_gold_symbol != sym) {
        if(eod_handle_ema_fast_h1 != INVALID_HANDLE) IndicatorRelease(eod_handle_ema_fast_h1);
        if(eod_handle_ema_slow_h1 != INVALID_HANDLE) IndicatorRelease(eod_handle_ema_slow_h1);
        eod_handle_ema_fast_h1 = iMA(sym, PERIOD_H1, EMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
        eod_handle_ema_slow_h1 = iMA(sym, PERIOD_H1, EMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
        eod_gold_symbol        = sym;
        if(eod_handle_ema_fast_h1 == INVALID_HANDLE ||
           eod_handle_ema_slow_h1 == INVALID_HANDLE) {
            Log.Warn("EOD_HEDGE", "iMA H1 init KO");
            return;
        }
    }

    double efBuf[1], esBuf[1];
    if(CopyBuffer(eod_handle_ema_fast_h1, 0, 0, 1, efBuf) <= 0 ||
       CopyBuffer(eod_handle_ema_slow_h1, 0, 0, 1, esBuf) <= 0) {
        Log.Warn("EOD_HEDGE", "CopyBuffer EMA H1 KO");
        return;
    }
    double emaFast = efBuf[0];
    double emaSlow = esBuf[0];

    // ATR dispo via UpdateIndicators appele en OnTimer
    double atr = symbols[gidx].lastATR;
    if(atr <= 0.0) {
        Log.Warn("EOD_HEDGE", "ATR GOLD non dispo, skip");
        return;
    }

    int    dominantType = (emaFast > emaSlow) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
    int    hedgeType    = (dominantType == ORDER_TYPE_BUY)    ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
    string dominantLbl  = (dominantType == ORDER_TYPE_BUY)    ? "BUY"  : "SELL";
    string hedgeLbl     = (hedgeType    == ORDER_TYPE_BUY)    ? "BUY"  : "SELL";

    double point   = SymbolInfoDouble(sym, SYMBOL_POINT);
    int    digits  = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
    double stopLv  = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) * point;
    double buffer  = StopLevelBuffer_Pts * point;

    // ── V7.25 MATH : Base risk comme le reste du système ──────────────────────────
    // SL = ATR * 1.5 minimum (respiration suffisante même sur marché agité)
    // TP = ATR * 15.0 (filet de sécurité lointain, le trailing est le vrai exit)
    // LOT = 0.20% balance / (SL_distance en $ par lot)
    // ──────────────────────────────────────────────────────────────────
    double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
    double riskUSD    = balance * (RiskPerTrade_Pct / 100.0) * adaptiveLotMult;
    double tickVal    = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
    double tickSize   = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
    double maxLotGold = MaxLot_Gold;

    // SL Dominant : 1.5 * ATR (respiration) — minimum enforcé par broker
    double slDistDom = MathMax(atr * EOD_Dominant_SL_ATR, stopLv + buffer);
    // TP Dominant : Filet de sécurité lointain. Le trailing stop est le vrai exit.
    double tpDistDom = MathMax(atr * EOD_Dominant_TP_ATR, stopLv + buffer);
    // Lot DOM basé sur 0.20% de risque / distance SL
    double lotDom    = NormalizeVolume_V7(sym, riskUSD / (slDistDom * tickVal / tickSize));
    lotDom = MathMin(lotDom, maxLotGold);

    // Switch magic pour isolation
    ulong mainMagic  = (ulong)MagicNumber;
    ulong hedgeMagic = (ulong)(MagicNumber + EOD_MagicOffset);
    trade.SetExpertMagicNumber(hedgeMagic);

    int placed = 0;

    // ─── 3 DOMINANTS ─────────────────────────────────────────────────────────────────
    for(int k = 0; k < EOD_Dominant_Count; k++) {
        double ask   = SymbolInfoDouble(sym, SYMBOL_ASK);
        double bid   = SymbolInfoDouble(sym, SYMBOL_BID);
        double price = (dominantType == ORDER_TYPE_BUY) ? ask : bid;
        double sl, tp;
        if(dominantType == ORDER_TYPE_BUY) {
            sl = NormalizeDouble(price - slDistDom, digits);
            tp = NormalizeDouble(price + tpDistDom, digits);
        } else {
            sl = NormalizeDouble(price + slDistDom, digits);
            tp = NormalizeDouble(price - tpDistDom, digits);
        }
        string comment = "EOD_DOM" + IntegerToString(k+1) +
                         "_SL" + DoubleToString(slDistDom, 0) +
                         "_TP" + DoubleToString(tpDistDom, 0);
        bool ok = (dominantType == ORDER_TYPE_BUY)
                    ? trade.Buy (lotDom, sym, price, sl, tp, comment)
                    : trade.Sell(lotDom, sym, price, sl, tp, comment);
        if(ok) {
            placed++;
            // ── Connexion au Ratchet Audit (V7.25) ──
            if(trackedCount < MAX_TRACKED_TRADES) {
                ulong dealTicket = trade.ResultDeal();
                long  realPosId  = 0;
                HistorySelect(TimeCurrent() - 10, TimeCurrent());
                for(int d = HistoryDealsTotal()-1; d >= 0; d--) {
                    ulong dt = HistoryDealGetTicket(d);
                    if(dt == dealTicket) { realPosId = HistoryDealGetInteger(dt, DEAL_POSITION_ID); break; }
                }
                if(realPosId > 0) SaveTradeRiskState(realPosId, gidx, price, sl);
            }
        } else {
            Log.Warn("EOD_HEDGE", "DOM " + dominantLbl + " #" + IntegerToString(k+1) +
                     " KO code=" + IntegerToString(trade.ResultRetcode()));
        }
    }

    // ─── 2 HEDGES (sens opposé) ─────────────────────────────────────────────────────────
    // SL/TP Hedge : Alignés sur les dominants pour une gestion de risque cohérente
    double slDistHdg = MathMax(atr * EOD_Hedge_SL_ATR, stopLv + buffer);
    double tpDistHdg = MathMax(atr * EOD_Hedge_TP_ATR, stopLv + buffer);
    // Lot HDG : même risque 0.20%
    double lotHdg    = NormalizeVolume_V7(sym, riskUSD / (slDistHdg * tickVal / tickSize));
    lotHdg = MathMin(lotHdg, maxLotGold);

    for(int k = 0; k < EOD_Hedge_Count; k++) {
        double ask   = SymbolInfoDouble(sym, SYMBOL_ASK);
        double bid   = SymbolInfoDouble(sym, SYMBOL_BID);
        double price = (hedgeType == ORDER_TYPE_BUY) ? ask : bid;
        double sl, tp;
        if(hedgeType == ORDER_TYPE_BUY) {
            sl = NormalizeDouble(price - slDistHdg, digits);
            tp = NormalizeDouble(price + tpDistHdg, digits);
        } else {
            sl = NormalizeDouble(price + slDistHdg, digits);
            tp = NormalizeDouble(price - tpDistHdg, digits);
        }
        string comment = "EOD_HDG" + IntegerToString(k+1) +
                         "_SL" + DoubleToString(slDistHdg, 0) +
                         "_TP" + DoubleToString(tpDistHdg, 0);
        bool ok = (hedgeType == ORDER_TYPE_BUY)
                    ? trade.Buy (lotHdg, sym, price, sl, tp, comment)
                    : trade.Sell(lotHdg, sym, price, sl, tp, comment);
        if(ok) {
            placed++;
            if(trackedCount < MAX_TRACKED_TRADES) {
                ulong dealTicket = trade.ResultDeal();
                long  realPosId  = 0;
                HistorySelect(TimeCurrent() - 10, TimeCurrent());
                for(int d = HistoryDealsTotal()-1; d >= 0; d--) {
                    ulong dt = HistoryDealGetTicket(d);
                    if(dt == dealTicket) { realPosId = HistoryDealGetInteger(dt, DEAL_POSITION_ID); break; }
                }
                if(realPosId > 0) SaveTradeRiskState(realPosId, gidx, price, sl);
            }
        } else {
            Log.Warn("EOD_HEDGE", "HDG " + hedgeLbl + " #" + IntegerToString(k+1) +
                     " KO code=" + IntegerToString(trade.ResultRetcode()));
        }
    }

    // Restaurer magic EA principal
    trade.SetExpertMagicNumber(mainMagic);

    eod_hedge_triggered_today = true;

    string summary = "EOD Hedge GOLD " + sym +
                     " | dir=" + dominantLbl +
                     " | placed=" + IntegerToString(placed) +
                     "/" + IntegerToString(EOD_Dominant_Count + EOD_Hedge_Count) +
                     " | ATR=" + DoubleToString(atr, digits) +
                     " | magic=" + IntegerToString((int)hedgeMagic);
    Log.Info("EOD_HEDGE", summary);

    if(EOD_Alert_Popup) Alert("[V7.22 EOD_HEDGE] " + summary);
}

//+------------------------------------------------------------------+
//| IsGlobalTradingAllowed — V7.16 patch GMT+0                       |
//| Broker Deriv = GMT+0. Paris = GMT+1.                            |
//| Heures bloquées converties en heure BROKER (GMT+0)              |
//| Paris 01h = Broker 00h | Paris 10h = Broker 09h (London = OK!) |
//+------------------------------------------------------------------+
bool IsGlobalTradingAllowed() {
    if(!Enable_Global_TimeFilter) return true;
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    int h = dt.hour;  // Heure broker GMT+0

    // Heures bloquées (heure broker GMT+0)
    // Données réelles converties : heure Paris -1h = heure broker
    if(h == 0)  return false;  // Paris 01h — perte -$30
    if(h == 1)  return false;  // Paris 02h — surveillance uniquement
    if(h == 6)  return false;  // Paris 07h — perte -$44 (V7.18)
    if(h == 12) return false;  // Paris 13h — perte -$58
    if(h == 13) return false;  // Paris 14h — perte -$54 (V7.18)
    if(h == 18) return false;  // Paris 19h — perte -$36
    if(h == 19) return false;  // Paris 20h — perte -$57
    if(h == 20) return false;  // Paris 21h — perte -$36
    if(h == 21) return false;  // Paris 22h — perte -$100 (pire heure)

    // LIBÉRÉES vs version précédente :
    // h==8 (Paris 09h) = London open → AUTORISÉ ✅
    // h==9 (Paris 10h) = London actif → AUTORISÉ ✅
    return true;
}

//+------------------------------------------------------------------+
//| IsGoldTradingAllowed — V7.13                                     |
//| Retourne true uniquement si l'heure broker est dans la plage     |
//| Gold_StartHour (inclus) → Gold_EndHour (exclus)                 |
//| Exemple : 8 → 22 = trading de 08:00:00 à 21:59:59              |
//+------------------------------------------------------------------+
bool IsGoldTradingAllowed() {
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    int hour = dt.hour;

    if(Gold_StartHour < Gold_EndHour) {
        // Cas normal : 08h → 22h (pas de minuit)
        return (hour >= Gold_StartHour && hour < Gold_EndHour);
    } else {
        // Cas overnight : ex 22h → 06h (franchit minuit)
        return (hour >= Gold_StartHour || hour < Gold_EndHour);
    }
}

void ApplyBreakEven_V7() {
    if(!EnableBreakEven) return;

    for(int i = PositionsTotal()-1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(!PositionSelectByTicket(ticket)) continue;
        // V7.25+: Break-Even universel (Main EA + EOD + Manuel)
        // Aucun filtre Magic Number

        // Une seule fois par trade
        if(IsBEDone(ticket)) continue;

        string sym   = PositionGetString(POSITION_SYMBOL);
        int    ptype = (int)PositionGetInteger(POSITION_TYPE);
        double open  = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl    = PositionGetDouble(POSITION_SL);
        double tp    = PositionGetDouble(POSITION_TP);
        double cur   = PositionGetDouble(POSITION_PRICE_CURRENT);
        double pnl   = PositionGetDouble(POSITION_PROFIT)
                     + PositionGetDouble(POSITION_SWAP);

        // Seuil pas encore atteint
        if(pnl < BE_TriggerUSD) continue;

        int    digits    = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
        double point     = SymbolInfoDouble(sym, SYMBOL_POINT);
        double stopLevel = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) * point;
        double bePts     = BE_PipsBuffer * point;
        double newSL     = 0.0;

        if(ptype == POSITION_TYPE_BUY) {
            newSL = NormalizeDouble(open + bePts, digits);
            if(sl >= newSL) continue;
            if((cur - newSL) < stopLevel) continue;
        }
        else if(ptype == POSITION_TYPE_SELL) {
            newSL = NormalizeDouble(open - bePts, digits);
            if(sl > 0.0 && sl <= newSL) continue;
            if((newSL - cur) < stopLevel) continue;
        }
        else continue;

        if(trade.PositionModify(ticket, newSL, tp)) {
            MarkBEDone(ticket);
            Log.Info("BE", sym +
                     " Break-Even ACTIVE" +
                     " PnL=$" + DoubleToString(pnl, 2) +
                     " SL: "  + DoubleToString(sl,  digits) +
                     " -> BE+" + (string)BE_PipsBuffer + "pts=" +
                     DoubleToString(newSL, digits));
        }
    }
}

//=============================================================
// 6. BB DIAGNOSTIC (V7.11)
//=============================================================
void DiagnoseBBFilter() {
    static datetime last_bb_diag = 0;
    if(TimeCurrent() - last_bb_diag < 60) return;
    last_bb_diag = TimeCurrent();

    for(int i = 0; i < symbolCount; i++) {
        if(!symbols[i].enabled) continue;

        if(symbols[i].handle_bb == INVALID_HANDLE) {
            Log.Warn("BB_DIAG", symbols[i].symbol + " handle_bb INVALID_HANDLE - reinit requis");
            continue;
        }

        double bbu[1], bbl[1];
        int res_u = CopyBuffer(symbols[i].handle_bb, UPPER_BAND, 0, 1, bbu);
        int res_l = CopyBuffer(symbols[i].handle_bb, LOWER_BAND, 0, 1, bbl);

        if(res_u <= 0 || res_l <= 0) {
            Log.Warn("BB_DIAG", symbols[i].symbol +
                     " CopyBuffer echoue res_u=" + (string)res_u +
                     " res_l=" + (string)res_l +
                     " err=" + (string)GetLastError());
            continue;
        }

        double price    = SymbolInfoDouble(symbols[i].symbol, SYMBOL_BID);
        double spreadBB = bbu[0] - bbl[0];
        double pctB     = (spreadBB > 0.0) ?
                          ((price - bbl[0]) / spreadBB * 100.0) : 50.0;

        string zone = (price > bbu[0]) ? "ABOVE_UPPER" :
                      (price < bbl[0]) ? "BELOW_LOWER" : "IN_BAND";

        Log.Info("BB_DIAG", symbols[i].symbol +
                 " Bid="      + DoubleToString(price,    5) +
                 " Lower="    + DoubleToString(bbl[0],   5) +
                 " Upper="    + DoubleToString(bbu[0],   5) +
                 " SpreadBB=" + DoubleToString(spreadBB, 5) +
                 " pctB="     + DoubleToString(pctB,     1) + "%" +
                 " Zone="     + zone);

        // Blocages BUY
        if(price > bbu[0]) {
            bb_block_count_buy[i]++;
            if(bb_block_count_buy[i] == 1 || bb_block_count_buy[i] % 10 == 0) {
                Log.Warn("BB_DIAG", symbols[i].symbol +
                         " ACHATS BLOQUES x" + (string)bb_block_count_buy[i] +
                         " prix=" + DoubleToString(price,  5) +
                         " > Upper=" + DoubleToString(bbu[0], 5));
            }
        } else {
            if(bb_block_count_buy[i] > 0) {
                Log.Info("BB_DIAG", symbols[i].symbol +
                         " BUY debloque apres " + (string)bb_block_count_buy[i] + " checks");
                bb_block_count_buy[i] = 0;
            }
        }

        // Blocages SELL
        if(price < bbl[0]) {
            bb_block_count_sell[i]++;
            if(bb_block_count_sell[i] == 1 || bb_block_count_sell[i] % 10 == 0) {
                Log.Warn("BB_DIAG", symbols[i].symbol +
                         " VENTES BLOQUEES x" + (string)bb_block_count_sell[i] +
                         " prix=" + DoubleToString(price,  5) +
                         " < Lower=" + DoubleToString(bbl[0], 5));
            }
        } else {
            if(bb_block_count_sell[i] > 0) {
                Log.Info("BB_DIAG", symbols[i].symbol +
                         " SELL debloque apres " + (string)bb_block_count_sell[i] + " checks");
                bb_block_count_sell[i] = 0;
            }
        }
    }
}

//=============================================================
// 7. SAVE TRADE INDICATORS (Phase A++)
//=============================================================
//=============================================================
// 7. SAVE TRADE RISK STATE (Phase A - Ratchet Foundations)
//=============================================================
void SaveTradeRiskState(long posId, int idx, double requestedPrice, double slAtEntry) {
    if(trackedCount >= MAX_TRACKED_TRADES) {
        for(int k = 0; k < MAX_TRACKED_TRADES - 1; k++)
            trackedTrades[k] = trackedTrades[k+1];
        trackedCount = MAX_TRACKED_TRADES - 1;
    }

    string sym = symbols[idx].symbol;
    double totalVol   = 0.0;
    double totalValue = 0.0;
    
    // 1. Récupération des données d'exécution VWAP (Institutional Fill-Aware)
    HistorySelect(TimeCurrent() - 60, TimeCurrent());
    for(int d = 0; d < HistoryDealsTotal(); d++) {
        ulong dt = HistoryDealGetTicket(d);
        if(HistoryDealGetInteger(dt, DEAL_POSITION_ID) == posId && 
           HistoryDealGetInteger(dt, DEAL_ENTRY) == DEAL_ENTRY_IN) {
            double price = HistoryDealGetDouble(dt, DEAL_PRICE);
            double vol   = HistoryDealGetDouble(dt, DEAL_VOLUME);
            totalValue += (price * vol);
            totalVol   += vol;
        }
    }
    
    double fillPrice = (totalVol > 0) ? (totalValue / totalVol) : 0.0;
    double lotSize   = totalVol;
    
    // Fallback si aucun deal trouvé (rare sur position_id)
    if(fillPrice <= 0.0) {
        if(PositionSelectByTicket((ulong)posId)) {
            fillPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            lotSize   = PositionGetDouble(POSITION_VOLUME);
        }
    }

    // 2. Calcul du Risque Initial (1R) Immutable
    double tickVal  = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
    double tickSize = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
    double point    = SymbolInfoDouble(sym, SYMBOL_POINT);
    
    double riskDistPoints = MathAbs(fillPrice - slAtEntry);
    double riskUSD = lotSize * (riskDistPoints * tickVal / tickSize);

    // 3. Stockage Immutable
    trackedTrades[trackedCount].positionId         = posId;
    trackedTrades[trackedCount].initialRiskUSD     = riskUSD;
    trackedTrades[trackedCount].initialRiskDistance = riskDistPoints;
    trackedTrades[trackedCount].entryFill          = fillPrice;
    trackedTrades[trackedCount].slippage           = (requestedPrice > 0) ? MathAbs(fillPrice - requestedPrice) / point : 0.0;
    
    // Initialisation Ratchet
    trackedTrades[trackedCount].lockedFloorR       = 0.0;
    trackedTrades[trackedCount].highestLockedFloorR = 0.0;
    trackedTrades[trackedCount].highestProfitR     = 0.0;
    trackedTrades[trackedCount].maxDrawdownR       = 0.0;
    trackedTrades[trackedCount].ratchetStage       = 0;
    trackedTrades[trackedCount].lastRatchetUpdate  = TimeCurrent();
    trackedTrades[trackedCount].virtualExitR       = -99.0;
    trackedTrades[trackedCount].isVirtualClosed    = false;

    // Heritage Indicateurs
    trackedTrades[trackedCount].rsi         = symbols[idx].lastRSI;
    trackedTrades[trackedCount].adx         = symbols[idx].lastADX;
    trackedTrades[trackedCount].atr         = symbols[idx].lastATR;
    trackedTrades[trackedCount].spread      = SymbolInfoInteger(sym, SYMBOL_SPREAD);
    trackedTrades[trackedCount].regime      = (int)DetectRegime(idx);
    trackedTrades[trackedCount].session     = GetSessionName();

    MqlDateTime _dt; TimeToStruct(TimeCurrent(), _dt);
    trackedTrades[trackedCount].hour        = _dt.hour;
    trackedTrades[trackedCount].day_of_week = (_dt.day_of_week == 0) ? 6 : _dt.day_of_week - 1;
    trackedTrades[trackedCount].confluence   = symbols[idx].currentConfluence;
    trackedTrades[trackedCount].partial_done = false;

    trackedCount++;

    Log.Info("RATCHET_A", "1R LOCK: " + sym + " Risk=$" + DoubleToString(riskUSD, 2) + 
             " | Fill:" + DoubleToString(fillPrice, (int)SymbolInfoInteger(sym, SYMBOL_DIGITS)) +
             " | Slip:" + DoubleToString(trackedTrades[trackedCount-1].slippage, 1) + "pts");
}

string GetSessionName() {
    MqlDateTime _dt; TimeToStruct(TimeCurrent(), _dt);
    int h = _dt.hour;
    if(h >= 0  && h < 7)  return "ASIA";
    if(h >= 7  && h < 13) return "LONDON";
    if(h >= 13 && h < 21) return "NEW_YORK";
    return "OFF";
}

//=============================================================
// 8. EXECUTE ENTRY
//=============================================================
void ExecuteEntry_V7(int idx, int signal, double lot_mult=1.0, double sl_mult=0.0, double tp_mult=0.0) {
    string sym      = symbols[idx].symbol;
    double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
    
    // Override multiples if provided by Python Brain
    double final_sl_mult = (sl_mult > 0) ? sl_mult : ATR_SL_Multiplier;
    double final_tp_mult = (tp_mult > 0) ? tp_mult : ATR_TP_Multiplier;
    
    double risk_val = balance * (RiskPerTrade_Pct / 100.0) * adaptiveLotMult * lot_mult;
    double sl_dist  = symbols[idx].lastATR * final_sl_mult;

    double tick_val  = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
    double tick_size = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);

    double lot = NormalizeVolume_V7(sym, risk_val / (sl_dist * tick_val / tick_size));
    if(lot <= 0.0) return;

    double maxLot = MaxLot_Gold;
    if(symbols[idx].instrType == 1) maxLot = MaxLot_Forex;
    if(symbols[idx].instrType == 2) maxLot = MaxLot_Index;
    if(symbols[idx].instrType == 3) maxLot = MaxLot_NGAS;
    if(lot > maxLot) {
        Log.Warn("LOT", sym + " lot plafonne: " + DoubleToString(lot, 2) +
                 " -> " + DoubleToString(maxLot, 2));
        lot = NormalizeVolume_V7(sym, maxLot);
    }

    double p         = (signal == 1) ? SymbolInfoDouble(sym, SYMBOL_ASK)
                                     : SymbolInfoDouble(sym, SYMBOL_BID);
    double stopLevel = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL)
                       * SymbolInfoDouble(sym, SYMBOL_POINT);
    double buffer    = StopLevelBuffer_Pts * SymbolInfoDouble(sym, SYMBOL_POINT);

    sl_dist = MathMax(sl_dist, stopLevel + buffer);
    double sl = (signal == 1) ? (p - sl_dist) : (p + sl_dist);
    double tp = (signal == 1) ? (p + symbols[idx].lastATR * final_tp_mult)
                              : (p - symbols[idx].lastATR * final_tp_mult);

    if(SimulationMode) {
        Log.Trade("SIM", "[SIM] " + sym + " " + (signal==1?"BUY":"SELL") +
                  " @ " + DoubleToString(p, 5));
        symbols[idx].lastTradeTime = TimeCurrent();
        dailyTradeCount++;
        RecordPerformance_V7(idx, sym, signal, lot, p, sl, tp,
                             "[SIM] V7 " + symbols[idx].activeStratName);
        RecordBlackBoxEntry_V7(idx, signal, lot, p, sl, tp);
        return;
    }

    bool res = false;
    if(signal == 1) res = trade.Buy(lot,  sym, p, sl, tp, "V7 " + symbols[idx].activeStratName);
    else            res = trade.Sell(lot, sym, p, sl, tp, "V7 " + symbols[idx].activeStratName);

    if(res) {
        symbols[idx].lastTradeTime = TimeCurrent();
        dailyTradeCount++;

        // FIX v7.07 : Récupération DEAL_POSITION_ID correct
        ulong dealTicket = trade.ResultDeal();
        long  realPosId  = 0;

        HistorySelect(TimeCurrent() - 10, TimeCurrent());
        for(int d = HistoryDealsTotal()-1; d >= 0; d--) {
            ulong dt = HistoryDealGetTicket(d);
            if(dt == dealTicket) {
                realPosId = HistoryDealGetInteger(dt, DEAL_POSITION_ID);
                break;
            }
        }

        // Fallback : chercher dans les positions ouvertes
        if(realPosId == 0) {
            for(int pi = PositionsTotal()-1; pi >= 0; pi--) {
                ulong pt = PositionGetTicket(pi);
                if(PositionSelectByTicket(pt) &&
                   PositionGetInteger(POSITION_MAGIC) == MagicNumber) {
                    realPosId = (long)pt;
                    break;
                }
            }
        }

        if(realPosId > 0) SaveTradeRiskState(realPosId, idx, p, sl);

        Log.Info("TRACK", "SaveIndicators Deal=" + (string)trade.ResultDeal() +
                 " Order=" + (string)trade.ResultOrder());

        RecordPerformance_V7(idx, sym, signal, lot, p, sl, tp,
                             "V7 " + symbols[idx].activeStratName);
        RecordBlackBoxEntry_V7(idx, signal, lot, p, sl, tp);
    }
}

//=============================================================
// 9. ML FILTER
//=============================================================
bool IsMLSignalOK(string symbol, int direction) {
    string path = "ml_signal.json";
    if(!FileIsExist(path)) {
        Log.Error("ML", "Fichier ml_signal.json ABSENT - Securite Fail-Safe");
        return false;
    }

    int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_ANSI);
    if(h == INVALID_HANDLE) return true;

    string content = "";
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);

    string search = "\"sym\":\"" + symbol + "\"";
    int pos = StringFind(content, search);
    if(pos < 0) {
        Log.Debug("ML", "Symbole " + symbol + " non trouve dans ml_signal.json - Trade BLOCKED (Sniper Security)");
        return false;
    }

    int sig_pos = StringFind(content, "\"signal\":", pos);
    if(sig_pos < 0) return true;
    int sig_val = (int)StringToInteger(StringSubstr(content, sig_pos + 9, 2));

    int    pr_pos = StringFind(content, "\"proba\":", pos);
    double proba  = 0.0;
    if(pr_pos > 0) proba = StringToDouble(StringSubstr(content, pr_pos + 8, 6));

    if(sig_val == 0)             { Log.Debug("ML", "Signal neutralise (sig=0)");            return false; }
    if(sig_val != direction)     { Log.Debug("ML", "Signal ML oppose a la strategie");       return false; }
    if(proba < ML_MinConfidence) { Log.Info("ML",  "Confiance insuffisante: " + DoubleToString(proba,2)); return false; }

    Log.Info("ML", "Confirme par ML (" + DoubleToString(proba, 2) + ")");
    return true;
}

//+------------------------------------------------------------------+
//| Compte les positions ouvertes pour un symbole spécifique         |
//+------------------------------------------------------------------+
int CountPositionsBySymbol(string symbol) {
    int count = 0;
    for(int i = 0; i < PositionsTotal(); i++) {
        if(posInfo.SelectByIndex(i)) {
            if(posInfo.Symbol() == symbol && posInfo.Magic() == MagicNumber)
                count++;
        }
    }
    return count;
}

//=============================================================
// 10. DAILY RESET & RULES ENGINE
//=============================================================
void CheckDailyReset_V7() {
    MqlDateTime dt;
    TimeCurrent(dt);
    datetime start = StringToTime(IntegerToString(dt.year) + "." +
                                  IntegerToString(dt.mon)  + "." +
                                  IntegerToString(dt.day)  + " 00:00");
    if(start > lastResetDay) {
        dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
        dailyTradeCount   = 0;
        dailyCutTriggered = false;
        lastResetDay      = start;
        // V7.22 — reset Overnight Hedge pour la nouvelle journee
        eod_hedge_triggered_today = false;
        eod_last_trigger_day      = start;
        if(Rule_ResetOnNewDay) { tradingEnabled = true; manualPause = false; lotReduceTriggered = false; }
        Log.Info("RESET", "Nouveau jour. Balance: " + DoubleToString(dailyStartBalance, 2));
    }
}

void EvaluateRulesEngine() {
    // V7.20 FIX: Guard against division by zero when account not yet synced
    if(dailyStartBalance <= 0.0) {
        dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
        if(dailyStartBalance <= 0.0) return; // Skip rules until account syncs
    }
    // V7.20: Calculate P&L only for EA positions (magic=707070)
    // Manual trades (magic=0) must NOT block the EA — we are a team
    double eaPnL = 0.0;
    for(int p = PositionsTotal()-1; p >= 0; p--) {
        ulong tk = PositionGetTicket(p);
        if(tk > 0 && PositionSelectByTicket(tk)) {
            if(PositionGetInteger(POSITION_MAGIC) == MagicNumber)
                eaPnL += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
        }
    }
    double eq    = dailyStartBalance + eaPnL;
    double dLoss = ((dailyStartBalance - eq) / dailyStartBalance) * 100.0;
    double dGain = ((eq - dailyStartBalance) / dailyStartBalance) * 100.0;

    consecutiveLosses = CountConsecutiveLosses_V7();

    // V7.18b : NE PAS réinitialiser adaptiveLotMult ici — c'est la cause de la boucle
    // adaptiveLotMult est géré par lotReduceTriggered

    for(int i = 0; i < 3; i++) {
        if(!rules[i].active) continue;
        bool t = false;
        if(rules[i].trigger == TRIGGER_DAILY_LOSS    && dLoss >= rules[i].threshold)                       t = true;
        if(rules[i].trigger == TRIGGER_DAILY_PROFIT  && dGain >= rules[i].threshold && !dailyCutTriggered) t = true;
        if(rules[i].trigger == TRIGGER_CONSEC_LOSSES && consecutiveLosses >= (int)rules[i].threshold)      t = true;

        if(t) {
            // V7.18 FIX — ne loguer qu'une seule fois par déclenchement
            if(rules[i].action == ACTION_CLOSE_ALL && tradingEnabled) {
                CloseAllPositions_V7(rules[i].description);
                tradingEnabled = false;
                Log.Warn("RULE", "Declenchee: " + rules[i].description);
            }
            if(rules[i].action == ACTION_PAUSE && tradingEnabled) {
                tradingEnabled = false;
                if(rules[i].trigger==TRIGGER_DAILY_PROFIT) dailyCutTriggered=true;
                Log.Warn("RULE", "Declenchee: " + rules[i].description);
            }
            // V7.18b FIX — utiliser flag pour eviter boucle
            if(rules[i].action == ACTION_REDUCE_LOT && !lotReduceTriggered) {
                adaptiveLotMult    = rules[i].actionParam;
                lotReduceTriggered = true;
                Log.Warn("RULE", "Declenchee: " + rules[i].description +
                         " — lots reduits a x" + DoubleToString(rules[i].actionParam, 1));
            }
        } else {
            // Condition plus active — reset lot si c'était REDUCE_LOT
            if(rules[i].action == ACTION_REDUCE_LOT && lotReduceTriggered) {
                adaptiveLotMult    = 1.0;
                lotReduceTriggered = false;
                Log.Info("RULE", "Pertes consecutives resolues — lots restaures a x1.0");
            }
        }
    }
}

//=============================================================
// 11. STRATEGY DISPATCHER
//=============================================================
int StrategyDispatcher(int idx, MarketRegime regime, double &outConf, string &outName) {
    if(regime == REGIME_RANGING || regime == REGIME_VOLATILE) return 0;

    double scoreBuy = 0.0, scoreSell = 0.0;
    string namesBuy = "",  namesSell = "";

    if(strategies[0].enabled) {
        double ef[2], es[2];
        if(CopyBuffer(symbols[idx].handle_ema_fast, 0,0,2,ef)==2 &&
           CopyBuffer(symbols[idx].handle_ema_slow, 0,0,2,es)==2) {
            if(regime==REGIME_TRENDING_UP   && ef[1]<=es[1] && ef[0]>es[0]) { scoreBuy  += strategies[0].weight; namesBuy  += "EMA+"; }
            if(regime==REGIME_TRENDING_DOWN && ef[1]>=es[1] && ef[0]<es[0]) { scoreSell += strategies[0].weight; namesSell += "EMA+"; }
        }
    }

    if(strategies[1].enabled) {
        double rsi[2], ef[1], es[1];
        if(CopyBuffer(symbols[idx].handle_rsi, 0,0,2,rsi)==2) {
            CopyBuffer(symbols[idx].handle_ema_fast, 0,0,1,ef);
            CopyBuffer(symbols[idx].handle_ema_slow, 0,0,1,es);
            double pr = SymbolInfoDouble(symbols[idx].symbol, SYMBOL_BID);
            if(regime==REGIME_TRENDING_UP   && pr>es[0] && pr<ef[0] && rsi[0]>40.0 && rsi[0]>rsi[1]) { scoreBuy  += strategies[1].weight; namesBuy  += "RSI+"; }
            if(regime==REGIME_TRENDING_DOWN && pr<es[0] && pr>ef[0] && rsi[0]<60.0 && rsi[0]<rsi[1]) { scoreSell += strategies[1].weight; namesSell += "RSI+"; }
        }
    }

    // ── Stratégie 3 : Momentum (V7.17) ──
    // V7.18 : Momentum désactivé sur EURUSD (WR 18.8% — inefficace)
    if(strategies[2].enabled && symbols[idx].symbol != "EURUSD") {
        double rsi[2], tE[1], ef[1], es[1];
        if(CopyBuffer(symbols[idx].handle_rsi,       0,0,2,rsi)==2 &&
           CopyBuffer(symbols[idx].handle_ema_trend,  0,0,1,tE) >0 &&
           CopyBuffer(symbols[idx].handle_ema_fast,   0,0,1,ef) >0 &&
           CopyBuffer(symbols[idx].handle_ema_slow,   0,0,1,es) >0) {
            double pr = SymbolInfoDouble(symbols[idx].symbol, SYMBOL_BID);
            // BUY : EMA_fast > EMA_slow (tendance haussière) + RSI monte
            if(regime==REGIME_TRENDING_UP &&
               ef[0] > es[0] &&
               rsi[0] >= Momentum_RSI_Bull && rsi[0] > rsi[1]) {
                scoreBuy += strategies[2].weight;
                namesBuy += "MOM+";
            }
            // SELL : EMA_fast < EMA_slow (tendance baissière) + RSI descend
            if(regime==REGIME_TRENDING_DOWN &&
               ef[0] < es[0] &&
               rsi[0] <= Momentum_RSI_Bear && rsi[0] < rsi[1]) {
                scoreSell += strategies[2].weight;
                namesSell += "MOM+";
            }
        }
    }

    if(scoreBuy > 0.0 && scoreBuy >= scoreSell) {
        outConf = scoreBuy;
        outName = (namesBuy == "") ? "NONE" : StringSubstr(namesBuy, 0, StringLen(namesBuy)-1);
        return 1;
    }
    if(scoreSell > 0.0 && scoreSell > scoreBuy) {
        outConf = scoreSell;
        outName = (namesSell == "") ? "NONE" : StringSubstr(namesSell, 0, StringLen(namesSell)-1);
        return -1;
    }
    return 0;
}

//=============================================================
// 12. BLACK BOX & MONITORING
//=============================================================
void RecordBlackBoxEntry_V7(int idx, int sig, double lot, double p, double sl, double tp) {
    int h = FileOpen("aladdin_bb_entry.csv",
                     FILE_WRITE|FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON);
    if(h != INVALID_HANDLE) {
        if(FileSize(h) == 0)
            FileWrite(h, "Time","Symbol","Type","Lot","Entry","SL","TP",
                         "RSI","ADX","ATR","Regime","Session","Conf","Strats","Magic","Comment");
        FileSeek(h, 0, SEEK_END);
        FileWrite(h, TimeToString(TimeCurrent()),
                  symbols[idx].symbol, (sig==1?"BUY":"SELL"),
                  lot, p, sl, tp,
                  DoubleToString(symbols[idx].lastRSI, 2),
                  DoubleToString(symbols[idx].lastADX, 2),
                  DoubleToString(symbols[idx].lastATR, 5),
                  (string)symbols[idx].superTrendDir,
                  GetSessionName(),
                  symbols[idx].currentConfluence,
                  symbols[idx].activeStratName,
                  MagicNumber, "V7");
        FileClose(h);
    }
}

void TrackLiveEvolution_V7() {
    int h = FileOpen("aladdin_bb_evolution.csv",
                     FILE_WRITE|FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON);
    if(h != INVALID_HANDLE) {
        if(FileSize(h) == 0)
            FileWrite(h, "Ticket","Time","Symbol","Price","PnL_Pts","PnL_Money","Equity");
        FileSeek(h, 0, SEEK_END);
        for(int i = 0; i < PositionsTotal(); i++) {
            ulong t = PositionGetTicket(i);
            if(t > 0 && PositionSelectByTicket(t)) {
                if(PositionGetInteger(POSITION_MAGIC) == MagicNumber) {
                    string s   = PositionGetString(POSITION_SYMBOL);
                    double pts = MathAbs(PositionGetDouble(POSITION_PRICE_CURRENT) -
                                        PositionGetDouble(POSITION_PRICE_OPEN)) /
                                 SymbolInfoDouble(s, SYMBOL_POINT);
                    FileWrite(h, t, TimeToString(TimeCurrent()), s,
                              PositionGetDouble(POSITION_PRICE_CURRENT),
                              pts,
                              PositionGetDouble(POSITION_PROFIT),
                              AccountInfoDouble(ACCOUNT_EQUITY));
                }
            }
        }
        FileClose(h);
    }
}

void UpdateMFE_MAE() {
    for(int k = 0; k < trackedCount; k++) {
        long posID = trackedTrades[k].positionId;
        bool found = false;

        if(PositionSelectByTicket((ulong)posID)) {
            found = true;
        } else {
            for(int p = 0; p < PositionsTotal(); p++) {
                ulong pt = PositionGetTicket(p);
                if(PositionSelectByTicket(pt)) {
                    if(PositionGetInteger(POSITION_IDENTIFIER) == posID) {
                        found = true;
                        break;
                    }
                }
            }
        }

        if(!found) continue;

        double currentPnL = PositionGetDouble(POSITION_PROFIT)
                          + PositionGetDouble(POSITION_SWAP);
        
        // 1. Calcul du profit/perte en unités R
        double currentR = (trackedTrades[k].initialRiskUSD > 0) ? (currentPnL / trackedTrades[k].initialRiskUSD) : 0.0;

        // 2. Update MFE (Maximum Favorable Excursion) en R
        if(currentR > trackedTrades[k].highestProfitR) {
            trackedTrades[k].highestProfitR = currentR;
        }
        
        // 3. Update MAE (Maximum Adverse Excursion) en R
        if(currentR < trackedTrades[k].maxDrawdownR) {
            trackedTrades[k].maxDrawdownR = currentR;
        }
    }
}

void CheckForExits_V7() {
    static datetime lastExitCheck = 0;
    if(TimeCurrent() - lastExitCheck < 1) return;
    lastExitCheck = TimeCurrent();

    HistorySelect(TimeCurrent() - 86400, TimeCurrent());
    for(int i = HistoryDealsTotal()-1; i >= 0; i--) {
        ulong t = HistoryDealGetTicket(i);
        if(HistoryDealGetInteger(t, DEAL_MAGIC) == MagicNumber &&
           HistoryDealGetInteger(t, DEAL_ENTRY) == DEAL_ENTRY_OUT) {
            datetime dt = (datetime)HistoryDealGetInteger(t, DEAL_TIME);
            if(dt > TimeCurrent() - 10) {
                int h = FileOpen("aladdin_bb_exit.csv",
                                 FILE_WRITE|FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON);
                if(h != INVALID_HANDLE) {
                    if(FileSize(h) == 0)
                        FileWrite(h, "Ticket","Time","Symbol","ExitPrice","Profit","Reason","Magic");
                    FileSeek(h, 0, SEEK_END);
                    FileWrite(h,
                              HistoryDealGetInteger(t, DEAL_POSITION_ID),
                              TimeToString(dt),
                              HistoryDealGetString(t,  DEAL_SYMBOL),
                              HistoryDealGetDouble(t,  DEAL_PRICE),
                              HistoryDealGetDouble(t,  DEAL_PROFIT),
                              HistoryDealGetString(t,  DEAL_COMMENT),
                              HistoryDealGetInteger(t, DEAL_MAGIC));
                    FileClose(h);

                    // ── V7.14 : Mise à jour cooldown XAUUSD ──
                    string closedSym = HistoryDealGetString(t, DEAL_SYMBOL);
                    double closedPnl = HistoryDealGetDouble(t, DEAL_PROFIT)
                                     + HistoryDealGetDouble(t, DEAL_SWAP);
                    for(int s = 0; s < symbolCount; s++) {
                        if(symbols[s].symbol == closedSym) {
                            UpdateGoldCooldown(s, closedPnl >= 0.0);
                            for(int k = 0; k < trackedCount; k++) {
                                if(trackedTrades[k].positionId == HistoryDealGetInteger(t, DEAL_POSITION_ID)) {
                                    double actualExitR = (trackedTrades[k].initialRiskUSD > 0) ? (closedPnl / trackedTrades[k].initialRiskUSD) : 0.0;
                                    double shadowExitR = (trackedTrades[k].isVirtualClosed) ? trackedTrades[k].virtualExitR : actualExitR;
                                    double alphaR      = shadowExitR - actualExitR;
                                    double effScore    = (trackedTrades[k].highestProfitR > 0) ? (actualExitR / trackedTrades[k].highestProfitR * 100.0) : 0.0;
                                    bool isFalseLock = (trackedTrades[k].isVirtualClosed && (trackedTrades[k].highestProfitR - trackedTrades[k].virtualExitR >= 0.75));
                                    string regStr = (trackedTrades[k].regime == 0) ? "NORMAL" : (trackedTrades[k].regime == 3) ? "EXPANSION" : "CHAOS";
                                    Log.Info("RATCHET_FINAL", closedSym + " [" + regStr + "]" + " | Alpha:" + DoubleToString(alphaR, 2) + "R");
                                    break;
                                }
                            }
                            break;
                        }
                    }
                }
            }
        }
    }

    ExportTradeHistory_V7();
    ApplyManualProtection_V7(); 
    ApplyPreNewsSecure();   
    ApplyBreakEven_V7();    
    ApplyScalingOut_V7();   
    ApplyRatchetProfitLocks_V7(); 
    ApplyTrailingStop_V7(); 
}

//=============================================================
// 13. TRAILING STOP ATR-BASED (V7.20 — GOLD-OPTIMIZED)
//=============================================================
void ApplyTrailingStop_V7() {
    if(!EnableTrailingStop) return;

    for(int i = PositionsTotal()-1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(!PositionSelectByTicket(ticket)) continue;
        // V7.25+: Trail TOUTES les positions — aucun filtre Magic Number
        // EA principal + EOD Hedge + Trades manuels + Signaux Python
        // Seul critère : la position existe et a un ATR disponible

        string sym   = PositionGetString(POSITION_SYMBOL);
        int    ptype = (int)PositionGetInteger(POSITION_TYPE);
        double open  = PositionGetDouble(POSITION_PRICE_OPEN);
        double cur   = PositionGetDouble(POSITION_PRICE_CURRENT);
        double sl    = PositionGetDouble(POSITION_SL);
        double tp    = PositionGetDouble(POSITION_TP);
        double atr   = 0.0;

        for(int j = 0; j < symbolCount; j++) {
            if(StringFind(sym, symbols[j].symbol) >= 0) { atr = symbols[j].lastATR; break; }
        }
        
        if(atr <= 0.0) {
            // Tentative de secours : utiliser l'ATR du graphique actuel si c'est le même symbole
            if(sym == _Symbol) atr = iATR(_Symbol, _Period, 14);
            if(atr <= 0.0) {
               static datetime lastLog = 0;
               if(TimeCurrent()-lastLog > 60) { Log.Warn("TRAIL_SKIP", sym + " ATR indisponible"); lastLog=TimeCurrent(); }
               continue;
            }
        }

        double point  = SymbolInfoDouble(sym, SYMBOL_POINT);
        int    digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
        double newSL  = sl;

        // ── V7.25: PROFILS TRAILING ──────────────────────────────────────────
        // Philosophie : SL initial = respiration. TP = filet lointain.
        // Le TRAILING STOP est le vrai exit. Il colle le prix une fois activé.
        // Aucune fermeture forcée par drawdown — le trailing gère seul.
        // ─────────────────────────────────────────────────────────────────────
        bool isGold  = (sym == "GOLD" || sym == "XAUUSD" || sym == "XAUUSDm");
        bool isIndex = (StringFind(sym, "Volatility") >= 0 ||
                        StringFind(sym, "US30") >= 0 ||
                        StringFind(sym, "US500") >= 0);

        double activation, step;

        if(isGold) {
            // GOLD : Hyper-réactif — protection immédiate
            activation = atr * 0.10; // Se déclenche dès 10% ATR
            step       = atr * 0.08; // Colle à 8% ATR
        }
        else if(isIndex) {
            // INDEX/Volatility : Protection equilibree (Re-stabilise apres test Sticky)
            activation = atr * 0.20; 
            step       = atr * 0.12; 
        }
        else {
            // FOREX : Paramètres inputs standards
            activation = atr * Trail_ATR_Activation;
            step       = atr * Trail_ATR_Step;
        }

        if(ptype == POSITION_TYPE_BUY) {
            if((cur - open) < activation) continue;
            double candidate = NormalizeDouble(cur - step, digits);
            if(candidate <= sl) continue;
            newSL = candidate;
        }
        else if(ptype == POSITION_TYPE_SELL) {
            if((open - cur) < activation) continue;
            double candidate = NormalizeDouble(cur + step, digits);
            if(sl > 0.0 && candidate >= sl) continue;
            newSL = candidate;
        }
        else continue;
        
        static datetime lastDbg = 0;
        if(TimeCurrent() - lastDbg > 10) {
           Log.Info("TRAIL_DBG", sym + " PnL=" + DoubleToString(MathAbs(cur-open)/point, 0) + " pts | TargetSL=" + DoubleToString(newSL, digits));
           lastDbg = TimeCurrent();
        }

        double stopLevel = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL) * point;
        if(ptype == POSITION_TYPE_BUY  && (cur - newSL) < stopLevel) continue;
        if(ptype == POSITION_TYPE_SELL && (newSL - cur) < stopLevel) continue;

        if(trade.PositionModify(ticket, newSL, tp)) {
            Log.Trade("TRAIL_V725", sym + " SL: " + DoubleToString(sl, digits) + " -> " + DoubleToString(newSL, digits));
        } else {
            // Si rejeté (probablement Stop Level), on essaie avec un buffer plus large
            int ret = trade.ResultRetcode();
            if(ret == 10016 || ret == 10014) { // Invalid stops
                double minDist = (stopLevel + 5*point);
                if(ptype == POSITION_TYPE_BUY)  newSL = NormalizeDouble(cur - minDist, digits);
                if(ptype == POSITION_TYPE_SELL) newSL = NormalizeDouble(cur + minDist, digits);
                trade.PositionModify(ticket, newSL, tp);
            }
        }
    }
}

//=============================================================
// 13c. RATCHET ENGINE (Phase B/C)
//=============================================================
void InitRatchetProfiles_V7() {
    // ── PROFILE GOLD (User Specification) ──
    profileGold.symbol      = "GOLD";
    profileGold.activationR = 0.10;
    profileGold.trailGapR   = 0.15;
    profileGold.locks[0]    = 0.5;
    profileGold.locks[1]    = 1.0;
    profileGold.locks[2]    = 1.5;
    profileGold.locks[3]    = 2.5;
    profileGold.lockCount   = 4;

    // ── PROFILE DEFAULT (Forex/Indices) ──
    profileDefault.symbol      = "DEFAULT";
    profileDefault.activationR = 0.50;
    profileDefault.trailGapR   = 0.50;
    profileDefault.locks[0]    = 1.0;
    profileDefault.locks[1]    = 2.0;
    profileDefault.lockCount   = 2;
}

void ApplyScalingOut_V7() {
    for(int k = 0; k < trackedCount; k++) {
        if(trackedTrades[k].partial_done) continue;
        
        ulong t = (ulong)trackedTrades[k].positionId;
        if(!PositionSelectByTicket(t)) continue;

        string sym = PositionGetString(POSITION_SYMBOL);
        double curPnL = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
        double riskUSD = trackedTrades[k].initialRiskUSD;
        
        if(riskUSD <= 0) continue;

        // Scaling Out à 1R (Encaisser 50% du lot)
        if(curPnL >= riskUSD) {
            double vol = PositionGetDouble(POSITION_VOLUME);
            if(vol > 0.01) {
                double closeVol = NormalizeVolume_V7(sym, vol * 0.5);
                if(trade.PositionClosePartial(t, closeVol)) {
                    trackedTrades[k].partial_done = true;
                    Log.Info("SCALE_OUT", sym + " 1R Atteint — 50% encaissé (" + DoubleToString(closeVol, 2) + " lots)");
                    
                    // Après scaling out, on force le BE si pas déjà fait
                    double open = PositionGetDouble(POSITION_PRICE_OPEN);
                    double sl   = PositionGetDouble(POSITION_SL);
                    double tp   = PositionGetDouble(POSITION_TP);
                    int    type = (int)PositionGetInteger(POSITION_TYPE);
                    int    digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
                    double point = SymbolInfoDouble(sym, SYMBOL_POINT);
                    
                    double newSL = (type == POSITION_TYPE_BUY) ? (open + 2*point) : (open - 2*point);
                    newSL = NormalizeDouble(newSL, digits);
                    
                    trade.PositionModify(t, newSL, tp);
                }
            }
        }
    }
}

void ApplyRatchetProfitLocks_V7() {
    // Phase B : Toujours actif pour le logging (Shadow Mode), 
    // mais ne modifie le SL que si USE_RATCHET_ENGINE = true

    for(int k = 0; k < trackedCount; k++) {
        long posId = trackedTrades[k].positionId;
        if(!PositionSelectByTicket((ulong)posId)) continue;
        
        string sym = PositionGetString(POSITION_SYMBOL);
        double curPnL = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
        double riskUSD = trackedTrades[k].initialRiskUSD;
        
        if(riskUSD <= 0) continue;
        
        double currentR = curPnL / riskUSD;
        
        // Sélection du profil
        RatchetProfile p = (sym == "GOLD" || sym == "XAUUSD") ? profileGold : profileDefault;
        
        // 1. Logique RATCHET LOCKS (Floors)
        double newFloorR = trackedTrades[k].lockedFloorR;
        int    newStage  = trackedTrades[k].ratchetStage;
        
        for(int i = 0; i < p.lockCount; i++) {
            if(currentR >= p.locks[i] && p.locks[i] > newFloorR) {
                newFloorR = p.locks[i];
                newStage  = i + 1;
            }
        }
        
        // 2. Logique TRAILING DYNAMIQUE (Gap)
        double dynamicTrailR = -999.0;
        if(currentR >= p.activationR) {
            dynamicTrailR = currentR - p.trailGapR;
        }
        
        // 3. EFFECTIVE STOP (Max entre Trail et Floor)
        double effectiveStopR = MathMax(dynamicTrailR, newFloorR);
        
        if(effectiveStopR > -900.0) {
            // Conversion R -> Prix
            int    type   = (int)PositionGetInteger(POSITION_TYPE);
            double fill   = trackedTrades[k].entryFill;
            double dist   = trackedTrades[k].initialRiskDistance;
            double currentSL = PositionGetDouble(POSITION_SL);
            double tp     = PositionGetDouble(POSITION_TP);
            int    digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
            
            double targetSL = 0.0;
            if(type == POSITION_TYPE_BUY)  targetSL = fill + (effectiveStopR * dist);
            if(type == POSITION_TYPE_SELL) targetSL = fill - (effectiveStopR * dist);
            
            targetSL = NormalizeDouble(targetSL, digits);
            
            // On ne peut que monter le stop (Ratchet)
            bool canMove = false;
            if(type == POSITION_TYPE_BUY  && targetSL > currentSL) canMove = true;
            if(type == POSITION_TYPE_SELL && (currentSL == 0 || targetSL < currentSL)) canMove = true;
            
            if(canMove) {
                if(USE_RATCHET_ENGINE) {
                    // ... (Code existant pour modification réelle) ...
                    if(trade.PositionModify(posId, targetSL, tp)) {
                        trackedTrades[k].lockedFloorR = newFloorR;
                        trackedTrades[k].ratchetStage = newStage;
                        trackedTrades[k].lastRatchetUpdate = TimeCurrent();
                        if(newFloorR > trackedTrades[k].highestLockedFloorR)
                            trackedTrades[k].highestLockedFloorR = newFloorR;
                            
                        Log.Info("RATCHET", sym + " Stage " + (string)newStage + " LOCK: " + 
                                 DoubleToString(effectiveStopR, 2) + "R (SL: " + DoubleToString(targetSL, digits) + ")");
                    }
                } else {
                    // MODE SHADOW : Audit seulement
                    if(!trackedTrades[k].isVirtualClosed) {
                        Log.Info("RATCHET_SHADOW", sym + " WOULD LOCK " + DoubleToString(effectiveStopR, 2) + "R (Stage " + (string)newStage + ")" +
                                 " | CurrentR: " + DoubleToString(currentR, 2) + 
                                 " | ExitEff: " + DoubleToString((currentR > 0 && trackedTrades[k].highestProfitR > 0) ? (currentR / trackedTrades[k].highestProfitR * 100.0) : 100.0, 1) + "%");
                        
                        trackedTrades[k].lockedFloorR = newFloorR;
                        trackedTrades[k].ratchetStage = newStage;
                    }
                }
            }
            
            // 4. DETECTION SORTIE VIRTUELLE (Shadow Exit)
            if(!USE_RATCHET_ENGINE && !trackedTrades[k].isVirtualClosed && effectiveStopR > -900.0) {
                double bid = SymbolInfoDouble(sym, SYMBOL_BID);
                double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
                bool hit = (type == POSITION_TYPE_BUY)  ? (bid <= targetSL) 
                                                        : (ask >= targetSL);
                if(hit) {
                    trackedTrades[k].virtualExitR   = effectiveStopR;
                    trackedTrades[k].isVirtualClosed = true;
                    Log.Warn("RATCHET_AUDIT", sym + " SHADOW EXIT at " + DoubleToString(effectiveStopR, 2) + "R");
                }
            }
        }
    }
}

//=============================================================
// 14. EXPORT TRADE HISTORY
//=============================================================
void ExportTradeHistory_V7() {
    HistorySelect(TimeCurrent() - 86400 * 365, TimeCurrent()); // Historique sur 1 an au lieu de 30 jours
    
    // --- FIX V7.23 : Collecter les tickets d'abord car HistorySelectByPosition casse la boucle ---
    int totalDeals = HistoryDealsTotal();
    ulong dealTickets[];
    ArrayResize(dealTickets, totalDeals);
    for(int i = 0; i < totalDeals; i++) dealTickets[i] = HistoryDealGetTicket(i);

    string j = "[";
    int count = 0;

    for(int i = 0; i < totalDeals; i++) {
        ulong t = dealTickets[i];
        if(HistoryDealGetInteger(t, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;

        if(count > 0) j += ",";

        long   posID  = HistoryDealGetInteger(t, DEAL_POSITION_ID);
        string sym    = HistoryDealGetString(t,  DEAL_SYMBOL);
        double profit = HistoryDealGetDouble(t,  DEAL_PROFIT)
                      + HistoryDealGetDouble(t,  DEAL_SWAP)
                      + HistoryDealGetDouble(t,  DEAL_COMMISSION);

        long   dealType = HistoryDealGetInteger(t, DEAL_TYPE);
        string typeStr  = (dealType == DEAL_TYPE_BUY) ? "buy" : "sell";

        double   priceOpen = 0.0;
        datetime timeOpen  = 0;

        HistorySelectByPosition(posID);
        for(int d = 0; d < HistoryDealsTotal(); d++) {
            ulong dtick = HistoryDealGetTicket(d);
            if(HistoryDealGetInteger(dtick, DEAL_ENTRY) == DEAL_ENTRY_IN) {
                priceOpen = HistoryDealGetDouble(dtick,  DEAL_PRICE);
                timeOpen  = (datetime)HistoryDealGetInteger(dtick, DEAL_TIME);
                break;
            }
        }
        
        // Rétablir la sélection globale pour que l'itération suivante ne plante pas
        HistorySelect(TimeCurrent() - 86400 * 365, TimeCurrent());

        double entryRSI        = 50.0;
        double entryADX        = 25.0;
        double entryATR        = 0.001;
        long   entrySpread     = 20;
        int    entryRegime     = 0;
        string entrySession    = "OFF";
        MqlDateTime _dtO; TimeToStruct(timeOpen, _dtO);
        int    entryHour       = _dtO.hour;
        int    entryDayOfWeek  = (_dtO.day_of_week == 0) ? 6 : _dtO.day_of_week - 1;
        double entryEmaDist    = 0.0;
        double entryConfluence = 0.0;
        double entryBBUpper    = 0.0;
        double entryBBLower    = 0.0;
        double entryBBPos      = 1.0;
        double entryMFE        = 0.0;
        double entryMAE        = 0.0;

        for(int k = 0; k < trackedCount; k++) {
            if(trackedTrades[k].positionId == posID) {
                entryRSI        = trackedTrades[k].rsi;
                entryADX        = trackedTrades[k].adx;
                entryATR        = trackedTrades[k].atr;
                entrySpread     = trackedTrades[k].spread;
                entryRegime     = trackedTrades[k].regime;
                entrySession    = trackedTrades[k].session;
                entryHour       = trackedTrades[k].hour;
                entryDayOfWeek  = trackedTrades[k].day_of_week;
                entryEmaDist    = trackedTrades[k].ema_distance;
                entryConfluence = trackedTrades[k].confluence;
                entryBBUpper    = trackedTrades[k].bb_upper;
                entryBBLower    = trackedTrades[k].bb_lower;
                entryBBPos      = trackedTrades[k].bb_position;
                entryMFE        = trackedTrades[k].mfe;
                entryMAE        = trackedTrades[k].mae;
                break;
            }
        }

        // Fallback INTELLIGENT : On essaie de lire les infos dans le commentaire du trade
        string comment = HistoryDealGetString(t, DEAL_COMMENT);
        if(StringFind(comment, "V7[") >= 0) {
            int start = StringFind(comment, "[") + 1;
            int pipe  = StringFind(comment, "|", start);
            int end   = StringFind(comment, "]", pipe);
            if(pipe > start && end > pipe) {
                entryConfluence = StringToDouble(StringSubstr(comment, start, pipe - start));
                entryRSI        = StringToDouble(StringSubstr(comment, pipe + 1, end - pipe - 1));
            }
        }
        
        // Si vraiment rien n'est trouvé, on ne ment pas : on met 0 au lieu des valeurs LIVE
        if(entryRSI == 50.0) {
            entryRSI = 0; entryADX = 0; entryConfluence = 0;
        }

        j += "{\"ticket\":"       + (string)posID +
             ",\"symbol\":\""     + sym + "\"" +
             ",\"type\":\""       + typeStr + "\"" +
             ",\"volume\":"       + DoubleToString(HistoryDealGetDouble(t, DEAL_VOLUME), 2) +
             ",\"price_open\":"   + DoubleToString(priceOpen, 5) +
             ",\"price_close\":"  + DoubleToString(HistoryDealGetDouble(t, DEAL_PRICE), 5) +
             ",\"pnl\":"          + DoubleToString(profit, 2) +
             ",\"duration\":"     + (string)(HistoryDealGetInteger(t, DEAL_TIME) - timeOpen) +
             ",\"time_open\":"    + (string)((long)timeOpen) +
             ",\"magic\":"        + (string)HistoryDealGetInteger(t, DEAL_MAGIC) +
             ",\"rsi\":"          + DoubleToString(entryRSI, 2) +
             ",\"adx\":"          + DoubleToString(entryADX, 2) +
             ",\"atr\":"          + DoubleToString(entryATR, 5) +
             ",\"spread\":"       + (string)entrySpread +
             ",\"regime\":"       + (string)entryRegime +
             ",\"session\":\""    + entrySession + "\"" +
             ",\"hour\":"         + (string)entryHour +
             ",\"day_of_week\":"  + (string)entryDayOfWeek +
             ",\"ema_distance\":" + DoubleToString(entryEmaDist, 4) +
             ",\"confluence\":"   + DoubleToString(entryConfluence, 2) +
             ",\"bb_upper\":"     + DoubleToString(entryBBUpper, 5) +
             ",\"bb_lower\":"     + DoubleToString(entryBBLower, 5) +
             ",\"bb_position\":"  + DoubleToString(entryBBPos, 1) +
             ",\"mfe\":"          + DoubleToString(entryMFE, 2) +
             ",\"mae\":"          + DoubleToString(entryMAE, 2) +
             "}";
        count++;
    }

    j += "]";

    int fh = FileOpen("trade_history.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(fh != INVALID_HANDLE) {
        FileWriteString(fh, "{\"trades\":"     + j +
                            ",\"total\":"      + (string)count +
                            ",\"exported_at\":\"" + TimeToString(TimeCurrent()) + "\"}");
        FileClose(fh);
    }
}

//=============================================================
// 15. EXPORT TICK DATA
//=============================================================
void ExportTickData_V7() {
    string j = "[";
    for(int i = 0; i < symbolCount; i++) {
        MqlTick t;
        SymbolInfoTick(symbols[i].symbol, t);
        if(i > 0) j += ",";

        double ef[1], es[1];
        double ema_fast_val = 0.0, ema_slow_val = 0.0;
        if(CopyBuffer(symbols[i].handle_ema_fast, 0, 0, 1, ef) > 0) ema_fast_val = ef[0];
        if(CopyBuffer(symbols[i].handle_ema_slow, 0, 0, 1, es) > 0) ema_slow_val = es[0];

        j += "{\"sym\":\""       + symbols[i].symbol + "\"" +
             ",\"bid\":"         + DoubleToString(t.bid, 5) +
             ",\"ask\":"         + DoubleToString(t.ask, 5) +
             ",\"rsi\":"         + DoubleToString(symbols[i].lastRSI, 2) +
             ",\"adx\":"         + DoubleToString(symbols[i].lastADX, 2) +
             ",\"atr\":"         + DoubleToString(symbols[i].lastATR, 5) +
             ",\"spread\":"      + (string)SymbolInfoInteger(symbols[i].symbol, SYMBOL_SPREAD) +
             ",\"regime\":"      + (string)symbols[i].superTrendDir +
             ",\"ema_fast\":"    + DoubleToString(ema_fast_val, 5) +
             ",\"ema_slow\":"    + DoubleToString(ema_slow_val, 5) +
             ",\"confluence\":"  + DoubleToString(symbols[i].currentConfluence, 1) +
             ",\"active_strat\":\"" + symbols[i].activeStratName + "\"}";
    }
    j += "]";

    int h = FileOpen("ticks_v3.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h != INVALID_HANDLE) { FileWriteString(h, j); FileClose(h); }
}

//=============================================================
// 16. STATUS EXPORT & PERFORMANCE LOG
//=============================================================
void ExportStatus_V7() {
    bool terminalTrading = (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)
                        && (bool)MQLInfoInteger(MQL_TRADE_ALLOWED)
                        && (bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED);
    string j = "{\"balance\":"  + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) +
               ",\"equity\":"   + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),  2) +
               ",\"trading\":"  + (terminalTrading ? "true" : "false") +
               ",\"trades_today\":" + (string)dailyTradeCount +
               ",\"account\":"  + (string)AccountInfoInteger(ACCOUNT_LOGIN) +
               ",\"server\":\"" + AccountInfoString(ACCOUNT_SERVER) + "\"" +
               ",\"ts\":"       + (string)((long)TimeCurrent()) +
               ",\"strategy_paused\":" + ((tradingEnabled && !manualPause) ? "false" : "true") +
               ",\"positions\":[";
    int count = 0;
    for(int i = 0; i < PositionsTotal(); i++) {
        ulong t = PositionGetTicket(i);
        if(t > 0 && PositionSelectByTicket(t)) {
            // V7.25+: Affiche TOUT sur le Dashboard (EA + Manuel + EOD)
            if(count > 0) j += ",";
            j += "{\"ticket\":"  + (string)t +
                 ",\"sym\":\""   + PositionGetString(POSITION_SYMBOL) + "\"" +
                 ",\"type\":\""  + (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"BUY":"SELL") + "\"" +
                 ",\"lot\":"     + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) +
                 ",\"price\":"   + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), 5) +
                 ",\"sl\":"      + DoubleToString(PositionGetDouble(POSITION_SL), 5) +
                 ",\"pnl\":"     + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + 
                 ",\"magic\":"   + (string)PositionGetInteger(POSITION_MAGIC) + "}";
            count++;
        }
    }
    j += "]}";
    int h = FileOpen("status.json", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h != INVALID_HANDLE) { FileWriteString(h, j); FileClose(h); }
}

//+------------------------------------------------------------------+
//| ACTION PLAN BRIDGE (V5-V7 BRIDGE)                                |
//+------------------------------------------------------------------+
string ExtractJSONValue_V7(string src, string key) {
    int kp = StringFind(src, "\"" + key + "\"");
    if(kp == -1) return "";
    int cp = StringFind(src, ":", kp);
    if(cp == -1) return "";
    int start = StringFind(src, "\"", cp);
    if(start == -1) {
        start = cp + 1;
        while(start < StringLen(src) && StringGetCharacter(src, start) == ' ') start++;
        int end_c = StringFind(src, ",", start);
        int end_b = StringFind(src, "}", start);
        int end = (end_c != -1 && end_b != -1) ? (int)MathMin(end_c, end_b) : (end_c != -1 ? end_c : end_b);
        if(end == -1) return "";
        return StringSubstr(src, start, end - start);
    }
    int end = StringFind(src, "\"", start + 1);
    if(end == -1) return "";
    return StringSubstr(src, start + 1, end - start - 1);
}

void ProcessActionPlan() {
    if(!FileIsExist("action_plan.json", FILE_COMMON)) return;
    int h = FileOpen("action_plan.json", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h == INVALID_HANDLE) return;
    string content = "";
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);
    FileDelete("action_plan.json", FILE_COMMON); // Acquitter immediatement
    if(StringLen(content) < 10) return;
    
    string decision = ExtractJSONValue_V7(content, "decision");
    string asset    = ExtractJSONValue_V7(content, "asset");
    if(decision == "" || asset == "") return;
    
    // NEW: Extract dynamic risk/RR parameters from Python Brain
    double l_mult  = StringToDouble(ExtractJSONValue_V7(content, "lot_multiplier"));
    double s_mult  = StringToDouble(ExtractJSONValue_V7(content, "sl_mult"));
    double t_mult  = StringToDouble(ExtractJSONValue_V7(content, "tp_mult"));
    
    if(l_mult <= 0) l_mult = 1.0;
    
    int idx = -1;
    for(int i=0; i<symbolCount; i++) if(symbols[i].symbol == asset) { idx = i; break; }
    if(idx == -1) return;
    
    int sig = (decision == "BUY") ? 1 : (decision == "SELL") ? -1 : 0;
    if(sig != 0) {
        Log.Trade("AI_BRIDGE", "AI Signal Received: " + decision + " on " + asset + " | LotMult: " + DoubleToString(l_mult, 2));
        ExecuteEntry_V7(idx, sig, l_mult, s_mult, t_mult);
    }
}

void RecordPerformance_V7(int idx, string sym, int sig, double lot,
                          double p, double sl, double tp, string comment) {
    int h = FileOpen("aladdin_performance.csv",
                     FILE_WRITE|FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON);
    if(h != INVALID_HANDLE) {
        if(FileSize(h) == 0)
            FileWrite(h, "Time","Symbol","Type","Lot","Entry","SL","TP",
                         "Comment","Strategy","Confluence","RSI","ADX","ATR","Session");
        FileSeek(h, 0, SEEK_END);
        FileWrite(h, TimeToString(TimeCurrent()), sym,
                  (sig==1?"BUY":"SELL"), lot, p, sl, tp,
                  comment, symbols[idx].activeStratName,
                  symbols[idx].currentConfluence,
                  DoubleToString(symbols[idx].lastRSI, 2),
                  DoubleToString(symbols[idx].lastADX, 2),
                  DoubleToString(symbols[idx].lastATR, 5),
                  GetSessionName());
        FileClose(h);
    }
}

//=============================================================
// 17. INDICATOR HELPERS
//=============================================================
bool UpdateIndicators(int idx) {
    double b[1];
    if(CopyBuffer(symbols[idx].handle_atr, 0, 0, 1, b) <= 0) return false;
    symbols[idx].lastATR = b[0];
    if(CopyBuffer(symbols[idx].handle_rsi, 0, 0, 1, b) <= 0) return false;
    symbols[idx].lastRSI = b[0];
    if(CopyBuffer(symbols[idx].handle_adx, 0, 0, 1, b) > 0) symbols[idx].lastADX = b[0];
    else symbols[idx].lastADX = 25.0;
    UpdateSuperTrend(idx);
    return true;
}

void UpdateSuperTrend(int idx) {
    if(!Enable_SuperTrend_Filter) return;
    string sym = symbols[idx].symbol;
    if(sym != "EURUSD" && sym != "GBPUSD") { symbols[idx].superTrendDir = 0; return; }

    double atr[], high[], low[], close[];
    int hATR   = symbols[idx].handle_atr_st;
    int copied = CopyBuffer(hATR, 0, 0, 200, atr);
    if(copied <= 0) return;
    if(CopyHigh (sym, ST_Timeframe, 0, copied, high)  <= 0) return;
    if(CopyLow  (sym, ST_Timeframe, 0, copied, low)   <= 0) return;
    if(CopyClose(sym, ST_Timeframe, 0, copied, close) <= 0) return;

    double final_upper = 0.0, final_lower = 0.0;
    int    trend = 1;

    for(int i = 1; i < copied; i++) {
        double hl2     = (high[i] + low[i]) / 2.0;
        double b_upper = hl2 + ST_Multiplier * atr[i];
        double b_lower = hl2 - ST_Multiplier * atr[i];

        if(b_upper < final_upper || close[i-1] > final_upper) final_upper = b_upper;
        if(b_lower > final_lower || close[i-1] < final_lower) final_lower = b_lower;

        if(trend ==  1 && close[i] < final_lower) trend = -1;
        else if(trend == -1 && close[i] > final_upper) trend = 1;
    }
    symbols[idx].superTrendDir = trend;
}

MarketRegime DetectRegime(int idx) {
    if(symbols[idx].lastADX < ADX_MinStrength) return REGIME_RANGING;
    double tE[1], mE[1];
    CopyBuffer(symbols[idx].handle_ema_trend, 0, 0, 1, tE);
    CopyBuffer(symbols[idx].handle_ema_mid,   0, 0, 1, mE);
    double p = SymbolInfoDouble(symbols[idx].symbol, SYMBOL_BID);

    // Regime strict — prix au-dessus des deux EMA
    if(p > tE[0] && p > mE[0]) return REGIME_TRENDING_UP;
    if(p < tE[0] && p < mE[0]) return REGIME_TRENDING_DOWN;

    // V7.17 : Regime assoupli si ADX fort — direction via EMA_fast vs EMA_slow
    if(symbols[idx].lastADX >= ADX_Strong) {
        double ef[1], es[1];
        CopyBuffer(symbols[idx].handle_ema_fast, 0, 0, 1, ef);
        CopyBuffer(symbols[idx].handle_ema_slow, 0, 0, 1, es);
        if(ef[0] > es[0]) return REGIME_TRENDING_UP;
        if(ef[0] < es[0]) return REGIME_TRENDING_DOWN;
    }

    return REGIME_RANGING;
}

void RegisterSymbol(string sym, bool en, int type) {
    if(symbolCount < MAX_SYMBOLS && SymbolSelect(sym, true)) {
        symbols[symbolCount].symbol    = sym;
        symbols[symbolCount].enabled   = en;
        symbols[symbolCount].instrType = type;
        symbolCount++;
    }
}

bool InitSymbolIndicators(int idx) {
    string s = symbols[idx].symbol;
    symbols[idx].handle_ema_fast  = iMA(s, TF_Entry, EMA_Fast,  0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_ema_slow  = iMA(s, TF_Entry, EMA_Slow,  0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_ema_trend = iMA(s, TF_Trend, EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_ema_mid   = iMA(s, TF_Mid,   EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
    symbols[idx].handle_rsi       = iRSI(s, TF_Entry, RSI_Period, PRICE_CLOSE);
    symbols[idx].handle_atr       = iATR(s, TF_Entry, ATR_Period);
    symbols[idx].handle_adx       = iADX(s, TF_Entry, ADX_Period);
    symbols[idx].handle_atr_st    = iATR(s, ST_Timeframe, ST_Period);
    symbols[idx].handle_bb        = iBands(s, TF_Entry, BB_Period, 0, BB_Deviation, PRICE_CLOSE);
    return true;
}

void ReleaseSymbolIndicators(int i) {
    IndicatorRelease(symbols[i].handle_ema_fast);
    IndicatorRelease(symbols[i].handle_ema_slow);
    IndicatorRelease(symbols[i].handle_ema_trend);
    IndicatorRelease(symbols[i].handle_ema_mid);
    IndicatorRelease(symbols[i].handle_rsi);
    IndicatorRelease(symbols[i].handle_atr);
    IndicatorRelease(symbols[i].handle_adx);
    IndicatorRelease(symbols[i].handle_atr_st);
    IndicatorRelease(symbols[i].handle_bb);
}

//=============================================================
// 19. UTILITY FUNCTIONS
//=============================================================
void CloseAllPositions_V7(string r) {
    for(int i = PositionsTotal()-1; i >= 0; i--) {
        ulong t = PositionGetTicket(i);
        if(t > 0 && PositionSelectByTicket(t)) {
            if(PositionGetInteger(POSITION_MAGIC) == MagicNumber)
                trade.PositionClose(t);
        }
    }
    Log.Warn("CLOSE", r);
}

int CountConsecutiveLosses_V7() {
    HistorySelect(TimeCurrent() - 86400*3, TimeCurrent());
    int l = 0;
    for(int i = HistoryDealsTotal()-1; i >= 0; i--) {
        ulong t = HistoryDealGetTicket(i);
        if(HistoryDealGetInteger(t, DEAL_MAGIC) == MagicNumber &&
           HistoryDealGetInteger(t, DEAL_ENTRY) == DEAL_ENTRY_OUT) {
            if(HistoryDealGetDouble(t, DEAL_PROFIT) < 0.0) l++; else break;
        }
    }
    return l;
}

double NormalizeVolume_V7(string sym, double v) {
    double st = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
    return NormalizeDouble(
        MathMax(SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN),
        MathMin(SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX),
        MathFloor(v / st) * st)), 2);
}

bool CheckSpreadOK(int i) {
    long sp  = SymbolInfoInteger(symbols[i].symbol, SYMBOL_SPREAD);
    long max = (symbols[i].instrType == 0) ? MaxSpread_Gold  :
               (symbols[i].instrType == 2) ? MaxSpread_Index :
               (symbols[i].instrType == 3) ? MaxSpread_NGAS  : MaxSpread_Forex;
    return (sp <= max);
}

//=============================================================
// 20. PYTHON COMMANDS (RATCHET)
//=============================================================
void ProcessPythonCommands() {
    string path = "python_commands.json";
    if(!FileIsExist(path, FILE_COMMON)) return;

    int h = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h == INVALID_HANDLE) return;

    string content = "";
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);
    
    if(StringLen(content) < 10) return;

    int pos = 0;
    while((pos = StringFind(content, "\"action\"", pos)) >= 0) {
        string sub = StringSubstr(content, pos, 200); 
        string action = ExtractJSONValue_V7(sub, "action");
        
        if(action == "modify_sl") {
            long   ticket = StringToInteger(ExtractJSONValue_V7(sub, "ticket"));
            double newSL  = StringToDouble( ExtractJSONValue_V7(sub, "new_sl"));
            if(ticket > 0 && PositionSelectByTicket(ticket)) {
                if(trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP))) {
                    Log.Trade("RATCHET", "SL modifie #" + (string)ticket + " -> " + DoubleToString(newSL, 5));
                }
            }
        }
        else if(action == "close") {
            long ticket = StringToInteger(ExtractJSONValue_V7(sub, "ticket"));
            if(ticket > 0 && PositionSelectByTicket(ticket)) {
                if(trade.PositionClose(ticket)) {
                    Log.Trade("REMOTE_CLOSE", "Fermeture manuelle #" + (string)ticket);
                }
            }
        }
        pos += 20;
    }
    FileDelete(path, FILE_COMMON);
}

//+------------------------------------------------------------------+
//| V7.25+ : Synchronisation stricte du compteur journalier          |
//+------------------------------------------------------------------+
void SyncDailyTradeCount_V7() {
    MqlDateTime dt;
    TimeCurrent(dt);
    // Minuit aujourd'hui (Broker Time)
    datetime midnight = StringToTime(IntegerToString(dt.year) + "." +
                                    IntegerToString(dt.mon)  + "." +
                                    IntegerToString(dt.day)  + " 00:00");
    
    HistorySelect(midnight, TimeCurrent());
    int totalDeals = HistoryDealsTotal();
    int count = 0;
    
    for(int i = 0; i < totalDeals; i++) {
        ulong ticket = HistoryDealGetTicket(i);
        if(ticket == 0) continue;
        
        long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
        if(entry != DEAL_ENTRY_IN) continue; // On ne compte que les entrées
        
        long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
        // On ne compte que les trades du bot (Sniper), pas les manuels ni le Hedge
        if(magic == MagicNumber) {
            count++;
        }
    }
    
    dailyTradeCount = count;
    Log.Info("SYNC", "Compteur journalier synchronisé : " + IntegerToString(count) + " trades détectés aujourd'hui.");
}
