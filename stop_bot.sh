#!/bin/bash

if [ -f bot.pid ]; then
    PID=$(cat bot.pid)
    echo "🛑 Stopping Bot Alpha (PID: $PID)..."
    kill $PID
    rm bot.pid
    echo "✅ Bot stopped."
else
    echo "⚠️ No PID file found. Using pkill..."
    pkill -f "bot/main.py"
    echo "✅ Process killed."
fi
