import logging
import asyncio
from bot.risk.regime import RegimeDetector
from bot.risk.guard import MultiLevelKillSwitch
from bot.risk.sizer import VolatilityPricer
from bot.risk.advanced_filters import AdvancedFilterManager
from bot.ai_agents.audit_logger import log_event
from bot.ai_agents.orchestrator import AIOrchestrator

logger = logging.getLogger("MANAGER")

class TradingManager:
    """
    TradingManager: Orchestrateur central institutionnel.
    Vérifie les régimes, applique les kill-switches et calcule le sizing final.
    """

    def __init__(self):
        self.regime_detector = RegimeDetector()
        self.risk_guard = MultiLevelKillSwitch()
        self.sizer = VolatilityPricer()
        self.advanced_filters = AdvancedFilterManager()
        self.current_regime = "RANGE_CALM"
        
        # 🧠 INITIALISATION CERVEAU IA (Supervision Continue)
        self.ai_orchestrator = AIOrchestrator()
        self.ai_orchestrator.start_background_loop()

    async def update_market_stats(self, symbol, candles, indicators, balance=0.0):
        """
        Met à jour l'état du manager avec les dernières données du marché.
        """
        try:
            self.current_regime = self.regime_detector.compute(candles)
            
            # Mise à jour du Contexte IA (Fire-and-forget)
            market_data = {
                "regime": self.current_regime,
                "atr": indicators.get("atr"),
                "atr_percentile": indicators.get("atr_percentile", 50),
                "adx": indicators.get("adx", 20),
                "vol_of_vol": indicators.get("vol_of_vol", 0.0),
                "spread": indicators.get("spread", 0.0),
                "price": float(candles[-1]['close'])
            }
            # Pass real equity/balance to AI context
            self.ai_orchestrator.update_context(market_data, {"equity": balance, "dd_global": 0.0}) 
            
            # Structured MARKET log for AI Professor
            log_event("MARKET", symbol, {
                **market_data,
                "tick_rate": indicators.get("tick_rate", 0)
            })
            
            return self.current_regime
        except Exception as e:
            logger.error(f"❌ Error updating market stats: {e}")
            return self.current_regime

    async def validate_signal(self, signal, trades, stats, context):
        """
        Vérification finale du signal avant exécution.
        """
        sig_type = signal.get("type", "MEAN_REVERSION")
        
        # 0. 🧠 AI SUPERVISION CHECK (ZERO LATENCY)
        approved, reason, ai_resp = await self.ai_orchestrator.evaluate_signal(signal, context, {"equity": context.get("balance", 0.0), "dd_global": 0.0})
        if not approved:
            logger.warning(f"🛡️ [AI VETO] Signal REJECTED by AI Supervision: {reason}")
            return False, f"AI: {reason}"
        
        # 1. Régime CHAOS : Blocage Total
        if self.current_regime == "CHAOS":
            logger.warning(f"🛡️ [GATE] Signal {sig_type} REJECTED: CHAOS Regime is active. Capital protection engaged.")
            return False, "CHAOS Regime"

        # 2. Vérification des Kill-Switches (Daily / Global DD)
        allowed, reason = self.risk_guard.is_allowed(trades, stats, self.current_regime)
        if not allowed:
            logger.warning(f"🛡️ [GATE] Signal {sig_type} REJECTED: Risk Guard - {reason}")
            return False, reason

        # 3. Stratégie vs Régime Match
        if sig_type == "MEAN_REVERSION":
            if self.current_regime != "RANGE_CALM":
                logger.info(f"🛡️ [GATE] RSI Rejection: Price is in {self.current_regime}. Mean reversion is dangerous here.")
                return False, f"Regime {self.current_regime} mismatch"
        
        elif sig_type == "TREND_FOLLOWING":
            if self.current_regime != "TREND_STABLE":
                logger.info(f"🛡️ [GATE] Trend Rejection: Market is in {self.current_regime}. Need TREND_STABLE for breakouts.")
                return False, f"Regime {self.current_regime} mismatch"
        
        else:
            # Type inconnu
            logger.info(f"🛡️ [GATE] Type {sig_type} REJECTED: Strategy mapping unknown.")
            return False, "Unknown strategy type"

        # 4. Advanced Filters (RSI Extreme, Frequency, Cooldown, Fatigue)
        symbol = context.get("asset", "UNKNOWN")
        rsi = context.get("indicators", {}).get("rsi", 50)
        signal_side = signal.get("side", "CALL")
        
        approved, filter_reason = self.advanced_filters.validate_signal(
            symbol=symbol,
            signal_side=signal_side,
            rsi=rsi,
            regime=self.current_regime,
            signal_type=sig_type
        )
        
        if not approved:
            logger.info(f"🛡️ [ADVANCED FILTERS] {symbol} rejected: {filter_reason}")
            return False, filter_reason

        # 5. Calcul du Sizing Dynamique
        equity = context.get("balance", 0.0)
        atr = context.get("atr", 0.0)
        
        effective_size = self.sizer.calculate(equity, atr, self.current_regime)
        
        if effective_size <= 0:
            logger.warning(f"🛡️ [GATE] Sizing Rejection: Calculated size is {effective_size}. Balance or ATR missing.")
            return False, "Sizing failed"

        # 6. Injection finale
        signal["amount"] = effective_size
        signal["regime"] = self.current_regime
        
        # Record trade execution for frequency governor
        self.advanced_filters.record_trade_executed(symbol)
        
        logger.info(f"✅ [GATE] Approved {sig_type} | Size: ${effective_size:.2f} | Regime: {self.current_regime} | AI: OK")
        return True, "Approved"
