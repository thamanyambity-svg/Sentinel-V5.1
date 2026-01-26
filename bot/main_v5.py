import asyncio
import logging
import os
import sys
import time
from dotenv import load_dotenv

# Load Env
load_dotenv("bot/.env")

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("v5.1.log", mode='a')
    ]
)
logger = logging.getLogger("SENTINEL_V5")

# Import Core Modules
from bot.bridge.mt5_interface import MT5Bridge
from bot.ai_agents.market_intelligence import MarketIntelligence
from bot.telegram_interface.notifier import TelegramNotifier
from bot.discord_interface.discord_api_notifier import DiscordAPINotifier
from bot.journal.experience_logger import experience_logger  # V5.2 Deep Learning
from bot.ai_agents.brain_orchestrator import brain_orchestrator
from bot.saas_connector import saas_connector # V5.2 SaaS Bridge

# Configuration V5.1
FOREX_PAIRS = ["EURUSD", "GBPUSD", "USDCHF", "USDJPY", "USDCNH", "AUDUSD", "NZDUSD", "USDCAD", "USDSEK"]
GOLD = ["GOLD"]
STOCKS = ["Nvidia", "Apple"]
CRYPTO = ["BTCUSD", "ETHUSD"]
ALL_ASSETS = FOREX_PAIRS + GOLD + STOCKS + CRYPTO

FAST_SCAN_INTERVAL = 10 
SLOW_SCAN_INTERVAL = 60 

LOT_SIZES = {
    "FOREX": 0.10,
    "GOLD": 0.10,
    "STOCKS": 0.10,
    "CRYPTO": 0.01
}

# Initialize Notifiers
telegram_notifier = TelegramNotifier()
discord_notifier = DiscordAPINotifier()
brain = MarketIntelligence()

async def run_bot():
    logger.info("🚀 SENTINEL V5 (Deep Evolution): STARTING MAIN LOOP (XM GLOBAL)")
    
    # Start Brain Evolution Loop (Background)
    asyncio.create_task(brain_orchestrator.start_evolution_loop())
    
    # Start Telegram Listener (Background) for JARVIS Commands
    asyncio.create_task(telegram_notifier.start_polling(bot_instance=brain))
    
    # 1. Initialize Bridge
    mt5_path = os.getenv("MT5_FILES_PATH")
    if not mt5_path:
        logger.error("❌ MT5_FILES_PATH missing in .env")
        return

    bridge = MT5Bridge(root_path=mt5_path)
    
    # 2. Start Intelligence
    await brain.initialize()
    logger.info("🧠 Brain (Deep Learning Ready) initialized.")
    
    # 3. Notify Start
    msg = "🚀 *Sentinel V5.2 Evolution Live*\nBot démarré. Apprentissage profond activé."
    await telegram_notifier.send_message(msg)

    # Tracking for state
    known_positions = {} # ticket -> {symbol, price_open, side, volume, last_profit}
    last_stock_scan = 0

    try:
        while True:
            current_time = time.time()
            
            # A. Check and Notify Position Closures
            status = bridge.get_raw_status()
            current_positions = {p['ticket']: p for p in status.get('positions', [])}
            
            closed_tickets = set(known_positions.keys()) - set(current_positions.keys())
            for ticket in closed_tickets:
                pos = known_positions[ticket]
                final_profit = pos.get('last_profit', 0)
                logger.info(f"🚩 Position Closed: {pos['symbol']} (Ticket: {ticket}) | Profit: {final_profit}")
                
                # 1. UPDATE EXPERIENCE OUTCOME (L'IA Apprend)
                experience_logger.update_outcome(pos['symbol'], final_profit)
                
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

            # B. Determine Scan List
            do_stock_scan = (current_time - last_stock_scan) >= SLOW_SCAN_INTERVAL
            scan_list = FOREX_PAIRS + GOLD + CRYPTO
            if do_stock_scan:
                scan_list += STOCKS
                last_stock_scan = current_time
                logger.info("\n⏳ --- FULL SCAN CYCLE (Forex + Stocks) ---")
            else:
                logger.info("\n⏳ --- FAST SCAN CYCLE (Forex/Gold) ---")
            
            # C. Global Risk Check
            global_cond = await brain.analyze_market_conditions()
            risk_level = global_cond.get('risk_level', 'HIGH')
            
            if risk_level == "HIGH":
                logger.warning("⚠️ High Impact Events Detected. Skipping Trading this cycle.")
                await asyncio.sleep(FAST_SCAN_INTERVAL)
                continue
                
            # D. Asset Scan
            for asset in scan_list:
                try:
                    analysis = await brain.get_symbol_analysis(asset)
                    if not analysis.get('valid'): continue
                        
                    trend = analysis.get('trend')
                    price = analysis.get('price')
                    spread = analysis.get('spread', 0)
                    
                    signal = None
                    if trend == "STRONG_UP": signal = "BUY"
                    elif trend == "STRONG_DOWN": signal = "SELL"
                    
                    if signal:
                        # Position Check
                        already_open = any(p['symbol'] == asset for p in current_positions.values())
                        if already_open: continue

                        # Lot sizing
                        volume = LOT_SIZES["FOREX"] if asset in FOREX_PAIRS else \
                                 LOT_SIZES["GOLD"] if asset in GOLD else LOT_SIZES["STOCKS"]
                        
                        # LOG SIGNAL TO EXPERIENCE DB
                        experience_logger.log_signal(asset, signal, analysis, risk_level)
                        
                        # EXECUTE
                        logger.info(f"⚡ EXECUTING {signal} {asset}...")
                        bridge.send_order(symbol=asset, side=signal, volume=volume, sl=0.0, tp=0.0)
                        
                        trade_msg = (
                            f"🚀 *NOUVEAU TRADE EXECUTE*\n\n"
                            f"📈 *Marché*: {asset}\n"
                            f"🎯 *Action*: {signal}\n"
                            f"💰 *Volume*: {volume} lots\n"
                            f"💵 *Prix*: {price}\n"
                            f"⚡ *Spread*: {spread}"
                        )
                        await telegram_notifier.send_message(trade_msg)
                        await discord_notifier.send_message(trade_msg, title="🚀 NOUVELLE POSITION", color=0x3498db)
                        
                except Exception as e:
                    logger.error(f"Error scanning {asset}: {e}")
                    
            await asyncio.sleep(FAST_SCAN_INTERVAL)
            
    except Exception as e:
        logger.critical(f"🔥 FATAL ERROR: {e}")
    finally:
        await brain.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
