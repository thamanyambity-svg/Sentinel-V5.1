"""
Agent 6: Strategy Drift Monitor
Detects silent degradation of strategy performance
"""
from bot.ai_agents.base_agent import BaseAgent
from typing import Dict, Any

class StrategyDriftMonitor(BaseAgent):
    """
    Strategy Drift Monitor
    Identifies structural degradation in strategy behavior
    """
    
    PROMPT = """
You are a Strategy Drift Monitor.

Input data:
- Rolling performance metrics
- Expected vs actual return distribution
- Drawdown evolution
- Frequency of stop losses

Your task:
- Detect deviation from expected behavior.
- Identify structural degradation.

Rules:
- Distribution shift or skew deterioration = drift.
- Increased drawdown with stable market = drift.

Output ONLY valid JSON:

{
  "drift_detected": true | false,
  "severity": "low | medium | high",
  "reason": "short technical justification"
}
"""
    
    def __init__(self):
        super().__init__(
            agent_name="StrategyDrift",
            prompt_template=self.PROMPT
        )
    
    def get_expected_schema(self) -> Dict[str, Any]:
        return {
            "drift_detected": False,
            "severity": "low",
            "reason": "default"
        }
    
    def _get_fallback_response(self) -> Dict[str, Any]:
        """On error, assume high severity drift"""
        return {
            "drift_detected": True,
            "severity": "high",
            "reason": "Agent error - assuming drift for safety"
        }
