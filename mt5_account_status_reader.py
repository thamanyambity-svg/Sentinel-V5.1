import json
import os
from datetime import datetime

# Chemin du dossier MT5 Files (à adapter si besoin)
MT5_FILES_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/"

# Cherche le status.json le plus à jour
status_file = os.path.join(MT5_FILES_PATH, "status.json")

# Lecture du status.json
if not os.path.exists(status_file):
    print(f"❌ Fichier {status_file} introuvable !")
    exit(1)

with open(status_file, "r") as f:
    data = json.load(f)

account = data.get("account", "?")
balance = data.get("balance", "?")
equity = data.get("equity", "?")
positions = data.get("positions", [])

print(f"\n🟢 COMPTE ACTIF : {account}")
print(f"💰 Balance : {balance}")
print(f"📈 Equity : {equity}")
print(f"📦 Positions ouvertes : {len(positions)}")

for pos in positions:
    symbol = pos.get("symbol", "?")
    type_ = pos.get("type", "?")
    volume = pos.get("volume", "?")
    price = pos.get("price", "?")
    profit = pos.get("profit", "?")
    print(f"   - {symbol} | {type_} | {volume} lots | Prix: {price} | Profit: {profit}")

# Exemple d'intégration pour notification Telegram/Discord
def build_report():
    msg = f"📊 RAPPORT COMPTE MT5\n━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"Compte: {account}\nBalance: {balance}\nEquity: {equity}\nPositions ouvertes: {len(positions)}\n"
    for pos in positions:
        msg += f"- {pos.get('symbol','?')} | {pos.get('type','?')} | {pos.get('volume','?')} lots | Profit: {pos.get('profit','?')}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return msg

if __name__ == "__main__":
    print("\n--- Message pour notification ---\n")
    print(build_report())
