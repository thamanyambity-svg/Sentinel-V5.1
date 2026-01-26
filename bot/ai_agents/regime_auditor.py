"""
Agent 1: Regime Auditor (VETO AGENT)
Validates regime detection coherence
Can override to CHAOS/TRANSITION
"""
from bot.ai_agents.base_agent import BaseAgent
from typing import Dict, Any

class RegimeAuditor(BaseAgent):
    """
    Regime Auditor - VETO AGENT
    Validates if detected regime is statistically coherent
    """
    
    PROMPT = """
You are a Market Regime Auditor.

Input data:
- ATR percentile
- ADX value
- Volatility-of-Volatility (normalized)
- Wick/Body ratio
- Current regime detected by the system

Your task:
- Verify if the detected regime is statistically coherent.
- Detect signs of instability, transition, or chaos.
- You may BLOCK trading, but you may NEVER authorize it.

Rules:
- If volatility-of-volatility is extreme → CHAOS.
- If indicators conflict strongly → TRANSITION.
- If regime is unstable → BLOCK.

Output ONLY valid JSON:

{
  "regime_vote": "CONFIRM | TRANSITION | CHAOS",
  "confidence": 0.0 to 1.0,
  "reason": "short technical justification"
}
"""
    
    def __init__(self):
        super().__init__(
            agent_name="RegimeAuditor",
            prompt_template=self.PROMPT
        )
    
    def get_expected_schema(self) -> Dict[str, Any]:
        return {
            "regime_vote": "CONFIRM",
            "confidence": 0.5,
            "reason": "default"
        }
    
    def _get_fallback_response(self) -> Dict[str, Any]:
        """On error, assume CHAOS (most conservative)"""
        return {
            "regime_vote": "CHAOS",
            "confidence": 0.0,
            "reason": "Agent error - defaulting to CHAOS for capital protection"
        }
