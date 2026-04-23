import json
import os
import time
import logging
import sys
from datetime import datetime, timedelta
import yfinance as yf
from openai import OpenAI
from dotenv import load_dotenv
from supabase import create_client, Client

# =================================================================
# 0. LOGGING CONFIGURATION
# =================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("/Users/macbookpro/Downloads/bot_project/manus_bridge.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ManusBridge")

# =================================================================
# 1. CONFIGURATION & SECRETS
# =================================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Chemins
MT5_BIAS_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/macro_bias.json"
MT5_STATUS_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/status.json"
MT5_TICKS_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/ticks_v3.json"
MT5_STATS_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/account_stats.json"
DASHBOARD_DATA_PATH = "/Users/macbookpro/Downloads/bot_project/macro_bias.json"
HISTORY_FILE = "/Users/macbookpro/Downloads/bot_project/account_history.json"
TICK_BUFFER_FILE = "/Users/macbookpro/Downloads/bot_project/tick_buffer.json"

client = OpenAI(api_key=OPENAI_API_KEY)

client = OpenAI(api_key=OPENAI_API_KEY)

# Buffer de Ticks en mémoire
gold_tick_buffer = []

# =================================================================
# 1.5 SUPABASE & MOBILE BRIDGE CONFIG
# =================================================================
SUPABASE_URL = "https://ucoughwtxwsapolrxnqk.supabase.co"
SUPABASE_KEY = "sb_publishable_AYAgBJUAIa8mV16hpYwr0w_vQhXiEUZ"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logger.error(f"Erreur init Supabase Client: {e}")

MT5_COMMAND_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/mobile_commands.json"

def sync_mobile_orders():
    """Vérifie s'il y a de nouveaux ordres venant de l'application mobile via Supabase."""
    try:
        # On récupère les ordres en attente (PENDING)
        response = supabase.table("orders").select("*").eq("status", "PENDING").execute()
        orders = response.data

        if orders:
            logger.info(f"[{time.strftime('%H:%M:%S')}] {len(orders)} nouvel(s) ordre(s) mobile détecté(s) !")
            
            for order in orders:
                # Préparation de la commande pour MT5
                cmd = {
                    "action": "execute_trade",
                    "symbol": order["symbol"],
                    "type": order["type"], # BUY ou SELL
                    "quantity": float(order["quantity"]),
                    "price": float(order["price"]),
                    "order_id": order["id"]
                }

                # On écrit la commande dans le fichier de communication MT5
                with open(MT5_COMMAND_PATH, "w") as f:
                    json.dump(cmd, f)

                # On met à jour le statut dans Supabase pour éviter les doublons
                supabase.table("orders").update({"status": "EXECUTED"}).eq("id", order["id"]).execute()
                logger.info(f"Ordre #{order['id']} ({order['type']} {order['symbol']}) transmis à MT5 avec succès.")

    except Exception as e:
        logger.error(f"Erreur Synchronisation Supabase: {e}")

# =================================================================
# 2. PERCEPTION & HISTOIRE
# =================================================================
def get_live_ticks():
    """Récupère le dernier tick depuis MT5 et met à jour le buffer."""
    global gold_tick_buffer
    if not os.path.exists(MT5_TICKS_PATH):
        return []

    try:
        with open(MT5_TICKS_PATH, "r") as f:
            ticks = json.load(f)
            # On cherche l'Or
            gold = next((t for t in ticks if t['sym'] in ["XAUUSD", "GOLD", "XAUUSDm"]), None)
            if gold:
                new_tick = {
                    "time": int(time.time()), # Timestamp pour Lightweight Charts
                    "price": (gold['bid'] + gold['ask']) / 2,
                    "bb_u": gold.get('bb_u', 0),
                    "bb_l": gold.get('bb_l', 0)
                }
                # On évite d'ajouter le même prix s'il n'a pas bougé
                if not gold_tick_buffer or gold_tick_buffer[-1]['price'] != new_tick['price']:
                    gold_tick_buffer.append(new_tick)
                
                if len(gold_tick_buffer) > 60: gold_tick_buffer.pop(0)
    except Exception as e:
        logger.debug(f"Erreur Lecture Ticks : {e}")
    
    return gold_tick_buffer

