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
    "XAUUSD": "🥇 OR (Gold)", "GOLD": "🥇 OR (Gold)", "XAGUSD": "🥈 Argent", 
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
        self.active_account = None
        self.active_server = None
        self.active_broker = None
        self.withdrawal_alert_sent = set()  # tickets déjà alertés pour retrait
        self.global_withdrawal_alerted = False  # alerte retrait global envoyée
        self.WITHDRAWAL_TRADE_PCT = 200  # % du volume pour alerte retrait par trade
        self.WITHDRAWAL_GLOBAL_PCT = 100  # % du dépôt initial pour alerte retrait global
        # V7.22 — OVERNIGHT HEDGE Countdown
        self.overnight_hedge_target = "20:55"  # GMT+0
        self.overnight_alerts_sent = set()  # {5min, 1min, 30s, 10s, 0s}
        self.last_overnight_day = None

    def detect_active_account(self):
        """Lit status.json pour détecter le compte MT5 actif."""
        data = self.read_status()
        if not data:
            return None, None, None
        account = data.get('account', os.getenv('MT5_LOGIN', '?'))
        server = data.get('server', os.getenv('MT5_SERVER', '?'))
        # Détection du broker
        srv = str(server).lower()
        if 'xmglobal' in srv or 'xm' in srv:
            broker = 'XM Global'
        elif 'deriv' in srv:
            broker = 'Deriv'
        elif 'exness' in srv:
            broker = 'Exness'
        else:
            broker = server
        self.active_account = str(account)
        self.active_server = server
        self.active_broker = broker
        return account, server, broker

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

    async def check_overnight_hedge_countdown(self):
        """
        V7.22 — Annonce le compte à rebours avant l'exécution OVERNIGHT HEDGE à 20:55 GMT+0.
        Envoie des alertes à -5min, -1min, -30s, -10s, et à l'exécution.
        """
        now = datetime.utcnow()
        current_day = now.date()
        
        # Reset les alertes chaque jour
        if self.last_overnight_day != current_day:
            self.overnight_alerts_sent = set()
            self.last_overnight_day = current_day
        
        # Cible : 20:55 GMT+0
        target_hour = 20
        target_minute = 55
        target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        # Calcul du temps jusqu'à la cible
        time_diff = (target_time - now).total_seconds()
        
        # Définir les seuils d'alerte
        alerts = {
            300: "🔔 **OVERNIGHT HEDGE dans 5 MIN**\n" +
                 "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" +
                 "⏰ Exécution prévue à **20:55 GMT+0**\n" +
                 "🥇 **3 dominants + 2 hedges GOLD**\n" +
                 "📊 Stratégie: Overnight Hedge Gap\n" +
                 "💡 Basé sur EMA H1 (tendance du jour)\n" +
                 "🎯 TP: 4×ATR | SL: 1.5×ATR\n" +
                 "🛡️ Hedges: TP: 0.5×ATR | SL: 0.3×ATR\n" +
                 "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            
            60: "⏳ **OVERNIGHT HEDGE dans 1 MIN**\n" +
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" +
                "⚡ Exécution IMMÉDIATE\n" +
                "🌙 Marché: XAUUSD (Or)\n" +
                "📍 Heure précise: 20:55:00 GMT+0\n" +
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            
            30: "⏱️ **OVERNIGHT HEDGE dans 30 SEC**\n" +
                "🚀 Préparez-vous ! C'est maintenant !",
            
            10: "⚡ **OVERNIGHT HEDGE dans 10 SEC**\n" +
                "🔥 MAINTENANT !",
            
            0: "✅ **OVERNIGHT HEDGE EXÉCUTÉ**\n" +
               "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" +
               "🌙 **3 BUY / 3 SELL GOLD PLACÉS**\n" +
               "⚡ Positions actives sur le marché\n" +
               "🎯 En attente de TP/SL\n" +
               "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        }
        
        # Déterminer si on doit envoyer une alerte
        for threshold, message in alerts.items():
            if -5 <= time_diff <= threshold + 5:  # Fenêtre de ±5s
                if threshold not in self.overnight_alerts_sent:
                    await self.send_all(message)
                    self.overnight_alerts_sent.add(threshold)
                    print(f"[OVERNIGHT] ✅ Alerte {threshold}s envoyée")

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
            account, server, broker = self.detect_active_account()
            await self.send_all(
                f"🟢 **SENTINEL ACTIVÉ** — {broker} `{account}`\n"
                f"🌐 Serveur: `{server}`\n"
                f"🏦 Solde: `${bal:.2f}` | Équité: `${eq:.2f}`\n"
                f"📊 Positions ouvertes: {nb_pos}\n"
                f"🔔 Notifications: ouverture, clôture, P&L, alertes"
            )
            with open(startup_flag, 'w') as f:
                f.write(str(time.time()))

        while True:
            # V7.22 — Check OVERNIGHT HEDGE countdown
            await self.check_overnight_hedge_countdown()
            
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

                # 5. ALERTE RETRAIT — Profit par trade ≥ 200% du volume engagé
                for ticket, pos in positions.items():
                    if ticket in self.withdrawal_alert_sent:
                        continue
                    pnl = pos.get('pnl', pos.get('profit', 0))
                    lot = pos.get('lot', pos.get('volume', 0.01))
                    sym = pos.get('sym', pos.get('symbol', '?'))
                    # Estimation marge engagée selon le symbole
                    if sym in ('XAUUSD', 'GOLD'):
                        margin_used = lot * 4675 / 1000  # levier 1:1000
                    else:
                        margin_used = lot * 100  # estimation par défaut
                    threshold = margin_used * (self.WITHDRAWAL_TRADE_PCT / 100)
                    if pnl >= threshold and threshold > 0:
                        self.withdrawal_alert_sent.add(ticket)
                        pct_gain = (pnl / margin_used * 100) if margin_used > 0 else 0
                        mtype = get_market_type(sym)
                        msg = (f"💎 **ALERTE RETRAIT POSSIBLE**\n"
                               f"━━━━━━━━━━━━━━━━━━\n"
                               f"📊 {mtype} — {pos.get('type', '?')}\n"
                               f"💰 Profit: `{pnl:+.2f}$` ({pct_gain:.0f}% du volume)\n"
                               f"📦 Volume: `{lot:.2f}` lots | Marge: `${margin_used:.2f}`\n"
                               f"━━━━━━━━━━━━━━━━━━\n"
                               f"✅ Ce trade a généré **{self.WITHDRAWAL_TRADE_PCT}%+** de sa marge\n"
                               f"💸 Vous pouvez envisager un retrait partiel\n"
                               f"🔒 Pensez à sécuriser : TP partiel ou trailing stop")
                        await self.send_all(msg)

                # 6. ALERTE RETRAIT GLOBAL — Profit total ≥ 100% du dépôt initial
                if self.initial_balance and self.initial_balance > 0:
                    profit_total = current_balance - self.initial_balance
                    pct_total = (profit_total / self.initial_balance) * 100
                    if pct_total >= self.WITHDRAWAL_GLOBAL_PCT and not self.global_withdrawal_alerted:
                        self.global_withdrawal_alerted = True
                        withdrawable = profit_total * 0.5  # suggestion: retirer 50% du profit
                        msg = (f"🏆 **OBJECTIF RETRAIT ATTEINT !**\n"
                               f"━━━━━━━━━━━━━━━━━━\n"
                               f"📈 Profit total: `{profit_total:+.2f}$` (+{pct_total:.0f}%)\n"
                               f"🏦 Dépôt initial: `${self.initial_balance:.2f}`\n"
                               f"💰 Solde actuel: `${current_balance:.2f}`\n"
                               f"━━━━━━━━━━━━━━━━━━\n"
                               f"💸 Retrait suggéré: `${withdrawable:.2f}` (50% du profit)\n"
                               f"🔄 Capital restant: `${current_balance - withdrawable:.2f}`\n"
                               f"━━━━━━━━━━━━━━━━━━\n"
                               f"⚠️ Retrait = sur le site du broker\n"
                               f"✅ Sécurisez vos gains régulièrement !")
                        await self.send_all(msg)
                    elif pct_total < (self.WITHDRAWAL_GLOBAL_PCT * 0.5):
                        self.global_withdrawal_alerted = False  # reset si le profit retombe

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
