//+------------------------------------------------------------------+
//|                                              Sentinel_Socket.mqh |
//|                                  Copyright 2026, Sentinel System |
//+------------------------------------------------------------------+
#property copyright "Sentinel System"
#property link      "https://sentinel.ai"
//+------------------------------------------------------------------+
//| Socket Communication Functions (WebRequest JSON bridge)          |
//| Uses MQL5 native WebRequest to talk to Python FastAPI server     |
//+------------------------------------------------------------------+

string SendToCognitiveServer(string action, string asset, string tech_signal) {
   string cookie = NULL;
   string req_headers = "Content-Type: application/json\r\n";
   string res_headers;
   char post[], result[];
   string url = "http://127.0.0.1:5555/evaluate";
   
   // --- EXTRACTION DU FLUX D'ORDRES (VISION BOOKMAP) ---
   MqlBookInfo book[];
   double imbalance = 0.0;
   if(MarketBookGet(asset, book)) {
      double totalBidVol = 0;
      double totalAskVol = 0;
      int size = ArraySize(book);
      for(int i=0; i<size; i++) {
         if(book[i].type == BOOK_TYPE_BUY) totalBidVol += (double)book[i].volume;
         if(book[i].type == BOOK_TYPE_SELL) totalAskVol += (double)book[i].volume;
      }
      if(totalBidVol + totalAskVol > 0)
         imbalance = (totalBidVol - totalAskVol) / (totalBidVol + totalAskVol);
   }
   
   // Construire le JSON payload enrichi
   string json = StringFormat("{\"action\":\"%s\", \"asset\":\"%s\", \"tech_signal\":\"%s\", \"imbalance\":%.3f}", 
                              action, asset, tech_signal, imbalance);
   StringToCharArray(json, post, 0, StringLen(json), CP_UTF8);
   
   // Premier essai (timeout 5 secondes pour laisser l'IA réfléchir)
   int res = WebRequest("POST", url, req_headers, 5000, post, result, res_headers);
   
   // Système de retry simple pour l'erreur 1003 (Saturation/Timeout MT5)
   if(res == 1003 || res == -1) {
      Sleep(200); // Petite pause de respiration
      res = WebRequest("POST", url, req_headers, 5000, post, result, res_headers);
   }
   
   if(res == 200) {
      string response = CharArrayToString(result, 0, ArraySize(result), CP_UTF8);
      return response;
   } else if(res == -1) {
      int err = GetLastError();
      if(err == 4014)
         Print("⚠️ WebRequest interdit. Ajouter http://127.0.0.1:5555 dans Outils > Options > Expert Advisors");
      else
         Print("❌ ERROR WebRequest (erreur ", err, ")");
      return "";
   } else {
      Print("❌ ERROR: Cognitive Server returned HTTP ", res);
      return "";
   }
}

//+------------------------------------------------------------------+
//| Simple JSON Parser (Extracts value by key)                       |
//+------------------------------------------------------------------+
string ExtractJSONValue(string json, string key) {
   string key_search = "\"" + key + "\":";
   int pos = StringFind(json, key_search);
   if(pos == -1) return "";
   
   int val_start = pos + StringLen(key_search);
   // Ignorer les espaces et les guillemets de début
   while(val_start < StringLen(json) && (StringSubstr(json, val_start, 1) == " " || StringSubstr(json, val_start, 1) == "\""))
      val_start++;
      
   int val_end = val_start;
   while(val_end < StringLen(json) && StringSubstr(json, val_end, 1) != "," && StringSubstr(json, val_end, 1) != "}" && StringSubstr(json, val_end, 1) != "\"" && StringSubstr(json, val_end, 1) != "]")
      val_end++;
      
   return StringSubstr(json, val_start, val_end - val_start);
}

//+------------------------------------------------------------------+
//| Feedback to APEX (Transactional Autopsy)                         |
//+------------------------------------------------------------------+
void SendFeedbackToServer(long ticket, string asset, string type, double profit, double spm, double prob, double imbalance) {
   string req_headers = "Content-Type: application/json\r\n";
   string res_headers;
   char post[], result[];
   string url = "http://127.0.0.1:5555/feedback";
   
   string json = StringFormat("{\"ticket\":%lld, \"asset\":\"%s\", \"type\":\"%s\", \"profit\":%.2f, \"spm_score\":%.3f, \"nexus_prob\":%.3f, \"imbalance\":%.3f}",
                              ticket, asset, type, profit, spm, prob, imbalance);
   
   StringToCharArray(json, post, 0, StringLen(json), CP_UTF8);
   WebRequest("POST", url, req_headers, 2000, post, result, res_headers);
}
