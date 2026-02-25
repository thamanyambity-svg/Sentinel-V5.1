#!/usr/bin/env python3
import os
import json
import time
import asyncio
import aiohttp
import ssl
import certifi
from datetime import datetime
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv(".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

# Chemin vers le fichier exporté par l'EA (Source de vérité)
STATUS_FILE = os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5/"
    "drive_c/Program Files/MetaTrader 5/MQL5/Files/status.json"
)

SCAN_INTERVAL = 1 # On passe à 1 seconde pour une réactivité chirurgicale

ssl_context = ssl.create_default_context(cafile=certifi.where())

class GlobalMonitor:
    def __init__(self):
        self.last_positions = {}
        self.last_balance = 0
        self.initial_balance = None
        self.start_time = datetime.now()

    async def send_all(self, message):
        """Envoie à Telegram et Discord Bot simultanément."""
        tasks = []
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            tasks.append(self.send_telegram(message))
        if DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID:
            tasks.append(self.send_discord(message))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    print(f"❌ Erreur d'envoi notification: {res}")

    async def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                async with session.post(url, json=payload, timeout=5) as resp:
                    if resp.status != 200:
                        print(f"❌ Erreur Telegram: {await resp.text()}")
                    return resp.status == 200
        except Exception as e:
            print(f"❌ Exception Telegram: {e}")
            return False

    async def send_discord(self, message):
        """Envoi via l'API Discord Bot (Token + Channel ID)."""
        url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
        headers = {
            "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        # Discord utilise ** pour le gras au lieu de *
        d_msg = message.replace("*", "**")
        payload = {"content": d_msg}
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                async with session.post(url, json=payload, headers=headers, timeout=5) as resp:
                    if resp.status not in [200, 201]:
                        print(f"❌ Erreur Discord: {await resp.text()}")
                    return resp.status in [200, 201]
        except Exception as e:
            print(f"❌ Exception Discord: {e}")
            return False

    def read_status(self):
        if not os.path.exists(STATUS_FILE): return None
        try:
            with open(STATUS_FILE, 'r') as f:
                content = f.read()
                if not content: return None
                return json.loads(content)
        except Exception as e:
            # Souvent une erreur de lecture concurrente si l'EA écrit en même temps
            return None

    async def run(self):
        print("\n" + "═"*40)
        print("  🛰️  SENTINEL NOTIFIER PRO V11.4")
        print("  🔔  Discord: ONLINE | Telegram: ONLINE")
        print("═"*40 + "\n")
        
        await self.send_all("🚀 **SENTINEL V11.4 - HUB DE NOTIFICATION ACTIVÉ**\nSurveillance réelle du compte XM en cours...")

        while True:
            data = self.read_status()
            if data:
                current_balance = data.get('balance', 0)
                current_equity = data.get('equity', 0)
                
                if self.initial_balance is None: 
                    self.initial_balance = current_balance
                    self.last_balance = current_balance
                
                positions = {str(p['ticket']): p for p in data.get('positions', [])}
                
                # 1. DÉTECTION NOUVELLES POSITIONS
                for ticket, pos in positions.items():
                    if ticket not in self.last_positions:
                        msg = (f"🟢 **NOUVELLE POSITION OUVERTE**\n"
                               f"━━━━━━━━━━━━━━━━━━\n"
                               f"📊 Actif: `{pos['symbol']}`\n"
                               f"🎯 Signal: *{pos['type']}*\n"
                               f"📦 Lots: `{pos['volume']:.2f}`\n"
                               f"💰 Prix: `{pos['price']:.5f}`\n"
                               f"🏦 Solde Réel: `${current_balance:.2f}`\n"
                               f"━━━━━━━━━━━━━━━━━━")
                        await self.send_all(msg)

                # 2. DÉTECTION CLÔTURES AVEC P&L RÉEL
                for ticket, pos in self.last_positions.items():
                    if ticket not in positions:
                        # Calcul du profit réel sur la balance
                        real_profit = current_balance - self.last_balance
                        icon = "✅" if real_profit >= 0 else "🚨"
                        status = "GAIN" if real_profit >= 0 else "PERTE"
                        
                        msg = (f"{icon} **POSITION CLÔTURÉE ({status})**\n"
                               f"━━━━━━━━━━━━━━━━━━\n"
                               f"📊 Actif: `{pos['symbol']}`\n"
                               f"💰 Profit/Perte: `{real_profit:+.2f}$`\n"
                               f"🏦 Nouveau Solde: `${current_balance:.2f}`\n"
                               f"📈 Équité: `${current_equity:.2f}`\n"
                               f"━━━━━━━━━━━━━━━━━━")
                        await self.send_all(msg)
                        # On met à jour la balance de référence immédiatement
                        self.last_balance = current_balance

                self.last_positions = positions
                # Toujours mettre à jour la balance de référence pour le prochain tick
                if current_balance != self.last_balance and not (len(self.last_positions.keys() ^ positions.keys()) > 0):
                    # Changement de balance sans changement de position (ex: swap ou autre)
                    self.last_balance = current_balance

            await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    monitor = GlobalMonitor()
    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        print("\n👋 Moniteur arrêté.")
