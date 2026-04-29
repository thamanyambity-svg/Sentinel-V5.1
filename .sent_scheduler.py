import time, subprocess, sys, os, datetime
SCRIPT = os.path.join(os.path.dirname(__file__), "bot", "ai_agents", "gold_news_feed.py")
PYTHON = sys.executable
LOG    = os.path.join(os.path.dirname(__file__), "logs", "sentiment.log")

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f: f.write(line + "\n")
    except: pass

log("Sentiment Agent Scheduler démarré")
while True:
    try:
        subprocess.run([PYTHON, SCRIPT], check=True)
        log("Analyse Sentiment IA terminée avec succès")
    except Exception as e:
        log(f"Erreur Agent Sentiment: {e}")
    time.sleep(900) # 15 minutes
