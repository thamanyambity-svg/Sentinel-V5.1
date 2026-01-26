import os
import sys
import subprocess
import signal
import time

def kill_all_python():
    """Tue tous les processus Python sauf celui-ci"""
    
    current_pid = os.getpid()
    
    # Pour Windows
    if sys.platform == "win32":
        try:
            # Méthode 1: Tuer tout python.exe
            subprocess.run(["taskkill", "/F", "/IM", "python.exe"], 
                          capture_output=True, timeout=5)
            subprocess.run(["taskkill", "/F", "/IM", "pythonw.exe"], 
                          capture_output=True, timeout=5)
            
            # Méthode 2: Plus agressive avec wmic
            subprocess.run('wmic process where "name=\'python.exe\'" delete', 
                          shell=True, capture_output=True, timeout=5)
            
            print("✅ Tous les processus Python tués")
            
        except Exception as e:
            print(f"⚠️ Erreur: {e}")
    
    # Pour Linux/Mac
    else:
        try:
            # Obtenir tous les PIDs Python
            result = subprocess.run(["pgrep", "-f", "python"], 
                                   capture_output=True, text=True)
            if result.stdout:
                pids = result.stdout.strip().split()
                
                for pid in pids:
                    pid = int(pid)
                    if pid != current_pid:  # Ne pas se tuer soi-même
                        try:
                            os.kill(pid, signal.SIGKILL)
                            print(f"✅ Process {pid} tué")
                        except:
                            pass
            
            # Tuer aussi par nom de script
            subprocess.run(["pkill", "-9", "-f", "main.py"], 
                          capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "bot.py"], 
                          capture_output=True)
            
        except Exception as e:
            print(f"⚠️ Erreur: {e}")
    
    # Attendre pour être sûr
    time.sleep(2)
    
    return True

if __name__ == "__main__":
    print("🧟 ÉLIMINATION DES ZOMBIES EN COURS...")
    if kill_all_python():
        print("✅ ZOMBIES ÉLIMINÉS - Vous pouvez relancer le bot")
    else:
        print("❌ Échec, essayez de redémarrer votre ordinateur")
