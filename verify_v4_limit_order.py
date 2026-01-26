import os
import json
import time
import random

# MT5 Paths
MT5_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
CMD_DIR = os.path.join(MT5_PATH, "Command")

if not os.path.exists(CMD_DIR):
    print(f"⚠️ Warning: Command directory not found at {CMD_DIR}")
    # Try creating it if it doesn't exist? No, better to warn.
else:
    print(f"✅ Command directory found: {CMD_DIR}")

# Command: BUY_LIMIT (Smart Price)
# We send price="0.0" to test if the bot correctly calculates the passive price based on spread.
cmd = {
    "action": "TRADE",
    "symbol": "Volatility 100 (1s) Index", 
    "type": "BUY_LIMIT",
    "volume": "0.2",
    "price": "0.0", 
    "sl": "0.0",
    "tp": "0.0",
    "comment": f"V4-LimitTest-{int(time.time())}"
}

fname = f"cmd_limit_{int(time.time())}.json"
fpath = os.path.join(CMD_DIR, fname)
tpath = fpath + ".tmp"

try:
    with open(tpath, "w") as f:
        json.dump(cmd, f)
    os.rename(tpath, fpath)
    print(f"🚀 Sent BUY_LIMIT command: {fname}")
    print(f"ℹ️  Payload: {json.dumps(cmd, indent=2)}")
    print("\n👉 CHECK MT5 TERMINAL NOW:")
    print("1. Look at the 'Trade' tab.")
    print("2. You should see a PENDING ORDER (Buy Limit) placed below the current price.")
    print("3. Check 'Experts' tab for log: '✅ BUYLIMIT PLACED'")
except Exception as e:
    print(f"❌ Failed to write command file: {e}")
