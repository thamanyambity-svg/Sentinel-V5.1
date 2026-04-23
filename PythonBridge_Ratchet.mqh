//+------------------------------------------------------------------+
//|  PythonBridge_Ratchet.mqh                                        |
//|  Pont JSON simple pour commandes Python -> MT5 (Ratchet)         |
//|  Lit python_commands.json et exécute :                           |
//|  - modify_sl : modifie SL d'un ticket spécifique                 |
//|  - resume_trading : réactive le trading                          |
//+------------------------------------------------------------------+
#property copyright "Ambity Project V7"
#property strict

// Appel depuis Aladdin Pro V7
void ProcessPythonCommands() {
    string path = "python_commands.json";
    if(!FileIsExist(path, FILE_COMMON)) return;

    int h = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if(h == INVALID_HANDLE) return;

    string content = "";
    while(!FileIsEnding(h)) content += FileReadString(h);
    FileClose(h);

    // Commande resume_trading
    if(StringFind(content, "\"resume_trading\":true") >= 0) {
        extern bool tradingEnabled;
        extern bool manualPause;
        tradingEnabled = true;
        manualPause = false;
        Print("[RATCHET] Trading REACTIVE par Python Bridge");
        // Acquitter
        int hClear = FileOpen(path, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
        if(hClear != INVALID_HANDLE) {
            FileWriteString(hClear, "{\"commands\":[],\"processed\":[\"resume_trading\"]}");
            FileClose(hClear);
        }
        return;
    }

    // Commandes modify_sl multiples
    if(StringFind(content, "\"action\":\"modify_sl\"") >= 0) {
        int pos = 0;
        while((pos = StringFind(content, "\"action\":\"modify_sl\"", pos)) >= 0) {
            int tpos = StringFind(content, "\"ticket\":", pos);
            int slpos = StringFind(content, "\"new_sl\":", pos);
            if(tpos > 0 && slpos > 0) {
                // Extract ticket (assume integer after :)
                int t_start = tpos + 9;
                while(t_start < StringLen(content) && StringGetCharacter(content, t_start) <= ' ') t_start++;
                int t_end = t_start;
                while(t_end < StringLen(content) && StringGetCharacter(content, t_end) >= '0' && StringGetCharacter(content, t_end) <= '9') t_end++;
                long ticket = StringToInteger(StringSubstr(content, t_start, t_end - t_start));

                // Extract new_sl (double after :)
                int sl_start = slpos + 9;
                while(sl_start < StringLen(content) && StringGetCharacter(content, sl_start) <= ' ') sl_start++;
                int sl_end = sl_start;
                while(sl_end < StringLen(content) && 
                      (StringGetCharacter(content, sl_end) >= '0' && StringGetCharacter(content, sl_end) <= '9' ||
                       StringGetCharacter(content, sl_end) == '.' || StringGetCharacter(content, sl_end) == '-')) sl_end++;
                double newSL = StringToDouble(StringSubstr(content, sl_start, sl_end - sl_start));

                if(PositionSelectByTicket(ticket)) {
                    double currentTP = PositionGetDouble(POSITION_TP);
                    if(trade.PositionModify(ticket, newSL, currentTP)) {
                        Print("[RATCHET] SL Ticket #" + (string)ticket + " -> " + DoubleToString(newSL, _Digits));
                    } else {
                        Print("[RATCHET] ÉCHEC SL Ticket #" + (string)ticket + " Error: " + (string)GetLastError());
                    }
                }
            }
            pos += 20; // Skip to next
        }
        // Acquitter toutes les commandes
        int hClear = FileOpen(path, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
        if(hClear != INVALID_HANDLE) {
            FileWriteString(hClear, "{\"commands\":[],\"processed\":[\"modify_sl\"]}");
            FileClose(hClear);
        }
    }
}
