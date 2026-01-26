from bot.broker.base import BaseBroker
from bot.journal.audit import audit

class PaperBroker(BaseBroker):
    name = "PAPER"

    def execute(self, trade: dict, shadow: bool = False) -> dict:
        result = {
            "status": "EXECUTED",
            "asset": trade.get("asset"),
            "side": trade.get("side"),
            "amount": trade.get("amount"),
            "pnl": 0.0,
            "broker": self.name,
            "shadow": shadow,
        }

        audit("PAPER_EXECUTION", context=result)
        return result
