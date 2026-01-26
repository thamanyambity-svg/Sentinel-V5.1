from dotenv import load_dotenv
env_path = "/Users/macbookpro/Downloads/bot_project/bot/.env"
load_dotenv(env_path, override=True)

import os
import sys
# Debug Keys
print(f"DEBUG: GEMINI_API_KEY from os.environ: {bool(os.environ.get('GEMINI_API_KEY'))}")
print(f"DEBUG: GROQ_API_KEY from os.environ: {bool(os.environ.get('GROQ_API_KEY'))}")

import ssl
import certifi


# --- PATCH DE SÉCURITÉ SSL POUR MAC (DOIT ÊTRE EN PREMIER) ---
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
try:
    _create_unverified_https_context = ssl._create_unverified_context
    ssl._create_default_https_context = _create_unverified_https_context
except AttributeError:
    pass

import asyncio
import subprocess
import time
import time as tm
import pandas as pd
import logging
import sys

from bot.config import runtime
from bot.broker.deriv.client import DerivClient
from bot.broker.deriv.broker import DerivBroker
from bot.strategy.rsi import RSIStrategy
from bot.discord_interface.bot import TradingBot
from bot.broker.trade_counter import is_limit_reached, increment_trade_count, get_trade_count, get_max_trades
from bot.ai_agents.audit_logger import log_event, generate_signal_id
from bot.state.override import is_force_enabled
# --- 🛡️ AI MODULE DEFENSIVE WRAPPERS ---
try:
    from bot.ai_agents.regime_classifier import RegimeClassifier # [PHASE 2]
    from bot.ai_agents.smart_execution import SmartExecutionAgent # [PHASE 3]
    AI_CORE_AVAILABLE = True
except Exception as e:
    print(f"⚠️ AI CORE LOAD ERROR: {e}. Falling back to MOCK modules for stability.")
    AI_CORE_AVAILABLE = False
    
    class RegimeClassifier:
        def detect_regime(self, candles):
            return {"regime": "TREND_STABLE", "reason": "AI Mock (Stability Mode)"}
            
    class SmartExecutionAgent:
        def __init__(self): pass
        def analyze(self, data): return {"signal": "STABLE", "reason": "AI Mock"}

try:
    from bot.ai_agents.market_structure import MarketStructureAgent
    from bot.ai_agents.quant_predictor import QuantPredictor
    from bot.ai_agents.quantum_filter import QuantumFilter
    AI_ADVANCED_AVAILABLE = True
except Exception as e:
    print(f"⚠️ AI ADVANCED LOAD ERROR: {e}. Using Core Math only.")
    AI_ADVANCED_AVAILABLE = False
    class MarketStructureAgent:
        def analyze(self, data): return {"signal": "STABLE", "reason": "Core Math Mode"}
    class QuantumFilter:
        def update(self, price): return price, 0.0


# --- 🛡️ ROBUST SINGLE INSTANCE GUARD (USER PROVIDED) ---
import sys
import os
import signal
import atexit
import socket
import time
import subprocess

LOCK_FILE = "trading_bot.lock"

def safe_exit(signum=None, frame=None):
    """Nettoyage propre à la sortie"""
    print(f"\n{'='*50}")
    print("🛑 ARRÊT PROPRE DU BOT")
    
    # Supprimer le lock file
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
            print(f"✅ Lock file supprimé: {LOCK_FILE}")
        except: pass
    
    print(f"⏱️ Bot arrêté à {time.strftime('%H:%M:%S')}")
    print("="*50)
    sys.exit(0)

def kill_old_instances():
    """Tuer les anciennes instances du bot"""
    print("🧹 Nettoyage des anciens processus...")
    try:
        if sys.platform != "win32":
            subprocess.run(["pkill", "-9", "-f", "main.py"], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"⚠️ Nettoyage partiel: {e}")
    time.sleep(1)

def single_instance_guard():
    """Assure qu'une seule instance tourne"""
    
    # Vérifier si un lock existe
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = f.read().strip()
            
            # Check if process really exists (Mac/Linux)
            try:
                os.kill(int(old_pid), 0) # Signal 0 checks existence
                print(f"🚨 Un bot tourne déjà (PID: {old_pid})")
                
                # Force kill old
                print(f"🔫 Killing old instance {old_pid}...")
                os.kill(int(old_pid), 9)
                time.sleep(1)
            except OSError:
                print("⚠️ Lock file stérile (processus mort). Nettoyage.")
        except:
            pass
    
    # Créer nouveau lock
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    
    # Configurer le cleanup à la sortie
    atexit.register(lambda: os.remove(LOCK_FILE) if os.path.exists(LOCK_FILE) else None)
    
    # Capturer les signaux d'arrêt
    signal.signal(signal.SIGINT, safe_exit)
    signal.signal(signal.SIGTERM, safe_exit)
    
    return True

# EXECUTE GUARD IMMMEIDATELY
if not single_instance_guard():
    print("❌ Fatal Error: Could not acquire lock.")
    sys.exit(1)

print("✅ SINGLE INSTANCE GUARD ACTIVE.")



# Setup Logger
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", mode='a')
    ]
)
logger = logging.getLogger("BOT")

# Load Configuration
ASSETS_STR = os.getenv("TRADING_ASSETS", "1HZ10V,1HZ100V,STP")
logger.info(f"📋 LOADED ASSETS: {ASSETS_STR}")
ASSETS = ASSETS_STR.split(",") # Deriv + AvaTrade (dynamic)
TIMEFRAME = "1m"
ENABLE_GOVERNANCE = True # [INSTITUTIONAL] Full AI Veto Active
# --- 🛡️ SIGNAL & EXECUTION THRESHOLDS (GLOBAL) ---
MIN_QUALITY_SCORE = 40       # Aggressive: Lowered from 75
MIN_AI_CONFIDENCE = 0.40     # Aggressive: Lowered from 0.65
MAX_CONSECUTIVE_LOSSES = 3

# --- 🛡️ SAFETY CONTROLLER (V3.0) ---
import json
from datetime import datetime, timedelta

# MT5 DATA PATH (Synced with mt5_interface.py)
DEFAULT_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
MT5_ROOT_PATH = os.getenv("MT5_FILES_PATH", DEFAULT_PATH)
STATUS_FILE = os.path.join(MT5_ROOT_PATH, "status.json")

class SafetyController:
    def __init__(self):
        self.volatility_threshold = 0.8  # 0.8% ATR Threshold
        self.max_position_size = 0.1     # Max total volume

    def check_volatility(self, candles):
        """ Check ATR Volatility % """
        try:
            if not candles or len(candles) < 20: return False, "No Data"
            
            df = pd.DataFrame(candles)
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            
            # Simple ATR Calculation
            df['tr'] = df['high'] - df['low'] # Simplified TR for speed
            atr = df['tr'].rolling(window=14).mean().iloc[-1]
            price = df['close'].iloc[-1]
            
            atr_percent = (atr / price) * 100
            
            if atr_percent > self.volatility_threshold:
                return False, f"Volatility Risk: {atr_percent:.2f}% > {self.volatility_threshold}%"
            
            return True, f"Vol OK: {atr_percent:.2f}%"
        except Exception as e:
            return False, f"Vol Check Error: {e}"

    def check_market_conditions(self, symbol):
        return []

