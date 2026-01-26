import os
import glob
import datetime
import sys

OUTPUT_FILE = "diagnostic_output.txt"

def log(msg):
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# Clear file
with open(OUTPUT_FILE, "w") as f:
    f.write(f"--- DIAGNOSTIC RUN {datetime.datetime.now()} ---\n")

# Paths
BASE_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5"
FILES_PATH = os.path.join(BASE_PATH, "Files")
COMMAND_PATH = os.path.join(FILES_PATH, "Command")
LOGS_PATH = os.path.join(BASE_PATH, "Logs")
TEST_FILE = os.path.join(COMMAND_PATH, "manual_test.json")

# 1. Check Command File
if os.path.exists(TEST_FILE):
    log(f"✅ manual_test.json EXISTS at: {TEST_FILE}")
else:
    log(f"❌ manual_test.json MISSING at: {TEST_FILE}")

# 2. List Command Directory
if os.path.exists(COMMAND_PATH):
    files = os.listdir(COMMAND_PATH)
    log(f"📂 Command Directory Content ({len(files)} files):")
    for f in files:
        log(f"   - {f}")
else:
    log(f"❌ Command Directory NOT FOUND: {COMMAND_PATH}")

# 3. Find latest Log
log("🔍 Searching for recent MT5 logs...")
if os.path.exists(LOGS_PATH):
    log_files = glob.glob(os.path.join(LOGS_PATH, "*.log"))
    if log_files:
        latest_log = max(log_files, key=os.path.getmtime)
        log(f"📄 Latest Log File: {latest_log}")
        try:
            size = os.path.getsize(latest_log)
            # Read last 8000 bytes
            seek_pos = max(0, size - 8000)
            
            with open(latest_log, 'rb') as f:
                f.seek(seek_pos)
                raw_data = f.read()
                try:
                    text = raw_data.decode('utf-16le', errors='ignore')
                except:
                    text = raw_data.decode('utf-8', 'ignore')
                
                lines = text.splitlines()[-30:] # Last 30 lines
                log("   📜 LAST 30 LINES:")
                for line in lines:
                    log(f"      {line.strip()}")
        except Exception as e:
            log(f"   ❌ Error reading log file: {e}")
    else:
        log("❌ No .log files found in Logs directory.")
else:
    log(f"❌ Logs directory NOT FOUND: {LOGS_PATH}")
