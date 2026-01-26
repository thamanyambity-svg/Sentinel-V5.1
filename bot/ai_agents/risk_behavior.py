"""
Agent 2: Risk Behavior Analyst
Detects dangerous loss patterns and overtrading
"""
from bot.ai_agents.base_agent import BaseAgent
from typing import Dict, Any

class RiskBehaviorAnalyst(BaseAgent):
    """
    Risk Behavior Analyst
    Identifies loss clustering and regime mismatches
    """
    
    PROMPT = """
You are a Risk Behavior Analyst.

Input data:
- Last N trades (win/loss, duration, R-multiple)
- Current regime
- Time between trades
- Drawdown metrics (session, 24h, global)

Your task:
- Identify loss clustering, overtrading, or regime mismatch.
- Do NOT evaluate performance, only risk behavior.

Rules:
- Multiple losses in same regime = elevated risk.
- Increasing trade frequency after losses = danger.
- When unsure, escalate risk.

Output ONLY valid JSON:

{
  "risk_flag": "OK | WARNING | HALT",
  "reason": "loss_cluster | overtrading | regime_mismatch | unknown"
}
"""
    
    def __init__(self):
        super().__init__(
            agent_name="RiskBehavior",
            prompt_template=self.PROMPT
        )
    
    def get_expected_schema(self) -> Dict[str, Any]:
        return {
            "risk_flag": "OK",
            "reason": "default"
        }
    
    def _get_fallback_response(self) -> Dict[str, Any]:
        """On error, halt trading"""
        return {
            "risk_flag": "HALT",
            "reason": "Agent error - halting for safety"
        }
