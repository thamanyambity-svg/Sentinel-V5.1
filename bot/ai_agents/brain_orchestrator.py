import logging
import asyncio
import time
import os
from bot.ai_agents.quant_trainer import QuantTrainer
from bot.ai_agents.professor_agent import ProfessorAgent

logger = logging.getLogger("BRAIN_ORCHESTRATOR")

class BrainOrchestrator:
    """
    Manages the learning lifecycle:
    1. Triggers periodic retraining of models.
    2. Analyzes performance shifts.
    3. Feeds strategic insights to JARVIS/Professor.
    """
    
    def __init__(self, interval_hours=6):
        self.trainer = QuantTrainer()
        self.professor = ProfessorAgent()
        self.interval_hours = interval_hours
        self.last_train_time = 0
        self.is_running = False

    async def start_evolution_loop(self):
        """Background loop for continuous learning"""
        if self.is_running: return
        self.is_running = True
        
        logger.info(f"🧠 Brain Orchestrator: Evolution Loop Started (Interval: {self.interval_hours}h)")
        
        while self.is_running:
            try:
                current_time = time.time()
                # Check if it's time to retrain
                if (current_time - self.last_train_time) >= (self.interval_hours * 3600):
                    await self.evolve()
                    self.last_train_time = current_time
                
                # Check every hour
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in evolution loop: {e}")
                await asyncio.sleep(600)

    async def evolve(self):
        """Perform a full learning and reporting cycle"""
        logger.info("🧪 Starting Evolution Cycle...")
        
        # 1. Retrain models
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.trainer.train)
        
        # 2. Get AI Summary from Professor
        summary = self.professor.analyze_24h_window()
        
        # 3. Log milestone
        logger.info("✅ Evolution Cycle Complete.")
        return summary

    async def get_strategic_proposal(self):
        """Manually trigger a strategic review"""
        return self.professor.analyze_24h_window()

brain_orchestrator = BrainOrchestrator()
