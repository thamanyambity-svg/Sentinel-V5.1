import os
import signal
import subprocess
import time

def kill_process_by_pattern(pattern):
    try:
        # Pgrep to get PIDs
        result = subprocess.check_output(["pgrep", "-f", pattern])
        pids = [int(p) for p in result.decode().split()]
        print(f"Found PIDs for '{pattern}': {pids}")
        for pid in pids:
            try:
                print(f"Killing PID {pid}...")
                os.kill(pid, signal.SIGKILL)
                print(f"Killed PID {pid}")
            except Exception as e:
                print(f"Error killing PID {pid}: {e}")
    except subprocess.CalledProcessError:
        print(f"No process found for '{pattern}'")

if __name__ == "__main__":
    print("Killing bot processes...")
    kill_process_by_pattern("bot/main.py")
    kill_process_by_pattern("webhook_server.py")
    print("Done.")
