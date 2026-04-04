//+------------------------------------------------------------------+
//|  Aladdin_AI_Bridge.mqh — Include V6.00                          |
//|  Pont MQL5 ↔ OpenAI via fichiers JSON                           |
//|                                                                  |
//|  USAGE — ajouter en haut du bot :                               |
//|    #include "Aladdin_AI_Bridge.mqh"                             |
//|                                                                  |
//|  Fonctions disponibles :                                         |
//|    SendAIRequest(type, priority, log_text)                       |
//|    string ReadAIResponse()                                       |
//|    OnTradeClosedAI(ticket, profit, reason)  // déclencheur      |
//|    OnSessionEndAI()                          // fin de session   |
//|    OnMLSignalAI(sym, proba, confidence)      // signal ML        |
//|    OnNewsAlertAI(event, currency, minutes)   // alerte news      |
//+------------------------------------------------------------------+
#ifndef ALADDIN_AI_BRIDGE_MQH
#define ALADDIN_AI_BRIDGE_MQH

// ─── Paramètre global (peut être surchargé avant l'include) ───────
#ifndef AI_BRIDGE_ENABLED
input bool EnableAIBridge = true; // Activer le pont OpenAI
#endif

// Chemins des fichiers de communication
#define AI_REQUEST_FILE   "ai_request.json"
#define AI_RESPONSE_FILE  "ai_response.json"

// Types de requêtes disponibles
#define AI_TYPE_REPORT    "COMMUNICATOR_REPORT"
#define AI_TYPE_SESSION   "SESSION_REVIEW"
#define AI_TYPE_ML        "ML_INSIGHT"
#define AI_TYPE_NEWS      "NEWS_ALERT"
#define AI_TYPE_EMBED     "DATA_MINING_EMBED"

// Priorités
#define AI_PRIO_NORMAL    "NORMAL"
#define AI_PRIO_HIGH      "HIGH"
#define AI_PRIO_CRITICAL  "CRITICAL"

// Cooldown entre deux requêtes du même niveau (secondes)
#define AI_COOLDOWN_NORMAL   300   // 5 minutes
#define AI_COOLDOWN_HIGH     60    // 1 minute
#define AI_COOLDOWN_CRITICAL 20    // 20 secondes

// ─── État interne ─────────────────────────────────────────────────
static datetime _aiLastNormal   = 0;
static datetime _aiLastHigh     = 0;
static datetime _aiLastCritical = 0;
static int      _aiRequestCount = 0;
static int      _aiErrorCount   = 0;

//+------------------------------------------------------------------+
//|  _AIEscape — Échappe les caractères JSON dangereux               |
//+------------------------------------------------------------------+
string _AIEscape(string s) {
   StringReplace(s, "\\", "\\\\");
   StringReplace(s, "\"", "\\\"");
   StringReplace(s, "\n", " ");
   StringReplace(s, "\r", "");
   StringReplace(s, "\t", " ");
   return s;
}

//+------------------------------------------------------------------+
//|  SendAIRequest — Envoie une requête au bridge Python             |
//|                                                                  |
//|  Paramètres:                                                     |
//|    req_type  — AI_TYPE_REPORT / AI_TYPE_SESSION / etc.           |
//|    priority  — AI_PRIO_NORMAL / HIGH / CRITICAL                  |
//|    log_text  — Log technique à analyser                          |
//|                                                                  |
//|  Retourne: true si la requête a été écrite avec succès           |
//+------------------------------------------------------------------+
bool SendAIRequest(string req_type, string priority, string log_text)
{
   if(!EnableAIBridge) return false;

   // Cooldown check
   datetime now     = TimeCurrent();
   datetime *pLast  = (priority == AI_PRIO_CRITICAL) ? &_aiLastCritical :
                      (priority == AI_PRIO_HIGH)     ? &_aiLastHigh     :
                                                       &_aiLastNormal;
   int cooldown     = (priority == AI_PRIO_CRITICAL) ? AI_COOLDOWN_CRITICAL :
                      (priority == AI_PRIO_HIGH)     ? AI_COOLDOWN_HIGH     :
                                                       AI_COOLDOWN_NORMAL;

   if(now - *pLast < cooldown) return false;

   // Génération d'un ID unique
   _aiRequestCount++;
   string req_id = IntegerToString((int)now) + "_" + IntegerToString(_aiRequestCount);

   // Construction du JSON
   string j = "{"
      + "\"id\":\""       + req_id           + "\","
      + "\"type\":\""     + req_type         + "\","
      + "\"priority\":\"" + priority         + "\","
      + "\"payload\":{"
      + "\"technical_log\":\"" + _AIEscape(log_text) + "\""
      + "}"
      + "}";

   // Écriture du fichier
   int h = FileOpen(AI_REQUEST_FILE, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) {
      _aiErrorCount++;
      Print("[AI-BRIDGE] ERREUR: impossible d'écrire ai_request.json (erreur=",
            GetLastError(), ")");
      return false;
   }
   FileWriteString(h, j);
   FileClose(h);

   *pLast = now;

   Print("[AI-BRIDGE] Requête envoyée — type=", req_type,
         " priority=", priority, " id=", req_id);
   return true;
}

