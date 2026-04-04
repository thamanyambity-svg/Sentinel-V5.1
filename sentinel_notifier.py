#!/usr/bin/env python3
import os
import json
import time
import asyncio
import requests
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
PNL_UPDATE_INTERVAL = 60  # Mise à jour P&L toutes les 60 secondes
SIGNIFICANT_PNL_THRESHOLD = 5.0  # Alerte si P&L > $5 (gain ou perte)

MARKET_TYPES = {
    "XAUUSD": "🥇 OR (Gold)", "XAGUSD": "🥈 Argent", 
    "EURUSD": "💶 Forex EUR/USD", "GBPUSD": "💷 Forex GBP/USD",
    "USDJPY": "💴 Forex USD/JPY", "USDCHF": "🏦 Forex USD/CHF",
    "AUDUSD": "🦘 Forex AUD/USD", "NZDUSD": "🥝 Forex NZD/USD",
    "USDCAD": "🍁 Forex USD/CAD", "BTCUSD": "₿ Crypto BTC",
    "ETHUSD": "⟠ Crypto ETH", "US30": "🇺🇸 Indice US30",
    "US100": "🇺🇸 Indice NASDAQ", "Volatility 100 Index": "🎰 Synth V100",
}

def get_market_type(symbol):
    return MARKET_TYPES.get(symbol, f"📊 {symbol}")

