import os
import json
import time

MT5_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
CMD_DIR = os.path.join(MT5_PATH, "Command")

if not os.path.exists(CMD_DIR):
    print(f"Directory not found: {CMD_DIR}")
    exit(1)

# 1. Compact JSON (No spaces)
cmd_compact = {
    "action": "TRADE",
    "symbol": "Volatility 100 (1s) Index",
    "type": "SELL",
    "volume": "0.5",
    "sl": "0.0",
    "tp": "0.0",
    "comment": "Test-Compact"
}
file_c = os.path.join(CMD_DIR, "test_compact.json")
with open(file_c, "w") as f:
    # separators removes spaces
    json.dump(cmd_compact, f, separators=(',', ':'))
print(f"Wrote {file_c}")

# 2. Normal JSON (With spaces)
cmd_normal = {
    "action": "TRADE",
    "symbol": "Volatility 100 (1s) Index",
    "type": "SELL",
    "volume": "0.5",
    "sl": "0.0",
    "tp": "0.0",
    "comment": "Test-Normal"
}
file_n = os.path.join(CMD_DIR, "test_normal.json")
with open(file_n, "w") as f:
    json.dump(cmd_normal, f) # Defaults to spaces
print(f"Wrote {file_n}")
