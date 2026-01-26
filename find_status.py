from bot.bridge.mt5_interface import MT5Bridge, STATUS_FILE
import os

print(f"Checking status file at: {STATUS_FILE}")
if os.path.exists(STATUS_FILE):
    with open(STATUS_FILE, 'r') as f:
        print(f"Content: {f.read()}")
else:
    print("❌ Status file not found.")
