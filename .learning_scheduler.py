import time, subprocess, sys, os, datetime
SCRIPT = os.path.join(os.path.dirname(__file__), "adaptive_learning_engine.py")
PYTHON = sys.executable
LOG    = os.path.join(os.path.dirname(__file__), "logs", "learning.log")

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f: f.write(line + "\n")
    except: pass

log("Learning Engine Scheduler démarré")
# Exécution immédiate au démarrage pour corriger les erreurs d'aujourd'hui
try:
    subprocess.run([PYTHON, SCRIPT], check=True)
except Exception as e:
    log(f"Erreur Learning Engine (init): {e}")

while True:
    # Attendre minuit
    now = datetime.datetime.now()
    tomorrow = now.replace(hour=0, minute=1, second=0, microsecond=0) + datetime.timedelta(days=1)
    wait_time = (tomorrow - now).total_seconds()
    log(f"Prochaine réévaluation dans {int(wait_time/3600)}h")
    time.sleep(wait_time)
    
    try:
        subprocess.run([PYTHON, SCRIPT], check=True)
        log("Cycle d'apprentissage de minuit terminé avec succès")
    except Exception as e:
        log(f"Erreur Learning Engine: {e}")
