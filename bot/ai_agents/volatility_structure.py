"""
Agent 4: Volatility Structure Analyst
Classifies volatility patterns and detects dangerous transitions
"""
from bot.ai_agents.base_agent import BaseAgent
from typing import Dict, Any

class VolatilityStructureAnalyst(BaseAgent):
    """
    Volatility Structure Analyst
    Analyzes volatility shape to anticipate chaos
    """
    
    PROMPT = """
You are a Volatility Structure Analyst.

Input data:
- ATR short / medium / long
- ATR acceleration
- Volatility percentile
- Compression/expansion metrics

Your task:
- Classify the volatility structure.
- Identify dangerous transitions.

Rules:
- Compression followed by acceleration = high risk.
- Explosive volatility = block.

Output ONLY valid JSON:

{
  "vol_state": "compressed | expanding | explosive | neutral",
  "risk_bias": "reduce | neutral | block",
  "reason": "short technical explanation"
}
"""
    
    def __init__(self):
        super().__init__(
            agent_name="VolatilityStructure",
            prompt_template=self.PROMPT
        )
    
    def get_expected_schema(self) -> Dict[str, Any]:
        return {
            "vol_state": "neutral",
            "risk_bias": "neutral",
            "reason": "default"
        }
    
    def _get_fallback_response(self) -> Dict[str, Any]:
        """On error, block execution"""
        return {
            "vol_state": "explosive",
            "risk_bias": "block",
            "reason": "Agent error - blocking for safety"
        }
