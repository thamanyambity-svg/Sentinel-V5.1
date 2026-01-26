"""
DerivBroker – shadow-first + dry-run API (Go 4.7)
"""

from bot.broker.base import BaseBroker
from bot.broker.deriv.mapper import map_trade
from bot.broker.deriv.validator import validate_response
from bot.broker.deriv.client import DerivClient
from bot.broker.deriv.config import DERIV_API_MODE

class DerivBroker(BaseBroker):
    name = "DERIV"

    def execute(self, trade: dict, shadow: bool = False) -> dict:
        payload = map_trade(trade)

        # ===== SHADOW =====
        if shadow:
            response = {
                "status": "EXECUTED",
                "payload": payload,
                "pnl": 0.0,
                "broker": "DERIV_SAFE",
                "shadow": True,
            }
            return response

        # ===== DRY-RUN API =====
        if DERIV_API_MODE == "DRY_RUN":
            client = DerivClient()
            client.connect()
            api_result = client.send_order(payload)

            if not validate_response(api_result):
                return {"status": "ERROR", "reason": "Invalid API response"}

            return {
                "status": "DRY_RUN",
                "api": api_result,
            }

        return {
            "status": "BLOCKED",
            "reason": "DERIV_API_NOT_ENABLED",
        }
