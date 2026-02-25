//+------------------------------------------------------------------+
//|                                     Sentinel_Pro_v10_FIXED.mq5   |
//|                                  Copyright 2026, Ambity Trading  |
//|                     PRO-GRADE HYBRID + STATUS BRIDGE FIXED       |
//+------------------------------------------------------------------+
#property copyright "Ambity Trading Systems"
#property version   "10.11"
#property strict
#property description "Professional Hybrid Trading System - Production Ready + Python Bridge"

#include <Trade\Trade.mqh>

//--- ENUMS ---
enum ENUM_LOG_LEVEL { LOG_DEBUG, LOG_INFO, LOG_WARN, LOG_ERROR };

//+------------------------------------------------------------------+
//| CLASS: CLogger - Advanced Logging System                         |
//+------------------------------------------------------------------+
class CLogger {
private:
    ENUM_LOG_LEVEL m_level;
public:
    CLogger(ENUM_LOG_LEVEL level) : m_level(level) {}
    void SetLevel(ENUM_LOG_LEVEL level) { m_level = level; }
    
    void Log(ENUM_LOG_LEVEL level, string source, string msg) {
        if(level < m_level) return;
        string lvStr = EnumToString(level);
        string entry = StringFormat("[%s][%s] %s: %s", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), lvStr, source, msg);
        Print(entry);
    }
};

//+------------------------------------------------------------------+
//| CLASS: CRiskManager - Professional Risk Control                  |
//+------------------------------------------------------------------+
class CRiskManager {
private:
    double m_maxLoss;
    double m_maxDD;
    double m_hwm;
    bool   m_enabled;
    CLogger *m_log;
public:
    CRiskManager(CLogger *log, double maxLoss, double maxDD) : m_log(log), m_maxLoss(maxLoss), m_maxDD(maxDD), m_hwm(0), m_enabled(true) {}
    
    void UpdateHWM(double equity) { if(equity > m_hwm) m_hwm = equity; }
    
    bool CanTrade(double equity, double balance) {
        if(!m_enabled) return false;
        if(m_hwm <= 0) m_hwm = equity;
        
        if(balance - equity > m_maxLoss) {
            m_log.Log(LOG_ERROR, "RISK", "Max Daily Loss Reached. Trading Disabled.");
            m_enabled = false;
            return false;
        }
        
        double dd = (m_hwm > 0) ? (m_hwm - equity) / m_hwm * 100.0 : 0;
        if(dd > m_maxDD) {
            m_log.Log(LOG_WARN, "RISK", StringFormat("Max Drawdown (%.2f%%) Reached. New Trades Disabled.", dd));
            m_enabled = false;
            return false;
        }
        return true;
    }
    
    void Reset(double equity) { m_hwm = equity; m_enabled = true; m_log.Log(LOG_INFO, "RISK", "System Risk Reset."); }
    bool IsEnabled() const { return m_enabled; }
    void SetHWM(double val) { m_hwm = val; }
    void SetEnabled(bool state) { m_enabled = state; }
    double GetHWM() const { return m_hwm; }
};

//+------------------------------------------------------------------+
//| CLASS: CCommandProcessor - JSON Command Handler                  |
//+------------------------------------------------------------------+
class CCommandProcessor {
private:
    CLogger *m_log;
    string m_dir;
public:
    CCommandProcessor(CLogger *log, string dir) : m_log(log), m_dir(dir) {}
    
    string GetJsonVal(string json, string key) {
        string k = "\"" + key + "\"";
        int p = StringFind(json, k);
        if(p == -1) return "";
        int c = StringFind(json, ":", p + StringLen(k));
        if(c == -1) return "";
        int s = c + 1;
        while(s < StringLen(json) && (json[s] == ' ' || json[s] == '\"' || json[s] == '\t')) s++;
        int e = s;
        while(e < StringLen(json) && json[e] != '\"' && json[e] != ',' && json[e] != '}' && json[e] != '\r' && json[e] != '\n') e++;
        return StringSubstr(json, s, e - s);
    }
    
