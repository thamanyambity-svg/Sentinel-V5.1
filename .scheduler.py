"""
Scheduler léger — tourne en fond, lance gold_analysis.py
à 19h55 GMT+0 tous les jours (1h avant l'Overnight Hedge à 20h55)
"""
import time, subprocess, sys, os, datetime

SCRIPT = os.path.join(os.path.dirname(__file__), "gold_analysis.py")
PYTHON = sys.executable
LOG    = os.path.join(os.path.dirname(__file__), "logs", "gold_analysis.log")

triggered_today = None

def now_utc():
    return datetime.datetime.utcnow()

def log(msg):
    ts = now_utc().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except: pass

log("Scheduler Gold EOD Analysis démarré")
log(f"Analyse prévue chaque jour à 19h55 UTC")

while True:
    now = now_utc()
    today = now.date()

    # Fenêtre de déclenchement : 19h55 → 19h59 UTC
    is_window = (now.hour == 19 and now.minute >= 55) or \
                (now.hour == 20 and now.minute == 0)

    if is_window and triggered_today != today:
        log("★ DÉCLENCHEMENT Gold EOD Analysis (1h avant hedge)")
        try:
            result = subprocess.run(
                [PYTHON, SCRIPT],
                capture_output=True, text=True, timeout=60
            )
            log("Analyse terminée")
            if result.stdout: log(result.stdout[:500])
            if result.returncode != 0:
                log(f"WARN: returncode={result.returncode}")
                if result.stderr: log(result.stderr[:200])
        except Exception as e:
            log(f"ERREUR analyse: {e}")
        triggered_today = today

    # Prochaine analyse dans
    next_t = now.replace(hour=19, minute=55, second=0, microsecond=0)
    if now >= next_t:
        next_t = (next_t + datetime.timedelta(days=1))
    remaining = (next_t - now).total_seconds()
    if int(remaining) % 300 == 0:  # Log toutes les 5 min
        log(f"Prochaine analyse dans {int(remaining//3600)}h{int((remaining%3600)//60)}m")

    time.sleep(30)
