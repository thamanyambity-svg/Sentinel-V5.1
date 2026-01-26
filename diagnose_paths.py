import os
import glob
import datetime

# Helper to print safely
def log(msg):
    print(msg.encode('utf-8', 'replace').decode('utf-8'))

# Paths
BASE_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5"
FILES_PATH = os.path.join(BASE_PATH, "Files")
COMMAND_PATH = os.path.join(FILES_PATH, "Command")
LOGS_PATH = os.path.join(BASE_PATH, "Logs")
TEST_FILE = os.path.join(COMMAND_PATH, "manual_test.json")

log(f"🔍 DIAGNOSTIC START: {datetime.datetime.now()}")

# 1. Check Command File
if os.path.exists(TEST_FILE):
    log(f"✅ manual_test.json EXISTS at: {TEST_FILE}")
    try:
        with open(TEST_FILE, 'r') as f:
            log(f"   Content: {f.read()}")
    except Exception as e:
        log(f"   ❌ Error reading file: {e}")
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
            # Read binary/text mix safely
            with open(latest_log, 'rb') as f:
                # Seek to end minus 2KB to get recent lines
                size = os.path.getsize(latest_log)
                seek_pos = max(0, size - 4000)
                f.seek(seek_pos)
                raw_data = f.read()
                # Decode utf-16le (common in MT5) or utf-8 or latin1
                try:
                    text = raw_data.decode('utf-16le', errors='ignore')
                except:
                    text = raw_data.decode('utf-8', 'ignore')
                
                lines = text.splitlines()[-20:]
                log("   📜 LAST 20 LINES:")
                for line in lines:
                    log(f"      {line.strip()}")
        except Exception as e:
            log(f"   ❌ Error reading log file: {e}")
    else:
        log("❌ No .log files found in Logs directory.")
else:
    log(f"❌ Logs directory NOT FOUND: {LOGS_PATH}")
