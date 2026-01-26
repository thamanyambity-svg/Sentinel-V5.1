#!/bin/bash

# SENTINEL - WEEKLY EVOLUTIONARY CYCLE
# This script should be run by cron (e.g., Sunday 00:00)
# 0 0 * * 0 /Users/macbookpro/Downloads/bot_project/weekly_evolution.sh >> /tmp/sentinel_evolution.log 2>&1

PROJECT_DIR="/Users/macbookpro/Downloads/bot_project"

echo "========================================"
echo "🧬 SENTINEL EVOLUTION: $(date)"
echo "========================================"

cd "$PROJECT_DIR"
source venv/bin/activate

# Ensure Environment Variables are Loaded (optional explicit export if needed)
export PYTHONPATH="$PROJECT_DIR"

# Run Optimizer
python3 bot/ai_agents/evolutionary_optimizer.py

echo "========================================"
echo "🏁 CYCLE COMPLETE: $(date)"
echo "========================================"
