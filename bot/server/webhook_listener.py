import asyncio
import logging
from aiohttp import web
import json
import os

logger = logging.getLogger("WEBHOOK")

class WebhookServer:
    def __init__(self, bot_instance, port=8080):
        self.bot = bot_instance
        self.port = port
        self.app = web.Application()
        self.app.router.add_post('/webhook', self.handle_webhook)
        self.app.router.add_get('/', self.handle_health)
        self.runner = None
        self.site = None
        
        # Security: Allow environment variable or default
        self.passphrase = os.getenv("WEBHOOK_PASSPHRASE", "AMBITY_SECRET_SIGNAL")

    async def handle_health(self, request):
        return web.Response(text="Webhook Listener is Active 🟢")

    async def handle_webhook(self, request):
        try:
            data = await request.json()
            
            # 1. Security Check
            if data.get("passphrase") != self.passphrase:
                logger.warning(f"⛔ Unauthorized Webhook Attempt from {request.remote}")
                return web.Response(status=401, text="Unauthorized: Invalid Passphrase")

            # 2. Extract Signal
            symbol = data.get("symbol")
            side = data.get("side", "").upper() # BUY/SELL
            comment = data.get("comment", "TV-Signal")
            stake = data.get("stake", 0.35) # Default Stake

            logger.info(f"📨 TradingView Signal Received: {side} {symbol} ({comment})")

            # 3. Inject into Bot Logic
            # We construct a signal dictionary compatible with bot's broker
            signal = {
                "asset": symbol,
                "side": side,
                "amount": float(stake),
                "duration": "1m",
                "ai_confirmation": {"reason": f"TradingView Alert: {comment}"},
                "source": "TRADINGVIEW"
            }
            
            # --- EXECUTION ---
            # Ideally, we put this in a queue, but for speed we can direct execute via bot.broker
            # if bot has broker.
            if hasattr(self.bot, "broker") and self.bot.broker:
                logger.info(f"⚡ Executing TV Signal: {symbol}...")
                
                # Execute in background task to not block response
                asyncio.create_task(self._process_signal(signal))
                
                return web.Response(text=f"Signal Received: {symbol}")
            else:
                return web.Response(status=503, text="Bot Broker not ready")

        except Exception as e:
            logger.error(f"❌ Webhook Error: {e}")
            return web.Response(status=500, text="Internal Error")

    async def _process_signal(self, signal):
        try:
            await self._apply_manual_security(signal)
            res = await self.bot.broker.execute(signal)
            
            # Notify Discord
            if hasattr(self.bot, "send_signal_embed"):
                # Adapt signal to display format
                data = {
                    "asset": signal["asset"],
                    "stake_advice": f"${signal['amount']}",
                    "probability": "100% (TV)",
                    "market_details": [f"Source: TradingView", f"Comment: {signal['ai_confirmation']['reason']}"],
                    "score": 99,
                    "balance": 0.0, # Pass actual buffer if possible
                    "duration": "1m"
                }
                await self.bot.send_signal_embed(data)
                
        except Exception as e:
            logger.error(f"Failed to process TV signal: {e}")

    async def _get_current_balance(self):
        client = getattr(self.bot, "deriv_client", None)
        if not client:
            return 0.0

        try:
            balance_data = await client.get_balance()
            if isinstance(balance_data, dict):
                return float(balance_data.get("balance", 0.0) or 0.0)
        except Exception as e:
            logger.warning(f"⚠️ Manual security balance fetch failed: {e}")

        return 0.0

    async def _apply_manual_security(self, signal):
        signal.setdefault("type", "MEAN_REVERSION")
        signal.setdefault("indicators", {"rsi": 50})

        requested_amount = float(signal.get("amount", 0.50) or 0.50)
        balance = await self._get_current_balance()

        sl_dist = signal.get("risk_plan", {}).get("sl_dist")
        if not sl_dist:
            atr_value = float(signal.get("atr", 0.0) or 0.0)
            sl_dist = (atr_value * 2.0) if atr_value > 0.0 else 50.0

        atr_for_governance = float(signal.get("atr", 0.0) or (sl_dist / 2.0))

        manager = getattr(self.bot, "manager", None)
        if manager:
            context = {
                "asset": signal.get("asset", "UNKNOWN"),
                "price": float(signal.get("current_price", 0.0) or 0.0),
                "indicators": signal.get("indicators", {"rsi": 50}),
                "balance": balance,
                "atr": atr_for_governance,
            }
            approved, reason = await manager.validate_signal(
                signal,
                [],
                {"global_drawdown": 0.0, "losing_streak": 0},
                context,
            )
            if not approved:
                raise RuntimeError(f"Manual signal blocked by governance: {reason}")

        risk_manager = getattr(self.bot, "risk_manager", None)
        if risk_manager and balance > 0.0:
            safe_amount = risk_manager.calculate_lot_size(balance, float(sl_dist), signal.get("asset", "DEFAULT"))
            if safe_amount > 0.0:
                requested_amount = min(requested_amount, safe_amount)

        signal["amount"] = round(requested_amount, 2)
        signal["stake"] = signal["amount"]
        signal["risk_plan"] = {**signal.get("risk_plan", {}), "sl_dist": float(sl_dist)}
        logger.info(
            f"🛡️ Manual security active for {signal.get('asset')} | stake={signal['amount']}$ | sl_dist={float(sl_dist):.2f}"
        )

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, 'localhost', self.port)
        await self.site.start()
        logger.info(f"👂 Webhook Server listening on port {self.port}")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
