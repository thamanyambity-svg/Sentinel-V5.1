import sys
import os
import time
from dotenv import load_dotenv

# Charger les variables d'environnement locales
load_dotenv("bot/.env")

# Ajout du dossier racine au path
sys.path.append(os.getcwd())

from bot.saas_connector import saas_connector

print("🦅 Test du Pont Numérique vers Antigravity...")

# On fabrique un FAUX trade gagnant pour tester l'affichage
fake_trade = {
    "ticket": 999999,      # Faux ticket
    "symbol": "TEST-USD",  # Faux symbole
    "type": "BUY",
    "open_price": 1.0000,
    "close_price": 1.0050,
    "profit": 10.0,        # Profit fictif
    "duration": 60
}

# On envoie
saas_connector.report_trade(fake_trade)
print("📡 Donnée envoyée. Vérifie ton Dashboard Antigravity !")
time.sleep(2)
