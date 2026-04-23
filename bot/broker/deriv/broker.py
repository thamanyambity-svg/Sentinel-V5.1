"""
DerivBroker – shadow-first + dry-run API (Go 4.7)
"""

from bot.broker.base import BaseBroker
from bot.broker.deriv.mapper import map_trade
from bot.broker.deriv.validator import validate_response
from bot.broker.deriv.client import DerivClient
from bot.broker.deriv.config import DERIV_API_MODE
from bot.state.active_trades import add_active_trade
from bot.bridge.mt5_interface_v2 import MT5Bridge
import os
import time
import logging

logger = logging.getLogger("DerivBroker")

class DerivBroker(BaseBroker):
    name = "DERIV"

    def __init__(self):
        self.bridge_enabled = os.getenv("MT5_BRIDGE_ENABLED", "false").lower() == "true"
        if self.bridge_enabled:
            self.bridge = MT5Bridge()
            logger.info("🌉 [DERIV BROKER] MT5 Bridge via Files ENABLED")
        else:
            self.bridge = None
            logger.info("🌐 [DERIV BROKER] MT5 Bridge DISABLED")

    async def execute(self, trade: dict, shadow: bool = False, channel: str = None, bridge=None) -> dict:
        """
        Execute trade. 
        channel: "API" for Multipliers, "BRIDGE" for MT5/CFD. 
                 None = Auto (Bridge if enabled, else API).
        """
        payload = map_trade(trade)

        # ===== SHADOW =====
        if shadow:
            return {
                "status": "EXECUTED",
                "payload": payload,
                "pnl": 0.0,
                "broker": "DERIV_SAFE",
                "shadow": True,
            }

        # ===== BRIDGE SELECTION =====
        target_bridge = bridge or self.bridge
        
        use_bridge = False
        if channel == "BRIDGE":
            use_bridge = True
        elif channel == "API":
            use_bridge = False
        elif self.bridge_enabled and target_bridge:
            use_bridge = True

        if use_bridge and target_bridge:
            # Send via Bridge
            symbol = trade.get("asset")
            action = trade.get("side", "BUY")
            if action in ("CALL", "UP"): action = "BUY"
            if action in ("PUT", "DOWN"): action = "SELL"
            
            # SL/TP from trade object or defaults
            sl_price = trade.get("sl", 0.0)
            tp_price = trade.get("tp", 0.0)
            
            logger.info(f"📤 Sending via Bridge: {action} {symbol} Vol: 0.50 SL: {sl_price}")
            
            sent = target_bridge.send_order(
                symbol=symbol,
                side=action,
                volume=0.50, # HARD LOCK: Strictly 0.50 USD stake equivalent for MT5
                sl=sl_price,
                tp=tp_price
            )
            
            if sent:
                # Add to local tracking
                add_active_trade(
                    trade_id=f"mt5_{int(time.time())}",
                    asset=symbol,
                    stake=0.50,
                    duration=trade.get("duration", "1m"),
                    grid_plan=trade.get("risk_plan", {}).get("grid_levels", []),
                    metadata=trade.get("metadata", {}),
                    signal_id=trade.get("id")
                )
                return {"status": "FILLED", "bridge": True}
            else:
                return {"status": "ERROR", "reason": "MT5_BRIDGE_SEND_FAILED"}

        # ===== API DIRECT (Deriv WebSocket) =====
        try:
            client = DerivClient()
            symbol = payload.get("symbol", trade.get("asset", "R_100"))
            side = trade.get("side", "BUY")
            contract_type = "CALL" if side in ("BUY", "CALL", "UP") else "PUT"
            amount = trade.get("stake", 0.50)
            dur_str = str(trade.get("duration", "1m"))
            unit = dur_str[-1].lower() if dur_str[-1].isalpha() else "m"
            val = int(dur_str[:-1]) if dur_str[:-1].isdigit() else 1

            res = await client.buy_contract(
                symbol=symbol,
                contract_type=contract_type,
                amount=amount,
                duration=val,
                duration_unit=unit,
            )

            if "error" in res:
                logger.error(f"❌ Deriv API error: {res['error'].get('message')}")
                return {"status": "ERROR", "reason": res["error"].get("message", "API_ERROR")}

            contract_id = res.get("buy", {}).get("contract_id")
            add_active_trade(
                trade_id=f"deriv_{contract_id}",
                asset=trade.get("asset", symbol),
                stake=amount,
                duration=trade.get("duration", "1m"),
                metadata={"contract_id": contract_id, "channel": "API"},
                signal_id=trade.get("id"),
            )
            logger.info(f"✅ API TRADE: {contract_type} {symbol} ${amount} | Contract: {contract_id}")
            return {"status": "FILLED", "api": True, "contract_id": contract_id}

        except Exception as e:
            logger.error(f"❌ Deriv API execution failed: {e}")
            return {"status": "ERROR", "reason": str(e)}
