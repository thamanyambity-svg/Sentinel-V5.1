//+------------------------------------------------------------------+
//|  ALADDIN PRO V6 — logging_module.mq5                            |
//|  Capture chaque trade + tous les indicateurs → JSONL             |
//|  Compatible optimizer.py / log_collector.py                      |
//|                                                                  |
//|  INTEGRATION : Copier ce contenu dans Aladdin_Pro_V6.00.mq5     |
//|  dans la section "ÉTAT INTERNE" puis appeler les fonctions       |
//|  depuis ExecuteEntry() et ManageOpenPositions()                  |
//+------------------------------------------------------------------+

// ================================================================
// VARIABLES GLOBALES — coller dans la section globale du bot
// ================================================================
// double sessionStartBalance = 0.0;  // <- deja dans le bot V6

// ================================================================
// STRUCTURE D'UN TRADE LOG
// ================================================================
struct TradeLogEntry {
   ulong    ticket;
   string   symbol;
   string   direction;
   datetime open_time;
   datetime close_time;
   double   open_price;
   double   close_price;
   double   lot;
   double   profit;
   double   commission;
   double   swap;
   double   net_profit;
   double   sl;
   double   tp;
   double   sl_distance;
   double   tp_distance;
   double   rr_ratio;
   double   atr_at_entry;
   double   rsi_at_entry;
   double   adx_at_entry;
   double   ema_fast_entry;
   double   ema_slow_entry;
   double   spread_at_entry;
   int      regime;
   double   rsi_at_exit;
   double   adx_at_exit;
   bool     hit_tp;
   bool     hit_sl;
   bool     be_triggered;
   bool     trail_triggered;
   int      duration_minutes;
   string   close_reason;
   double   balance_after;
   double   equity_after;
};

TradeLogEntry g_pending[50];
int           g_pendingCount = 0;

int _FindPending(ulong ticket) {
   for(int i = 0; i < g_pendingCount; i++)
      if(g_pending[i].ticket == ticket) return i;
   return -1;
}

//================================================================
// LogTradeEntry — Appeler APRES trade.Buy() / trade.Sell() reussi
//================================================================
void LogTradeEntry(ulong ticket, string sym, string direction,
                   double lot, double sl, double tp,
                   double atr, double rsi, double adx,
                   double ema_fast, double ema_slow,
                   int regime, long spread_pts)
{
   if(g_pendingCount >= 49) g_pendingCount = 0;
   int i = g_pendingCount++;
   g_pending[i].ticket          = ticket;
   g_pending[i].symbol          = sym;
   g_pending[i].direction       = direction;
   g_pending[i].open_time       = TimeCurrent();
   g_pending[i].close_time      = 0;
   g_pending[i].lot             = lot;
   g_pending[i].sl              = sl;
   g_pending[i].tp              = tp;
   g_pending[i].atr_at_entry    = atr;
   g_pending[i].rsi_at_entry    = rsi;
   g_pending[i].adx_at_entry    = adx;
   g_pending[i].ema_fast_entry  = ema_fast;
   g_pending[i].ema_slow_entry  = ema_slow;
   g_pending[i].spread_at_entry = (double)spread_pts;
   g_pending[i].regime          = regime;
   g_pending[i].be_triggered    = false;
   g_pending[i].trail_triggered = false;
   g_pending[i].rsi_at_exit     = 0.0;
   g_pending[i].adx_at_exit     = 0.0;

   if(PositionSelectByTicket(ticket)) {
      double op = PositionGetDouble(POSITION_PRICE_OPEN);
      g_pending[i].open_price  = op;
      g_pending[i].sl_distance = (sl > 0) ? MathAbs(op - sl) : atr * 1.5;
      g_pending[i].tp_distance = (tp > 0) ? MathAbs(tp - op) : atr * 2.5;
      double sd = g_pending[i].sl_distance;
      double td = g_pending[i].tp_distance;
      g_pending[i].rr_ratio    = (sd > 0) ? td / sd : 0.0;
   }

   if(EnableLogs)
      Print("[LOG-IN] ", sym, " ", direction, " tk:", ticket,
            " ATR:", DoubleToString(atr, 5),
            " RSI:", DoubleToString(rsi, 1),
            " ADX:", DoubleToString(adx, 1),
            " R:R:", DoubleToString(g_pending[i].rr_ratio, 2));
}

