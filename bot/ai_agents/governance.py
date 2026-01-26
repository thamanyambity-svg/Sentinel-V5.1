"""
Unified Governance Agent
Consolidates all 6 risk/quality checks into a single prompt to respect API limits.
"""
from bot.ai_agents.base_agent import BaseAgent
from typing import Dict, Any

class UnifiedGovernanceAgent(BaseAgent):
    """
    Unified Governance Agent
    Performs simultaneous checks:
    1. Regime Audit
    2. Risk Behavior
    3. Execution Sentinel
    4. Volatility Structure
    5. Signal Quality
    6. Strategy Drift
    """
    
    PROMPT = """
You are the **Lead Risk Officer** for an institutional trading bot.
 You must evaluate a proposed trade signal against the current market context and account state.
 You have **VETO POWER**. If any single dimension is unsafe, you must BLOCK the trade.

### Input Data
**1. Signal:** {signal}
**2. Market Context:** {market_data}
**3. Account State:** {account_state}

### Your Mission
Evaluate these 6 dimensions simultaneously. 
**PROJECT 100 DIRECTIVE**: You are authorized to be AGGRESSIVE if the setup is high quality.
**CRITICAL EXCEPTION**: If Strategy is 'MEAN_REVERSION' (RSI) and Regime is 'RANGE_CALM' (or similar), this is a **VALID MATCH**. Do NOT Veto based on "low volatility" in this specific case. Range trading requires calm markets.

1. **Regime Audit**: Is the detected regime consistent with indicators? (Remember: Range is Good for MeanReversion).
2. **Risk Behavior**: Is the recent trading behavior safe (Drawdown, Frequency, Streaks)?
3. **Execution Sentinel**: Are conditions safe for execution (Spread, Slippage, Latency)?
4. **Volatility Structure**: Is the volatility structure stable? (Explosive is bad for MeanReversion, Good for Trend).
5. **Signal Quality**: Does the signal meet high-quality standards (Confluence, R/R)?
6. **Strategy Drift**: Is the strategy behaving as expected?

### Output Requirements
Return a SINGLE JSON object. 
- If **ANY** dimension is CRITICALLY unsafe, set `governance_vote` to "VETO".
- Only set `governance_vote` to "APPROVED" if the trade makes sense.

**JSON Schema:**
{{
  "governance_vote": "APPROVED | VETO",
  "reason": "Clear explanation of the decision (cite specific metrics)",
  "dimensions": {{
    "regime": "CONFIRM | CHAOS",
    "risk": "SAFE | HALT",
    "execution": "OK | ANOMALY",
    "volatility": "STABLE | EXPLOSIVE",
    "quality": "GOOD | POOR",
    "drift": "NORMAL | HIGH"
  }},
  "modifications": {{
    "size_factor": 1.0  // Reduce size (e.g. 0.5) if risk is elevated but acceptable. Default 1.0
  }}
}}
"""
    
    def __init__(self):
        super().__init__(
            agent_name="UnifiedGovernance",
            prompt_template=self.PROMPT
        )
    
    def get_expected_schema(self) -> Dict[str, Any]:
        return {
            "governance_vote": "APPROVED",
            "reason": "Default safety check",
            "dimensions": {
                "regime": "CONFIRM",
                "risk": "SAFE",
                "execution": "OK",
                "volatility": "STABLE",
                "quality": "GOOD",
                "drift": "NORMAL"
            },
            "modifications": {
                "size_factor": 1.0
            }
        }
    
    def _build_prompt(self, data: Dict[str, Any]) -> str:
        # Override to format the specific prompt structure
        return self.PROMPT.format(
            signal=data.get("signal", {}),
            market_data=data.get("market_data", {}),
            account_state=data.get("account_state", {}),
            regime=data.get("market_data", {}).get("regime", "UNKNOWN")
        )

    def _get_fallback_response(self) -> Dict[str, Any]:
        """
        On error/timeout, FAIL OPEN (Allow Strategy to trade technically).
        We do not want API outages to stop the bot.
        """
        return {
            "governance_vote": "APPROVED",
            "reason": "AI Error/Timeout - Using Technical Fallback",
            "dimensions": {
                "regime": "CONFIRM", # Assume strategy is right
                "risk": "SAFE",
                "execution": "OK",
                "volatility": "STABLE",
                "quality": "GOOD",
                "drift": "NORMAL"
            },
            "modifications": { "size_factor": 1.0 }
        }
