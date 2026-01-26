
import logging
from typing import Dict, Tuple

logger = logging.getLogger("SMART_EXECUTION")

class SmartExecutionAgent:
    """
    Phase 3: Intelligent Execution.
    Replaces "Market Orders" with "Passive Limit Orders" to capture spread.
    
    Logic:
    - PASSIVE: Place limit inside the spread (Better Price).
    - AGGRESSIVE: If high urgency, cross the spread (Market).
    """
    
    def __init__(self):
        pass

    def optimize_entry(self, symbol: str, side: str, current_price: float, spread: float, urgency: str = "NORMAL") -> Dict:
        """
        Calculate optimal order parameters.
        Returns: { "type": "BUY_LIMIT"|"BUY", "price": float }
        """
        
        # 1. High Urgency (e.g. Breakout) -> Market Order
        if urgency == "HIGH":
            return {
                "type": "BUY" if side == "BUY" else "SELL",
                "price": 0.0, # 0.0 means Market in Sentinel
                "reason": "High Urgency (Market)"
            }
            
        # 2. Normal Urgency -> Passive Limit
        # Goal: Be the best Bid/Ask without crossing spread completely.
        # Deriv Spread is often fixed or tight. 
        # Strategy: Mid-Price or just Inside Spread.
        
        # Estimate Bid/Ask from Mid-Price and Spread
        # This is an approximation if we only have 'current_price' (Mid).
        # ideally we need real Bid/Ask. Assuming current_price is LAST.
        
        half_spread = spread / 2
        bid = current_price - half_spread
        ask = current_price + half_spread
        
        limit_price = 0.0
        order_type = ""
        
        if side == "BUY":
            # We want to buy. Low is better.
            # Market Order pays Ask.
            # Limit Order at Bid saves the spread.
            # To ensure fill, we bid slightly above best bid?
            # Strategy: Bid + 10% of spread.
            limit_price = bid + (spread * 0.1)
            order_type = "BUY_LIMIT"
        else: # SELL
            # We want to sell. High is better.
            # Market Order pays Bid.
            # Limit Order at Ask saves the spread.
            limit_price = ask - (spread * 0.1)
            order_type = "SELL_LIMIT"
            
        return {
            "type": order_type,
            "price": float(limit_price),
            "reason": f"Passive {side} (Saved ~{spread*0.9:.2f})"
        }
