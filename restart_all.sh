#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  ALADDIN MASTER RESTART — Institutional Grade Launcher
# ═══════════════════════════════════════════════════════════════

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${YELLOW}${BOLD}🛑 ARRÊT COMPLET DU SYSTÈME...${RESET}"

# 1. Arrêt via run_all.sh (Dashboard + Agents)
bash run_all.sh stop

# 2. Arrêt forcé du moteur de trading (au cas où)
pkill -f "main_v5.py" 2>/dev/null
pkill -f "bot.main" 2>/dev/null

# 3. Nettoyage des PIDs
rm -f .pid_*
sleep 2

echo -e "${CYAN}${BOLD}🚀 RELANCEMENT DE LA STACK ALADDIN...${RESET}"

# 4. Lancement de la base (Dashboard + Agents Sentiment/Learning/Gold)
# On le lance en arrière-plan sans 'tail -f' pour garder la main
bash run_all.sh &
sleep 5

# 5. Lancement du Trading Engine (V5.1)
echo -e "${CYAN}[4/4]${RESET} Démarrage du Trading Engine (Sentinel V5.1)..."
export PYTHONPATH=$PYTHONPATH:.
nohup ./venv/bin/python3 bot/main_v5.py >> logs/bot_engine.log 2>&1 &
echo $! > .pid_bot_engine

echo -e "\n${GREEN}${BOLD}╔═══════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║  ✓ SYSTÈME REDÉMARRÉ AVEC SUCCÈS             ║${RESET}"
echo -e "${GREEN}${BOLD}╠═══════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}${BOLD}║${RESET}  Dashboard (Unified) → ${CYAN}http://localhost:5000${RESET} ${GREEN}${BOLD}║${RESET}"
echo -e "${GREEN}${BOLD}║${RESET}  Risk Cockpit Tab    → ${CYAN}Intégré /risk${RESET}         ${GREEN}${BOLD}║${RESET}"
echo -e "${GREEN}${BOLD}║${RESET}  Trading Engine Logs → logs/bot_engine.log    ${GREEN}${BOLD}║${RESET}"
echo -e "${GREEN}${BOLD}╚═══════════════════════════════════════════════╝${RESET}\n"

# Ouvrir le portail
open http://localhost:5000 2>/dev/null || true