class GlobalMonitor:
    def __init__(self):
        self.last_positions = {}
        self.last_balance = 0
        self.initial_balance = None
        self.start_time = datetime.now()
        self.last_pnl_update = 0
        self.last_pnl_values = {}  # ticket -> last notified pnl

    async def send_all(self, message):
        """Envoie à Telegram et Discord (via requests synchrone pour fiabilité SSL macOS)."""
        loop = asyncio.get_event_loop()
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            await loop.run_in_executor(None, self.send_telegram_sync, message)
        if DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID:
            await loop.run_in_executor(None, self.send_discord_sync, message)

    def send_telegram_sync(self, message):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code != 200:
                print(f"❌ Erreur Telegram: {r.text}")
        except Exception as e:
            print(f"❌ Exception Telegram: {e}")

    def send_discord_sync(self, message):
        """Envoi via l'API Discord Bot (requests pour fiabilité SSL)."""
        url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
        headers = {
            "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        d_msg = message.replace("*", "**")
        payload = {"content": d_msg}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code not in [200, 201]:
                print(f"❌ Erreur Discord: {r.text}")
        except Exception as e:
            print(f"❌ Exception Discord: {e}")

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
        
        # Message de démarrage unique — pas de spam à chaque restart
        startup_flag = "/tmp/sentinel_notifier_started.flag"
        if not os.path.exists(startup_flag):
            data = self.read_status()
            bal = data.get('balance', 0) if data else 0
            eq = data.get('equity', 0) if data else 0
            nb_pos = len(data.get('positions', [])) if data else 0
            await self.send_all(
                f"🟢 **SENTINEL ACTIVÉ** — Compte `101573422`\n"
                f"🏦 Solde: `${bal:.2f}` | Équité: `${eq:.2f}`\n"
                f"📊 Positions ouvertes: {nb_pos}\n"
                f"🔔 Notifications: ouverture, clôture, P&L, alertes"
            )
            with open(startup_flag, 'w') as f:
                f.write(str(time.time()))

        while True:
            data = self.read_status()
            if data:
                current_balance = data.get('balance', 0)
                current_equity = data.get('equity', 0)
                
                if self.initial_balance is None: 
                    self.initial_balance = current_balance
                    self.last_balance = current_balance
                
                positions = {str(p.get('ticket', i)): p for i, p in enumerate(data.get('positions', []))}
                total_pnl = sum(p.get('pnl', p.get('profit', 0)) for p in positions.values())
                
                # 1. DÉTECTION NOUVELLES POSITIONS
                for ticket, pos in positions.items():
                    if ticket not in self.last_positions:
                        sym = pos.get('sym', pos.get('symbol', '?'))
                        mtype = get_market_type(sym)
                        source = pos.get('source', 'EA')
                        source_icon = "🤖" if source == "EA" else "👤"
                        sl = pos.get('sl', 0)
                        tp = pos.get('tp', 0)
                        sl_str = f"`{sl:.5f}`" if sl and sl > 0 else "❌ Aucun"
                        tp_str = f"`{tp:.5f}`" if tp and tp > 0 else "❌ Aucun"
                        
                        msg = (f"🟢 **NOUVELLE POSITION OUVERTE**\n"
                               f"━━━━━━━━━━━━━━━━━━\n"
                               f"{source_icon} Source: **{source}**\n"
                               f"📊 Marché: {mtype}\n"
                               f"🎯 Direction: **{pos.get('type', '?')}**\n"
                               f"📦 Volume: `{pos.get('lot', pos.get('volume', 0)):.2f}` lots\n"
                               f"💰 Prix entrée: `{pos.get('price', 0):.5f}`\n"
                               f"🛡️ Stop Loss: {sl_str}\n"
                               f"🎯 Take Profit: {tp_str}\n"
                               f"🏦 Solde: `${current_balance:.2f}`\n"
                               f"📈 Équité: `${current_equity:.2f}`\n"
                               f"━━━━━━━━━━━━━━━━━━")
                        await self.send_all(msg)
                        self.last_pnl_values[ticket] = 0

                # 2. DÉTECTION CLÔTURES AVEC P&L RÉEL
                for ticket, pos in self.last_positions.items():
                    if ticket not in positions:
                        real_profit = current_balance - self.last_balance
                        sym = pos.get('sym', pos.get('symbol', '?'))
                        mtype = get_market_type(sym)
                        source = pos.get('source', 'EA')
                        source_icon = "🤖" if source == "EA" else "👤"
                        icon = "✅" if real_profit >= 0 else "🚨"
                        status_txt = "GAIN" if real_profit >= 0 else "PERTE"
                        
                        msg = (f"{icon} **POSITION CLÔTURÉE — {status_txt}**\n"
                               f"━━━━━━━━━━━━━━━━━━\n"
                               f"{source_icon} Source: **{source}**\n"
                               f"📊 Marché: {mtype}\n"
                               f"🎯 Direction: **{pos.get('type', '?')}**\n"
                               f"💰 Prix entrée: `{pos.get('price', 0):.5f}`\n"
                               f"💵 Résultat: `{real_profit:+.2f}$`\n"
                               f"🏦 Nouveau Solde: `${current_balance:.2f}`\n"
                               f"📈 Équité: `${current_equity:.2f}`\n"
                               f"━━━━━━━━━━━━━━━━━━")
                        await self.send_all(msg)
                        self.last_balance = current_balance
                        self.last_pnl_values.pop(ticket, None)

                # 3. ÉVOLUTION P&L (toutes les 60s si positions ouvertes)
                now = time.time()
                if positions and (now - self.last_pnl_update) >= PNL_UPDATE_INTERVAL:
                    self.last_pnl_update = now
                    lines = []
                    for ticket, pos in positions.items():
                        sym = pos.get('sym', pos.get('symbol', '?'))
                        pnl = pos.get('pnl', pos.get('profit', 0))
                        source = pos.get('source', 'EA')
                        source_icon = "🤖" if source == "EA" else "👤"
                        pnl_icon = "🟢" if pnl >= 0 else "🔴"
                        lines.append(f"{source_icon}{pnl_icon} {sym} {pos.get('type','?')} → `{pnl:+.2f}$`")
                    
                    pnl_icon_total = "🟢" if total_pnl >= 0 else "🔴"
                    pct = (total_pnl / current_balance * 100) if current_balance > 0 else 0
                    
                    msg = (f"📊 **ÉVOLUTION POSITIONS** ({len(positions)} ouvertes)\n"
                           f"━━━━━━━━━━━━━━━━━━\n"
                           + "\n".join(lines) + "\n"
                           f"━━━━━━━━━━━━━━━━━━\n"
                           f"{pnl_icon_total} P&L Total: `{total_pnl:+.2f}$` ({pct:+.1f}%)\n"
                           f"🏦 Solde: `${current_balance:.2f}` | Équité: `${current_equity:.2f}`")
                    await self.send_all(msg)
                
                # 4. ALERTE GAIN/PERTE SIGNIFICATIF
                for ticket, pos in positions.items():
                    pnl = pos.get('pnl', pos.get('profit', 0))
                    last_pnl = self.last_pnl_values.get(ticket, 0)
                    # Alerte si le P&L a franchi un seuil de $5  
                    if abs(pnl) >= SIGNIFICANT_PNL_THRESHOLD and abs(last_pnl) < SIGNIFICANT_PNL_THRESHOLD:
                        sym = pos.get('sym', pos.get('symbol', '?'))
                        if pnl > 0:
                            msg = (f"💰 **GAIN SIGNIFICATIF !**\n"
                                   f"{get_market_type(sym)} → `{pnl:+.2f}$`\n"
                                   f"⚠️ Pensez à sécuriser vos gains !")
                        else:
                            msg = (f"⚠️ **PERTE SIGNIFICATIVE !**\n"
                                   f"{get_market_type(sym)} → `{pnl:+.2f}$`\n"
                                   f"🛑 Surveillez cette position !")
                        await self.send_all(msg)
                    self.last_pnl_values[ticket] = pnl

                self.last_positions = positions
                # Toujours mettre à jour la balance quand pas de changement de position
                if current_balance != self.last_balance and len(self.last_positions) == len(positions):
                    self.last_balance = current_balance

            await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    monitor = GlobalMonitor()
    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        print("\n👋 Moniteur arrêté.")