//+------------------------------------------------------------------+
//|  ReadAIResponse — Lit la réponse du bridge OpenAI                |
//|                                                                  |
//|  Retourne: le texte de la réponse GPT ou "" si pas de réponse    |
//+------------------------------------------------------------------+
string ReadAIResponse()
{
   if(!FileIsExist(AI_RESPONSE_FILE)) return "";

   int h = FileOpen(AI_RESPONSE_FILE, FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(h == INVALID_HANDLE) return "";

   string content = "";
   while(!FileIsEnding(h)) content += FileReadString(h);
   FileClose(h);

   if(StringLen(content) < 10) return "";

   // Extraction du champ "result" du JSON
   int pos_start = StringFind(content, "\"result\":");
   if(pos_start < 0) return "";
   pos_start += 9;

   // Chercher si c'est une string (commence par ") ou un array/number
   string remainder = StringSubstr(content, pos_start);
   StringTrimLeft(remainder);

   if(StringGetCharacter(remainder, 0) != '"') return "";  // Embedding → ignorer

   // Trouver le début et la fin de la string JSON
   int inner_start = StringFind(content, "\"result\":\"", 0);
   if(inner_start < 0) return "";
   inner_start += 10;

   // Chercher la fermeture de la string (en ignorant les \" échappés)
   string result = "";
   int i = inner_start;
   while(i < StringLen(content)) {
      ushort c = StringGetCharacter(content, i);
      if(c == '\\' && i + 1 < StringLen(content)) {
         ushort next = StringGetCharacter(content, i + 1);
         if(next == '"') { result += "\""; i += 2; continue; }
         if(next == 'n') { result += "\n"; i += 2; continue; }
         i += 2; continue;
      }
      if(c == '"') break;
      result += ShortToString(c);
      i++;
   }

   // Supprimer le fichier de réponse après lecture
   FileDelete(AI_RESPONSE_FILE);

   return result;
}

//+------------------------------------------------------------------+
//|  _BuildContextLog — Construit le log de contexte complet         |
//+------------------------------------------------------------------+
string _BuildContextLog(string extra = "")
{
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double prof = eq - bal;

   string log_text =
      "Balance: $" + DoubleToString(bal, 2)
      + " | Equity: $"   + DoubleToString(eq, 2)
      + " | PnL open: $" + DoubleToString(prof, 2)
      + " | Positions: " + IntegerToString(PositionsTotal())
      + " | Time: "      + TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES)
      + " | Server: "    + AccountInfoString(ACCOUNT_SERVER);

   if(extra != "") log_text += " | " + extra;
   return log_text;
}

//+------------------------------------------------------------------+
//|  DÉCLENCHEUR 1 — OnTradeClosedAI                                 |
//|  Appeler immédiatement après chaque fermeture de trade            |
//|                                                                  |
//|  Exemple:                                                         |
//|    OnTradeClosedAI(ticket, netProfit, "TP", consecutiveLosses,   |
//|                    drawdownPct, symbol, direction, atr, rsi, adx) |
//+------------------------------------------------------------------+
void OnTradeClosedAI(ulong    ticket,
                     double   net_profit,
                     string   close_reason,
                     int      consec_losses,
                     double   drawdown_pct,
                     string   symbol       = "",
                     string   direction    = "",
                     double   atr          = 0,
                     double   rsi          = 0,
                     double   adx          = 0)
{
   if(!EnableAIBridge) return;

   string priority;
   string req_type = AI_TYPE_REPORT;

   // Sélection de la priorité selon la gravité
   if(consec_losses >= 3 || drawdown_pct >= 4.0) {
      priority = AI_PRIO_CRITICAL;
   } else if(net_profit < 0) {
      priority = AI_PRIO_HIGH;
   } else {
      // Gain : rapport NORMAL si c'est heure pile (rapport de routine)
      if(TimeSeconds(TimeCurrent()) > 3600) return;  // Pas de rapport pour un gain isolé
      priority = AI_PRIO_NORMAL;
   }

   string extra =
      "Trade #"        + IntegerToString((int)ticket)
      + " | Sym: "     + symbol
      + " | Dir: "     + direction
      + " | PnL: $"    + DoubleToString(net_profit, 2)
      + " | Raison: "  + close_reason
      + " | ConsecL: " + IntegerToString(consec_losses)
      + " | DD: "      + DoubleToString(drawdown_pct, 2) + "%"
      + " | ATR: "     + DoubleToString(atr, 5)
      + " | RSI: "     + DoubleToString(rsi, 1)
      + " | ADX: "     + DoubleToString(adx, 1);

   SendAIRequest(req_type, priority, _BuildContextLog(extra));
}

