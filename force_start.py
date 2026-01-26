import os
import subprocess
import time
import signal
import sys

def kill_process_by_name(name):
    print(f"🔪 Searching for processes matching: {name}")
    try:
        # Get PIDs using pgrep
        pids = subprocess.check_output(["pgrep", "-f", name]).decode().split()
        for pid in pids:
            pid = int(pid)
            if pid == os.getpid(): continue # Don't kill self
            print(f"   ⚰️  Killing PID {pid}")
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except subprocess.CalledProcessError:
        print(f"   ✅ No active {name} processes found.")

def main():
    print("="*40)
    print("💀 NUCLEAR PROTOCOL INITIATED")
    print("="*40)

    # 1. KILL EVERYTHING
    targets = ["python", "main.py", "run_bot", "webhook_server"]
    for target in targets:
        kill_process_by_name(target)
    
    time.sleep(2)
    
    # 2. CLEAR LOGS
    if os.path.exists("bot_output.log"):
        with open("bot_output.log", "w") as f:
            f.write("=== FRESH LOG START ===\n")
        print("✅ Logs cleared.")

    # 3. RUN BOT
    print("🚀 STARTING BOT...")
    cmd = "export PYTHONPATH=$(pwd) && nohup .venv/bin/python3 bot/main.py > bot_output.log 2>&1 &"
    subprocess.Popen(cmd, shell=True, executable="/bin/zsh")
    
    print("✅ Bot command issued. Waiting for startup signature...")
    print("="*40)
    
    # 4. TAIL LOG
    time.sleep(3)
    try:
        subprocess.run(["tail", "-n", "20", "bot_output.log"])
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
