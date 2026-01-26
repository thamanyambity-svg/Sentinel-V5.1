import logging

logger = logging.getLogger("VOL_SIZER")

class VolatilityPricer:
    """
    VolatilityPricer: Calcule la taille de position basée sur la volatilité (ATR).
    Pondère le risque selon le régime détecté et impose un CAP de 1.5%.
    """

    REGIME_MULTIPLIERS = {
        "RANGE_CALM": 1.0,
        "TREND_STABLE": 1.3,
        "TRANSITION": 0.7, # Réduction du risque en transition
        "CHAOS": 0.0      # Trading interdit
    }

    def __init__(self, risk_per_trade=0.002, max_position_pct=0.015):
        self.risk_per_trade = risk_per_trade # 0.20%
        self.max_position_pct = max_position_pct # 1.5%

    def calculate(self, equity, atr, regime):
        """
        Formule institutionnelle : Size = (Equity * Risk) / (ATR * Multiplier)
        """
        if regime not in self.REGIME_MULTIPLIERS or regime == "CHAOS":
            logger.warning(f"🚫 Sizing refused: Regime is {regime}")
            return 0.0

        multiplier = self.REGIME_MULTIPLIERS[regime]
        
        if atr <= 0:
            logger.error("❌ ATR is zero or negative. Sizing failed.")
            return 0.0

        # Calcul de base
        target_risk_amount = equity * self.risk_per_trade
        raw_size = target_risk_amount / (atr * multiplier)

        # Application du CAP (1.5% de l'Equity)
        max_size = equity * self.max_position_pct
        final_size = min(raw_size, max_size)

        if final_size == max_size:
            logger.info(f"⚠️ Position size capped at {self.max_position_pct*100}% of Equity")

        # Force minimum stake for small accounts (Deriv Min ~0.35$ - Set to 0.50$ per user request)
        MIN_STAKE = 0.50
        if 0 < final_size < MIN_STAKE:
             logger.info(f"⚠️ Upgrading size to Minimum Stake: ${MIN_STAKE}")
             final_size = MIN_STAKE

        logger.info(f"📐 Sizing: Regime={regime}, ATR={atr:.4f}, Size={final_size:.2f}")
        return round(final_size, 2)
