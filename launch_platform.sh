#!/bin/zsh
# ═══════════════════════════════════════════════════════════════════════╗
# SENTINEL V11 - PLATEFORME INSTITUTIONNELLE (1-clic)
# Lance API + Dashboard Premium lié au compte MT5 live
# ═══════════════════════════════════════════════════════════════════════╝

echo "🚀 Lancement Plateforme Trading Institutionnelle SENTINEL V11..."

# Vérifications prérequis
if [[ ! -f dashboard_manager.py ]]; then
  echo "❌ dashboard_manager.py manquant"
  exit 1
fi
if [[ ! -f api_server.py ]]; then
  echo "❌ api_server.py manquant"
  exit 1
fi
if [[ ! -f dashboard_premium.html ]]; then
  echo "❌ dashboard_premium.html manquant"
  exit 1
fi

# Kill éventuel ancien serveur
pkill -f "api_server.py" 2>/dev/null || true

# Lancer API serveur en arrière-plan
echo "✅ Démarrage API Server (localhost:5000)..."
python api_server.py &
API_PID=$!

# Attendre démarrage
sleep 3

# Vérifier API
if curl -s http://localhost:5000/api/v1/health > /dev/null; then
  echo "✅ API Server OK - Connecté au compte MT5 live"
else
  echo "❌ API Server erreur"
  kill $API_PID 2>/dev/null || true
  exit 1
fi

# Ouvrir Dashboard Premium
echo "✅ Ouverture Dashboard Institutionnel..."
open http://localhost:5000

# Sauvegarder PID pour arrêt facile
echo $API_PID > sentinel_platform.pid
echo "🎯 Plateforme lancée! PID: $API_PID"
echo "Arrêt: ./stop_platform.sh"
echo "Dashboard: http://localhost:5000"