def get_real_pnl_from_sentinel():
    """ Read accurate PnL from Sentinel status.json """
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                data = json.load(f)
            
            # 1. CHECK EMERGENCY FLAG
            if data.get("emergency") == True:
                logger.critical(f"🔥 SENTINEL EMERGENCY TRIGGERED: {data.get('reason')}")
                return -9999.0 # Force Stop
            
            # 2. CHECK PnL
            total_open_pnl = sum(p.get("profit", 0) for p in data.get("positions", []))
            return total_open_pnl
    except Exception as e:
        logger.error(f"⚠️ Failed to read Sentinel Status at {STATUS_FILE}: {e}")
        pass
    return 0.0

def confirm_momentum(candles, side):
    """ Technical Confirmation (RSI) """
    if not candles: return False
    rsi = calculate_rsi(candles)
    if not isinstance(rsi, pd.Series): return True # Fallback
    
    val = rsi.iloc[-1]
    if side == "BUY": return val < 70
    if side == "SELL": return val > 30
    return True

# --- END SAFETY CONTROLLER ---

def calculate_probability(rsi, side):
    base_prob = 55
    deviation = 0
    if side == "BUY": deviation = 50 - rsi
    else: deviation = rsi - 50
    bonus = max(0, (deviation - 20) * 1.5)
    prob = min(95, base_prob + bonus)
    return int(prob)

def calculate_atr(candles, period=14):
    if not candles or len(candles) < period: return None
    df = pd.DataFrame(candles)
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift()).abs()
    tr3 = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr.iloc[-1]
    
# fetch_candles implementation
async def fetch_candles(driver, symbol, granularity, count):
    """
    Fetch candles from Deriv API with automatic symbol mapping.
    """
    api_symbol = symbol
    if symbol == "EURUSD": api_symbol = "frxEURUSD"
    if symbol == "GOLD": api_symbol = "frxXAUUSD"
    if symbol == "XAUUSD": api_symbol = "frxXAUUSD"
    
    try:
        req = {
            "ticks_history": api_symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "style": "candles",
            "granularity": granularity
        }
        res = await driver.send(req)
        if "candles" in res:
            return res["candles"]
        
        if "error" in res:
            logger.debug(f"API Error for {symbol} ({api_symbol}): {res['error'].get('message')}")
        
        return []
        return []
    except Exception as e:
        logger.error(f"Error fetching candles for {symbol}: {e}")
        return []


def calculate_rsi(candles, period=14):
    """ Calculates RSI for technical confirmation """
    if not candles or len(candles) < period: return None
    df = pd.DataFrame(candles)
    df['close'] = df['close'].astype(float)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return val if not pd.isna(val) else 50

def calculate_adx(candles, period=14):
    if not candles or len(candles) < period * 2: return 0
    df = pd.DataFrame(candles)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift(1))
    df['tr2'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)

    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    
    df['plus_dm'] = 0.0
    df.loc[(df['up_move'] > df['down_move']) & (df['up_move'] > 0), 'plus_dm'] = df['up_move']
    
    df['minus_dm'] = 0.0
    df.loc[(df['down_move'] > df['up_move']) & (df['down_move'] > 0), 'minus_dm'] = df['down_move']
    
    df['tr'] = df['tr'].rolling(window=period).sum()
    df['plus_dm'] = df['plus_dm'].rolling(window=period).sum()
    df['minus_dm'] = df['minus_dm'].rolling(window=period).sum()

    df['plus_di'] = 100 * (df['plus_dm'] / df['tr'])
    df['minus_di'] = 100 * (df['minus_dm'] / df['tr'])
    
    df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
    df['adx'] = df['dx'].rolling(window=period).mean()
    
    val = df['adx'].iloc[-1]
    return val if not pd.isna(val) else 0

from bot.risk.governance import CircuitBreaker
print("DEBUG: 🚀 INITIALIZING CIRCUIT BREAKER V4.0 (Limit: 1000.0, Loss: -300.0)")
governor = CircuitBreaker(max_loss=-300.0, max_profit=1000.0) # Recalibrated V4.0 Risk Scale

from bot.strategy.rsi import RSIStrategy
from bot.strategy.trend_following import TrendFollowingStrategy
from bot.core.manager import TradingManager
from bot.journal.logger import load_trades

def calculate_ema(candles, period=20):
    if not candles or len(candles) < period: return None
    df = pd.DataFrame(candles)
    df['close'] = df['close'].astype(float)
    ema = df['close'].ewm(span=period, adjust=False).mean()
    return ema.iloc[-1]

from bot.data.collector import DataCollector
from bot.ai_agents.market_structure import MarketStructureAgent
from bot.ai_agents.quant_predictor import QuantPredictor
from bot.ai_agents.quantum_filter import QuantumFilter

from bot.telegram_interface.notifier import TelegramNotifier

async def delayed_learning(bot_instance, trade_id, asset, bridge):
    """Wait 5 minutes after a trade, sync balance, and run audit."""
    logger.info(f"🕒 [LEARNING] Scheduled for Trade {trade_id} ({asset}) in 5 minutes...")
    await asyncio.sleep(300) # 5 minutes
    
    logger.info(f"🧠 [LEARNING] Starting Post-Trade Review for {trade_id}...")
    
    # 1. Update Balance Priority
    raw_status = bridge.get_raw_status()
    mt5_bal = raw_status.get("balance")
    if mt5_bal:
        logger.info(f"💎 [LEARNING] Post-Trade Balance Update: ${mt5_bal:.2f}")
        
    # 2. Trigger Professor Audit via Bot Command
    from bot.discord_interface.commands import professor_command
    report = professor_command()
    
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if report and channel_id:
        channel = bot_instance.get_channel(int(channel_id))
        if channel:
            header = f"🎓 **Post-Trade Audit (Trade: {trade_id})**\n"
            if len(report) > 1900:
                 await channel.send(header + report[:1900] + "...")
            else:
                 await channel.send(header + report)
            logger.info(f"✅ [LEARNING] Audit sent to Discord for {trade_id}")

