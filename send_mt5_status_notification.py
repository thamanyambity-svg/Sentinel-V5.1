import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

MT5_FILES_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/"
status_file = os.path.join(MT5_FILES_PATH, "status.json")

if not os.path.exists(status_file):
    print(f"❌ Fichier {status_file} introuvable !")
    exit(1)

with open(status_file, "r") as f:
    data = json.load(f)

account = data.get("account", "?")
balance = data.get("balance", "?")
equity = data.get("equity", "?")
positions = data.get("positions", [])

# Construction du message
msg = f"📊 RAPPORT COMPTE MT5\n━━━━━━━━━━━━━━━━━━━━\n"
msg += f"Compte: {account}\nBalance: {balance}\nEquity: {equity}\nPositions ouvertes: {len(positions)}\n"
for pos in positions:
    msg += f"- {pos.get('symbol','?')} | {pos.get('type','?')} | {pos.get('volume','?')} lots | Profit: {pos.get('profit','?')}\n"
msg += f"━━━━━━━━━━━━━━━━━━━━\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

# Envoi Telegram
if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    r = requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'HTML'})
    print(f'Telegram: {r.status_code} - {r.json().get("ok", False)} - {r.json().get("description", "OK")}')
else:
    print("❌ Variables Telegram manquantes")

# Envoi Discord
if DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID:
    url = f'https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages'
    payload = {
        'embeds': [{
            'title': 'RAPPORT COMPTE MT5',
            'description': msg.replace('━━━━━━━━━━━━━━━━━━━━',''),
            'color': 65280,
            'footer': {'text': 'Sentinel Monitor | MT5'}
        }]
    }
    headers = {
        'Authorization': f'Bot {DISCORD_BOT_TOKEN}',
        'Content-Type': 'application/json'
    }
    r = requests.post(url, json=payload, headers=headers)
    print(f'Discord: {r.status_code}')
    if r.status_code == 200:
        print('OK - Message envoyé')
    else:
        print(r.text)
else:
    print("❌ Variables Discord manquantes")
