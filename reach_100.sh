#!/bin/bash
PROJECT_DIR="/Users/macbookpro/Downloads/bot_project"
cd "$PROJECT_DIR"

echo "Stopping previous processes..."
pkill -f start_production.py
pkill -f news_filter.py
pkill -f ai_bridge.py
pkill -f sentinel_notifier.py
pkill -f sentinel_server.py

rm -f production.pid bot.pid bot/bot.pid
rm -f production_launch.log

echo "Starting bot with venv python..."
nohup ./venv/bin/python3 -u start_production.py --no-dash > production_launch.log 2>&1 &

echo "Waiting for startup..."
sleep 15

if [ -f production.pid ]; then
    cp production.pid bot.pid
    echo "Bot started successfully. PID: $(cat production.pid)"
else
    echo "ERROR: Bot failed to start. Check production_launch.log"
    # Try one more time with a small fallback
    sleep 5
    if [ -f production.pid ]; then
        cp production.pid bot.pid
    fi
fi

echo "Running health check..."
./venv/bin/python3 system_health_check.py
