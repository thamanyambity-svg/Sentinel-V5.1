import os
import json

# Créer une commande CLOSE_ALL pour MT5
mt5_path = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
command_path = os.path.join(mt5_path, "Command")

os.makedirs(command_path, exist_ok=True)

command = {
    "action": "CLOSE_ALL",
    "timestamp": "emergency"
}

filepath = os.path.join(command_path, "emergency_close.json")
with open(filepath, 'w') as f:
    json.dump(command, f)
    
print("🚨 COMMANDE D'URGENCE ENVOYÉE : FERMETURE DE TOUTES LES POSITIONS")
print(f"Fichier créé : {filepath}")
