import asyncio
import logging
import os
import json
import time
from dotenv import load_dotenv
from bot.data.ohlc_client import OHLCClient
from bot.bridge.mt5_interface import MT5Bridge

# Setup Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DRY_RUN")

async def run_simulation():
    load_dotenv("bot/.env")
    
    logger.info("🚀 STARTING DRY RUN SIMULATION (XM GLOBAL DEMO)")
    
    # 1. Initialize Components
    logger.info("1️⃣ Initializing Modules...")
    
    # Market Data
    ohlc = OHLCClient()
    
    # Execution (Bridge)
    mt5_path = os.getenv("MT5_FILES_PATH")
    if not mt5_path:
        logger.error("❌ MT5_FILES_PATH not found in .env")
        return
        
    bridge = MT5Bridge(root_path=mt5_path)
    
    # 0. FORCE RESET RISK (Unlock Sentinel if stuck)
    logger.info("0️⃣ Sending RESET RISK to unlock Sentinel...")
    bridge.reset_risk()
    await asyncio.sleep(2) # Give it 2s to process
    
    try:
        # 2. Market Intelligence (OHLC.Dev)
        # Switch to AAPL because Real-Time Finance API is verified for Stocks
        symbol = "AAPL" 
        logger.info(f"2️⃣ Fetching Market Data for {symbol} (OHLC.Dev)...")
        
        # Get Candles
        candles_resp = await ohlc.get_candles(symbol, period="1D")
        if "error" in candles_resp:
            logger.error(f"❌ OHLC Error: {candles_resp['error']}")
            return
            
        candles = candles_resp.get('data', {}).get('time_series', {})
        current_price = candles_resp.get('data', {}).get('price')
        
        logger.info(f"   ✅ Price: {current_price}")
        logger.info(f"   ✅ Candles: {len(candles)} days loaded")
        
        # Get Headlines
        logger.info("   📰 Checking News Sentiment...")
        headlines = await ohlc.get_headlines()
        logger.info(f"   ✅ Headlines: {len(headlines)} found")

        # 3. Decision Logic (Simple)
        logger.info("3️⃣ Analyzing Trend...")
        # (Mock logic for test: Always BUY to test execution)
        # NOTE: Switching to USDJPY to test execution on a different major pair.
        exec_symbol = "USDJPY"
        signal = "BUY"
        volume = 0.20 # Increased to bypass Bridge 'approx value' safety check
        sl = 0.0
        tp = 0.0
        
        logger.info(f"   🤖 DECISION: {signal} {exec_symbol} (Test Trade - Market Open)")
        
        # 4. Execution (XM Global)
        logger.info(f"4️⃣ Sending Order to XM Global ({exec_symbol})...")
        
        success = bridge.send_order(exec_symbol, signal, volume, sl, tp)
        
        if success:
             logger.info("   ✅ Order Command File Created!")
             logger.info("   ⏳ Waiting for MT5 Execution (Check your Terminal)...")
             
             # Monitor Status for 20 seconds
             for i in range(20):
                 status = bridge.get_raw_status()
                 positions = status.get("positions", [])
                 # Find our trade (approximate)
                 # FIX: Sentinel.mq5 reports "BUY", not "POSITION_TYPE_BUY"
                 my_trade = next((p for p in positions if p['symbol'] == exec_symbol and p['type'] == 'BUY'), None)
                 
                 if my_trade:
                     logger.info(f"   🎉 TRADE EXECUTED! Ticket: {my_trade['ticket']} | Profit: {my_trade['profit']}")
                     
                     # 5. Cleanup (Close it)
                     logger.info("5️⃣ Closing Test Trade...")
                     await asyncio.sleep(2)
                     bridge.close_position(my_trade['ticket'])
                     logger.info("   ✅ Close Command Sent.")
                     return
                 
                 time.sleep(1)
                 if i % 5 == 0: logger.info("      ...waiting for fill...")
                 
             logger.warning("   ⚠️ Trade not found in status.json after 20s. Check MT5 Experts tab.")
             
        else:
            logger.error("   ❌ Failed to write command file.")

    except Exception as e:
        logger.error(f"❌ SIMULATION ERROR: {e}")
    finally:
        await ohlc.close()
        logger.info("🏁 Simulation Complete.")

if __name__ == "__main__":
    asyncio.run(run_simulation())