    bool ReadFile(string path, string &out) {
        int h = FileOpen(path, FILE_READ|FILE_BIN|FILE_SHARE_READ);
        if(h == INVALID_HANDLE) return false;
        ulong size = FileSize(h);
        if(size == 0) { FileClose(h); return false; }
        uchar buf[];
        ArrayResize(buf, (int)size);
        FileReadArray(h, buf);
        FileClose(h);
        out = CharArrayToString(buf, 0, WHOLE_ARRAY, CP_UTF8);
        return true;
    }
};

//--- INPUTS ---
input group "=== CORE SETTINGS ==="
input long           MagicNumber     = 1000001;
input ENUM_LOG_LEVEL MinLogLevel     = LOG_INFO;
input int            ScanTimerSec    = 1;

input group "=== RISK SETTINGS ==="
input double         DailyLossLimit  = 100.0;
input double         DailyDDLimit    = 10.0;
input double         MaxLot          = 2.0;
input double         DefaultRiskPct  = 2.0;
input double         TakeProfitRatio = 1.5;

input bool           UseAladdinAI    = true;
input double         MinAIConfidence = 0.60; 
input bool           UseProtector    = false;
input double         ProtectPips     = 10.0;
input int            MaxPositions    = 1; 

//--- GLOBAL ENGINE ---
CLogger          *Logger;
CRiskManager     *Risk;
CCommandProcessor *Cmd;
CTrade           Trade;
const string     StateFile = "Sentinel_v10_State.dat";
const string     TickFile  = "ticks_v3.json";

//--- PROTOTYPES ---
bool Execute(string json);
double CalcVol(string sym, double r, double sl);
void CloseAll();
void RunProtector();
void SaveState();
void LoadState();
void ExportTickData();
void BroadcastStatus(); // ✅ AJOUTÉ
int CountPositions(string symbol); 

//+------------------------------------------------------------------+
//| MQL5 EVENTS                                                      |
//+------------------------------------------------------------------+
int OnInit() {
    Logger = new CLogger(MinLogLevel);
    Risk = new CRiskManager(Logger, DailyLossLimit, DailyDDLimit);
    Cmd = new CCommandProcessor(Logger, "Command\\");
    
    Trade.SetExpertMagicNumber(MagicNumber);
    Trade.SetTypeFilling(ORDER_FILLING_IOC);
    Trade.SetDeviationInPoints(10);
    
    LoadState();
    EventSetTimer(ScanTimerSec);
    
    if(Risk.GetHWM() == 0) Risk.SetHWM(AccountInfoDouble(ACCOUNT_EQUITY));
    Risk.Reset(AccountInfoDouble(ACCOUNT_EQUITY)); 
    
    Logger.Log(LOG_INFO, "INIT", "Sentinel Pro v10.11 (Python Bridge FIXED) Started.");
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
    SaveState();
    EventKillTimer();
    FileDelete("status.json"); // Clean up
    delete Risk; delete Logger; delete Cmd;
}

void OnTick() {
    double eq = AccountInfoDouble(ACCOUNT_EQUITY);
    double bal = AccountInfoDouble(ACCOUNT_BALANCE);
    
    Risk.UpdateHWM(eq);
    if(!Risk.CanTrade(eq, bal)) SaveState();
    
    if(UseProtector && Risk.IsEnabled()) RunProtector();
    
    ExportTickData();
    BroadcastStatus(); // ✅ AJOUTÉ - Critical for Python Communication
}

void OnTimer() {
    string file;
    long h = FileFindFirst("Command\\*.json", file);
    if(h == INVALID_HANDLE) return;
    
    do {
        string path = "Command\\" + file;
        string json;
        if(Cmd.ReadFile(path, json)) {
            if(Execute(json)) {
               if(!FileDelete(path)) Logger.Log(LOG_WARN, "CMD", "Could not delete " + path);
            }
        }
    } while(FileFindNext(h, file));
    FileFindClose(h);
    
    BroadcastStatus(); // Ensure regular updates
}

