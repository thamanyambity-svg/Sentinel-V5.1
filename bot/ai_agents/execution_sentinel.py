"""
Agent 3: Execution & Microstructure Sentinel
Prevents execution in technically dangerous conditions
"""
from bot.ai_agents.base_agent import BaseAgent
from typing import Dict, Any

class ExecutionSentinel(BaseAgent):
    """
    Execution & Microstructure Sentinel
    Monitors execution quality and market microstructure
    """
    
    PROMPT = """
You are an Execution and Microstructure Sentinel.

Input data:
- Current spread
- Tick rate
- Slippage (expected vs observed)
- WebSocket latency
- Recent execution anomalies

Your task:
- Detect abnormal execution conditions.
- Decide if execution is safe or unsafe.

Rules:
- Abnormal spread or latency = unsafe.
- Sudden tick acceleration = unsafe.
- If uncertain, block execution.

Output ONLY valid JSON:

{
  "execution_ok": true | false,
  "anomaly": "spread | latency | tick_spike | slippage | none"
}
"""
    
    def __init__(self):
        super().__init__(
            agent_name="ExecutionSentinel",
            prompt_template=self.PROMPT
        )
    
    def get_expected_schema(self) -> Dict[str, Any]:
        return {
            "execution_ok": True,
            "anomaly": "none"
        }
    
    def _get_fallback_response(self) -> Dict[str, Any]:
        """On error, block execution"""
        return {
            "execution_ok": False,
            "anomaly": "agent_error"
        }
