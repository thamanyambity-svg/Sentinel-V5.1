from bot.bridge.mt5_interface import COMMAND_PATH # Import global path
import json
import os
import time
import uuid

print("🔄 Sending RESET_RISK command to Sentinel...")

cmd = {
    "action": "RESET_RISK",
    "magic": 999999
}

# Use COMMAND_PATH directly
timestamp = int(os.times()[4] * 1000000)
filename = f"cmd_reset_{int(time.time())}_{uuid.uuid4().hex[:8]}.json"
temp_path = os.path.join(COMMAND_PATH, filename + ".tmp")
final_path = os.path.join(COMMAND_PATH, filename)

try:
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(cmd, f)
    # Atomic rename
    os.rename(temp_path, final_path)
    print(f"✅ Command file created: {filename}")
except Exception as e:
    print(f"❌ Failed to write command: {e}")
