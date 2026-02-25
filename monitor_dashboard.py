import json
import time
from datetime import datetime
import sys

# Try imports
try:
    import psutil
except ImportError:
    psutil = None

class SystemMonitor:
    def __init__(self):
        self.start_time = time.time()
    
    def get_system_stats(self):
        """Récupère les stats système"""
        stats = {
            "timestamp": datetime.now().isoformat(),
            "uptime_hours": round((time.time() - self.start_time) / 3600, 2),
            "bot_status": "RUNNING" if self.is_bot_running() else "STOPPED"
        }
        
        if psutil:
             stats.update({
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
             })
        else:
             stats["warning"] = "psutil not installed"
             
        return stats
    
    def is_bot_running(self):
        """Vérifie si le bot Python tourne"""
        if not psutil:
            return False # Fallback or implementation without psutil
            
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    if proc.info['cmdline'] and any('bot/main_v5.py' in cmd for cmd in proc.info['cmdline']):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

if __name__ == "__main__":
    monitor = SystemMonitor()
    print(json.dumps(monitor.get_system_stats(), indent=2))
