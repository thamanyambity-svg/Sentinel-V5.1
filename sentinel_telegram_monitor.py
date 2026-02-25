#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════╗
║  SENTINEL V10 - TELEGRAM COMBAT MONITOR          ║
║  Surveillance temps réel + Rapports comptables    ║
╚═══════════════════════════════════════════════════╝

Fonctions:
  1. Notification à l'OUVERTURE de chaque position
  2. Notification à la FERMETURE avec rapport P&L
  3. Rapport comptable complet toutes les heures
  4. Alerte quand le gain atteint 100% du solde initial
  5. Rapport quotidien (matin et soir)
"""

import os
import json
import time
import asyncio
import aiohttp
import ssl
import certifi
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv("bot/.env")

# ══════════════════════════════════════
#            CONFIGURATION
# ══════════════════════════════════════

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5/"
    "drive_c/Program Files/MetaTrader 5/MQL5/Files/status.json"
)

SCAN_INTERVAL = 5        # Secondes entre chaque vérification
REPORT_INTERVAL = 3600   # Rapport toutes les heures (secondes)

ssl_context = ssl.create_default_context(cafile=certifi.where())

# ══════════════════════════════════════
#           ÉTAT DU MONITEUR
# ══════════════════════════════════════

class MonitorState:
    def __init__(self):
        self.initial_balance = None         # Solde au démarrage du moniteur
        self.daily_start_balance = None     # Solde début de journée
        self.last_known_positions = []      # Positions précédentes
        self.last_known_balance = 0
        self.last_report_time = 0
        self.trade_history = []             # Historique des trades détectés
        self.total_wins = 0
        self.total_losses = 0
        self.total_profit = 0
        self.total_loss = 0
        self.gain_100_notified = False      # Éviter les doublons de notif 100%
        self.session_start = datetime.now()

state = MonitorState()

# ══════════════════════════════════════
#         ENVOI TELEGRAM
# ══════════════════════════════════════

async def send_telegram(message):
    """Envoie un message Telegram formaté."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram non configuré")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_context)
        ) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    print(f"📲 Telegram OK")
                else:
                    print(f"❌ Telegram Error: {await resp.text()}")
    except Exception as e:
        print(f"❌ Telegram Exception: {e}")

# ══════════════════════════════════════
#          LECTURE STATUS.JSON
# ══════════════════════════════════════

def read_status():
    """Lit le fichier status.json exporté par la Sentinel."""
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

# ══════════════════════════════════════
#       NOTIFICATIONS DE POSITION
# ══════════════════════════════════════

async def notify_position_opened(pos, balance):
    """Notification quand une nouvelle position est ouverte."""
    icon = "🟢" if pos['type'] == "BUY" else "🔴"
    risk_pct = (pos['volume'] * 100) / balance if balance > 0 else 0
    
    msg = (
        f"{icon} *NOUVELLE POSITION OUVERTE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Symbole*: `{pos['symbol']}`\n"
        f"🎯 *Direction*: *{pos['type']}*\n"
        f"📦 *Volume*: {pos['volume']:.2f} lots\n"
        f"🆔 *Magic*: {pos.get('magic', 'N/A')}\n"
        f"💲 *Prix d'entrée*: {pos['price']:.5f}\n"
        f"🏦 *Solde actuel*: ${balance:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"🤖 _Sentinel V10 COMBAT_"
    )
    await send_telegram(msg)

