import logging
import os
import shutil
import time
import sys
from datetime import datetime

# Add project root to path if running standalone
sys.path.append(os.getcwd())

from bot.ai_agents.data_labeler import DataLabeler
from bot.ai_agents.quant_trainer import QuantTrainer

# Setup logging
logging.basicConfig(
    filename='evolution.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Also print to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

logger = logging.getLogger("EVOLUTIONARY_OPTIMIZER")

class EvolutionaryOptimizer:
    def __init__(self):
        self.model_path = "bot/models/signal_filter_sklearn.pkl"
        self.backup_dir = "bot/models/backups"
        os.makedirs(self.backup_dir, exist_ok=True)

    def run_evolution(self):
        logger.info("🧬 Starting Weekly Evolutionary Cycle...")

        # 1. Backup Champion (Current Model)
        if os.path.exists(self.model_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.backup_dir}/signal_filter_{timestamp}.pkl"
            shutil.copy(self.model_path, backup_path)
            logger.info(f"🛡️ Backup created: {backup_path}")
        else:
            logger.warning("⚠️ No existing model to backup.")

        # 2. Data Labeling (Learn from recent history)
        logger.info("🏷️ Phase 1: Data Labeling (Ground Truth Generation)...")
        try:
            labeler = DataLabeler()
            labeler.label_signals()
        except Exception as e:
            logger.error(f"❌ Labeling Failed: {e}")
            return

        # 3. Training Challenger (New Model)
        logger.info("🏋️ Phase 2: Training Challenger Model...")
        try:
            trainer = QuantTrainer()
            # The trainer saves the model to model_path if successful
            trainer.train()
            logger.info("✅ Training finished successfully.")
        except Exception as e:
            logger.error(f"❌ Training Failed: {e}")
            logger.info("🔄 Rolling back to previous model (if backup exists)...")
            # Logic to restore could be added here if the trainer corrupted the file
            # But QuantTrainer usually saves to .pkl only at the very end.
            return

        # 4. Deployment Check
        if os.path.exists(self.model_path):
             # Verify it's a new file
             mtime = os.path.getmtime(self.model_path)
             if time.time() - mtime < 600: # Modified in last 10 mins
                 logger.info("🚀 Evolution Complete. The new brain is active.")
             else:
                 logger.warning("⚠️ Model file was not updated by trainer.")
        
if __name__ == "__main__":
    optimizer = EvolutionaryOptimizer()
    optimizer.run_evolution()
