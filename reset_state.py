import os
import subprocess
import time
import signal
import glob

def main():
    print("🧹 STARTING CLEAN RESET...")
    
    # 1. KILL EVERYTHING
    print("🔪 Killing active processes...")
    os.system("pkill -9 -f python")
    os.system("pkill -9 -f main.py")
    os.system("pkill -9 -f run_bot")
    time.sleep(1)

    # 2. DELETE STATE FILES
    print("🗑️ Deleting state cache...")
    
    # List of patterns to delete
    patterns = [
        "bot/data/*.json",         # Active trades
        "bot/data/*_state.json",  # Agent states
        "*.log",                   # Logs
        "bot/broker/mt5_bridge/*.dat", # Broker cache
        "__pycache__"
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        for f in files:
            try:
                os.remove(f)
                print(f"   ✅ Deleted: {f}")
            except Exception as e:
                print(f"   ⚠️ Failed to delete {f}: {e}")

    # 3. RESTART
    print("🚀 RESTARTING BOT FRESH (Logs cleared)...")
    
    # Ensure correct PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    cmd = "nohup .venv/bin/python3 bot/main.py > bot_output.log 2>&1 &"
    subprocess.Popen(cmd, shell=True, executable="/bin/zsh", env=env)
    
    print("✅ Bot relaunched. Monitoring logs...")
    time.sleep(3)
    os.system("tail -n 20 bot_output.log")

if __name__ == "__main__":
    main()
