"""
Agent 5: Signal Quality Assessor
Scores statistical quality of signals (never judges direction)
"""
from bot.ai_agents.base_agent import BaseAgent
from typing import Dict, Any

class SignalQualityAssessor(BaseAgent):
    """
    Signal Quality Assessor
    Evaluates statistical quality of signal setup
    """
    
    PROMPT = """
You are a Signal Quality Assessor.

Input data:
- Risk/Reward ratio
- Distance to stop loss
- Signal type
- Regime context
- Recent win rate of similar signals

Your task:
- Score the statistical quality of the signal.
- Do NOT judge market direction.

Rules:
- Low R:R or bad regime alignment = low score.
- When data is insufficient, score conservatively.

Output ONLY valid JSON:

{
  "signal_score": 0 to 100,
  "confidence": "low | medium | high",
  "reason": "short explanation"
}
"""
    
    def __init__(self):
        super().__init__(
            agent_name="SignalQuality",
            prompt_template=self.PROMPT
        )
    
    def get_expected_schema(self) -> Dict[str, Any]:
        return {
            "signal_score": 75,
            "confidence": "medium",
            "reason": "default"
        }
    
    def _get_fallback_response(self) -> Dict[str, Any]:
        """On error, return low score"""
        return {
            "signal_score": 0,
            "confidence": "low",
            "reason": "Agent error - rejecting signal"
        }
