import os
import sys

# Patch Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from bot.bridge.mt5_interface import COMMAND_PATH, STATUS_FILE, MT5_ROOT_PATH

print(f"--- PATH DEBUG ---")
print(f"ROOT: {MT5_ROOT_PATH}")
print(f"CMD:  {COMMAND_PATH}")
print(f"STATUS: {STATUS_FILE}")

print(f"\n--- EXISTENCE CHECK ---")
print(f"ROOT EXIST? {os.path.exists(MT5_ROOT_PATH)}")
print(f"CMD  EXIST? {os.path.exists(COMMAND_PATH)}")
print(f"STATUS EXIST? {os.path.exists(STATUS_FILE)}")

print(f"\n--- ROOT CONTENT ---")
try:
    if os.path.exists(MT5_ROOT_PATH):
        for f in os.listdir(MT5_ROOT_PATH):
            print(f"  - {f}")
    else:
        print("Root not found.")
except Exception as e:
    print(f"Error listing root: {e}")

print(f"\n--- COMMAND CONTENT ---")
try:
    if os.path.exists(COMMAND_PATH):
        for f in os.listdir(COMMAND_PATH):
            print(f"  - {f}")
    else:
        print("Command dir not found.")
except Exception as e:
    print(f"Error listing command: {e}")
