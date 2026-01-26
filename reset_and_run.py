import os
import subprocess
import time
import glob
import shutil

def cleanup_and_start():
    # 1. Kill existing
    subprocess.call(["python3", "kill_bot.py"])
    
    # 2. Delete Stats
    stats_file = "bot/data/daily_stats.json"
    if os.path.exists(stats_file):
        os.remove(stats_file)
        print(f"Deleted {stats_file}")
    
    # 3. Delete Logs
    log_file = "bot_output.log"
    if os.path.exists(log_file):
        os.remove(log_file)
        print(f"Deleted {log_file}")
        
    # 4. Delete pycache
    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d))
                print(f"Removed {os.path.join(root, d)}")
    
    # 5. Start Bot
    print("Starting bot/main.py...")
    # Using subprocess.Popen to start in background like nohup
    with open("bot_output.log", "w") as out:
        subprocess.Popen(["python3", "bot/main.py"], stderr=subprocess.STDOUT, stdout=out, env=dict(os.environ, PYTHONPATH="."))
    
    print("Bot started. Logging to bot_output.log")

if __name__ == "__main__":
    cleanup_and_start()
