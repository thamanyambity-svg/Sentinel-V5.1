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
# Exécution immédiate au démarrage
try:
    subprocess.run([PYTHON, SCRIPT], check=True)
except Exception as e:
    log(f"Erreur Learning Engine (init): {e}")

while True:
    time.sleep(43200) # 12 heures
    try:
        subprocess.run([PYTHON, SCRIPT], check=True)
        log("Cycle d'apprentissage terminé avec succès")
    except Exception as e:
        log(f"Erreur Learning Engine: {e}")