//================================================================
// LogTradeExit — Appeler AVANT chaque fermeture de position
// close_reason: "TP" | "SL" | "SAFETY" | "NEWS" | "DAILY_LIMIT"
//================================================================
void LogTradeExit(ulong ticket, string close_reason)
{
   int idx = _FindPending(ticket);
   if(idx < 0) return;
   if(!PositionSelectByTicket(ticket)) return;

   TradeLogEntry e = g_pending[idx];
   e.close_time   = TimeCurrent();
   e.close_price  = PositionGetDouble(POSITION_PRICE_CURRENT);
   e.profit       = PositionGetDouble(POSITION_PROFIT);
   e.close_reason = close_reason;

   int sidx = FindSymbolIndex(e.symbol);
   if(sidx >= 0) {
      e.rsi_at_exit = symbols[sidx].lastRSI;
      e.adx_at_exit = symbols[sidx].lastADX;
   }

   e.duration_minutes = (int)((e.close_time - e.open_time) / 60);

   double tol = SymbolInfoDouble(e.symbol, SYMBOL_POINT) * 5;
   bool   ib  = (e.direction == "BUY");
   e.hit_tp = (e.tp > 0) && (ib ? e.close_price >= e.tp - tol : e.close_price <= e.tp + tol);
   e.hit_sl = (e.sl > 0) && (ib ? e.close_price <= e.sl + tol : e.close_price >= e.sl - tol);

   e.commission = 0.0;
   e.swap       = 0.0;
   HistorySelect(e.open_time - 5, TimeCurrent() + 5);
   for(int j = HistoryDealsTotal() - 1; j >= 0; j--) {
      ulong dk = HistoryDealGetTicket(j);
      if((long)HistoryDealGetInteger(dk, DEAL_POSITION_ID) == (long)ticket &&
          HistoryDealGetInteger(dk, DEAL_ENTRY) == DEAL_ENTRY_OUT) {
         e.commission = HistoryDealGetDouble(dk, DEAL_COMMISSION);
         e.swap       = HistoryDealGetDouble(dk, DEAL_SWAP);
         break;
      }
   }
   e.net_profit    = e.profit + e.commission + e.swap;
   e.balance_after = AccountInfoDouble(ACCOUNT_BALANCE);
   e.equity_after  = AccountInfoDouble(ACCOUNT_EQUITY);

   _WriteTradeJSONL(e);

   if(EnableLogs)
      Print("[LOG-OUT] ", e.symbol, " ", e.direction,
            " PnL:$", DoubleToString(e.net_profit, 2),
            " ", close_reason, " ", e.duration_minutes, "min",
            " TP:", (e.hit_tp ? "YES" : "no"),
            " SL:", (e.hit_sl ? "YES" : "no"));

   g_pending[idx] = g_pending[g_pendingCount - 1];
   g_pendingCount--;
}