//+------------------------------------------------------------------+
//|  DÉCLENCHEUR 2 — OnSessionEndAI                                  |
//|  Appeler dans OnTimer() à la fermeture de session                 |
//+------------------------------------------------------------------+
void OnSessionEndAI(int    day_trades,
                    int    day_wins,
                    int    day_losses,
                    double pf,
                    double wr,
                    double session_pnl,
                    double max_dd_pct)
{
   if(!EnableAIBridge) return;

   string priority = (pf < 0.8 || max_dd_pct > 3.0) ? AI_PRIO_HIGH : AI_PRIO_NORMAL;

   string extra =
      "SESSION FIN | Trades: " + IntegerToString(day_trades)
      + " W:" + IntegerToString(day_wins)
      + " L:" + IntegerToString(day_losses)
      + " | PF: "     + DoubleToString(pf, 3)
      + " | WR: "     + DoubleToString(wr, 1) + "%"
      + " | PnL: $"  + DoubleToString(session_pnl, 2)
      + " | MaxDD: "  + DoubleToString(max_dd_pct, 2) + "%";

   SendAIRequest(AI_TYPE_SESSION, priority, _BuildContextLog(extra));
}

//+------------------------------------------------------------------+
//|  DÉCLENCHEUR 3 — OnMLSignalAI                                    |
//|  Appeler quand le prédicteur ML émet un signal borderline         |
//+------------------------------------------------------------------+
void OnMLSignalAI(string symbol,
                  double proba,
                  string confidence,
                  int    signal_dir,
                  double rsi,
                  double adx,
                  double atr)
{
   if(!EnableAIBridge) return;
   if(confidence == "HIGH") return;  // Signal clair → pas besoin d'IA

   string priority = (confidence == "LOW") ? AI_PRIO_HIGH : AI_PRIO_NORMAL;

   string extra =
      "ML SIGNAL | Sym: "       + symbol
      + " | Proba: "    + DoubleToString(proba, 3)
      + " | Conf: "     + confidence
      + " | Dir: "      + IntegerToString(signal_dir)
      + " | RSI: "      + DoubleToString(rsi, 1)
      + " | ADX: "      + DoubleToString(adx, 1)
      + " | ATR: "      + DoubleToString(atr, 5);

   SendAIRequest(AI_TYPE_ML, priority, _BuildContextLog(extra));
}

//+------------------------------------------------------------------+
//|  DÉCLENCHEUR 4 — OnNewsAlertAI                                   |
//|  Appeler quand une news HIGH/TIER-1 approche                     |
//+------------------------------------------------------------------+
void OnNewsAlertAI(string event_title,
                   string currency,
                   int    minutes_until,
                   string impact = "HIGH")
{
   if(!EnableAIBridge) return;

   string priority = (minutes_until <= 15 && impact == "CRITICAL") ?
                     AI_PRIO_CRITICAL : AI_PRIO_HIGH;

   string extra =
      "NEWS ALERT | Event: " + event_title
      + " | Currency: "  + currency
      + " | Dans: "      + IntegerToString(minutes_until) + " min"
      + " | Impact: "    + impact;

   SendAIRequest(AI_TYPE_NEWS, priority, _BuildContextLog(extra));
}

//+------------------------------------------------------------------+
//|  CheckAIResponse — Vérifie et log la réponse GPT                 |
//|  Appeler dans OnTimer() toutes les 5-10 secondes                  |
//|                                                                  |
//|  Retourne "" si pas de nouvelle réponse, sinon le texte GPT      |
//+------------------------------------------------------------------+
string CheckAIResponse()
{
   string resp = ReadAIResponse();
   if(resp != "") {
      Print("[AI-GPT] ▶ ", resp);
   }
   return resp;
}

//+------------------------------------------------------------------+
//|  AIBridgeStatus — Retourne un statut compact pour les logs       |
//+------------------------------------------------------------------+
string AIBridgeStatus()
{
   return StringFormat("[AI-BRIDGE] Requests: %d | Errors: %d | Enabled: %s",
          _aiRequestCount, _aiErrorCount, EnableAIBridge ? "YES" : "NO");
}

#endif // ALADDIN_AI_BRIDGE_MQH