async def notify_position_closed(pos, new_balance, old_balance):
    """Notification quand une position est fermée avec rapport P&L."""
    profit = pos.get('profit', new_balance - old_balance)
    is_win = profit > 0
    icon = "✅" if is_win else "❌"
    
    # Mettre à jour les stats
    if is_win:
        state.total_wins += 1
        state.total_profit += profit
    else:
        state.total_losses += 1
        state.total_loss += abs(profit)
    
    state.trade_history.append({
        "time": datetime.now().isoformat(),
        "symbol": pos.get('symbol', 'N/A'),
        "type": pos.get('type', 'N/A'),
        "volume": pos.get('volume', 0),
        "magic": pos.get('magic', 'N/A'),
        "profit": profit,
        "balance_after": new_balance
    })
    
    # Calcul winrate
    total_trades = state.total_wins + state.total_losses
    winrate = (state.total_wins / total_trades * 100) if total_trades > 0 else 0
    
    # Calcul variation depuis le début
    session_pnl = new_balance - state.initial_balance if state.initial_balance else 0
    session_pct = (session_pnl / state.initial_balance * 100) if state.initial_balance and state.initial_balance > 0 else 0
    
    msg = (
        f"{icon} *POSITION FERMÉE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *{pos.get('symbol', 'N/A')}* | {pos.get('type', 'N/A')} | {pos.get('volume', 0):.2f} lots\n"
        f"🆔 *Magic*: {pos.get('magic', 'N/A')}\n"
        f"💰 *P/L*: `{profit:+.2f}$`\n\n"
        f"*📋 RAPPORT COMPTABLE*\n"
        f"┌─────────────────────────\n"
        f"│ 🏦 Solde: *${new_balance:.2f}*\n"
        f"│ 📈 Session: `{session_pnl:+.2f}$` ({session_pct:+.1f}%)\n"
        f"│ ✅ Gains: {state.total_wins} | ❌ Pertes: {state.total_losses}\n"
        f"│ 🎯 Winrate: *{winrate:.0f}%*\n"
        f"│ 💹 Total Gagné: +${state.total_profit:.2f}\n"
        f"│ 💸 Total Perdu: -${state.total_loss:.2f}\n"
        f"│ 📊 Net: `{state.total_profit - state.total_loss:+.2f}$`\n"
        f"└─────────────────────────\n\n"
        f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"🤖 _Sentinel V10 COMBAT_"
    )
    await send_telegram(msg)

# ══════════════════════════════════════
#        ALERTE GAIN 100%
# ══════════════════════════════════════

