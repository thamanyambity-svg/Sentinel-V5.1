import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from bot.ai_agents.quant_trainer import QuantTrainer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TRAINING_DRIVER")

ASSETS = ["R_100", "R_75", "R_50"]

def main():
    logger.info("🎬 --- STARTING PHASE 2: DEEP LEARNING (MLP) ---")
    logger.info(f"🎯 Targets: {', '.join(ASSETS)}")
    
    for asset in ASSETS:
        logger.info(f"\n🧠 [1/3] Initializing Trainer for {asset}...")
        try:
            trainer = QuantTrainer(asset=asset, lookback=60)
            
            logger.info(f"🏋️‍♀️ [2/3] Training Neural Network for {asset} (this is the heavy lifting)...")
            # Using 50 iterations, typically enough for convergence on this data size with Adam
            model_path = trainer.train(epochs=50) 
            
            logger.info(f"✅ [3/3] Success! Oracle for {asset} is born.")
            
        except Exception as e:
            logger.error(f"❌ Failed to train {asset}: {e}")
            
    logger.info("\n🎉 --- PHASE 2 COMPLETE ---")
    logger.info("The AI now possesses 'market intuition' based on 150k+ data points.")

if __name__ == "__main__":
    main()