async def trading_logic(bot_instance):

    logger.info("🚀 Institutional Trading Loop Started")
    
    # --- [SESSION] Auto-Stop Guard ---
    async def check_session_timeout():
        import datetime as dt
        now = dt.datetime.now()
        if now.hour == 3: # Stop exactly at 3am hour
            msg = "💤 **REPOS DU GUERRIER** : Il est 03h00. Session terminée comme prévu. À demain ! 🚀📉🛌"
            logger.info(msg)
            try: await bot_instance.log_to_discord(msg)
            except: pass
            try: 
                from bot.telegram_interface.notifier import TelegramNotifier
                tg = TelegramNotifier()
                await tg.send_message(msg)
            except: pass
            safe_exit()

    # --- [CRITICAL] MT5 BRIDGE & RESET ---
    # --- [CRITICAL] MT5 BRIDGE & RESET ---
    from bot.bridge.mt5_interface import MT5Bridge
    from bot.ai_agents.market_intelligence import MarketIntelligence
    
    # --- MULTI-BRIDGE INITIALIZATION ---
    # Using the path confirmed by grep/ls (Default MT5 path)
    AVA_PATH = os.getenv("MT5_FILES_PATH") or "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
    
    logger.info(f"🌉 Initializing MT5 Bridge at: {AVA_PATH}")
    bridge = MT5Bridge(root_path=AVA_PATH)
    
    # Init Market Intelligence
    logger.info("🧠 Initializing Market Intelligence (OHLC.Dev)...")
    market_mind = MarketIntelligence()
    
    logger.info("🛡️ [INIT] Global Risk Reset...")
    try:
        bridge.reset_risk()
    except Exception as e:
        logger.warning(f"⚠️ Risk Reset Warning: {e}")
    
    
    # Init Core
    client = DerivClient()
    bot_instance.deriv_client = client
    
    # --- [REAL HUNT] BALANCE VERIFICATION ---
    try:
        await client.connect()
        bal_data = await client.get_balance()
        if bal_data:
            logger.info(f"💰 [REAL HUNT] Verified Balance: ${bal_data['balance']} {bal_data['currency']}")
        await client.close()
    except Exception as bal_err:
        logger.error(f"❌ [REAL HUNT] Balance check failed: {bal_err}")
    
    manager = TradingManager()
    
    # [NEW] Risk Manager Integration
    from bot.risk.risk_manager import RiskManager
    risk_manager = RiskManager(max_grid_layers=3, risk_per_trade=0.015)

    broker = DerivBroker()
    # Attach broker to bot instance for Webhook access
    bot_instance.broker = broker
    
    # --- [REAL HUNT] FORCE RÉEL & ACCOUNT CHECK ---
    logger.info(f"🛡️ [REAL HUNT] Mode: {os.getenv('DERIV_API_MODE', 'REAL')} | Account: {os.getenv('DERIV_ACCOUNT_ID', 'CR9310584')}")
    if os.getenv('DERIV_ACCOUNT_ID') != "CR9310584":
        logger.warning("⚠️ [SECURITY] Account ID mismatch! Forcing CR9310584 path.")
    
    # Init Interfaces (After broker is ready)


    telegram = TelegramNotifier()
    asyncio.create_task(telegram.start_polling(bot_instance, broker=broker))

    # --- TRADINGVIEW WEBHOOK & NGROK ---
    from bot.server.webhook_listener import WebhookServer
    from pyngrok import ngrok
    
    # 1. Start Local Server
    webhook_server = WebhookServer(bot_instance, port=8080)
    asyncio.create_task(webhook_server.start())
    
    # --- WEBHOOK SERVER LAUNCH ---
    def launch_webhook_server():
        logger.info("📡 Launching Webhook Server (FastAPI)...")
        # Use simple Popen
        py_path = sys.executable  # Use current venv python
        try:
            srvr = subprocess.Popen(
                [py_path, "bot/webhook_server.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            return srvr
        except Exception as e:
            logger.error(f"❌ Failed to launch Webhook Server: {e}")
            return None

    webhook_proc = launch_webhook_server()
    if webhook_proc:
        logger.info(f"✅ Webhook Server PID: {webhook_proc.pid}")

    # --- [NEW] MT5 AUTO-RECOVERY TASK ---
    async def mt5_recovery_loop():
        """Monitor status.json and keep trying to reset if disabled."""
        while True:
            try:
                # Debug Check for Keys (Internal)
                os.environ['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY', '').strip()
                
                status = bridge.get_raw_status()
                if not status.get("trading_enabled", True):
                    reason = status.get("emergency_reason", "Unknown")
                    logger.warning(f"🛡️ [AUTO-RECOVERY] MT5 Disabled: {reason}. Forcing RESET...")
                    
                    # Manually create the reset file with a unique ID to ensure processing
                    rid = int(tm.time() * 1000)
                    cmd_path = os.path.join(bridge.MT5_ROOT_PATH if hasattr(bridge, 'MT5_ROOT_PATH') else "/Users/macbookpro/Downloads/bot_project/bot/bridge/Command", f"force_reset_{rid}.json")
                    # Fallback to direct path if needed
                    direct_cmd = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/Command"
                    force_path = os.path.join(direct_cmd, f"force_reset_{rid}.json")
                    
                    try:
                         with open(force_path, 'w') as f:
                             json.dump({"action": "RESET_RISK", "id": rid}, f)
                         logger.info(f"💾 [AUTO-RECOVERY] Force Reset File Written: {rid}")
                    except: pass
                    
                    # Target root for watermark
                    root = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
                    wmark = os.path.join(root, "Sentinel_Watermarks.dat")
                    if os.path.exists(wmark):
                        try:
                            os.remove(wmark)
                            logger.info("🗑️ [AUTO-RECOVERY] Watermark File Removed.")
                        except: pass
                
                await asyncio.sleep(45) # Check every 45s
            except Exception as e:
                logger.error(f"MT5 Recovery error: {e}")
                await asyncio.sleep(30)




    asyncio.create_task(mt5_recovery_loop())





    # --- WEBHOOK PROCESSOR ---
    def process_webhook_signals():
        import glob
        import json
        import os
        
        signal_dir = "bot/signals_queue"
        files = glob.glob(f"{signal_dir}/*.json")
        for fpath in files:
            try:
                with open(fpath, "r") as f:
                    payload = json.load(f)
                
                # Check latency
                now = int(time.time() * 1000)
                latency = now - payload.get("timestamp", 0)
                if latency > 60000: # 1 min timeout
                    logger.warning(f"⚠️ Webhook Signal Expired ({latency}ms): {fpath}")
                    os.remove(fpath)
                    continue

                logger.info(f"📨 WEBHOOK SIGNAL RECEIVED: {payload}")
                
                # EXECUTE IMMEDIATELY
                # Construct 'decision' object compatible with bridge
                asset = payload.get("asset")
                side = payload.get("action").upper() # BUY/SELL
                
                # Inject into execution pipeline
                # Bridge.execute expects: {asset, side, volume, sl, tp, comment}
                # But here we need to map via broker.py typically, OR call bridge directly.
                # Calling Bridge DIRECTLY is faster for Signals.
                
                # Map 1HZ10V -> Volatility 10 (1s) Index if needed.
                # Assuming payload sends "1HZ10V" (Symbol Map key).
                
                if asset not in SYMBOL_MAP:
                     logger.error(f"❌ Unknown Webhook Asset: {asset}")
                else:
                    final_symbol = SYMBOL_MAP[asset]
                    # Logic: Use Default Volume OR Calculated?
                    # For now: Strictly 0.50 risk as requested by user
                    volume = 0.50 # Standard Unit
                    
                    sl = payload.get("sl", 0.0)
                    tp = payload.get("tp", 0.0)
                    
                    order_cmd = {
                        "asset": final_symbol,
                        "side": side,
                        "volume": volume,
                        "sl": sl,
                        "tp": tp,
                        "comment": f"WH|{payload.get('risk')}",
                        "magic": 9999
                    }
                    
                    # Execute
                    bridge.execute_trade(order_cmd)
                    
                    # Log to Discord
                    asyncio.create_task(bot_instance.log_to_discord(
                        f"🚨 **WEBHOOK SIGNAL EXECUTED**\n"
                        f"Asset: `{asset}`\n"
                        f"Side: `{side}`\n"
                        f"Risk: `{payload.get('risk')}`"
                    ))
                
                # Cleanup
                os.remove(fpath)
                
            except Exception as e:
                logger.error(f"Error processing webhook file {fpath}: {e}")
                # os.remove(fpath) # Don't delete if error to debug? Or delete to unblock?
                # Safer to delete to prevent loops, but move to 'error' folder usually.
                try: os.remove(fpath) 
                except: pass

    # --- WEBHOOK (Cloudflare Tunnel) ---
    logger.info("🚇 Starting Cloudflare Tunnel...")
    try:
        # Start cloudflared process
        # We use Popen to keep it running
        # cloudflared outputs the URL to stderr
        tunnel_process = subprocess.Popen(
            ["/usr/local/bin/cloudflared", "tunnel", "--url", "http://localhost:8080"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Parse stderr for the URL (non-blockingish)
        public_url = None
        for _ in range(20): # Wait up to 10s
            line = tunnel_process.stderr.readline()
            if "trycloudflare.com" in line:
                # Extract URL
                import re
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    public_url = match.group(0)
                    break
            tm.sleep(0.5)
            
        if public_url:
            logger.info(f"🌍 TRADINGVIEW WEBHOOK URL: {public_url}/webhook")
            logger.info(f"🔑 SECRET PASSPHRASE: {webhook_server.passphrase}")
            asyncio.create_task(bot_instance.log_to_discord(
                f"🔌 **Cloudflare Webhook Active**\nURL: `{public_url}/webhook`\nPassphrase: `{webhook_server.passphrase}`"
            ))
        else:
            logger.error("❌ Cloudflare Tunnel URL not found in logs.")
            
    except Exception as e:
        logger.error(f"❌ Cloudflare Tunnel Failed: {e}")

    
    # Phase 1: Neuro-Symbolic Components
    data_collector = DataCollector()
    regime_classifier = RegimeClassifier() # [PHASE 2] GATEKEEPER
    execution_agent = SmartExecutionAgent() # [PHASE 3] SNIPER
    market_structure_agent = MarketStructureAgent()
    
    # Phase 3: AI Oracle
    # TEMPORARILY DISABLED: Models trained on R_100/R_75 but bot trades 1HZ10V/1HZ100V
    predictor = QuantPredictor() # [INSTITUTIONAL] Oracle Active
    
    # Phase 4: Quantum Filters (Kalman)
    quantum_filters = {asset: QuantumFilter() for asset in ASSETS}
    logger.info("⚛️ Quantum Modules (Kalman) Initialized.")

    strategies = [RSIStrategy(), TrendFollowingStrategy()]

    logger.info("Connecting to Deriv API...")
    logger.info("Connecting to Deriv API...")
    
    # --- PROTOCOLE VIGILANCE ELITE (Hourly Stats) ---
    import datetime
    hourly_signals = [] # List of scores
    last_logged_hour = datetime.datetime.now().hour
    
    # --- PERIODIC REPORT (2min) ---
    import time
    last_periodic_report = time.time()
    
    retry_count = 0
    while retry_count < 3:
        # 0. Check Webhook Signals (High Priority)
        process_webhook_signals()

        # Check Periodic Report (Every 120s)
        if time.time() - last_periodic_report > 120:
            try:
                # 1. Get Live Positions & MT5 Balance
                raw_status = bridge.get_raw_status()
                active_positions = raw_status.get("positions", [])
                mt5_bal = raw_status.get("balance")
                
                # 2. Get Live Balance
                try:
                    bal_data = await client.get_balance()
                    curr_balance = float(bal_data['balance']) if bal_data else previous_balance
                except:
                    curr_balance = previous_balance
                
                # 3. Send Report
                await bot_instance.send_periodic_report(active_positions, curr_balance, mt5_balance=mt5_bal)
                last_periodic_report = time.time()
                logger.info("📡 Startup Periodic Report Sent.")
            except Exception as e:
                logger.error(f"Failed periodic report: {e}")

        try:
            await client.connect()
            logger.info("✅ Connected to Deriv (Data Source).")
            break
        except Exception as e:
            retry_count += 1
            logger.warning(f"⚠️ Deriv connection attempt {retry_count}/3 failed. Continuing for AvaTrade...")
            if retry_count >= 3: break
            await asyncio.sleep(2)

    try:
        initial_balance_data = await client.get_balance()
        previous_balance = float(initial_balance_data['balance']) if initial_balance_data else 0.0
        logger.info(f"Initial Balance: {previous_balance} USD")
    except Exception:
        previous_balance = 100.0 # Default demo balance if Deriv is disconnected
        logger.warning(f"⚠️ Deriv Disconnected. Using default internal balance: ${previous_balance}")

    async def scan_asset(asset):
        nonlocal previous_balance
        try:
            # --- [PRIORITY] REAL MT5 BALANCE FETCH ---
            raw_status = bridge.get_raw_status()
            mt5_bal = raw_status.get("balance")
            if mt5_bal and mt5_bal > 0:
                if previous_balance != mt5_bal:
                    logger.info(f"💎 [CAPITAL SYNC] Using MT5 Real Balance: ${mt5_bal:.2f}")
                previous_balance = float(mt5_bal)
            
            # --- FETCH CANDLES ---
            candles = await fetch_candles(client, asset, 60, 100)
            if not candles: return

            
            # 1. Data Collection (Foundation for LSTM)
            data_collector.save_candles(asset, candles)

            # [PHASE 2] REGIME DETECTION
            regime_info = regime_classifier.detect_regime(candles)
            regime = regime_info["regime"]
            logger.info(f"🧬 [REGIME] {asset}: {regime} ({regime_info['reason']})")
            
            
            rsi = calculate_rsi(candles)
            ema20 = calculate_ema(candles, 20)
            current_price = float(candles[-1]['close'])
            atr = calculate_atr(candles, 14) or 0.0
            
            indicators = {
                "rsi": rsi, "ema20": ema20, "atr": atr,
                "vol_of_vol": 0.25, "adx": 25.0, "atr_percentile": 50,
                "spread": 0.5, "tick_rate": 100
            }
            
            # --- PHASE 3: ORACLE PREDICTION ---
            ai_price_pred = predictor.predict(asset, candles) if predictor else None
            ai_diff = (ai_price_pred - current_price) if ai_price_pred else 0
            ai_direction = "BUY" if ai_diff > 0 else "SELL"
            ai_direction_str = f"{ai_direction} ({ai_diff:+.4f} pts)" if ai_price_pred else "N/A"
            ai_perf = 0.85 # Assumed baseline for new model
            logger.info(f"🔮 AI Oracle ({asset}): {ai_direction_str}")
            
            # --- PHASE 4: QUANTUM UPDATE ---
            q_price, q_velocity = 0.0, 0.0
            q_gap = 0.0
            if asset in quantum_filters:
                q_price, q_velocity = quantum_filters[asset].update(current_price)
                q_gap = current_price - q_price
                logger.info(f"⚛️ [QUANTUM] {asset} | Real: {current_price} | True: {q_price:.2f} | Vel: {q_velocity:.4f} | Gap: {q_gap:.2f}")
            # -------------------------------

            regime = await manager.update_market_stats(asset, candles, indicators, balance=previous_balance)
            logger.info(f"[{asset}] Regime: {regime} | RSI: {rsi:.2f}")

            context = {
                "asset": asset, "price": current_price, 
                "indicators": {"rsi": rsi, "ema20": ema20}, 
                "balance": previous_balance, "atr": atr
            }
            
            for strategy in strategies:
                signal = strategy.decide(context)
                if not signal: continue
                
            # --- PHASE AI: MARKET STRUCTURE ANALYSIS (GROQ) ---
            # Independent of strategies to feed the Hybrid Scalper continuously
            ai_analysis = {}
            try:
                logger.info(f"🧠 Asking Market Structure AI about {asset}...")
                ai_input = {
                    "asset": asset, 
                    "candles": candles,
                    "current_price": current_price,
                    "rsi": rsi if rsi else 0.0,
                    "oracle": {
                         "prediction": ai_price_pred,
                         "direction": ai_direction if ai_price_pred else "N/A",
                         "perf": ai_perf if ai_price_pred else 0.0
                    },
                    "quantum": {
                        "true_price": q_price,
                        "velocity": q_velocity,
                        "gap": q_gap
                    }
                }
                
                # Run AI logic in thread
                ai_analysis = await asyncio.to_thread(market_structure_agent.analyze, ai_input)
                logger.info(f"🧠 AI says: {ai_analysis.get('signal')} | {ai_analysis.get('reason')}")
                
                # --- MARKET INTELLIGENCE (OHLC.Dev) ---
                try:
                    mi_analysis = await market_mind.get_symbol_analysis(asset)
                    if mi_analysis.get('valid'):
                         logger.info(f"🧠 [MI] {asset}: {mi_analysis.get('trend')} | {mi_analysis.get('change_percent')}%")
                         # Enhance AI Reason with Real Market Data
                         ai_analysis['reason'] += f" | Trend: {mi_analysis.get('trend')}"
                except Exception as mi_err:
                     logger.warning(f"MI Check Failed: {mi_err}")

                # --- [HYBRID SCALPER] BROADCAST AI BIAS ---
                if bridge:
                     bridge.write_ai_bias(
                         signal=ai_analysis.get("signal", "WAIT"),
                         trend=ai_analysis.get("trend", "RANGING"),
                         reason=ai_analysis.get("reason", "N/A")
                     )
                     logger.info(f"📡 AI Bias Broadcasted to Bridge for {asset}")
            except Exception as e:
                logger.error(f"AI Analysis Failed: {e}")

            for strategy in strategies:
                signal = strategy.decide(context)
                if not signal: continue
                
                # Attach AI analysis to signal for Execution logic
                signal["ai_confirmation"] = ai_analysis

                trades = load_trades()
                stats = {"global_drawdown": 0.0, "losing_streak": 0} 
                
                if ENABLE_GOVERNANCE:
                    approved, reason = await manager.validate_signal(signal, trades, stats, context)
                else:
                    logger.info(f"🛡️ [GOVERNANCE] BYPASS ACTIVE. Trade Approved automatically (Signal: {signal['side']}).")
                    approved, reason = True, "Governance Disabled (Manual Override)"
                
                if not approved: continue
                
                # Call Risk Manager BEFORE creating final signal
                sl_dist = (atr * 2.0) if atr else 0.0
                
                # 1. Dynamic Sizing
                safe_stake = risk_manager.calculate_lot_size(previous_balance, sl_dist, asset)
                
                # 2. Neuro-Grid Plan (Visual only for now, execution logic to follow)
                grid_lvl = risk_manager.get_safe_grid_levels(current_price, signal['side'], atr)
                
                # Update Signal with Safety Data
                signal['amount'] = safe_stake
                signal['current_price'] = current_price # REQUIRED FOR HARD SL BRIDGE
                signal['risk_plan'] = {
                    "sl_dist": sl_dist,
                    "grid_levels": grid_lvl
                }

                logger.info(f"🚨 INSTITUTIONAL SIGNAL Approved: {signal}")
                logger.info(f"🕸️ [SAFE GRID] Plan: {len(grid_lvl)} layers prepared.")
                
                if is_limit_reached():
                    log_event("RISK", asset, {"equity": previous_balance, "reason": "Daily limit reached"})
                    continue
                
                # --- STRICT FILTERING (Real Training Mode) ---
                # 1. Quality Score (The "Beauty" - 0-100)
                base_score = calculate_probability(rsi if rsi else 50, signal['side'])
                
                # AI BOOSTER: ENABLED
                ai_bonus = (signal.get('ml_confidence', 0.5) - 0.5) * 40 # Up to +20 penalty/reward
                logger.info(f"🧠 AI Bonus logic active: {ai_bonus:+.1f}")
                
                final_score = base_score  # Pure technical score
                signal['quality_score'] = final_score
                
                # 2. Probability (The "Stats")
                ai_conf = signal.get('ml_confidence', 0.0) 
                
                # --- STATS CAPTURE ---
                if "hourly_signals" in locals() or "hourly_signals" in globals():
                     hourly_signals.append(final_score)
                else:
                     # Fallback if scope issue (should be captured by closure if defined in main)
                     # But since scan_asset is inner function, need ensures scope
                     pass
                     
                # FILTER LOGIC
                # --- DEMO RECOVERY MODE (Increased Volume) ---
                # LOWERED THRESHOLDS: AI disabled, need more signal volume for testing
                # Score 60 = "Acceptable Setup" (lowered from 75)
                # Conf 0.0 = AI disabled (was 0.60)
                # MIN_QUALITY_SCORE = 50  # REMOVED: Using global MIN_QUALITY_SCORE
                # MIN_AI_CONFIDENCE = 0.40  # REMOVED: Using global MIN_AI_CONFIDENCE
                
                # Check metrics
                score = final_score
                ai_conf = signal.get('ml_confidence', 0.0)
                
                if (score < MIN_QUALITY_SCORE or ai_conf < MIN_AI_CONFIDENCE) and (not is_force_enabled()):
                     logger.info(f"🛡️ [FILTER] Signal rejected: {asset} | Score: {score}/{MIN_QUALITY_SCORE} | Conf: {ai_conf:.2f}/{MIN_AI_CONFIDENCE}")
                     continue
                elif is_force_enabled():
                     logger.warning("⚠️ [FORCE] Signal Forced by Commander Override!")
                     signal['quality_score'] = 99 # Fake high score for display

                # --- 2.5 GOVERNANCE CHECK (Circuit Breaker) ---

                     
                # --- 2.5 BRIDGE ROUTING ---
                # Determine which terminal to use
                target_bridge = ava_bridge if asset in ["EURUSD", "GOLD", "NVDA", "TSLA"] else deriv_bridge
                
                raw_status = target_bridge.get_raw_status()
                current_balance = raw_status.get("balance")
                if current_balance:
                    governor.update(float(current_balance))
                
                if not governor.can_trade():
                    logger.warning(f"🛡️ GOVERNANCE BLOCK: {governor.get_status()}")
                    await asyncio.sleep(60) # Wait 1 min
                    continue
                
                # --- 2.5.1 SINGLE SHOT MODE (No Stacking) ---
                open_pos = raw_status.get("positions", [])
                if len(open_pos) >= 1:
                    logger.info(f"🔒 SINGLE SHOT MODE: 1 Trade Active ({open_pos[0].get('symbol')}). Waiting for exit.")
                    await asyncio.sleep(5) 
                    continue
                
                # --- 2.6 ADX FILTER (No Sleeping Markets) ---
                adx_val = calculate_adx(candles)
                if adx_val < 15:
                    logger.info(f"💤 MARKET SLEEPING: ADX {adx_val:.2f} < 15. Skipping {asset}.")
                    continue # SKIP THIS ASSET

                # --- 3. ANTI-SLEEP FILTER (Volatility Check) ---
                # Ensure market is active (using recent candle range as proxy for volatility)
                # We need Candles. They are in 'candles' variable from line 194.
                # Calculate average range of last 5 candles.
                if candles:
                    recent_ranges = [abs(c['high'] - c['low']) for c in candles[-5:]]
                    avg_range = sum(recent_ranges) / len(recent_ranges) if recent_ranges else 0
                    MIN_RANGE = 0.05 # Minimum points movement required
                    
                    if avg_range < MIN_RANGE:
                        logger.info(f"😴 [ANTI-SLEEP] Market Sleeping for {asset} (Range: {avg_range:.3f} < {MIN_RANGE}). Skip.")
                        continue
                
                # --- 4. FIXED STAKING MODE (USER DIRECTIVE: Strictly $0.50) ---
                # "Pas de trade à 1usd" - Enforcing fixed 0.50.
                dynamic_stake = 0.50
                logger.critical(f"🛡️ [SAFETY] FORCED STAKE: {dynamic_stake} USD (Strict Protection)")

                signal['amount'] = dynamic_stake

                # --- 5. DEATH LINE CHECK ($1.00) ---
                if previous_balance < 1.00:
                    logger.critical("💀 [SURVIVAL] Balance < $1.00. Preservation Mode. SHUTTING DOWN.")
                    break # Break the loop to stop trading


                # Enhance description with AI Insights
                ai_reason = ai_analysis.get('reason', 'N/A')
                ai_trend = ai_analysis.get('trend', 'N/A')
                
                market_details = [
                    f"Regime: {regime}",
                    f"AI Trend: {ai_trend}",
                    f"🔮 Oracle: {ai_direction_str}",
                    f"AI Insight: {ai_reason[:100]}..." # Truncate for display
                ]
                
                data = {
                    "asset": asset, "stake_advice": f"${dynamic_stake}",
                    "probability": f"{ai_conf*100:.1f}%", # Display AI Conf as Proba
                    "market_details": market_details,
                    "score": score, # Display Quality as Score
                    "balance": previous_balance, "duration": "1m"
                }

                # --- 🚀 PROJECT 100 (WEEKLY CHALLENGE) ---
                # Goal: $2.60 -> $100. Strategy: Strict Compounding.
                
                daily_trades = get_trade_count()
                MAX_PROJECT_TRADES = 15  # "15 munitions" as per user plan
                
                # DIRECTIVE: AUTO MODE (USER REQUEST)
                # "Project 100" Signals sent for Execution.
                AUTO_TRADING_PAUSED = False 
                
                if daily_trades >= MAX_PROJECT_TRADES:
                    logger.info(f"💤 [PROJECT 100] Daily Limit ({MAX_PROJECT_TRADES}) Reached. Greed Control Active.")
                    # Only log once per session ideally, but for now simple check
                    continue

                if not AUTO_TRADING_PAUSED:
                    # --- V3.0 SAFETY GATE ---
                    
                    # 1. PnL Check
                    # 1. PnL Check
                    real_pnl = get_real_pnl_from_sentinel()
                    if real_pnl <= governor.max_loss: # Dynamic Check
                        logger.critical(f"🛑 [KILL SWITCH] Daily Loss Limit Exceeded (${real_pnl:.2f} <= ${governor.max_loss}). HALTING.")
                        AUTO_TRADING_PAUSED = True
                        break

                    # [PHASE 2] REGIME FILTER
                    # If Chaos -> BLOCK EVERYTHING
                    if regime == "CRASH_CHAOS":
                        logger.warning(f"🛑 [REGIME BLOCK] Market is CHAOS ({regime_info['reason']}). Staying cash.")
                        continue

                    # 2. Volatility Check
                    candles_1m = await fetch_candles(client, asset, 60, 20)
                    safety = SafetyController()
                    vol_ok, vol_msg = safety.check_volatility(candles_1m)
                    
                    if not vol_ok:
                        logger.warning(f"⛈️ [VOLATILITY FILTER] Skipped: {vol_msg}")
                        continue
                        
                    # 3. Momentum Confirmation
                    is_valid_momentum = confirm_momentum(candles_1m, signal["side"])
                    if not is_valid_momentum:
                         logger.warning(f"📉 [MOMENTUM FILTER] Skipped: RSI diverges from {signal['side']}")
                         continue
                    
                    # --- EXECUTIO (PHASE 3: SMART LIMITS) ---
                    logger.info(f"DEBUG: AUTO_TRADING_PAUSED = {AUTO_TRADING_PAUSED}")
                    
                    # 4. Generate Signal ID (Brain Identity)
                    signal["id"] = generate_signal_id(asset, time.time(), current_price)
                    
                    # Optimize Entry (Limit vs Market)
                    # Use fixed spread assumption or fetch real spread if available (indicators['spread'])
                    spread_val = indicators.get('spread', 0.5) 
                    current_price_exec = current_price
                    
                    exec_plan = execution_agent.optimize_entry(
                        symbol=asset, 
                        side=signal["side"], 
                        current_price=current_price_exec, 
                        spread=spread_val,
                        urgency="NORMAL" # Default to Passive
                    )
                    
                    # Update Signal with Smart Execution Params
                    signal["type"] = exec_plan["type"] # BUY_LIMIT / SELL_LIMIT
                    signal["price"] = exec_plan["price"]
                    signal["is_limit"] = "LIMIT" in exec_plan["type"]
                    
                    logger.info(f"🚀 [PROJECT 100] Execution Plan: {exec_plan['type']} @ {exec_plan['price']:.2f} ({exec_plan['reason']})")
                    
                    # --- PARALLEL DUAL-CHANNEL EXECUTION ---
                    execution_tasks = []
                    if asset in ["1HZ10V", "1HZ100V"]:
                        logger.info(f"🚀 [CHANNEL] Executing VANILLA API for {asset} (Stake: {signal['amount']})")
                        # bridge=target_bridge execution REMOVED to avoid Multipliers/CFD duplicates
                        execution_tasks.append(broker.execute(signal, channel="API"))
                    else:
                        # Single channel for AvaTrade
                        execution_tasks.append(broker.execute(signal, bridge=target_bridge))

                    execution_responses = await asyncio.gather(*execution_tasks)
                    
                    success_count = sum(1 for res in execution_responses if res.get("status") in ["FILLED", "DRY_RUN"])
                    
                    if success_count > 0:
                        data["amount"] = signal["amount"]
                        data["stake_advice"] = f"⚡ AUTO ({exec_plan['type']})"
                        # Consolidated Notification (One message for both channels)
                        await bot_instance.log_to_discord(f"🚀 **Signal {asset} Exécuté** ({success_count} canal/aux)")
                        await telegram.send_message(f"🚀 Signal {asset} Exécuté ({success_count} canal/aux)")
                        break
                    else:
                        logger.error(f"Project 100 Exec Failed: {res.get('error')}")
                else:
                    # --- MANUAL MODE (HUMAN VALIDATION) ---
                    logger.info(f"🔔 [MANUAL] Signal detected. Waiting for Discord/Telegram Validation.")
                    data["stake_advice"] = f"✋ MANUAL VALIDATION CLIQUEZ (${signal['amount']})"
                    # Send Interactive Embeds (WITH BUTTONS)
                    await bot_instance.send_interactive_signal(data, broker, signal)
                    await telegram.send_signal(data, signal)
                
                # --- END PROJECT 100 ---
            
            # --- UNIVERSAL LOGGING (Even if NO SIGNAL) ---
            # We log every tick analyzed
            decision = "WAIT"
            reasoning = "Market in range or weak signal."
            
            # If we had a signal and passed filters (meaning we executed or tried to)
            if 'signal' in locals() and signal:
                decision = signal.get("side", "WAIT")

                if "ai_confirmation" in signal:
                    reasoning = signal["ai_confirmation"].get("reason", reasoning)
            
            # Sanitize "No trade" to "WAIT"
            if "no trade" in str(decision).lower():
                decision = "WAIT"

            # --- PHASE 0: INSTRUMENTATION (Full Logging) ---
            # We log the decision (EXECUTE or WAIT) into the 'signals' table
            
            log_entry = {
                "id": generate_signal_id(asset, time.time(), current_price), # Ensure ID exists
                "timestamp": time.time(),
                "asset": asset,
                "rsi": rsi if rsi else 0,
                "atr": atr if atr else 0,
                "score": 0, # Placeholder
                "regime": regime if 'regime' in locals() else "UNKNOWN",
                "side": signal.get("side", "NONE") if signal else "NONE",
                "decision": decision,
                "reasoning": reasoning,
                "strategy": "Project100"
            }
            
            # Add raw signal data if exists
            if signal:
                log_entry.update(signal)
            
            data_collector.log_signal(log_entry)


        except Exception as e:
            logger.error(f"Error on {asset}: {e}")

    limit_notified = False
    
    # Throttle State
    import time
    last_scan_time = 0

    while True:
        await check_session_timeout()
        if not await client.ensure_connected():
            await asyncio.sleep(5)
            continue
            
        # --- HOURLY FLUSH ---
        current_hour_chk = datetime.datetime.now().hour
        if current_hour_chk != last_logged_hour:
             if hourly_signals:
                 health_data = {
                     "hour": last_logged_hour,
                     "timestamp": time.time(),
                     "signal_count": len(hourly_signals),
                     "max_score": max(hourly_signals),
                     "avg_score": round(sum(hourly_signals) / len(hourly_signals), 2),
                     "asset": ASSETS[0] if ASSETS else "R_10"
                 }
                 data_collector.log_market_health(health_data)
                 logger.info(f"🏥 [MARKET HEALTH] Hour {last_logged_hour}: {len(hourly_signals)} signals, Avg: {health_data['avg_score']}, Max: {health_data['max_score']}")
             else:
                 logger.info(f"🏥 [MARKET HEALTH] Hour {last_logged_hour}: No signals observed.")
             
             # Reset
             hourly_signals = []
             last_logged_hour = current_hour_chk

        current_daily = get_trade_count()
        max_daily = get_max_trades()
        if current_daily >= max_daily and not limit_notified:
            await bot_instance.send_limit_notification(current_daily, max_daily)
            limit_notified = True
            from bot.discord_interface.commands import professor_command
            report = professor_command()
            channel = bot_instance.get_channel(bot_instance.channel_id)
            if report and channel:
                if len(report) > 2000:
                    for i in range(0, len(report), 2000): await channel.send(report[i:i+2000])
                else: await channel.send(report)

        # --- ACTIVE TRADES MONITORING (Fast Loop - 1s) ---
        try:
            from bot.state.active_trades import get_active_trades, remove_active_trade, save_state
            
            active_trades = get_active_trades()
            if active_trades:
                # logger.info(f"🔎 Monitoring {len(active_trades)} active trades...")
                pass # Sient log to avoid spam
            
            # Prepare Asset PnL Map for Group Exit
            asset_pnl_map = {} # {asset: {'pnl': 0.0, 'ids': []}}

            for trade in active_trades:
                if not isinstance(trade, dict):
                    continue

                trade_id = trade.get("id")
                asset = trade.get("asset", "UNKNOWN")
                
                # Init Map
                if asset not in asset_pnl_map: asset_pnl_map[asset] = {'pnl': 0.0, 'ids': []}
                asset_pnl_map[asset]['ids'].append(trade_id)
                
                # --- ACTIVE GRID MONITORING ---
                grid_plan = trade.get("grid_plan", [])
                # Only check grid if trade is RUNNING (not sold)
                # We need current price. We can get it from candles or ticker stream.
                # Since this is a fast loop, fetching candles for every trade every 1s is heavy.
                # PROPOSAL: We use the last known price from 'scan_asset' loop if available, 
                # or fetch a tick snapshot here if needed. 
                # For now, let's fetch a TICK snapshot for precision (Grid needs precision).
                
                status_data = await client.get_contract_status(trade_id)
                current_spot = float(status_data.get("current_spot", 0.0)) if status_data else 0.0
                current_profit = float(status_data.get("profit", 0.0)) if status_data else 0.0
                asset_pnl_map[asset]['pnl'] += current_profit
                
                if current_spot > 0 and grid_plan:
                    # Check Grid Levels
                    # grid_plan is a LIST of dicts: [{'layer':1, 'trigger_price': X, 'executed': False, ...}]
                    # We need to iterate and check. 
                    # NOTE: grid_plan in active_trades needs to be MUTABLE to mark 'executed'.
                    
                    for level in grid_plan:
                        if not isinstance(level, dict):
                            logger.error(f"⚠️ [GRID MONITOR] Corrupted level data: {level} (Type: {type(level)})")
                            continue
                        if level.get("executed", False): continue
                        
                        trigger = level["trigger_price"]
                        # Logic depends on direction. 
                        # If BUY, we re-enter if Price <= Trigger (Dip)
                        # If SELL, we re-enter if Price >= Trigger (Pump)
                        # We need to know trade SIDE. 'trade' dict needs 'side'.
                        # Let's assume trade dict has 'side' (it should from signal). 
                        # If not, we infer from Grid Trigger vs Entry? No, explicitly easier.
                        # Assuming risk_manager generated triggers correctly per direction.
                        
                        # We lack 'side' in active_trades dict from broker.py. 
                        # We must rely on price relation: 
                        # If Trigger < Entry => It's a BUY Grid (catching dip)
                        # If Trigger > Entry => It's a SELL Grid (catching pump)
                        # Actually risk_manager.get_safe_grid_levels calculates trigger based on side.
                        
                        # Simple Proximity Check (Crossing)
                        # But wait, we need to know if we crossed it.
                        # Simplify: If we are close enough or past it.
                        
                        # Let's add 'side' to active_trades in next step to be clean.
                        # For now, assuming trigger is correct:
                        
                        # Check "Hit"
                        is_hit = False
                        if current_spot < trigger and (trigger < trade.get("entry_price", 999999)): # BUY DIP
                             is_hit = current_spot <= trigger
                        elif current_spot > trigger and (trigger > trade.get("entry_price", 0)): # SELL RALLY
                             is_hit = current_spot >= trigger
                             
                        if is_hit:
                             logger.info(f"🕸️ [GRID] Trigger Hit! Level {level['layer']} @ {current_spot} (Target {trigger})")
                             
                             # EXECUTE RE-ENTRY
                             # We use the broker to execute a new trade
                             # Logic: Multiplier * Initial Stake
                             new_stake = float(trade.get("stake", 0.35)) * level.get("size_multiplier", 1.2)
                             new_stake = round(new_stake, 2)
                             
                             grid_signal = {
                                 "asset": asset,
                                 "amount": new_stake,
                                 "side": "BUY" if trigger < trade.get("entry_price", current_spot) else "SELL", # Infer side
                                 "duration": trade.get("duration", "1m"),
                                 # recursive grid? No. prevents loops
                                 "risk_plan": {"grid_levels": []} 
                             }
                             
                             logger.info(f"🚀 [GRID EXEC] Firing Grid Layer {level['layer']}: {grid_signal['side']} {asset} ${new_stake}")
                             res = await broker.execute(grid_signal)
                             if res.get("status") == "FILLED":
                                 tid = res.get("id", "Unknown")
                                 asyncio.create_task(delayed_learning(bot_instance, tid, asset, bridge))

                             
                            # MARK EXECUTED
                             level["executed"] = True
                             # Force persist to disk to avoid double-fire on crash
                             save_state()
                
                # --- VANILLA EARLY EXIT (USER REQUEST: 0.10$ PROFIT) ---
                current_profit = float(status_data.get("profit", 0.0))
                if current_profit >= 0.10:
                    logger.info(f"🍦 [VANILLA EXIT] Profit Target Reached: ${current_profit:.2f} >= $0.10. Closing {asset}.")
                    await broker.sell(trade_id) # Close immediately
                    continue
                # ------------------------------------------------------
                
                # -------------------------------
                
                if status_data and status_data.get("is_sold"):
                    # Trade Finished
                    profit = float(status_data.get("profit", 0.0))
                    status = status_data.get("status", "sold")
                    is_win = profit > 0
                    result_str = "WIN" if is_win else "LOSS"
                    
                    logger.info(f"🏁 Trade {trade_id} finished: {result_str} ({profit}$)")

                    # Prepare Report
                    current_balance_data = await client.get_balance()
                    new_balance = float(current_balance_data['balance']) if current_balance_data else 0.0
                    
                    report_data = {
                        "pnl": profit,
                        "new_balance": new_balance,
                        "trade_id": trade_id,
                        "result": result_str,
                        "asset": trade.get("asset", "UNKNOWN"),
                        # NEW DETAILED FIELDS
                        "entry_balance": previous_balance - profit, # Approx (Balance before result)
                        "stake": trade.get("stake", 0.35),
                        "duration": trade.get("duration", "1m")
                    }
                    
                    # Notify
                    await bot_instance.send_report(report_data)
                    await telegram.notifier.send_report(report_data)
                    
                    # Log Data (Scientific Protocol)
                    metadata = trade.get("metadata", {})
                    signal_id = trade.get("signal_id") # Ensure signal_id is passed down
                    
                    log_data = {
                        "asset": trade.get("asset", "UNKNOWN"),
                        "pnl": profit,
                        "result": result_str,
                        "balance": new_balance,
                        "trade_id": trade_id,
                        "signal_id": signal_id,
                        # Science Fields
                        "human_delay": metadata.get("human_delay", 0.0),
                        "generated_at": metadata.get("generated_at", 0.0),
                        "score": metadata.get("score", 0.0),
                        "ai_conf": metadata.get("ai_confidence", 0.0)
                    }
                    data_collector.log_trade_result(log_data)
                    
                    # --- [RECOLTE] SYNC BRAIN ---
                    if signal_id:
                        outcome = 1 if is_win else 0
                        data_collector.sync_signal_outcome(signal_id, outcome)
                    
                    # Cleanup
                    remove_active_trade(trade_id)
                    previous_balance = new_balance

            
            # --- GLOBAL TP / GROUP EXIT CHECK ---
            # Exit entire group if Net PnL > Target (e.g. $0.50 fixed or 1% of equity)
            # For micro-stakes ($0.35), we target +0.35$ (100% ROI on risk) or small scalps (+0.20$).
            # STRATEGY: HIT & RUN.
            GROUP_TP_TARGET = 0.35 
            
            for asset, data in asset_pnl_map.items():
                # Only sell if there are trades to sell (ids not empty) and profit target hit
                if data['ids'] and data['pnl'] > GROUP_TP_TARGET:
                     logger.info(f"💰 [GROUP EXIT] {asset} Net PnL: {data['pnl']:.2f}$ > {GROUP_TP_TARGET}$. Closing {len(data['ids'])} trades.")
                     for tid in data['ids']:
                         # Sell at Market
                         res = await client.sell_contract(tid, 0)
                         if "error" in res:
                             logger.error(f"Failed to sell {tid}: {res['error']}")
                         else:
                             logger.info(f"✅ Sold {tid}")
                             # Trade will be removed in next loop iteration when 'is_sold' is detected
                     
                     # NOTIFY GROUP EXIT
                     # Fetch fresh balance quickly
                     bal_res = await client.get_balance()
                     new_bal = float(bal_res['balance']) if bal_res else previous_balance
                     
                     report_data = {
                         "trade_id": "GROUP_EXIT",
                         "asset": asset,
                         "pnl": data['pnl'],
                         "count": len(data['ids']),
                         "new_balance": new_bal
                     }
                     await bot_instance.send_report(report_data)
                     await telegram.send_report(report_data)
                    
        except Exception as e:
            logger.error(f"Active Trade Monitor Error: {e}")
            
        # --- MARKET SCANNING (Throttled - 60s) ---
        if time.time() - last_scan_time >= 60:
            try:
                # --- PORTFOLIO SYNC (Mobile Support) ---
                # Check for trades closed externally (MT5 Mobile)
                try:
                    portfolio_res = await client.get_portfolio()
                    if portfolio_res and "portfolio" in portfolio_res:
                         real_ids = [c["contract_id"] for c in portfolio_res["portfolio"].get("contracts", [])]
                         from bot.state.active_trades import get_active_trades, remove_active_trade
                         local_trades = get_active_trades()
                         for t in local_trades:
                             if t["id"] not in real_ids:
                                 logger.info(f"🔄 [SYNC] Trade {t['id']} closed externally (Mobile). Removing state.")
                                 remove_active_trade(t["id"])
                except Exception as sync_err:
                    logger.error(f"Sync Error: {sync_err}")
                # ---------------------------------------

                tasks = [scan_asset(asset) for asset in ASSETS]
                await asyncio.gather(*tasks)
                last_scan_time = time.time()
            except Exception as e:
                logger.error(f"🔥 Loop failure: {e}")
        
        await asyncio.sleep(1)

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    
    # Initialize Bot Instance
    bot = TradingBot(trading_logic)

    if token:
        try:
            logger.info("🚀 Attempting to connect to Discord...")
            bot.run(token)
        except Exception as e:
            logger.error(f"⚠️ DISCORD CONNECTION FAILED: {e}")
            logger.warning("🧱 SWITCHING TO OFFLINE TRADING MODE (No Discord)")
            # Run trading logic manually without Discord loop
            try:
                asyncio.run(trading_logic(bot))
            except KeyboardInterrupt:
                safe_exit()
            except Exception as e2:
                logger.critical(f"🔥 OFFLINE MODE CRASHED: {e2}")
    else:
        logger.warning("⚠️ No Discord Token found. Running in OFFLINE MODE.")
        try:
            asyncio.run(trading_logic(bot))
        except KeyboardInterrupt:
            safe_exit()
        except Exception as e:
            logger.critical(f"🔥 OFFLINE MODE CRASHED: {e}")
