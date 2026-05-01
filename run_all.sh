#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  run_all.sh — Aladdin Pro V7.22 · Lanceur Maître
#  Lance : Dashboard Flask + Analyse Gold EOD automatique
#  Usage : bash run_all.sh
#          bash run_all.sh stop
#          bash run_all.sh learn
# ═══════════════════════════════════════════════════════════════

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/venv"
PYTHON="$VENV/bin/python3"
PID_DASHBOARD="$DIR/.pid_dashboard"
PID_SCHEDULER="$DIR/.pid_scheduler"
PID_SENTIMENT="$DIR/.pid_sentiment"
PID_LEARNING="$DIR/.pid_learning"
LOG_DASHBOARD="$DIR/logs/dashboard.log"
LOG_GOLD="$DIR/logs/gold_analysis.log"
LOG_LEARNING="$DIR/logs/learning.log"

# ── Couleurs terminal ──────────────────────────────────────────
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

banner() {
  echo ""
  echo -e "${CYAN}${BOLD}"
  echo "  ╔═══════════════════════════════════════════════╗"
  echo "  ║      ALADDIN PRO V7.22 — LANCEUR MAÎTRE      ║"
  echo "  ╠═══════════════════════════════════════════════╣"
  echo "  ║  Dashboard  → http://localhost:5000           ║"
  echo "  ║  Gold EOD   → Analyse auto à 19h55 GMT+0     ║"
  echo "  ║  Logs       → ./logs/                        ║"
  echo "  ╚═══════════════════════════════════════════════╝"
  echo -e "${RESET}"
}

# ── STOP ──────────────────────────────────────────────────────
stop_all() {
  echo -e "${YELLOW}Arrêt de tous les processus Aladdin...${RESET}"
  if [ -f "$PID_DASHBOARD" ]; then
    kill "$(cat $PID_DASHBOARD)" 2>/dev/null && echo -e "  ${GREEN}✓${RESET} Dashboard arrêté"
    rm -f "$PID_DASHBOARD"
  fi
  if [ -f "$PID_SCHEDULER" ]; then
    kill "$(cat $PID_SCHEDULER)" 2>/dev/null && echo -e "  ${GREEN}✓${RESET} Scheduler arrêté"
    rm -f "$PID_SCHEDULER"
  fi
  if [ -f "$PID_SENTIMENT" ]; then
    kill "$(cat $PID_SENTIMENT)" 2>/dev/null && echo -e "  ${GREEN}✓${RESET} Sentiment Agent arrêté"
    rm -f "$PID_SENTIMENT"
  fi
  if [ -f "$PID_LEARNING" ]; then
    kill "$(cat $PID_LEARNING)" 2>/dev/null && echo -e "  ${GREEN}✓${RESET} Learning Agent arrêté"
    rm -f "$PID_LEARNING"
  fi
  # Kill par port au cas où
  lsof -ti:5000 | xargs kill -9 2>/dev/null
  echo -e "${GREEN}Tous les processus Aladdin sont arrêtés.${RESET}\n"
  exit 0
}

if [ "$1" = "learn" ]; then
  echo -e "${CYAN}Exécution manuelle du moteur d'apprentissage...${RESET}"
  "$PYTHON" "$DIR/adaptive_learning_engine.py"
  exit 0
fi

[ "$1" = "stop" ] && stop_all

# ── SETUP ─────────────────────────────────────────────────────
banner
mkdir -p "$DIR/logs"

# Venv (utilise le venv existant du projet si disponible)
if [ ! -f "$PYTHON" ]; then
  echo -e "${YELLOW}Création du venv...${RESET}"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install flask --quiet
  echo -e "${GREEN}✓ venv prêt${RESET}"
fi

# Vérifier Flask
"$PYTHON" -c "import flask" 2>/dev/null || {
  echo -e "${YELLOW}Installation de Flask...${RESET}"
  "$VENV/bin/pip" install flask --quiet
}

# ── DASHBOARD FLASK ───────────────────────────────────────────
# Arrêter si déjà lancé
if [ -f "$PID_DASHBOARD" ]; then
  kill "$(cat $PID_DASHBOARD)" 2>/dev/null
  sleep 1
fi
lsof -ti:5000 | xargs kill -9 2>/dev/null
sleep 0.5

