#!/bin/zsh
# ═══════════════════════════════════════════════════════════════════════╗
# SENTINEL V11 - UNE SEULE COMMANDE (Système Complet Institutionnel)
# Lance API + Dashboard HTML + Terminal + lié compte MT5 live
# ═══════════════════════════════════════════════════════════════════════╝

echo "🔥 SENTINEL V11 - LANCEMENT SYSTÈME COMPLET INSTITUTIONNEL..."

# Vérifications
required_files=( "api_server.py" "dashboard.py" "dashboard_premium.html" "dashboard_manager.py" )
for file in "${required_files[@]}"; do
  if [[ ! -