//================================================================
// LogSignalRejected — Enregistre les signaux filtres (throttled)
//================================================================
void LogSignalRejected(string sym, string reason, int dir,
                       double rsi, double adx, double spread,
                       double rr, int regime)
{
   static datetime last_ts[10];
   static string   last_sy[10];
   static int      log_idx = 0;
   datetime now = TimeCurrent();
   for(int i = 0; i < 10; i++)
      if(last_sy[i] == sym && now - last_ts[i] < 10) return;
   last_sy[log_idx] = sym;
   last_ts[log_idx] = now;
   log_idx = (log_idx + 1) % 10;

   string j = "{\"ts\":"     + IntegerToString((int)now)
            + ",\"sym\":\""  + sym + "\""
            + ",\"dir\":"    + IntegerToString(dir)
            + ",\"reason\":\"" + reason + "\""
            + ",\"rsi\":"    + DoubleToString(rsi, 1)
            + ",\"adx\":"    + DoubleToString(adx, 1)
            + ",\"spread\":" + DoubleToString(spread, 0)
            + ",\"rr\":"     + DoubleToString(rr, 3)
            + ",\"regime\":" + IntegerToString(regime)
            + "}\n";

   int h = FileOpen("signal_log.jsonl",
                    FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(h != INVALID_HANDLE) {
      FileSeek(h, 0, SEEK_END);
      FileWriteString(h, j);
      FileClose(h);
   }
}

// Helpers pour ManageOpenPositions
void LogBeTriggered(ulong t)    { int i = _FindPending(t); if(i >= 0) g_pending[i].be_triggered    = true; }
void LogTrailTriggered(ulong t) { int i = _FindPending(t); if(i >= 0) g_pending[i].trail_triggered = true; }

//================================================================
// ExportSessionSummary — Appeler dans OnTimer() toutes les 5 min
//================================================================
void ExportSessionSummary()
{
   static datetime last = 0;
   if(TimeCurrent() - last < 300) return;
   last = TimeCurrent();

   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnl = bal - (dailyStartBalance > 0 ? dailyStartBalance : bal);
   double dd  = (dailyHighWater > 0 && dailyHighWater > eq)
                ? (dailyHighWater - eq) / dailyHighWater * 100.0
                : 0.0;

   int    dw = 0, dl = 0;
   double gw = 0.0, gl = 0.0;
   HistorySelect(TimeCurrent() - 86400, TimeCurrent());
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--) {
      ulong tk = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(tk, DEAL_MAGIC)  != MagicNumber) continue;
      if(HistoryDealGetInteger(tk, DEAL_ENTRY)  != DEAL_ENTRY_OUT) continue;
      double p = HistoryDealGetDouble(tk, DEAL_PROFIT);
      if(p > 0) { dw++; gw += p; } else { dl++; gl += MathAbs(p); }
   }
   double pf = (gl > 0) ? gw / gl : (gw > 0 ? 9.99 : 0.0);
   double wr = (dw + dl > 0) ? (double)dw / (dw + dl) * 100.0 : 0.0;

   string sp = "";
   for(int i = 0; i < symbolCount; i++) {
      if(!symbols[i].enabled) continue;
      if(StringLen(sp) > 0) sp += ",";
      sp += "\"" + symbols[i].symbol + "\":"
            + IntegerToString((int)SymbolInfoInteger(symbols[i].symbol, SYMBOL_SPREAD));
   }

   string j = "{"
      + "\"ts\":"           + IntegerToString((int)TimeCurrent())
      + ",\"balance\":"     + DoubleToString(bal, 2)
      + ",\"equity\":"      + DoubleToString(eq,  2)
      + ",\"session_pnl\":" + DoubleToString(pnl, 2)
      + ",\"drawdown_pct\":" + DoubleToString(dd, 2)
      + ",\"daily_trades\":" + IntegerToString(dailyTradeCount)
      + ",\"day_wins\":"    + IntegerToString(dw)
      + ",\"day_losses\":"  + IntegerToString(dl)
      + ",\"pf\":"          + DoubleToString(pf, 3)
      + ",\"wr\":"          + DoubleToString(wr, 1)
      + ",\"consec_loss\":" + IntegerToString(consecutiveLosses)
      + ",\"lot_mult\":"    + DoubleToString(adaptiveLotMult, 2)
      + ",\"trading\":"     + (tradingEnabled ? "true" : "false")
      + ",\"positions\":"   + IntegerToString(PositionsTotal())
      + ",\"spreads\":{"    + sp + "}"
      + "}";

   int h = FileOpen("session_log.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h != INVALID_HANDLE) { FileWriteString(h, j); FileClose(h); }

   int ha = FileOpen("session_history.jsonl",
                     FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(ha != INVALID_HANDLE) {
      FileSeek(ha, 0, SEEK_END);
      FileWriteString(ha, j + "\n");
      FileClose(ha);
   }
}

//================================================================
// ExportEquityCurve — Appeler dans OnTimer() toutes les 30 sec
//================================================================
void ExportEquityCurve()
{
   static datetime last = 0;
   if(TimeCurrent() - last < 30) return;
   last = TimeCurrent();

   string line = "{"
      + "\"ts\":"      + IntegerToString((int)TimeCurrent())
      + ",\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2)
      + ",\"equity\":"  + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),  2)
      + ",\"profit\":"  + DoubleToString(AccountInfoDouble(ACCOUNT_PROFIT),  2)
      + "}\n";

   int h = FileOpen("equity_curve.jsonl",
                    FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(h != INVALID_HANDLE) {
      FileSeek(h, 0, SEEK_END);
      FileWriteString(h, line);
      FileClose(h);
   }
}

