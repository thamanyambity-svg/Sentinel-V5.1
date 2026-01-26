import os
import time
import logging
from dotenv import load_dotenv
from bot.bridge.mt5_interface import MT5Bridge

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_bridge():
    load_dotenv("bot/.env")
    
    path = os.getenv("MT5_FILES_PATH")
    login = os.getenv("MT5_LOGIN")
    server = os.getenv("MT5_SERVER")
    
    print(f"🌉 Testing Bridge for AvaTrade")
    print(f"   Path: {path}")
    print(f"   Login: {login}")
    print(f"   Server: {server}")
    
    if not path or not os.path.exists(path):
        print("❌ Error: MT5 Path does not exist!")
        return
        
    bridge = MT5Bridge(root_path=path)
    
    # 1. Check for Heartbeat (Status File)
    print("\n💓 Checking for Sentinel Heartbeat (status.json)...")
    status = bridge.get_raw_status()
    
    if status:
        print(f"   ✅ Status File Found!")
        print(f"   Balance: {status.get('balance')}")
        print(f"   Equity: {status.get('equity')}")
        print(f"   Broker: {status.get('broker', 'Unknown')}")
        
        # Check freshness
        status_file = bridge.status_file
        if os.path.exists(status_file):
            mtime = os.path.getmtime(status_file)
            age = time.time() - mtime
            print(f"   Last Update: {age:.1f} seconds ago")
            
            if age > 60:
                print("   ⚠️ WARNING: Status file is stale (> 60s). Is Sentinel running?")
            else:
                print("   🟢 Bridge is ACTIVE and FRESH.")
    else:
        print("   ❌ Status File NOT Found. Is Sentinel running?")

    # 2. Send PING (Reset Risk command to be safe)
    print("\n📡 Sending RESET RISK command (Ping)...")
    success = bridge.reset_risk()
    print(f"   Command Sent: {success}")
    
    # Wait to see if command file disappears (processed)
    print("⏳ Waiting for processing (5s)...")
    time.sleep(5)
    
    # Check if command folder is empty (processed)
    pending = os.listdir(bridge.command_path)
    if not pending:
         print("✅ Command Processed (Folder Empty)")
    else:
         print(f"⚠️ Command Pending: {pending} (Sentinel might be offline)")

if __name__ == "__main__":
    test_bridge()
