import os
import time
import datetime

MT5_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
CMD_DIR = os.path.join(MT5_PATH, "Command")
STATUS_FILE = os.path.join(MT5_PATH, "status.json")

def print_stat(path):
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        dt = datetime.datetime.fromtimestamp(mtime)
        print(f"File: {os.path.basename(path)}")
        print(f"  Modified: {dt} ({int(time.time() - mtime)} seconds ago)")
        print(f"  Size: {os.path.getsize(path)} bytes")
    else:
        print(f"File NOT FOUND: {path}")

print("--- BRIDGE STATUS ---")
print_stat(STATUS_FILE)

print("\n--- COMMAND QUEUE ---")
if os.path.exists(CMD_DIR):
    files = os.listdir(CMD_DIR)
    print(f"Files in Command: {len(files)}")
    for f in files:
        print(f" - {f}")
else:
    print("Command Dir NOT FOUND")