async def check_100_percent_gain(balance):
    """Alerte quand le solde a doublé (gain 100%)."""
    if state.initial_balance and state.initial_balance > 0:
        gain_pct = ((balance - state.initial_balance) / state.initial_balance) * 100
        
        if gain_pct >= 100 and not state.gain_100_notified:
            state.gain_100_notified = True
            msg = (
                f"🎉🎉🎉 *OBJECTIF 100% ATTEINT !* 🎉🎉🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 *Solde initial*: ${state.initial_balance:.2f}\n"
                f"💰 *Solde actuel*: *${balance:.2f}*\n"
                f"📈 *Gain*: *+{gain_pct:.1f}%*\n\n"
                f"✅ Trades gagnants: {state.total_wins}\n"
                f"❌ Trades perdants: {state.total_losses}\n"
                f"🎯 Winrate: {(state.total_wins/(state.total_wins+state.total_losses)*100) if (state.total_wins+state.total_losses)>0 else 0:.0f}%\n\n"
                f"🏆 *LA SENTINEL A DOUBLÉ LE CAPITAL !*\n"
                f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
            await send_telegram(msg)

# ══════════════════════════════════════
#        RAPPORT HORAIRE
# ══════════════════════════════════════

async def send_hourly_report(data):
    """Rapport comptable complet envoyé toutes les heures."""
    balance = data.get('balance', 0)
    equity = data.get('equity', 0)
    trades_today = data.get('trades_today', 0)
    
    session_pnl = balance - state.initial_balance if state.initial_balance else 0
    session_pct = (session_pnl / state.initial_balance * 100) if state.initial_balance and state.initial_balance > 0 else 0
    
    total_trades = state.total_wins + state.total_losses
    winrate = (state.total_wins / total_trades * 100) if total_trades > 0 else 0
    profit_factor = (state.total_profit / state.total_loss) if state.total_loss > 0 else float('inf')
    
    uptime = datetime.now() - state.session_start
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    
    # Derniers trades
    recent = ""
    for t in state.trade_history[-5:]:
        icon = "✅" if t['profit'] > 0 else "❌"
        recent += f"  {icon} {t['symbol']} {t['type']} {t['profit']:+.2f}$\n"
    
    if not recent:
        recent = "  Aucun trade pour le moment\n"
    
    msg = (
        f"📊 *RAPPORT HORAIRE SENTINEL V10*\n"
        f"══════════════════════════════\n\n"
        f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"🕐 Uptime: {hours}h{minutes:02d}\n\n"
        f"*💰 COMPTE*\n"
        f"┌─────────────────────────\n"
        f"│ Balance:   *${balance:.2f}*\n"
        f"│ Equity:    ${equity:.2f}\n"
        f"│ P/L Jour:  `{session_pnl:+.2f}$` ({session_pct:+.1f}%)\n"
        f"└─────────────────────────\n\n"
        f"*📈 PERFORMANCE*\n"
        f"┌─────────────────────────\n"
        f"│ Trades:    {total_trades}\n"
        f"│ Winrate:   *{winrate:.0f}%*\n"
        f"│ Gagné:     +${state.total_profit:.2f}\n"
        f"│ Perdu:     -${state.total_loss:.2f}\n"
        f"│ Net:       `{state.total_profit - state.total_loss:+.2f}$`\n"
        f"│ P.Factor:  {profit_factor:.2f}\n"
        f"└─────────────────────────\n\n"
        f"*🕐 DERNIERS TRADES*\n"
        f"{recent}\n"
        f"🤖 _Sentinel V10 COMBAT - Rapport Auto_"
    )
    await send_telegram(msg)

# ══════════════════════════════════════
#         BOUCLE PRINCIPALE
# ══════════════════════════════════════

async def main():
    print("═══════════════════════════════════════")
    print("  📡 SENTINEL TELEGRAM MONITOR v2.0")
    print("═══════════════════════════════════════")
    
    # Message de démarrage
    await send_telegram(
        "🚀 *SENTINEL MONITOR DÉMARRÉ*\n\n"
        "📡 Surveillance du bot V10 COMBAT activée.\n"
        "📲 Notifications activées:\n"
        "  • Ouverture de position\n"
        "  • Fermeture + Rapport P/L\n"
        "  • Rapport horaire complet\n"
        "  • Alerte gain 100%\n\n"
        f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )
    
    while True:
        try:
            data = read_status()
            
            if data is None:
                await asyncio.sleep(SCAN_INTERVAL)
                continue
            
            balance = data.get('balance', 0)
            equity = data.get('equity', 0)
            positions = data.get('positions', [])
            
            # Initialiser le solde au premier tick
            if state.initial_balance is None:
                state.initial_balance = balance
                state.daily_start_balance = balance
                state.last_known_balance = balance
                print(f"💰 Solde initial enregistré: ${balance:.2f}")
            
            # ── DÉTECTER NOUVELLE POSITION ──
            current_tickets = {p['ticket'] for p in positions}
            previous_tickets = {p['ticket'] for p in state.last_known_positions}
            
            # Nouvelles positions
            new_tickets = current_tickets - previous_tickets
            for pos in positions:
                if pos['ticket'] in new_tickets:
                    await notify_position_opened(pos, balance)
            
            # Positions fermées
            closed_tickets = previous_tickets - current_tickets
            for old_pos in state.last_known_positions:
                if old_pos['ticket'] in closed_tickets:
                    await notify_position_closed(old_pos, balance, state.last_known_balance)
            
            # ── VÉRIFIER GAIN 100% ──
            await check_100_percent_gain(balance)
            
            # ── RAPPORT HORAIRE ──
            now = time.time()
            if now - state.last_report_time >= REPORT_INTERVAL:
                await send_hourly_report(data)
                state.last_report_time = now
            
            # Mettre à jour l'état
            state.last_known_positions = positions.copy()
            state.last_known_balance = balance
            
        except Exception as e:
            print(f"❌ Erreur moniteur: {e}")
        
        await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
