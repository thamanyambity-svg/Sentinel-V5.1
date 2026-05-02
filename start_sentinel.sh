#!/bin/bash

echo "🚀 DÉMARRAGE DE LA MACHINE SENTINEL V5.1..."

# 1. Tuer les anciens processus si ils existent
fuser -k 5000/tcp 2>/dev/null

# 2. Lancer l'API Server en arrière-plan
echo "📡 Lancement de l'API Server..."
nohup venv/bin/python api_server.py > logs/api.log 2>&1 &

# 3. Attendre que l'API soit prête
sleep 5

# 4. Lancer le Swarm BlackRock en mode automatique
echo "🏦 Lancement de l'Essaim BlackRock (Mode Auto + Planning)..."
nohup venv/bin/python blackrock_swarm.py --auto > logs/swarm.log 2>&1 &

echo "✅ TOUT EST OPÉRATIONNEL !"
echo "📊 Dashboard : http://localhost:5000"
echo "📜 Logs Swarm  : tail -f logs/swarm.log"
