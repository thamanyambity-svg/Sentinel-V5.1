#!/usr/bin/env bash
# Aladdin V7.19 : bot principal (arrière-plan) + watchdog (premier plan).
set -e
cd "$(dirname "$0")/.."
PY=python3
if [[ -d ".venv" ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
  PY="$(command -v python3)"
fi
export MT5_FILES_PATH="${MT5_FILES_PATH:-$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files}"
mkdir -p logs
echo "MT5_FILES_PATH=$MT5_FILES_PATH"
echo "Python: $PY"
nohup "$PY" -m bot.main_v719 >> logs/bot_main_v719.log 2>&1 &
echo $! > .bot_main_v719.pid
echo "Bot main_v719 PID $(cat .bot_main_v719.pid) — logs/bot_main_v719.log"
sleep 2
exec "$PY" watchdog.py
