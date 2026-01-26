//+------------------------------------------------------------------+
//|                                           Sentinel_PathFinder.mq5 |
//|                                  Copyright 2026, Ambity Project  |
//|                                     PATH DISCOVERY UTILITY       |
//+------------------------------------------------------------------+
#property copyright "Ambity"
#property version   "1.00"

int OnInit()
{
   Print("🔎 === SENTINEL PATH FINDER ===");
   
   string dataPath = TerminalInfoString(TERMINAL_DATA_PATH);
   string commonPath = TerminalInfoString(TERMINAL_COMMONDATA_PATH);
   string path = TerminalInfoString(TERMINAL_PATH);
   
   Print("📂 DATA PATH: ", dataPath);
   Print("📂 COMMON PATH: ", commonPath);
   Print("📂 TERMINAL PATH: ", path);
   Print("📂 MQL5 FILES PATH: ", dataPath + "\\MQL5\\Files");
   
   string filename = "PATH_CHECK_V1.txt";
   int handle = FileOpen(filename, FILE_WRITE|FILE_TXT);
   if(handle != INVALID_HANDLE)
   {
      FileWrite(handle, "Sentinel was here at " + TimeToString(TimeCurrent()));
      FileClose(handle);
      Print("✅ Success: Wrote test file to ", filename);
   }
   else
   {
      Print("❌ Error: Could not write file. Error code: ", GetLastError());
   }
   
   Print("🔎 === END REPORT ===");
   
   return(INIT_SUCCEEDED);
}
