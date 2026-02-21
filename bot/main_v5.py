import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load Env
load_dotenv("bot/.env")

# Setup Logging (Unified)
from bot.core.logger import get_logger
logger = get_logger("SENTINEL_V5")


# Import Core Modules
from bot.bridge.mt5_interface_v2 import MT5Bridge
from bot.ai_agents.market_intelligence import MarketIntelligence
from bot.telegram_interface.notifier import TelegramNotifier
from bot.discord_interface.discord_api_notifier import DiscordAPINotifier
from bot.journal.experience_logger import experience_logger
from bot.ai_agents.learning_brain import learning_brain  # Cerveau opérationnel
from bot.ai_agents.brain_orchestrator import brain_orchestrator
from bot.saas_connector import saas_connector  # V5.2 SaaS Bridge
from bot.core.monitor import ResourceMonitor  # V5.2 Hardening
from bot.risk.risk_manager import RiskManager
from bot.state.risk.rules.engine import can_execute_trade, register_trade
from bot.state.risk.limits import reset_daily_limits
from bot.core.process_lock import acquire as lock_acquire, release as lock_release
from bot.strategy.ifvg_volatility import get_ifvg_signal

# Initialize Monitor
monitor = ResourceMonitor()

# Risk: Kill Switch drawdown max (5% par défaut)
MAX_DAILY_DD_PCT = float(os.getenv("MAX_DAILY_DD_PCT", "0.05"))
# Heartbeat: alerte si status.json non mis à jour depuis N secondes
EA_HEARTBEAT_TIMEOUT_SEC = int(os.getenv("EA_HEARTBEAT_TIMEOUT_SEC", "90"))
# Mode test: pas de stop trading daily (kill switch + limite trades/jour désactivés)
TESTING_MODE = os.getenv("TESTING_MODE", "1").strip().lower() in ("1", "true", "yes")
# Max positions simultanées par actif (agressif = 7)
MAX_POSITIONS_PER_ASSET = int(os.getenv("MAX_POSITIONS_PER_ASSET", "7"))
# Scalping précis: objectif TP plus serré (0.0003 = ~3 pips équiv.)
SCALP_TARGET_PCT = float(os.getenv("SCALP_TARGET_PCT", "0.0003"))
# SL Volatility par défaut (réfléchi, serré pour scalping)
DEFAULT_SL_PIPS_VOLATILITY = int(os.getenv("DEFAULT_SL_PIPS_VOLATILITY", "40"))

# Configuration V5.5 - Weekend Trading (Deriv Synthetics)
FOREX_PAIRS = []  # Désactivé le weekend
GOLD = []
STOCKS = []
CRYPTO = []

# DERIV SYNTHETIC INDICES (24/7 Trading)
SYNTHETIC_INDICES = [
    "Volatility 100 Index",  # Volatilité modérée, bon pour débuter
    "Volatility 75 Index",   # Volatilité moyenne
]

ALL_ASSETS = FOREX_PAIRS + GOLD + STOCKS + CRYPTO + SYNTHETIC_INDICES

FAST_SCAN_INTERVAL = 10 
SLOW_SCAN_INTERVAL = 60 

LOT_SIZES = {
    "FOREX": 0.10,
    "GOLD": 0.10,
    "STOCKS": 0.10,
    "CRYPTO": 0.01,
    "SYNTHETIC": 0.50  # Min requis pour certains indices
}

# Initialize Notifiers
telegram_notifier = TelegramNotifier()
discord_notifier = DiscordAPINotifier()
brain = MarketIntelligence()