def get_ohlc(symbol="GLD", interval="1h", period="7d"):
    """Récupère l'historique OHLC pour un intervalle donné."""
    try:
        hist = yf.Ticker(symbol).history(period=period, interval=interval)
        price_data = []
        for dt, row in hist.iterrows():
            price_data.append({
                "time": int(dt.timestamp()),
                "open": round(row['Open'], 2),
                "high": round(row['High'], 2),
                "low": round(row['Low'], 2),
                "close": round(row['Close'], 2)
            })
        return price_data
    except Exception as e:
        logger.debug(f"Erreur OHLC ({interval}): {e}")
        return []

def get_market_context():
    """Récupère les variables institutionnelles et l'historique multi-TF."""
    try:
        # 1. Données Instantanées
        tip = yf.Ticker("TIP").history(period="2d")
        vix = yf.Ticker("^VIX").history(period="2d")
        gold = yf.Ticker("GLD").history(period="2d")  # GLD ETF = proxy fiable pour XAU/USD
        tnx = yf.Ticker("^TNX").history(period="2d")
        dxy = yf.Ticker("DX-Y.NYB").history(period="2d")

        # 2. Historique Multi-TF
        # On définit les intervalles demandés par l'utilisateur
        intervals = {
            "1m": "1d",
            "5m": "1d",
            "15m": "2d",
            "30m": "3d",
            "1h": "7d",
            "4h": "14d",
            "1d": "1mo",
            "1wk": "6mo",
            "1mo": "2y"
        }
        
        charts = {}
        # Pour ne pas tout re-télécharger à chaque cycle de 2s, 
        # on peut limiter le rafraîchissement des TFs lents (implémenté dans run_cycle)
        for itv, prd in intervals.items():
            charts[itv] = get_ohlc("GLD", itv, prd)

        vix_val = vix['Close'].iloc[-1] if not vix.empty else 0
        tip_chg = ((tip['Close'].iloc[-1] - tip['Close'].iloc[-2]) / tip['Close'].iloc[-2]) * 100 if len(tip) > 1 else 0
        tnx_chg = ((tnx['Close'].iloc[-1] - tnx['Close'].iloc[-2]) / tnx['Close'].iloc[-2]) * 100 if len(tnx) > 1 else 0
        
        real_yield_pressure = "HAUSSIÈRE (Pression sur l'Or)" if tip_chg < 0 and tnx_chg > 0 else "BAISSIÈRE (Soutien pour l'Or)"

        gold_d1_chg = ((gold['Close'].iloc[-1] - gold['Open'].iloc[-1]) / gold['Open'].iloc[-1]) * 100 if not gold.empty else 0
        d1_bias = "HAUSSIER" if gold_d1_chg > 0 else "BAISSIER"

        return {
            "dxy": f"{(dxy['Close'].iloc[-1] - dxy['Close'].iloc[-2]):+.2f}" if len(dxy) > 1 else "0.00",
            "vix": round(vix_val, 2),
            "gold_price": round(gold['Close'].iloc[-1], 2) if not gold.empty else 0,
            "yield_context": real_yield_pressure,
            "d1_bias": d1_bias,
            "charts": charts
        }
    except Exception as e:
        logger.error(f"Erreur Perception : {e}")
        return None

def update_account_history(balance, equity):
    """Enregistre un point de données pour le graphique de performance."""
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except: history = []

    # On garde max 100 points
    new_point = {
        "time": datetime.now().strftime("%H:%M"),
        "balance": balance,
        "equity": equity
    }
    
    # Éviter les doublons trop fréquents (min 5 min entre points)
    if not history or (datetime.now() - datetime.strptime(history[-1].get('date', '2000-01-01'), "%Y-%m-%d %H:%M:%S")).total_seconds() > 300:
        new_point['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history.append(new_point)
    
    if len(history) > 100: history.pop(0)

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)
    return history

