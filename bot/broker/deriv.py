from bot.broker.base import BaseBroker
from bot.journal.audit import audit

class DerivBroker(BaseBroker):
    name = "DERIV_SAFE"

    def execute(self, trade: dict, shadow: bool = False) -> dict:
        asset = trade.get("asset")
        side = trade.get("side")

        if not asset or side not in ("BUY", "SELL", "CALL", "PUT"):
            result = {
                "status": "REJECTED",
                "reason": "Invalid trade",
                "broker": self.name,
                "shadow": shadow,
            }
            audit("DERIV_VALIDATION_FAILED", context=result)
            return result

        result = {
            "status": "EXECUTED",
            "asset": asset,
            "side": side,
            "amount": trade.get("amount"),
            "pnl": 0.0,
            "broker": self.name,
            "shadow": shadow,
        }

        audit("DERIV_SAFE_EXECUTION", context=result)
        return result