//+------------------------------------------------------------------+
//| ✅ PYTHON BRIDGE - STATUS.JSON (CRITICAL FIX)                    |
//+------------------------------------------------------------------+
void BroadcastStatus() {
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    
    string json = "{ \"updated\": " + IntegerToString(TimeCurrent()) + 
                  ", \"balance\": " + DoubleToString(balance, 2) + 
                  ", \"equity\": " + DoubleToString(equity, 2) + 
                  ", \"trading_enabled\": " + (Risk.IsEnabled() ? "true" : "false") +
                  ", \"positions\": [";
    
    int total = PositionsTotal();
    int count = 0;
    for(int i=0; i<total; i++) {
        ulong ticket = PositionGetTicket(i);
        if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MagicNumber) {
            if(count > 0) json += ",";
            json += StringFormat("{\"ticket\": %d, \"symbol\": \"%s\", \"type\": \"%s\", \"volume\": %.2f, \"profit\": %.2f, \"price\": %.5f}", 
                                ticket, 
                                PositionGetString(POSITION_SYMBOL), 
                                (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? "BUY" : "SELL"),
                                PositionGetDouble(POSITION_VOLUME), 
                                PositionGetDouble(POSITION_PROFIT), 
                                PositionGetDouble(POSITION_PRICE_OPEN));
            count++;
        }
    }
    json += "] }";
    
    int handle = FileOpen("status.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
    if(handle != INVALID_HANDLE) { 
        FileWriteString(handle, json); 
        FileClose(handle); 
    }
}

//+------------------------------------------------------------------+
//| DATA EXPORT                                                      |
//+------------------------------------------------------------------+
void ExportTickData() {
   string s[] = {"Volatility 100 Index", "Volatility 75 Index", "EURUSD", "XAUUSD"};
   string json = "{\"t\":" + IntegerToString(TimeCurrent()) + 
                 ",\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + 
                 ",\"ticks\":{";
   
   for(int i=0; i<ArraySize(s); i++) {
      if(!SymbolInfoInteger(s[i], SYMBOL_SELECT)) continue;
      if(i>0) json += ",";
      json += "\"" + s[i] + "\":" + DoubleToString(SymbolInfoDouble(s[i], SYMBOL_BID), (int)SymbolInfoInteger(s[i], SYMBOL_DIGITS));
   }
   json += "}}";

   int h = FileOpen(TickFile, FILE_WRITE|FILE_ANSI|FILE_TXT);
   if(h != INVALID_HANDLE) {
      FileWriteString(h, json);
      FileClose(h);
   }
}

//+------------------------------------------------------------------+
//| EXECUTION CORE                                                   |
//+------------------------------------------------------------------+
bool Execute(string json) {
    string act = Cmd.GetJsonVal(json, "action");
    if(act == "RESET_RISK") { Risk.Reset(AccountInfoDouble(ACCOUNT_EQUITY)); return true; }
    if(act == "CLOSE_ALL") { CloseAll(); return true; }
    if(act == "STATUS") { BroadcastStatus(); return true; }
    
    if(!Risk.IsEnabled()) return false;
    
    string sym = Cmd.GetJsonVal(json, "symbol");
    string type = Cmd.GetJsonVal(json, "type");
    double conf = StringToDouble(Cmd.GetJsonVal(json, "ai_confidence_score"));
    string strategy = Cmd.GetJsonVal(json, "strategy");
    
    if(sym == "" || (type != "BUY" && type != "SELL")) return false;
    
    if(CountPositions(sym) >= MaxPositions) {
        Logger.Log(LOG_WARN, "EXEC", "Trade Rejected: Max Positions Reached (" + IntegerToString(MaxPositions) + ") for " + sym);
        return true;
    }
    
    if(!SymbolInfoInteger(sym, SYMBOL_SELECT)) SymbolSelect(sym, true);
    
    if(UseAladdinAI && conf > 0 && conf < MinAIConfidence) {
        Logger.Log(LOG_INFO, "AI", "Signal filtered: " + DoubleToString(conf, 2) + " < " + DoubleToString(MinAIConfidence, 2));
        return true;
    }
    
    double sl_p = StringToDouble(Cmd.GetJsonVal(json, "stop_loss_pips"));
    if(sl_p <= 0) sl_p = 50; 
    
    double vol = CalcVol(sym, DefaultRiskPct, sl_p);
    double min_lot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
    if(vol < min_lot) vol = min_lot;
    
    double prc = (type == "BUY") ? SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);
    double pnt = SymbolInfoDouble(sym, SYMBOL_POINT);
    
    double sent_sl = 0; 
    double tp = (type == "BUY") ? prc + sl_p*pnt*TakeProfitRatio : prc - sl_p*pnt*TakeProfitRatio;
    
    bool res = (type == "BUY") ? Trade.Buy(vol, sym, prc, sent_sl, tp, "v10 " + strategy) : Trade.Sell(vol, sym, prc, sent_sl, tp, "v10 " + strategy);
    if(res) Logger.Log(LOG_INFO, "EXEC", StringFormat("Executed %s %s Vol:%.3f TP:%.2f [NO SL]", type, sym, vol, tp));
    else Logger.Log(LOG_ERROR, "EXEC", "Trade Failed: " + IntegerToString(Trade.ResultRetcode()) + " " + Trade.ResultComment());
    
    return res;
}

