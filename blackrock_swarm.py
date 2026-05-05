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
import requests
import json
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Import de tous les agents
from agents import (
    macro_agent, quant_agent, loss_analyst_agent, accountant_agent,
    devil_advocate_agent, error_analyst_agent, risk_manager_agent,
    cio_agent, guardian_agent, compliance_agent, sentiment_agent,
    regime_agent, shadow_agent, meta_arbitre_agent
)
# Agents V7.25+ (Simulation stubs if files missing)
def get_stub_report(name): return f"Analyse {name} active. En attente de confluences spécifiques."
import psutil 

# --- CHARGEMENT DES SCORES DE RÉPUTATION (V7.0) ---
def load_agent_scores():
    try:
        with open("agent_scores.json", "r") as f:
            return json.load(f)
    except:
        return {}

AGENT_SCORES = load_agent_scores()

# Chargement des variables d'environnement
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

# --- CONFIGURATION SNIPER ---
MAX_TRADES_DAY = 15
MAX_TRADES_EVENING = 3
MARKET_CLOSE_HOUR = 23 # Heure de clôture pour le rapport final

# --- CONSENSUS THRESHOLDS (V7.25) ---
CONSENSUS_THRESHOLD = {
    "NORMAL"   : 0.50,
    "TRENDING" : 0.65,
    "VOLATILE" : 0.75,
    "CRISIS"   : 0.90
}

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
    # 1. Tentative via API
    try:
        r = requests.get('http://127.0.0.1:5000/api/v1/account', timeout=2)
        if r.status_code == 200:
            data = r.json().get('data', {})
            if data and data.get('balance', 0) > 0:
                return data
    except:
        pass

    # 2. Fallback via fichier direct (Plus fiable pour la balance)
    try:
        if os.path.exists('status.json'):
            with open('status.json', 'r') as f:
                data = json.load(f)
                return {
                    "balance": data.get('balance', 0),
                    "equity": data.get('equity', 0),
                    "drawdown": 0, # Calculé côté Dashboard
                    "positions_count": len(data.get('positions', [])),
                    "trading_enabled": data.get('trading', False),
                    "daily_trades": data.get('trades_today', 0),
                    "positions": data.get('positions', [])
                }
    except Exception as e:
        print(f"{C.YELLOW}⚠️ Erreur lecture status.json: {e}{C.RESET}")

    return {"balance": 0, "equity": 0, "drawdown": 0, "positions_count": 0, "trading_enabled": False, "daily_trades": 0}

def get_market_context() -> tuple:
    macro_ctx = "- Contexte Macro standard. Logic Sniper active."
    market_cond = "- XAUUSD: Consolidation. Analyse en cours."
    return macro_ctx, market_cond

