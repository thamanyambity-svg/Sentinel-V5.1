#!/bin/bash
echo "🔫 KILLING ZOMBIES..."
pkill -9 -f "bot/main.py"
pkill -9 -f "webhook_server.py"
sleep 2
echo "✅ CLEANUP COMPLETE."

echo "🚀 STARTING SENTINEL..."
PYTHONPATH=. nohup .venv/bin/python3 bot/main.py > bot_output.log 2>&1 &
echo "✅ BOT STARTED. Logs in bot_output.log"
tail -f bot_output.log
