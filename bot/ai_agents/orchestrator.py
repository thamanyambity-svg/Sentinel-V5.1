"""
AI Orchestrator - Central Governance Coordinator
Runs all 6 agents in parallel and applies veto logic
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Tuple
from bot.ai_agents import (
    RegimeAuditor,
    RiskBehaviorAnalyst,
    ExecutionSentinel,
    VolatilityStructureAnalyst,
    SignalQualityAssessor,
    StrategyDriftMonitor
)
from bot.ai_agents.governance import UnifiedGovernanceAgent
from bot.ai_agents.ml_signal_filter import MLSignalFilter  # [ML]
from bot.ai_agents.audit_logger import log_decision, generate_signal_id

logger = logging.getLogger("AI_ORCHESTRATOR")

class AIOrchestrator:
    """
    Central AI Governance Coordinator
    
    Principles:
    - Unified Risk Engine (1 API Call to respect quotas)
    - 1 Veto = Block
    - Fail-safe defaults
    """
    
    # Latency budgets (milliseconds)
    AGENT_TIMEOUT_MS = 15000
    TOTAL_TIMEOUT_MS = 20000
    
    def __init__(self):
        # Initialize Unified Agent
        self.unified_agent = UnifiedGovernanceAgent()
        self.ml_filter = MLSignalFilter() # [ML] load model
        
        self.enabled = True
        self.latest_decision = {"approved": True, "reason": "Initializing", "timestamp": 0}
        self.latest_market_data = {}
        self.latest_account_state = {}
        self._supervision_task = None

    def start_background_loop(self):
        """Start the autonomous supervision loop"""
        if self._supervision_task and not self._supervision_task.done():
            return
        self._supervision_task = asyncio.create_task(self._supervision_loop())
        logger.info("🧠 AI Supervision Loop Started")

    async def _supervision_loop(self):
        """
        Periodically re-evaluates the last known state.
        This ensures that even if no trades happen, we know if the regime is safe.
        """
        while True:
            if self.latest_market_data and self.latest_account_state:
                try:
                    # Create a dummy signal just to test the waters
                    dummy_signal = {"type": "MONITORING", "asset": "GLOBAL", "side": "BUY"}
                    approved, reason, details = await self.evaluate_signal(
                        dummy_signal, 
                        self.latest_market_data, 
                        self.latest_account_state
                    )
                    self.latest_decision = {
                        "approved": approved,
                        "reason": reason,
                        "timestamp": time.time(),
                        "details": details
                    }
                    # Respect Free Tier Quotas (15 RPM / 1500 RPD)
                    # We run supervision every 10 minutes to save quota for real trades
                except Exception as e:
                    logger.error(f"Supervision loop error: {e}")
            
            await asyncio.sleep(600)  # 10 Minutes Eco-Mode

    def update_context(self, market_data: Dict[str, Any], account_state: Dict[str, Any]):
        """Update the context for the supervision loop"""
        self.latest_market_data = market_data
        self.latest_account_state = account_state

    def get_latest_decision(self) -> Dict[str, Any]:
        """Get the latest pre-computed decision (Zero Latency)"""
        # If decision is too old (> 60s), warn but don't block
        if time.time() - self.latest_decision.get("timestamp", 0) > 60:
             return {"approved": True, "reason": "AI Stale (Best Effort)", "details": {}}
        return self.latest_decision
    
    async def evaluate_signal(
        self,
        signal: Dict[str, Any],
        market_data: Dict[str, Any],
        account_state: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluate signal through Unified Governance Agent
        
        Args:
            signal: Trade signal to evaluate
            market_data: Current market conditions
            account_state: Account equity, DD, etc.
            
        Returns:
            (approved: bool, reason: str, full_response: dict)
        """
        start_time = time.time()
        
        if not self.enabled:
            logger.warning("AI Orchestrator disabled - rejecting signal")
            return False, "Orchestrator disabled", {}
        
        # [ML] PREDICTION STEP
        ml_score = 0.5
        try:
             # Extract metrics from signal raw data or regenerate
            rsi = float(signal.get('raw_data', {}).get('rsi', 50))
            atr = float(signal.get('raw_data', {}).get('atr', 1.0))
            score = float(signal.get('score', 0))
            regime = str(market_data.get('regime', 'UNKNOWN'))
            
            ml_score = self.ml_filter.predict_quality(rsi, atr, score, regime)
            signal['ml_confidence'] = round(ml_score, 4) # Inject into signal for Governance Agent
            logger.info(f"🧠 ML Confidence: {ml_score:.2%}")
        except Exception as e:
            logger.error(f"ML Prediction failed: {e}")

        # Prepare Unified Input
        unified_input = {
            "signal": signal,
            "market_data": market_data,
            "account_state": account_state
        }
        
        # Call Unified Agent
        try:
            decision_json = await asyncio.wait_for(
                asyncio.to_thread(self.unified_agent.analyze, unified_input),
                timeout=self.AGENT_TIMEOUT_MS / 1000.0
            )
        except asyncio.TimeoutError:
            logger.error(f"AI Orchestrator timeout ({self.AGENT_TIMEOUT_MS}ms)")
            # Fallback
            decision_json = self.unified_agent._get_fallback_response()
        
        # Parse Decision
        approved = (decision_json.get("governance_vote") == "APPROVED")
        reason = decision_json.get("reason", "No reason provided")
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"AI Governance: {decision_json.get('governance_vote')} | {reason} ({latency_ms:.1f}ms)")
        
        # Audit log
        signal_id = generate_signal_id(
            signal.get("asset", "UNKNOWN"),
            str(time.time()),
            market_data.get("price", 0.0)
        )
        
        log_decision(
            signal_id=signal_id,
            symbol=signal.get("asset", "UNKNOWN"),
            regime=market_data.get("regime", "UNKNOWN"),
            agent_votes=decision_json.get("dimensions", {}), # store dimension details
            final_decision="EXECUTE" if approved else "NO_TRADE",
            blocked_by=reason if not approved else "NONE",
            equity=account_state.get("equity", 0.0),
            dd_global=account_state.get("dd_global", 0.0)
        )
        
        return approved, reason, decision_json
