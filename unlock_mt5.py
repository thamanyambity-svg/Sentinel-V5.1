import os
import json
import time

# Path from .env (cleaned)
MT5_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"

def unlock():
    print("🔓 ATTEMPTING TO UNALIVE THE KILL SWITCH...")
    
    # 1. Check/Create Command Directory (V3.10 Requirement)
    cmd_dir = os.path.join(MT5_PATH, "Command")
    if not os.path.exists(cmd_dir):
        print(f"📁 Creating 'Command' directory: {cmd_dir}")
        try:
            os.makedirs(cmd_dir, exist_ok=True)
        except Exception as e:
            print(f"❌ Failed to create directory: {e}")
            return

    # 2. Prepare Command
    # Sentinel V3.10 looks for: {"action": "RESUME_TRADING"}
    command = {
        "action": "RESUME_TRADING",
        "timestamp": int(time.time()),
        "comment": "Unlock via Antigravity"
    }
    
    file_name = f"cmd_unlock_{int(time.time())}.json"
    file_path = os.path.join(cmd_dir, file_name)
    
    # 3. Write File
    try:
        with open(file_path, 'w') as f:
            json.dump(command, f)
        print(f"✅ Command Written: {file_path}")
        print("⏳ Waiting for Sentinel to pick it up...")
    except Exception as e:
        print(f"❌ Failed to write file: {e}")

if __name__ == "__main__":
    unlock()