async def run_bot():
    logger.info("🚀 SENTINEL V5 (Deep Evolution): STARTING MAIN LOOP (XM GLOBAL)")
    if TESTING_MODE:
        logger.warning("⚠️ TESTING_MODE=ON — Pas de stop trading daily (kill switch + limite trades désactivés)")
    
    if not lock_acquire():
        logger.critical("❌ Another Sentinel is running or lock failed. Exiting.")
        return

    # Start Brain Evolution Loop (Background)
    asyncio.create_task(brain_orchestrator.start_evolution_loop())
    
    # Start Telegram Listener (Background) for JARVIS Commands
    asyncio.create_task(telegram_notifier.start_polling(bot_instance=brain))
    
    # 1. Initialize Bridge
    mt5_path = os.getenv("MT5_FILES_PATH")
    if not mt5_path:
        logger.error("❌ MT5_FILES_PATH missing in .env")
        lock_release()
        return

    bridge = MT5Bridge(root_path=mt5_path)
    risk_manager = RiskManager(max_grid_layers=3, risk_per_trade=0.015, max_daily_loss=MAX_DAILY_DD_PCT)
    
    # 2. Start Intelligence
    await brain.initialize()
    logger.info("🧠 Brain (Deep Learning Ready) initialized.")
    
    # 3. Notify Start
    msg = "🚀 *Sentinel V5.2 Evolution Live*\nBot démarré. Apprentissage profond activé."
    await telegram_notifier.send_message(msg)

    # Tracking for state
    known_positions = {}  # ticket -> {symbol, price_open, side, volume, last_profit}
    last_stock_scan = 0
    balance_start_of_day = None
    last_day_utc = None

    try:
        while True:
            current_time = time.time()
            today_utc = datetime.now(timezone.utc).date()

            # A. Check and Notify Position Closures + Status
            status = bridge.get_raw_status()
            current_positions = {str(p.get('ticket', '')): p for p in status.get('positions', []) if p.get('ticket') is not None}

            # Heartbeat EA: alerte si status.json trop vieux
            status_mtime = bridge.get_status_mtime()
            if status_mtime and (current_time - status_mtime) > EA_HEARTBEAT_TIMEOUT_SEC:
                logger.critical("🫀 EA HEARTBEAT LOST: status.json not updated for %ds. Check MT5/Sentinel.", int(current_time - status_mtime))
                try:
                    await telegram_notifier.send_message("⚠️ *ALERTE*: EA Sentinel ne répond plus (heartbeat perdu). Vérifiez MT5.")
                except Exception:
                    pass

            # Balance / Kill Switch (source: status.json)
            balance = status.get("balance") or status.get("equity") or 0
            if balance_start_of_day is None and balance:
                balance_start_of_day = float(balance)
            if last_day_utc is not None and today_utc != last_day_utc:
                reset_daily_limits()
                balance_start_of_day = float(balance) if balance else balance_start_of_day
            last_day_utc = today_utc
            # Kill Switch (désactivé en TESTING_MODE pour mesurer l'efficacité)
            if not TESTING_MODE and balance and balance_start_of_day and balance_start_of_day > 0:
                ok, msg_risk = risk_manager.check_health(balance_start_of_day, float(balance))
                if not ok:
                    logger.critical("🛑 KILL SWITCH: %s", msg_risk)
                    try:
                        await telegram_notifier.send_message(f"🛑 *KILL SWITCH*\n{msg_risk}")
                    except Exception:
                        pass
                    await asyncio.sleep(FAST_SCAN_INTERVAL)
                    continue

            closed_tickets = set(known_positions.keys()) - set(current_positions.keys())
            for ticket in closed_tickets:
                pos = known_positions[ticket]
                final_profit = pos.get('last_profit', 0)
                logger.info(f"🚩 Position Closed: {pos['symbol']} (Ticket: {ticket}) | Profit: {final_profit}")
                
                # 1. UPDATE EXPERIENCE OUTCOME (L'IA Apprend)
                experience_logger.update_outcome(pos['symbol'], final_profit)
                # 1b. Risk limits: enregistrer la clôture (compteurs trades / PnL jour)
                register_trade({"pnl": final_profit})

                # 2. REPORT TO SAAS (Le SaaS se met à jour)
                try:
                    duration = int(time.time() - pos.get('open_time', time.time()))
                    saas_connector.report_trade({
                        "ticket": int(ticket),
                        "symbol": pos['symbol'],
                        "type": pos['side'],
                        "open_price": float(pos['price_open']),
                        "close_price": float(status.get('balance_update_price', pos['price_open'])), # Best effort close price
                        "profit": float(final_profit),
                        "duration": duration
                    })
                except Exception as e:
                    logger.error(f"SaaS Reporting Error: {e}")
                
                close_msg = (
                    f"🏁 *TRADE CLOTURÉ*\n"
                    f"📈 *Symbole*: {pos['symbol']}\n"
                    f"💰 *P/L*: {final_profit:+.2f}$\n"
                    f"💰 *Volume*: {pos['volume']}"
                )
                await telegram_notifier.send_message(close_msg)
                await discord_notifier.send_message(close_msg, title="🏁 CLÔTURE DE POSITION", color=0xe67e22)
                
                del known_positions[ticket]
            
            # Update known positions for next cycle
            for ticket, p in current_positions.items():
                if ticket not in known_positions:
                    known_positions[ticket] = {
                        "symbol": p['symbol'],
                        "price_open": p.get('price', 0),
                        "side": p['type'],
                        "volume": p.get('volume', 0.01),
                        "last_profit": p.get('profit', 0),
                        "open_time": time.time() # Start tracking duration
                    }
                else:
                    # Update profit but keep open_time
                    known_positions[ticket]["last_profit"] = p.get('profit', 0)

            # B. Determine Scan List (ALADDIN WEEKEND EDITION)
            do_stock_scan = (current_time - last_stock_scan) >= SLOW_SCAN_INTERVAL
            scan_list = FOREX_PAIRS + GOLD + CRYPTO + SYNTHETIC_INDICES  # Include synthetics
            if do_stock_scan:
                scan_list += STOCKS
                last_stock_scan = current_time
                logger.info("\n⏳ --- FULL SCAN CYCLE (All Assets) ---")
            else:
                logger.info("\n⏳ --- FAST SCAN CYCLE (Synthetics + Forex) ---")
            
            # C. Global Risk Check (en TESTING_MODE on ne bloque pas sur HIGH pour tester)
            global_cond = await brain.analyze_market_conditions()
            risk_level = global_cond.get('risk_level', 'HIGH')
            if risk_level == "HIGH" and not TESTING_MODE:
                logger.warning("⚠️ High Impact Events Detected. Skipping Trading this cycle.")
                await asyncio.sleep(FAST_SCAN_INTERVAL)
                continue
            if risk_level == "HIGH" and TESTING_MODE:
                logger.info("⚠️ Risk HIGH but TESTING_MODE: trading allowed this cycle.")

            # M5 bars for IFVG (Volatility 100/75)
            m5_bars = bridge.get_m5_bars()
                
            # D. Asset Scan (WITH DEBUG LOGS)
            for asset in scan_list:
                try:
                    analysis = await brain.get_symbol_analysis(asset)
                    if not analysis.get('valid'):
                        logger.warning(f"⏭️ {asset}: Skip — {analysis.get('error', 'no data')}")
                        continue

                    price = analysis.get('price')
                    change = analysis.get('change_percent', 0)
                    trend = analysis.get('trend')

                    # --- IFVG strategy for Volatility indices (M5) ---
                    use_ifvg = asset in SYNTHETIC_INDICES and asset in m5_bars and len(m5_bars.get(asset, [])) >= 20
                    signal = None
                    sl_pips = 50
                    ai_confidence = 0.75
                    strategy_name = "ALADDIN_SCALP"
                    pattern_extra = ""

                    if use_ifvg:
                        ifvg_candles = m5_bars[asset]
                        point = 0.01 if "Volatility" in asset else 0.01
                        ifvg_sig = get_ifvg_signal(asset, ifvg_candles, point=point)
                        if ifvg_sig:
                            signal = ifvg_sig["side"]
                            sl_pips = ifvg_sig.get("sl_pips", 50)
                            ai_confidence = ifvg_sig.get("confidence", 0.75)
                            strategy_name = ifvg_sig.get("strategy", "IFVG_SCALP")
                            pattern_extra = ifvg_sig.get("reason", "IFVG_M5")
                            logger.info(f"📐 IFVG {asset}: {signal} | SL {sl_pips} pips | {pattern_extra}")

                    if not signal:
                        # Fallback: trend-based (ALADDIN), seuil 0.001% ultra-bas pour tester
                        if "Volatility" in asset:
                            if change > 0.001: trend = "WEAK_UP"
                            elif change < -0.001: trend = "WEAK_DOWN"
                            # Si change=0 (premier cycle ou marché plat): micro-signal depuis dernière bougie M5
                            elif use_ifvg and abs(change) < 0.001:
                                candles = m5_bars.get(asset, [])
                                if len(candles) >= 2:
                                    last = candles[0]  # Sentinel: [0]=newest
                                    o, c = float(last.get("o", 0)), float(last.get("c", 0))
                                    if c > o + 0.01: trend, pattern_extra = "WEAK_UP", "M5_CANDLE_UP"
                                    elif c < o - 0.01: trend, pattern_extra = "WEAK_DOWN", "M5_CANDLE_DOWN"
                        if trend in ["STRONG_UP", "WEAK_UP"]: signal = "BUY"
                        elif trend in ["STRONG_DOWN", "WEAK_DOWN"]: signal = "SELL"
                        if signal:
                            if not pattern_extra: pattern_extra = f"{trend}_{risk_level}"
                            ai_confidence = 0.85 if "STRONG" in trend else 0.65

                    # LOGGING ANALYSIS
                    logger.info(f"🔍 {asset}: {price} | Trend: {trend} ({change:.3f}%)")
                    
                    if signal:
                        # Position Check (Max 7 par actif = agressif, positions intelligentes)
                        open_count = sum(1 for p in current_positions.values() if p['symbol'] == asset)
                        if open_count >= MAX_POSITIONS_PER_ASSET:
                            logger.info(f"⏸️ {asset}: Max positions reached ({open_count}/{MAX_POSITIONS_PER_ASSET})")
                            continue

                        # Risk gate: désactivé en TESTING_MODE (pas de stop daily pour tester)
                        if not TESTING_MODE:
                            allowed, reason = can_execute_trade({"asset": asset})
                            if not allowed:
                                logger.info(f"⏸️ {asset}: Risk gate — {reason}")
                                continue

                        # VOLUME CONFIGURATION (SCALPER MODE)
                        volume = 0.50 if "Volatility" in asset else 0.10

                        target_pct = SCALP_TARGET_PCT  # Scalping précis (TP serré)

                        if signal == "BUY":
                            tp_price = price * (1 + target_pct)
                        else:
                            tp_price = price * (1 - target_pct)

                        # Risk/confidence: agressif quand signal bon (>= 0.70 pour passer le filtre EA)
                        if strategy_name != "IFVG_SCALP":
                            ai_confidence = 0.85
                            if "WEAK" in trend: ai_confidence = 0.70
                            # Agressif: monter le risque quand conditions OK
                            ai_risk_multiplier = 1.2
                            if risk_level == "LOW": ai_risk_multiplier = 1.5
                            elif risk_level == "ELEVATED": ai_risk_multiplier = 0.9
                        else:
                            ai_risk_multiplier = 1.15  # IFVG un peu agressif aussi

                        # SL réfléchi: IFVG = zone-based; sinon Volatility serré (scalping), min 5
                        if strategy_name != "IFVG_SCALP":
                            if "Volatility" in asset or "Index" in asset:
                                sl_pips = DEFAULT_SL_PIPS_VOLATILITY
                            else:
                                sl_pips = int(price * 0.00025 * (100 if "JPY" in asset else 10000))
                        if sl_pips < 5:
                            sl_pips = 5

                        # --- LEARNING: log signal AVANT exécution (pour outcome tracking) ---
                        analysis_for_log = {"price": price, "change_percent": change, "trend": trend, "spread": 0}
                        learning_brain.log_signal(asset, signal, analysis_for_log, risk_level, strategy=strategy_name)

                        # Filtre ML optionnel: skip si prob win trop bas (hors TESTING_MODE pour laisser apprendre)
                        if not TESTING_MODE:
                            skip_ml, win_prob = learning_brain.should_skip_by_ml(change, trend, min_prob=0.35)
                            if skip_ml:
                                logger.info(f"⏭️ {asset}: ML skip (win_prob={win_prob:.2f} < 0.35)")
                                continue
                            # Boost confiance adaptatif
                            ai_confidence *= learning_brain.get_adaptive_confidence_boost(asset, strategy_name)

                        # EXECUTE VIA BRIDGE (IFVG or ALADDIN)
                        logger.info(f"⚡ EXEC {strategy_name} {signal} {asset} | Risk: x{ai_risk_multiplier} | Conf: {ai_confidence}")
                        
                        bridge.send_tudor_trade(
                            symbol=asset,
                            type=signal,
                            strategy=strategy_name,
                            pattern=pattern_extra or f"{trend}_{risk_level}",
                            signal_strength=ai_confidence,
                            stop_loss_pips=sl_pips,
                            ai_risk_multiplier=ai_risk_multiplier,
                            ai_confidence_score=ai_confidence
                        )

                        trade_msg = (
                            f"🧞‍♂️ *{strategy_name}*\n\n"
                            f"📈 *Marché*: {asset}\n"
                            f"🎯 *Action*: {signal}\n"
                            f"📊 *Pattern*: {pattern_extra}\n"
                            f"💵 *Prix*: {price}\n"
                        )
                        await telegram_notifier.send_message(trade_msg)
                        
                    else:
                        logger.info(f"💤 {asset}: No Signal (Range/Flat)")

                except Exception as e:
                    logger.error(f"Error scanning {asset}: {e}")
                    
            # 6. Resource Monitoring (Hardening)
            mem_usage, cpu_usage = monitor.check_resources()
            if mem_usage > 85:
                 logger.warning(f"⚠️ High Memory Usage: {mem_usage}%. Suggesting cleanup.")
                 # Future: trigger GC or restart recommendation

            await asyncio.sleep(FAST_SCAN_INTERVAL)
            
            
    except Exception as e:
        logger.critical(f"🔥 FATAL ERROR: {e}")
    finally:
        lock_release()
        await brain.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
