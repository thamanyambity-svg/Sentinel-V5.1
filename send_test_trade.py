import json
import os
import time

# Paths
MT5_FILES_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
COMMAND_PATH = os.path.join(MT5_FILES_PATH, "Command")
STATUS_FILE = os.path.join(MT5_FILES_PATH, "status.json")

# Ensure command directory exists
os.makedirs(COMMAND_PATH, exist_ok=True)

# Create a test trade command
command_id = int(time.time())
filename = f"cmd_{command_id}.json"
filepath = os.path.join(COMMAND_PATH, filename)

trade_command = {
    "action": "TRADE",
    "symbol": "EURUSD",
    "type": "BUY",
    "volume": 0.01,
    "sl": 0.0,
    "tp": 0.0,
    "comment": "Sentinel_Test_V4.5"
}

print(f"🚀 Sending Test Command: {json.dumps(trade_command)}")

with open(filepath, "w") as f:
    json.dump(trade_command, f)

print(f"✅ Command file created: {filepath}")
print("⏳ Waiting for execution...")

# Monitor status.json for 10 seconds
for i in range(10):
    time.sleep(1)
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                content = f.read()
                data = json.loads(content)
                positions = data.get("positions", [])
                print(f"📊 Status Update [T+{i}]: {len(positions)} positions open. Equity: {data.get('equity')}")
                
                # Check if our trade is there
                for pos in positions:
                    if pos.get("symbol") == "EURUSD" and abs(pos.get("vol") - 0.01) < 0.001:
                        print("🎉 SUCCESS! Trade executed and visible in status.")
                        exit(0)
        except Exception as e:
            print(f"⚠️ Error reading status: {e}")
    else:
        print("⚠️ status.json not found yet.")

print("❌ Timed out waiting for trade confirmation.")
