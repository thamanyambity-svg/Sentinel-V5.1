#!/usr/bin/env bash
# SENTINEL PREDATOR - GLOBAL LAUNCHER
# Démarrage automatique de l'API Flask et de l'interface Expo

echo "🚀 Initialisation du système Sentinel Predator..."

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd "$(dirname "$0")"
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

cd sentinel-predator-mobile
npm run dev:total
