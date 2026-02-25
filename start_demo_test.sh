#!/bin/bash
# Script de lancement TEST DEMO 7 JOURS - XM Global

echo "🧪 ============================================"
echo "   SENTINEL V5 - TEST DEMO 7 JOURS (XM)"
echo "=============================================="
echo ""

# Vérifications pré-démarrage
echo "📋 Vérifications de sécurité..."

# 1. Vérifier que c'est bien un compte DEMO
if ! grep -q "MT5_PASSWORD" bot/.env; then
    echo "❌ ERREUR: Mot de passe MT5 manquant dans .env"
    echo "   Ajoutez: MT5_PASSWORD=VotreMotDePasseDEMO"
    exit 1
fi

# 2. Confirmer compte DEMO
echo ""
echo "⚠️  CONFIRMATION REQUISE:"
echo "   Le compte XM 167933585 est-il un compte DEMO?"
read -p "   Tapez 'DEMO' pour confirmer: " confirmation

if [ "$confirmation" != "DEMO" ]; then
    echo "❌ Test annulé par l'utilisateur"
    exit 1
fi

# 3. Créer fichier de tracking
echo ""
echo "📊 Initialisation du tracking de performance..."
cat > demo_test_stats.json <<EOF
{
  "start_date": "$(date -Iseconds)",
  "account": "167933585",
  "broker": "XM Global DEMO",
  "status": "RUNNING",
  "initial_balance": 0,
  "current_balance": 0,
  "total_trades": 0,
  "wins": 0,
  "losses": 0
}
EOF

# 4. Backup des logs précédents
if [ -f "bot_full.log" ]; then
    mv bot_full.log "bot_full_backup_$(date +%Y%m%d_%H%M%S).log"
fi

# 5. Lancer le bot
echo ""
echo "🚀 Lancement de Sentinel V5 en mode DEMO TEST..."
echo ""

# Exporter variables d'environnement
export PYTHONPATH=$PYTHONPATH:.
export TESTING_MODE=DEMO_7DAYS

# Lancer avec logging complet
nohup python3 bot/main_v5.py > bot_full.log 2>&1 &
BOT_PID=$!

echo "✅ Bot démarré (PID: $BOT_PID)"
echo "$BOT_PID" > bot.pid

echo ""
echo "📱 Monitoring:"
echo "   - Logs: tail -f bot_full.log"
echo "   - Status: python check_status.py"
echo "   - Performance: python analyze_log_performance.py"
echo ""
echo "📅 Test programmé pour 7 jours (jusqu'au 18 février)"
echo "🔴 Vérifiez vos notifications Telegram/Discord"
echo ""