//================================================================
// _WriteTradeJSONL — Ecriture dans trade_log_YYYY-MM-DD.jsonl
//                    et trade_log_all.jsonl
//================================================================
void _WriteTradeJSONL(TradeLogEntry &e)
{
   string j = "{"
      + "\"ticket\":"       + IntegerToString((int)e.ticket)
      + ",\"symbol\":\""    + e.symbol + "\""
      + ",\"direction\":\"" + e.direction + "\""
      + ",\"open_time\":\"" + TimeToString(e.open_time,  TIME_DATE|TIME_SECONDS) + "\""
      + ",\"close_time\":\"" + TimeToString(e.close_time, TIME_DATE|TIME_SECONDS) + "\""
      + ",\"lot\":"         + DoubleToString(e.lot, 2)
      + ",\"profit\":"      + DoubleToString(e.profit, 2)
      + ",\"net_profit\":"  + DoubleToString(e.net_profit, 2)
      + ",\"commission\":"  + DoubleToString(e.commission, 2)
      + ",\"swap\":"        + DoubleToString(e.swap, 2)
      + ",\"open_price\":"  + DoubleToString(e.open_price,  5)
      + ",\"close_price\":" + DoubleToString(e.close_price, 5)
      + ",\"sl_distance\":" + DoubleToString(e.sl_distance, 5)
      + ",\"tp_distance\":" + DoubleToString(e.tp_distance, 5)
      + ",\"rr_ratio\":"    + DoubleToString(e.rr_ratio, 3)
      + ",\"atr_at_entry\":" + DoubleToString(e.atr_at_entry, 5)
      + ",\"rsi_at_entry\":" + DoubleToString(e.rsi_at_entry, 2)
      + ",\"adx_at_entry\":" + DoubleToString(e.adx_at_entry, 2)
      + ",\"ema_fast\":"    + DoubleToString(e.ema_fast_entry, 5)
      + ",\"ema_slow\":"    + DoubleToString(e.ema_slow_entry, 5)
      + ",\"spread_entry\":" + DoubleToString(e.spread_at_entry, 0)
      + ",\"regime\":"      + IntegerToString(e.regime)
      + ",\"rsi_at_exit\":" + DoubleToString(e.rsi_at_exit, 2)
      + ",\"adx_at_exit\":" + DoubleToString(e.adx_at_exit, 2)
      + ",\"hit_tp\":"      + (e.hit_tp  ? "true" : "false")
      + ",\"hit_sl\":"      + (e.hit_sl  ? "true" : "false")
      + ",\"be_triggered\":" + (e.be_triggered    ? "true" : "false")
      + ",\"trail_triggered\":" + (e.trail_triggered ? "true" : "false")
      + ",\"duration_min\":" + IntegerToString(e.duration_minutes)
      + ",\"close_reason\":\"" + e.close_reason + "\""
      + ",\"balance\":"     + DoubleToString(e.balance_after, 2)
      + "}\n";

   MqlDateTime dt; TimeToStruct(e.close_time, dt);
   string d = IntegerToString(dt.year) + "-"
            + (dt.mon < 10 ? "0" : "") + IntegerToString(dt.mon) + "-"
            + (dt.day < 10 ? "0" : "") + IntegerToString(dt.day);

   // Fichier journalier
   int h1 = FileOpen("trade_log_" + d + ".jsonl",
                     FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(h1 != INVALID_HANDLE) { FileSeek(h1, 0, SEEK_END); FileWriteString(h1, j); FileClose(h1); }

   // Fichier global (pour optimizer)
   int h2 = FileOpen("trade_log_all.jsonl",
                     FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(h2 != INVALID_HANDLE) { FileSeek(h2, 0, SEEK_END); FileWriteString(h2, j); FileClose(h2); }
}

/*
================================================================
INTEGRATION DANS Aladdin_Pro_V6.00.mq5 — MODIFICATIONS REQUISES
================================================================

1. Dans ExecuteEntry(), APRES trade.Buy()/Sell() reussi :

   if(ok) {
      ulong ticket = trade.ResultDeal();  // ou ResultOrder()
      double ef_buf[1], es_buf[1]; ArraySetAsSeries(ef_buf,true); ArraySetAsSeries(es_buf,true);
      CopyBuffer(symbols[idx].handle_ema_fast, 0, 0, 1, ef_buf);
      CopyBuffer(symbols[idx].handle_ema_slow, 0, 0, 1, es_buf);
      long spread = SymbolInfoInteger(sym, SYMBOL_SPREAD);
      LogTradeEntry(ticket, sym, (signal==1?"BUY":"SELL"),
                    lot, sl_price, tp_price,
                    symbols[idx].lastATR, symbols[idx].lastRSI, symbols[idx].lastADX,
                    ef_buf[0], es_buf[0],
                    (int)DetectRegime(idx), spread);
      // ... reste du code existant
   }

2. Dans ManageOpenPositions(), AVANT chaque trade.PositionClose() :

   LogTradeExit(ticket, "TP");   // ou "SL", "SAFETY", etc.
   trade.PositionClose(ticket);

3. Dans ManageOpenPositions(), apres ModifyPositionSafe() pour BE :
   LogBeTriggered(ticket);

4. Dans ManageOpenPositions(), apres trail update :
   LogTrailTriggered(ticket);

5. Dans OnTimer(), ajouter les deux appels :
   ExportSessionSummary();   // toutes les 5 min (throttle interne)
   ExportEquityCurve();      // toutes les 30 sec (throttle interne)

6. Dans GetEntrySignal(), avant chaque return 0 (signal rejete) :
   LogSignalRejected(sym, "SPREAD_HIGH", signal, rsi, adx, spread, rr, regime);
   // Raisons standard: SPREAD_HIGH | ADX_LOW | RR_LOW | NEWS_BLOCK | REGIME_RANGING
================================================================
*/