# =================================================================
# 3. CONSOLIDATION
# =================================================================
def run_cycle():
    logger.info("--- DÉBUT CYCLE PREMIUM ---")
    
    # 1. Perception Marché (Macro + Ticks)
    market = get_market_context()
    ticks = get_live_ticks()
    
    # 2. Perception Compte (MT5)
    mt5_data = {"balance": 0, "equity": 0, "positions": [], "pos_total": 0}
    if os.path.exists(MT5_STATUS_PATH):
        try:
            with open(MT5_STATUS_PATH, "r") as f:
                mt5_data = json.load(f)
        except Exception as e:
            logger.error(f"Erreur lecture status MT5 : {e}")

    # 3. Perception Stats Avancées (V7.26)
    acc_stats = {"margin_level": 0, "hedge_status": "EXPOSITION", "eod_hedge_triggered": False}
    if os.path.exists(MT5_STATS_PATH):
        try:
            with open(MT5_STATS_PATH, "r") as f:
                acc_stats = json.load(f)
        except: pass

    # 4. Historique Compte (Seulement si data valide)
    acc_history = []
    if mt5_data['balance'] > 0:
        acc_history = update_account_history(mt5_data['balance'], mt5_data['equity'])

    # 4. Cognition Manus AI (Une fois par cycle lent, ou simplifié pour le dashboard)
    # Pour ne pas saturer l'API OpenAI en mode tick, on utilise un cache
    global last_ai_run, cached_verdict
    if 'last_ai_run' not in globals() or (datetime.now() - last_ai_run).total_seconds() > 300:
        verdict = {"verdict": "NEUTRAL", "confidence": 0.5, "reason": "Analyse en attente...", "risk_level": "MED"}
        if market:
            prompt = (
                f"Analyse institutionnelle Or: prix={market['gold_price']}, VIX={market['vix']}, Context={market['yield_context']}. "
                "Génère un verdict JSON (verdict, confidence, reason, risk_level). "
                "CRITIQUE : La 'reason' doit être exclusivement en FRANÇAIS, très détaillée, pédagogique et explicite. "
                "Explique l'impact du VIX et du contexte sur l'Or de manière professionnelle."
            )
        else:
            verdict = {"verdict": "STABLE", "confidence": 1.0, "reason": "Le marché est actuellement fermé. L'analyse institutionnelle détaillée reprendra automatiquement à l'ouverture pour fournir des insights explicites sur l'Or et le VIX.", "risk_level": "LOW"}
            cached_verdict = verdict
            return verdict

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            verdict = json.loads(response.choices[0].message.content)
            last_ai_run = datetime.now()
            cached_verdict = verdict
        except Exception as e:
            logger.error(f"AI Logic Error: {e}")
            verdict = cached_verdict
    else:
        verdict = cached_verdict

    # 5. Export Centralisé
    dashboard_json = {
        "verdict": verdict['verdict'],
        "confidence": verdict['confidence'],
        "reason": verdict['reason'],
        "risk": verdict.get('risk_level', "MEDIUM"),
        "vix": market['vix'] if market else "--",
        "yield_context": market['yield_context'] if market else "No sync",
        "gold_price": market['gold_price'] if market else 0,
        "balance": mt5_data['balance'],
        "equity": mt5_data['equity'],
        "margin_level": acc_stats.get('margin_level', 0),
        "hedge_status": acc_stats.get('hedge_status', "EXPOSITION"),
        "eod_triggered": acc_stats.get('eod_hedge_triggered', False),
        "positions": mt5_data.get('positions', []),
        "charts": market['charts'] if market else {},
        "chart_ticks": ticks,
        "chart_account": acc_history,
        "d1_bias": market['d1_bias'] if market else "NEUTRE",
        "timestamp": mt5_data.get('ts', int(time.time())),
        "last_update": datetime.now().strftime("%H:%M:%S")
    }

    # Sauvegarde pour MT5
    try:
        with open(MT5_BIAS_PATH, "w") as f:
            json.dump(dashboard_json, f, indent=4)
        # Sauvegarde pour Dashboard
        with open(DASHBOARD_DATA_PATH, "w") as f:
            json.dump(dashboard_json, f, indent=4)
        logger.info(f"Dashboard & MT5 synchronisés. Verdict: {verdict['verdict']}")
    except Exception as e:
        logger.error(f"Erreur Export : {e}")

if __name__ == "__main__":
    is_loop = "--loop" in sys.argv

    if not is_loop:
        run_cycle()
        sync_mobile_orders()
    else:
        logger.info("Mode Production Actif (Scan Ticks toutes les 2 sec)")
        while True:
            sync_mobile_orders() # Vérifie les ordres mobiles
            run_cycle()
            time.sleep(2)
