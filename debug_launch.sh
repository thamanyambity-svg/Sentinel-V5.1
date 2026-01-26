#!/bin/bash
LOG_FILE="/Users/macbookpro/Downloads/bot_project/debug_launch.log"
echo "🚀 STARTING DEBUG LAUNCH at $(date)" > "$LOG_FILE"
echo "📂 PWD: $(pwd)" >> "$LOG_FILE"

echo "🔫 KILLING ZOMBIES..." >> "$LOG_FILE"
pkill -9 -f python
pkill -9 -f main.py
rm -f /Users/macbookpro/Downloads/bot_project/bot_output.log
sleep 2

echo "🐍 STARTING PYTHON..." >> "$LOG_FILE"
export PYTHONPATH=/Users/macbookpro/Downloads/bot_project
/Users/macbookpro/Downloads/bot_project/.venv/bin/python3 -u /Users/macbookpro/Downloads/bot_project/bot/main.py >> /Users/macbookpro/Downloads/bot_project/bot_output.log 2>&1 &
PID=$!
echo "✅ LAUNCHED PID: $PID" >> "$LOG_FILE"

sleep 5
echo "📊 PROCESS CHECK:" >> "$LOG_FILE"
ps aux | grep "$PID" >> "$LOG_FILE"