echo -e "${CYAN}[1/3]${RESET} Démarrage du Dashboard Flask..."
cd "$DIR"
"$PYTHON" app.py >> "$LOG_DASHBOARD" 2>&1 &
echo $! > "$PID_DASHBOARD"
sleep 2

# Vérifier que Flask tourne
if curl -s http://localhost:5000/api/status > /dev/null 2>&1; then
  echo -e "  ${GREEN}✓ Dashboard opérationnel → http://localhost:5000${RESET}"
else
  echo -e "  ${YELLOW}⚠ Dashboard démarré (vérifiez logs/dashboard.log)${RESET}"
fi

# ── SCHEDULER GOLD ANALYSIS ───────────────────────────────────
echo -e "${CYAN}[2/3]${RESET} Démarrage du scheduler Gold EOD Analysis..."

cat > "$DIR/.scheduler.py" << 'PYEOF'
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
PYEOF

"$PYTHON" "$DIR/.scheduler.py" >> "$LOG_GOLD" 2>&1 &
echo $! > "$PID_SCHEDULER"
echo -e "  ${GREEN}✓ Scheduler actif (analyse Gold à 19h55 UTC chaque jour)${RESET}"

# ── AGENT SENTIMENT FONDAMENTAL (IA) ──────────────────────────
echo -e "${CYAN}[2.5/3]${RESET} Démarrage de l'Agent Sentiment Fondamental (IA)..."

cat > "$DIR/.sent_scheduler.py" << 'PYEOF'
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
PYEOF

"$PYTHON" "$DIR/.sent_scheduler.py" >> "$DIR/logs/sentiment.log" 2>&1 &
echo $! > "$PID_SENTIMENT"
echo -e "  ${GREEN}✓ Agent Sentiment IA actif (refresh 15 min)${RESET}"

# ── MOTEUR D'APPRENTISSAGE ADAPTATIF (IA 3 NIVEAUX) ─────────
echo -e "${CYAN}[2.7/3]${RESET} Démarrage du Moteur d'Apprentissage Adaptatif..."

cat > "$DIR/.learning_scheduler.py" << 'PYEOF'
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
PYEOF

"$PYTHON" "$DIR/.learning_scheduler.py" >> "$LOG_LEARNING" 2>&1 &
echo $! > "$PID_LEARNING"
echo -e "  ${GREEN}✓ Moteur d'apprentissage actif (audit chaque soir à 00h01)${RESET}"

# ── ANALYSE GOLD IMMÉDIATE (optionnel) ────────────────────────
echo -e "${CYAN}[3/3]${RESET} Analyse Gold initiale..."
"$PYTHON" "$DIR/gold_analysis.py" 2>&1 | tail -12
echo -e "  ${GREEN}✓ gold_analysis.json écrit${RESET}"

# ── RÉSUMÉ FINAL ──────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔═══════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║  ✓ ALADDIN DASHBOARD OPÉRATIONNEL            ║${RESET}"
echo -e "${GREEN}${BOLD}╠═══════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}${BOLD}║${RESET}  Dashboard   → ${CYAN}http://localhost:5000${RESET}        ${GREEN}${BOLD}║${RESET}"
echo -e "${GREEN}${BOLD}║${RESET}  Logs Flask  → logs/dashboard.log          ${GREEN}${BOLD}║${RESET}"
echo -e "${GREEN}${BOLD}║${RESET}  Logs Gold   → logs/gold_analysis.log      ${GREEN}${BOLD}║${RESET}"
echo -e "${GREEN}${BOLD}║${RESET}  Arrêter     → ${YELLOW}bash run_all.sh stop${RESET}        ${GREEN}${BOLD}║${RESET}"
echo -e "${GREEN}${BOLD}╚═══════════════════════════════════════════════╝${RESET}"
echo ""

# Ouvrir le navigateur automatiquement sur Mac
sleep 1
open http://localhost:5000 2>/dev/null || true

# Suivre les logs en temps réel
echo -e "${CYAN}Logs en direct (Ctrl+C pour quitter les logs sans arrêter le bot) :${RESET}\n"
tail -f "$LOG_DASHBOARD" "$LOG_GOLD" 2>/dev/null
