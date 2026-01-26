
import psutil
import sys

def kill_zombies():
    with open("kill_log.txt", "w") as f:
        f.write("🧟 Hunting Zombies matching 'bot/main.py'...\n")
        count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = proc.info['cmdline']
                if cmd and any('bot/main.py' in arg for arg in cmd):
                    msg = f"🔫 Killing PID {proc.info['pid']} ({' '.join(cmd[:3])}...)\n"
                    print(msg)
                    f.write(msg)
                    proc.kill()
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                f.write(f"❌ Error killing {proc.info['pid']}: {e}\n")
        
        if count == 0:
            f.write("✅ No Zombies found. Clean.\n")
        else:
            f.write(f"💀 {count} Zombies terminated.\n")

if __name__ == "__main__":
    kill_zombies()
