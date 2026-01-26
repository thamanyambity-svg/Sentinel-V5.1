#!/bin/bash
echo "STOPPING OLD PROCESSES..."
pkill -9 python3
sleep 1
rm bot_output_v2.log

echo "STARTING VERIFICATION..."
# Run diagnostic first (synchronous)
venv/bin/python3 simple_test.py

echo "STARTING BOT..."
# Run main bot using nohup to detach and capture output
# export PYTHONPATH to include root dir so 'bot.config' works
export PYTHONPATH=$PYTHONPATH:.
nohup venv/bin/python3 bot/main.py > bot_output_v3.log 2>&1 &

echo "BOT LAUNCHED. MONITORING LOGS: bot_output_v3.log"
