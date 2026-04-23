#!/bin/bash
# SENTINEL V11 - One-Command Launcher
# Activation venv + Installation + Tests + Server Start

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Colors
GREEN='\033[92m'
CYAN='\033[96m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "\n${CYAN}${BOLD}════════════════════════════════════════════════════════${RESET}"
echo -e "${CYAN}${BOLD}  SENTINEL V11 - ALL-IN-ONE LAUNCHER${RESET}"
echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════${RESET}\n"

# Step 1: Activate venv
echo -e "${GREEN}✓${RESET} Activating virtual environment..."
source .venv/bin/activate 2>/dev/null || {
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
}

# Step 2: Install dependencies
echo -e "${GREEN}✓${RESET} Installing dependencies..."
pip install -q flask flask-cors 2>/dev/null || pip install flask flask-cors

# Step 3: Run tests
echo -e "${GREEN}✓${RESET} Running installation tests...\n"
python3 test_install.py --api

# Step 4: Start server
echo -e "\n${CYAN}${BOLD}════════════════════════════════════════════════════════${RESET}"
echo -e "${CYAN}${BOLD}  🚀 STARTING API SERVER${RESET}"
echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════${RESET}\n"
echo -e "  🌐 API Server:  http://localhost:5000"
echo -e "  📊 Full Dashboard:   http://localhost:5000/api/v1/dashboard"
echo -e "  💰 Account Data:     http://localhost:5000/api/v1/account"
echo -e "  📡 Health Check:     http://localhost:5000/api/v1/health"
echo -e "\n  🔗 Copy & paste in another terminal (while this runs):\n"
echo -e "     ${CYAN}curl http://localhost:5000/api/v1/dashboard | jq .${RESET}\n"
echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════${RESET}\n"

# Start Flask app
python3 api_server.py
