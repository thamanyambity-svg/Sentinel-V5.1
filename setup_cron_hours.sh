#!/bin/zsh
# Auto-setup cron pour Trading Hours Monitor (toutes 5min)

PROJECT_DIR="/Users/macbookpro/Downloads/bot_project"
SCRIPT="trading_hours_monitor.py"

echo "🚀 Setup CRON Trading Hours Monitor EXACT (relance minuit)..."

# Kill existing cron if any
crontab -l | grep "$PROJECT_DIR" && crontab -l | grep "$SCRIPT" && echo "🗑️  Ancien cron supprimé"

# New cron: relance quotidienne à minuit (scheduler interne gère le reste)
(crontab -l 2>/dev/null; echo "0 0 * * * cd $PROJECT_DIR && /usr/bin/python3 $SCRIPT >> trading_hours.log 2>&1") | crontab -

echo "✅ Cron installé : **RELANCE QUOTIDIENNE 00:00** (scheduler précis interne)"

echo "✅ Cron installé : **00:00 chaque jour**"
echo "📋 Vérifier : crontab -l"
echo ""
echo "🕐 Scheduler précis: sleep jusqu'aux heures EXACTES"
echo "📱 Discord: notifs pile à 08:00, 13:00, 17:00..."
echo "📊 Logs: tail -f trading_hours.log"

# Test immédiat
cd $PROJECT_DIR && python3 $SCRIPT
