#!/bin/zsh
# ═══════════════════════════════════════════════════════════════════════╗
# SENTINEL V11 - ARRÊT PLATEFORME INSTITUTIONNELLE
# ═══════════════════════════════════════════════════════════════════════╝

echo "🛑 Arrêt plateforme Sentinel V11..."

if [[ -f sentinel_platform.pid ]]; then
  PID=$(cat sentinel_platform.pid)
  echo "Arrêt API Server (PID $PID)..."
  kill $PID 2>/dev/null && rm -f sentinel_platform.pid
  sleep 2
  echo "✅ Serveur arrêté proprement"
else
  echo "Arrêt anciens serveurs API..."
  pkill -f "api_server.py" 2>/dev/null || true
  echo "✅ Tous serveurs arrêtés"
fi

echo "🎯 Plateforme arrêtée. À bientôt!"