# ── Swarm Principal ────────────────────────────────────────────────────────────
def get_system_health():
    """Audit technique pour le Guardian QA."""
    try:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        pids = [p.info['pid'] for p in psutil.process_iter(['pid', 'name']) if 'python' in (p.info['name'] or '').lower()]
        return f"CPU: {cpu}%, RAM: {ram}%, PIDs actifs: {len(pids)}"
    except:
        return "Audit système restreint."

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

    # PHASE 1 — ANALYSE & RÉGIME (Couche 1)
    section("COUCHE 1 — ANALYSE & RÉGIME (V7.0)", "🔬", C.BLUE)
    agents_p1 = [
        ("🌍 Macro-Économiste", macro_agent, [macro_ctx], "macro", C.BLUE),
        ("📊 Analyste Quant", quant_agent, [market_cond], "quant", C.MAGENTA),
        ("📰 Sentiment & News", sentiment_agent, [], "sentiment", C.CYAN),
        ("🌡️ Regime Detector", regime_agent, [market_cond], "regime", C.YELLOW),
        ("💧 Analyste Liquidité", None, [], "liquidity", C.BLUE),
        ("🔗 Corrélation Paires", None, [], "correlation", C.CYAN),
    ]
    
    def run_parallel(agents_list):
        # Architecture 3 niveaux V7.25 :
        #   Tier 1 (qwen2.5:0.5b)   → max 3 simultanés — léger, 30s timeout
        #   Tier 2 (tinyllama)       → max 2 simultanés — équilibré, 60s timeout
        #   Tier 3 (llama3:latest)   → séquentiel    — lourd, 120s timeout
        # max_workers=3 permet aux agents Tier 1 de ne pas bloquer les Tier 2.
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(m.run if m else lambda *a: get_stub_report(n), *args): (n, k, c) 
                      for n, m, args, k, c in agents_list}
            for future in futures:
                n, k, c = futures[future]
                try:
                    reports[k] = future.result()
                    agent_report(n, reports[k], c)
                    discord_log.append(f"\n{n}:\n{reports[k]}")
                except Exception as e:
                    reports[k] = f"Erreur: {e}"

    run_parallel(agents_p1)

    # Extraction du régime pour le Consensus Dynamique
    regime_report = reports.get('regime', '').upper()
    market_regime = "NORMAL"
    if "VOLATILE" in regime_report: market_regime = "VOLATILE"
    elif "CRISIS" in regime_report or "CRISE" in regime_report: market_regime = "CRISIS"
    elif "TRENDING" in regime_report: market_regime = "TRENDING"

    # PHASE 2 — CRITIQUE & SIMULATION (Couche 2)
    section("COUCHE 2 — CRITIQUE & SIMULATION", "⚖️", C.RED)
    
    # Préparer le setup pour le Shadow Trader
    shadow_setup = {
        'context': market_cond,
        'direction': "buy" if "ACHAT" in reports.get('quant', '').upper() or "BUY" in reports.get('macro', '').upper() else "sell",
        'regime': 1 if "TRENDING" in reports.get('regime', '').upper() else (0 if "RANGING" in reports.get('regime', '').upper() else 2)
    }

    p2_agents = [
        ("📉 Analyste Pertes", loss_analyst_agent, [account_data], "loss", C.YELLOW),
        ("😈 Avocat du Diable", devil_advocate_agent, [reports], "devil", C.RED),
        ("🔍 Audit Erreurs", error_analyst_agent, [reports], "errors", C.YELLOW),
        ("🎮 Shadow Trader", shadow_agent, [shadow_setup], "shadow", C.MAGENTA),
    ]
    run_parallel(p2_agents)

    # PHASE 3 — RISQUE & COMPLIANCE (Couche 3)
    section("COUCHE 3 — RISQUE & PROTECTION", "🛡️", C.GREEN)
    p3_agents = [
        ("🛡️ Risk Manager", risk_manager_agent, [account_data, reports], "risk", C.GREEN),
        ("⚖️ Compliance Officer", compliance_agent, [ts], "compliance", C.MAGENTA),
        ("🕵️ Guardian QA", guardian_agent, [get_system_health(), account_data.get('positions', []), "Audit PIDs actif"], "guardian", C.BLUE),
        ("⚰️ Post-Mortem", None, [], "post_mortem", C.RED),
        ("🐋 Whale Tracker", None, [], "whale", C.BLUE),
        ("📉 Volatility Expert", None, [], "volatility", C.YELLOW),
    ]
    run_parallel(p3_agents)

    # PHASE 4 — MÉMOIRE & RÉPUTATION (Couche 4)
    section("COUCHE 4 — MÉMOIRE & RÉPUTATION", "🧠", C.CYAN)
    reports["accountant"] = accountant_agent.run(account_data)
    reports["meta_arbitre"] = meta_arbitre_agent.run(AGENT_SCORES)
    
    agent_report("🧾 Comptable", reports["accountant"], C.CYAN)
    agent_report("🧠 Meta-Arbitre", reports["meta_arbitre"], C.WHITE)
    discord_log.append(f"\nMeta-Arbitre:\n{reports['meta_arbitre']}")

    # --- CALCUL DU CONSENSUS PONDÉRÉ (V7.0) ---
    section("COUCHE 5 — DÉCISION (Consensus Dynamique)", "🔮", C.WHITE)
    
    score_buy = 0.0
    score_sell = 0.0
    score_wait = 0.0
    
    for key, rep in reports.items():
        if key in ["meta_arbitre", "consensus_stats", "accountant"]: continue # Ne votent pas
        weight = AGENT_SCORES.get(key, 1.0)
        rep_up = rep.upper()
        if "ACHAT" in rep_up or "BUY" in rep_up: score_buy += weight
        elif "VENTE" in rep_up or "SELL" in rep_up: score_sell += weight
        else: score_wait += weight
        
    total_votes = score_buy + score_sell + score_wait
    
    # Seuil adaptatif (V7.25 Consensus Dynamique)
    threshold = CONSENSUS_THRESHOLD.get(market_regime, 0.50)
    
    consensus_msg = f"BUY: {score_buy:.1f} | SELL: {score_sell:.1f} | WAIT: {score_wait:.1f} | Seuil: {threshold:.0%} ({market_regime})"
    print(f"  {C.CYAN}⚖️ Consensus : {consensus_msg}{C.RESET}")
    
    # PHASE 5 — CIO DÉCISION FINALE
    reports['consensus_stats'] = consensus_msg
    final_decision = cio_agent.run(reports)
    
    # --- ARCHIVAGE POUR LE MÉTA-APPRENTISSAGE (V7.0) ---
    if "ACHAT" in final_decision.upper() or "VENTE" in final_decision.upper():
        memory_entry = {
            "timestamp": ts,
            "decision": final_decision,
            "votes": {k: ("BUY" if "ACHAT" in v.upper() or "BUY" in v.upper() else 
                          ("SELL" if "VENTE" in v.upper() or "SELL" in v.upper() else "WAIT"))
                      for k, v in reports.items() if isinstance(v, str)},
            "market_cond": market_cond,
            "status": "OPEN"
        }
        try:
            with open("swarm_memory.json", "a") as f:
                f.write(json.dumps(memory_entry) + "\n")
            print(f"  {C.GREEN}💾 Vote archivé dans swarm_memory.json pour futur apprentissage.{C.RESET}")
        except:
            pass

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
