#!/bin/bash
# Script de lancement facile pour le Bot

# Aller dans le dossier du projet (au cas où on le lance d'ailleurs)
cd "$(dirname "$0")"

# Vérifier si venv existe
if [ ! -d "venv" ]; then
    echo "❌ Erreur : L'environnement virtuel 'venv' n'existe pas."
    echo "Lance d'abord : python3 -m venv venv && source venv/bin/activate && pip install -r bot/requirements.txt"
    exit 1
fi

echo "🚀 Lancement du Bot..."
echo "--------------------------------"
# Lancer le bot avec le python du venv
venv/bin/python -m bot.main
