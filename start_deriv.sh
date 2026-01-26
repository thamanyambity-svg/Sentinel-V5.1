#!/bin/bash
# Lancement de l'instance Deriv (Originale)
echo "🚀 Démarrage de MetaTrader 5 - Deriv..."

APP_PATH="/Applications/MetaTrader 5.app/Contents/MacOS/MetaTrader 5"
EXE_PATH="/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/terminal64.exe"

if [ -f "$EXE_PATH" ]; then
    "$APP_PATH" "$EXE_PATH" /portable &
    echo "✅ Instance Deriv lancée."
else
    echo "❌ Erreur : Dossier Deriv introuvable."
fi
