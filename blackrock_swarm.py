"""
╔══════════════════════════════════════════════════════════════════════╗
║         🏦 BLACKROCK SWARM — COMITÉ D'INVESTISSEMENT IA V2          ║
║    Prompts optimisés • Discord • Boucle Automatique Horaire         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import requests
import time
import os
import schedule
import threading
import json
from datetime import datetime
from dotenv import load_dotenv

# Import de tous les agents
from agents import macro_agent, quant_agent, loss_analyst_agent
from agents import accountant_agent, devil_advocate_agent
from agents import error_analyst_agent, risk_manager_agent, cio_agent

# Chargement des variables d'environnement
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

# --- CONFIGURATION SNIPER ---
MAX_TRADES_DAY = 15
MAX_TRADES_EVENING = 3
MARKET_CLOSE_HOUR = 23 # Heure de clôture pour le rapport final

# ── Couleurs Terminal ──────────────────────────────────────────────────────────
class C:
    RESET   = '\033[0m';  BOLD    = '\033[1m'
    RED     = '\033[91m'; GREEN   = '\033[92m'
    YELLOW  = '\033[93m'; BLUE    = '\033[94m'
    MAGENTA = '\033[95m'; CYAN    = '\033[96m'
    WHITE   = '\033[97m'; BG_BLK  = '\033[40m'

# ── Discord ────────────────────────────────────────────────────────────────────
def send_discord(message: str):
    """Envoie un message sur Discord via le Bot Token."""
    if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
        print(f"{C.YELLOW}⚠️  Discord non configuré (vérifier .env){C.RESET}")
        return
    try:
        url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
        headers = {
            "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
        for chunk in chunks:
            requests.post(url, json={"content": chunk}, headers=headers, timeout=10)
    except Exception as e:
        print(f"{C.RED}❌ Erreur Discord: {e}{C.RESET}")

# ── Helpers Affichage et Persistance ──────────────────────────────────────────
def save_swarm_status(data):
    """Sauvegarde le dernier rapport pour le dashboard."""
    try:
        with open('swarm_status.json', 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Erreur sauvegarde status: {e}")

def banner():
    ts = datetime.now().strftime('%Y-%m-%d  %H:%M:%S')
    print(f"""
{C.BG_BLK}{C.BOLD}{C.WHITE}
╔══════════════════════════════════════════════════════════════════════╗
║      🏦  B L A C K R O C K   S W A R M   —   C O M I T É  V3     ║
║           Système Multi-Agents • Logique Sniper 15/3               ║
║      {ts}                               ║
╚══════════════════════════════════════════════════════════════════════╝
{C.RESET}""")

def section(title: str, emoji: str, color: str):
    print(f"\n{color}{C.BOLD}{'─'*70}{C.RESET}")
    print(f"{color}{C.BOLD}  {emoji}  {title}{C.RESET}")
    print(f"{color}{'─'*70}{C.RESET}")

def agent_report(name: str, report: str, color: str):
    print(f"\n{color}{C.BOLD}▶ {name}{C.RESET}")
    for line in report.strip().split('\n'):
        if line.strip():
            print(f"  {color}{line}{C.RESET}")

# ── Données ────────────────────────────────────────────────────────────────────
def get_sentinel_data() -> dict:
    try:
        r = requests.get('http://127.0.0.1:5000/api/v1/account', timeout=5)
        if r.status_code == 200:
            return r.json().get('data', {})
    except Exception as e:
        print(f"{C.YELLOW}⚠️  API Sentinel non disponible: {e}{C.RESET}")
    return {"balance": 0, "equity": 0, "drawdown": 0, "positions_count": 0, "trading_enabled": False, "daily_trades": 0}

def get_market_context() -> tuple:
    macro_ctx = "- Contexte Macro standard. Logic Sniper active."
    market_cond = "- XAUUSD: Consolidation. Analyse en cours."
    return macro_ctx, market_cond

# ── Swarm Principal ────────────────────────────────────────────────────────────
def run_swarm(is_daily_eval=False):
    banner()
    reports = {}
    discord_log = []
    ts = datetime.now().strftime('%d/%m/%Y %H:%M')

    if is_daily_eval:
        section("AUTO-ÉVALUATION & AMÉLIORATION DU SOIR", "🌙", C.MAGENTA)
        discord_log.append("🌙 **AUTO-ÉVALUATION DE MINUIT — PERFORMANCE DU JOUR**")

    discord_log.append(f"```")
    discord_log.append(f"🏦 BLACKROCK SWARM — CYCLE {ts}")
    discord_log.append(f"{'='*45}")

    section("DONNÉES MT5 EN DIRECT", "📡", C.CYAN)
    account_data = get_sentinel_data()
    daily_trades = account_data.get('daily_trades', 0)
    
    # Injection des règles Sniper dans les données pour les agents
    account_data['sniper_rules'] = f"Max {MAX_TRADES_DAY} trades/jour + {MAX_TRADES_EVENING} trades/soir."
    
    balance   = account_data.get('balance', 0)
    drawdown  = account_data.get('drawdown', 0)
    positions = account_data.get('positions_count', 0)
    auto      = 'Activé' if account_data.get('trading_enabled') else '🚫 Désactivé'
    
    print(f"  {C.GREEN}✅ Balance   : {balance} ${C.RESET}")
    print(f"  {C.GREEN}✅ Quota Day  : {daily_trades}/{MAX_TRADES_DAY}{C.RESET}")
    print(f"  {C.GREEN}✅ Drawdown  : {drawdown} %{C.RESET}")
    discord_log.append(f"💰 Balance: {balance}$ | Sniper: {daily_trades}/{MAX_TRADES_DAY} | DD: {drawdown}%")

    macro_ctx, market_cond = get_market_context()

    # PHASE 1
    section("PHASE 1 — ANALYSE (4 Agents)", "🔬", C.BLUE)
    agents_p1 = [
        ("🌍 Macro-Économiste", macro_agent, [macro_ctx], "macro", C.BLUE),
        ("📊 Analyste Quant", quant_agent, [market_cond], "quant", C.MAGENTA),
        ("📉 Analyste Pertes", loss_analyst_agent, [account_data], "loss", C.YELLOW),
        ("🧾 Comptable", accountant_agent, [account_data], "accountant", C.CYAN),
    ]
    for name, module, args, key, color in agents_p1:
        print(f"\n  {color}⏳ {name}...{C.RESET}", end="", flush=True)
        reports[key] = module.run(*args)
        agent_report(name, reports[key], color)
        discord_log.append(f"\n{name}:\n{reports[key]}")

    # PHASE 2
    section("PHASE 2 — CONTRE-EXPERTISE (3 Agents)", "⚖️", C.RED)
    p2_agents = [
        ("😈 Avocat du Diable", devil_advocate_agent, [reports], "devil", C.RED),
        ("🔍 Analyste des Erreurs", error_analyst_agent, [reports], "errors", C.YELLOW),
        ("🛡️ Risk Manager", risk_manager_agent, [account_data, reports], "risk", C.GREEN),
    ]
    for name, module, args, key, color in p2_agents:
        print(f"\n  {color}⏳ {name}...{C.RESET}", end="", flush=True)
        reports[key] = module.run(*args)
        agent_report(name, reports[key], color)
        discord_log.append(f"\n{name}:\n{reports[key]}")

    # PHASE 3 — CIO
    section("PHASE 3 — DÉCISION FINALE DU CIO", "👔", C.WHITE)
    final_decision = cio_agent.run(reports)
    print(f"\n  {C.WHITE}{C.BOLD}👔 DÉCISION DU CIO:{C.RESET}")
    print(f"  {final_decision}")

    discord_log.append(f"\n{'='*45}")
    discord_log.append(f"👔 DÉCISION DU CIO:\n{final_decision}")
    discord_log.append(f"```")

    save_swarm_status({
        "last_run": ts,
        "decision": final_decision,
        "reports": reports,
        "metrics": account_data
    })

    send_discord('\n'.join(discord_log))

# ── Boucle Automatique ─────────────────────────────────────────────────────────
def start_scheduler():
    print(f"{C.GREEN}🔄 Mode automatique V3 activé{C.RESET}")
    print(f"📅 Planning : Horaire + 23:00 Clôture + 00:00 Auto-Évaluation{C.RESET}")
    
    schedule.every(1).hours.do(run_swarm)
    schedule.every().day.at("00:00").do(run_swarm, is_daily_eval=True)
    schedule.every().day.at("23:00").do(run_swarm)
    
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    import sys
    run_swarm()
    if "--auto" in sys.argv:
        start_scheduler()
