import os
import json
import time
import random

MT5_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
CMD_DIR = os.path.join(MT5_PATH, "Command")
STATUS_FILE = os.path.join(MT5_PATH, "status.json")

def get_positions_count():
    if not os.path.exists(STATUS_FILE): return -1
    try:
        with open(STATUS_FILE, 'r') as f:
            data = json.load(f)
            return len(data.get("positions", []))
    except:
        return -1

start_count = get_positions_count()
print(f"Initial Positions: {start_count}")

# Command
cmd = {
    "action": "TRADE",
    "symbol": "Volatility 10 (1s) Index",
    "type": "BUY",
    "volume": "0.5",
    "sl": "0.0",
    "tp": "0.0",
    "comment": f"AutoTest-{int(time.time())}"
}

fname = f"cmd_test_{int(time.time())}.json"
fpath = os.path.join(CMD_DIR, fname)
tpath = fpath + ".tmp"

with open(tpath, "w") as f:
    json.dump(cmd, f)
os.rename(tpath, fpath)
print(f"Sent command: {fname}")

# Wait for reaction
print("Waiting for execution...")
for i in range(10):
    time.sleep(1)
    new_count = get_positions_count()
    if new_count != start_count and new_count != -1:
        print(f"SUCCESS! Position count changed: {start_count} -> {new_count}")
        exit(0)
    print(f".", end="", flush=True)

print("\nTimeout. No change in positions.")
