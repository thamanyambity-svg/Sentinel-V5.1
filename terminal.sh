#!/bin/bash

# ==============================================================================
# SENTINEL PREDATOR : UNIVERSAL STARTUP COMMAND (ROBUST V2)
# ==============================================================================

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo "----------------------------------------------------------------"
echo "🚀 INITIALIZING SENTINEL PREDATOR ECOSYSTEM..."
echo "----------------------------------------------------------------"

# 1. Automated Cleanup (Zombie Processes)
echo "🧹 Cleaning up legacy processes (Ports 3000, 8081)..."
lsof -ti:3000,8081 | xargs kill -9 2>/dev/null || true

# 2. Environment Verification
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
if command -v nvm &> /dev/null; then
    nvm use default > /dev/null
    echo "✅ Node.js: $(node -v)"
else
    echo "⚠️  NVM not found. Defaulting to system Node."
fi

if [ -d ".venv" ]; then
    export PYTHON_PATH="$BASE_DIR/.venv/bin/python"
    echo "✅ Python: Virtual Env detected"
else
    export PYTHON_PATH="python3"
    echo "⚠️  Python: Global detected"
fi

# 3. Log Preparation
mkdir -p logs
rm -f logs/bot_background.log logs/bridge_background.log
touch logs/bot_background.log logs/bridge_background.log

echo "----------------------------------------------------------------"
echo "🛠️  LAUNCHING CORE SERVICES..."

# 4. Starting AI Trading Engine (Python)
echo "📡 Starting AI Trading Engine..."
$PYTHON_PATH -m bot.main > logs/bot_background.log 2>&1 &
BOT_PID=$!

# 5. Starting Institutional Bridge (Node)
echo "💎 Starting Institutional TRPC Bridge..."
cd sentinel-predator-mobile
source "$HOME/.nvm/nvm.sh" && nvm use default > /dev/null
npx tsx server/index.ts > ../logs/bridge_background.log 2>&1 &
BRIDGE_PID=$!

# 6. Pre-flight Health Check
echo "🔍 Performing system health check (5s)..."
sleep 5

if ps -p $BOT_PID > /dev/null && ps -p $BRIDGE_PID > /dev/null; then
    echo "✅ [BACKEND OK] Bot PID: $BOT_PID | Bridge PID: $BRIDGE_PID"
    echo "✅ [LOGS ACTIVE] check logs/ folder"
else
    echo "❌ [ERROR] One or more core services failed to start."
    echo "   Bot Status: $(ps -p $BOT_PID > /dev/null && echo 'RUNNING' || echo 'FAILED')"
    echo "   Bridge Status: $(ps -p $BRIDGE_PID > /dev/null && echo 'RUNNING' || echo 'FAILED')"
    echo "   Exiting to prevent partial ecosystem launch."
    kill $BOT_PID $BRIDGE_PID 2>/dev/null
    exit 1
fi

# 7. Launching Final Mobile UI Terminal
echo "----------------------------------------------------------------"
echo "📱 LAUNCHING PREDATOR UI TERMINAL..."
echo "----------------------------------------------------------------"

# Setup exit trap to kill background services on Ctrl+C
trap "echo '🛑 Stopping Sentinel Ecosystem...'; kill $BOT_PID $BRIDGE_PID 2>/dev/null; exit" INT TERM EXIT

npm run predator
