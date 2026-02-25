import os
import json
import time
import sys
try:
    import psutil
except ImportError:
    psutil = None

LOCK_FILE = "trading_bot.lock"
MT5_STATUS = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/status.json"

def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

print("--- HEALTH CHECK ---")

# 1. LOCK FILE
if os.path.exists(LOCK_FILE):
    with open(LOCK_FILE, 'r') as f:
        pid = int(f.read().strip())
    print(f"🔒 Lock File: FOUND (PID {pid})")
    
    if check_pid(pid):
        print("✅ Process: RUNNING")
    else:
        print("❌ Process: DEAD (Zombie Lock)")
else:
    print("❌ Lock File: MISSING")

# 2. STATUS FILE
if os.path.exists(MT5_STATUS):
    try:
        # Read with retries for locking
        content = ""
        with open(MT5_STATUS, 'r', encoding='latin-1') as f:
            content = f.read()
            
        if content:
            data = json.loads(content)
            updated = data.get("updated", 0)
            now = time.time()
            gap = now - updated
            
            print(f"📄 Status: FOUND")
            print(f"   Updated: {time.ctime(updated)}")
            print(f"   Gap: {gap:.1f}s")
            
            if gap < 120:
                print("✅ Heartbeat: GOOD")
            else:
                print("⚠️ Heartbeat: STALE (> 2 mins)")
        else:
            print("⚠️ Status File: EMPTY")
    except Exception as e:
        print(f"❌ Status Read Error: {e}")
else:
    print("❌ Status File: MISSING")

print("--- END ---")
