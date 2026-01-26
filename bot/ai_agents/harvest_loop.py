
import asyncio
import logging
import time
import os
from bot.ai_agents.oracle_trainer import OracleTrainer
from bot.ai_agents.quant_trainer import QuantTrainer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HARVEST_LOOP")

async def harvest_cycle():
    """
    Main harvesting logic:
    1. Update Price Oracles (MLP)
    2. Update Signal Filter (Quant)
    """
    logger.info("🌾 [HARVEST] Starting Learning Cycle...")
    
    # 1. Oracle Training
    oracle_trainer = OracleTrainer()
    assets = os.getenv("TRADING_ASSETS", "1HZ10V,1HZ100V").split(",")
    for asset in assets:
        success = oracle_trainer.train_asset(asset.strip())
        if success:
            logger.info(f"🧠 [ORACLE] {asset} model updated.")
        else:
            logger.warning(f"⚠️ [ORACLE] {asset} training skipped (Lack of data?)")
            
    # 2. Quant Training (Global filter)
    logger.info("🧪 [QUANT] Training Global Signal Filter...")
    quant_trainer = QuantTrainer()
    quant_trainer.train()
    
    logger.info("✅ [HARVEST] Learning Cycle Complete. Models are live.")

async def main():
    # Wait for bot to collect some data initially if DB is empty
    logger.info("🚜 Harvest Loop Active. Waiting 1 hour for first cycle...")
    # await asyncio.sleep(3600) 
    
    while True:
        try:
            await harvest_cycle()
            # Sleep for 24 hours
            logger.info("💤 Harvest complete. Sleeping for 24 hours...")
            await asyncio.sleep(86400)
        except Exception as e:
            logger.error(f"❌ Harvest Loop Error: {e}")
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