double CalcVol(string sym, double r, double sl) {
    double eq = AccountInfoDouble(ACCOUNT_EQUITY);
    if(eq < 100.0) return SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);

    double tv = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
    double ts = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
    
    if(tv == 0 || ts == 0 || sl == 0) return SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
    
    double v = (eq * r / 100.0) / (sl * (tv / ts));
    
    double st = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
    v = MathFloor(v/st)*st;
    
    double minLot = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
    double maxLot = MathMin(MaxLot, SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX));
    
    if(eq < 500.0) {
       double safetyCap = MathMax(minLot, 0.01); 
       v = MathMin(v, safetyCap);
    }
    
    return MathMax(minLot, MathMin(maxLot, v));
}

void CloseAll() {
    for(int i=PositionsTotal()-1; i>=0; i--) {
        ulong t = PositionGetTicket(i);
        if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == MagicNumber) Trade.PositionClose(t);
    }
}

void RunProtector() {
    for(int i=PositionsTotal()-1; i>=0; i--) {
        ulong t = PositionGetTicket(i);
        if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == MagicNumber) {
            double op = PositionGetDouble(POSITION_PRICE_OPEN);
            double cp = PositionGetDouble(POSITION_PRICE_CURRENT);
            double sl = PositionGetDouble(POSITION_SL);
            double pnt = SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_POINT);
            
            if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) {
               if((cp - op) > ProtectPips*pnt && sl < op) Trade.PositionModify(t, op, PositionGetDouble(POSITION_TP));
            } else {
               if((op - cp) > ProtectPips*pnt && (sl == 0 || sl > op)) Trade.PositionModify(t, op, PositionGetDouble(POSITION_TP));
            }
        }
    }
}

void SaveState() {
    int h = FileOpen(StateFile, FILE_WRITE|FILE_BIN);
    if(h != INVALID_HANDLE) { FileWriteDouble(h, Risk.GetHWM()); FileWriteInteger(h, (int)Risk.IsEnabled()); FileClose(h); }
}

void LoadState() {
    int h = FileOpen(StateFile, FILE_READ|FILE_BIN);
    if(h != INVALID_HANDLE) { Risk.SetHWM(FileReadDouble(h)); Risk.SetEnabled((bool)FileReadInteger(h)); FileClose(h); }
}

int CountPositions(string symbol) {
    int count = 0;
    for(int i=PositionsTotal()-1; i>=0; i--) {
        ulong ticker = PositionGetTicket(i);
        if(PositionSelectByTicket(ticker)) {
            if(PositionGetString(POSITION_SYMBOL) == symbol && PositionGetInteger(POSITION_MAGIC) == MagicNumber) {
                count++;
            }
        }
    }
    return count;
}
