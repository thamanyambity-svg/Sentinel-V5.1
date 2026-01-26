import pandas as pd
import numpy as np
import logging
from bot.config.thresholds import REGIME_THRESHOLDS, REGIME_RULES

logger = logging.getLogger("REGIME_DETECTOR")

class RegimeDetector:
    """
    RegimeDetector v1.2: Institutional-grade calibration
    Thresholds optimized for M1/M5 synthetic indices
    Target: Max Drawdown ≤ 10%
    """
    
    STATES = ["RANGE_CALM", "TREND_STABLE", "TRANSITION", "CHAOS"]
    
    def __init__(self, window=None):
        self.window = window or REGIME_THRESHOLDS["hysteresis_bars"]
        self.current_state = "RANGE_CALM"
        self.buffer = []
        
        # Load thresholds
        self.vov_thresholds = REGIME_THRESHOLDS["vol_of_vol"]
        self.adx_thresholds = REGIME_THRESHOLDS["adx"]
        self.atr_thresholds = REGIME_THRESHOLDS["atr_percentile"]

    def compute(self, candles):
        """
        Calcule le régime actuel à partir des bougies.
        """
        if not candles or len(candles) < 250:
            return self.current_state

        df = pd.DataFrame(candles)
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)

        # 1. Calcul des composants
        atr = self._calculate_atr(df)
        adx = self._calculate_adx(df)
        vol_of_vol = self._calculate_vol_of_vol(df)
        
        # Percentile ATR (simplifié : relatif à la moyenne longue)
        atr_ema = df['atr'].ewm(span=100).mean().iloc[-1]
        atr_ratio = atr / atr_ema if atr_ema > 0 else 1.0

        # 2. Logique de décision brute (Raw State)
        raw_state = self._determine_raw_state(atr_ratio, adx, vol_of_vol)

        # 3. Hystérésis & Chaos Override
        return self._apply_hysteresis(raw_state, atr_ratio, vol_of_vol)

    def _calculate_atr(self, df, period=14):
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift()).abs()
        tr3 = (df['low'] - df['close'].shift()).abs()
        df['atr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(window=period).mean()
        return df['atr'].iloc[-1]

    def _calculate_adx(self, df, period=14):
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()

        tr = df['atr'] # Utilise l'ATR pré-calculé
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / tr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / tr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        return adx.iloc[-1]

    def _calculate_vol_of_vol(self, df, period=20):
        # Normalisé : std(ATR / EMA(ATR))
        atr_ema = df['atr'].ewm(span=period).mean()
        vol_ratio = df['atr'] / atr_ema
        vov = vol_ratio.rolling(window=period).std()
        return vov.iloc[-1]

    def _determine_raw_state(self, atr_ratio, adx, vov):
        """
        Institutional threshold-based regime classification
        Calibrated for synthetic indices M1/M5
        """
        # ⚠️ CHAOS : Vol-of-Vol ≥ 0.50 (institutional threshold)
        if vov >= self.vov_thresholds["unstable"]:
            return "CHAOS"
        
        # 📈 TREND_STABLE : ADX 22-35 & VoV < 0.30
        if (self.adx_thresholds["range_unstable"] <= adx <= self.adx_thresholds["trend_exploitable"] 
            and vov < 0.30):
            return "TREND_STABLE"
        
        # 📉 TRANSITION : VoV 0.20-0.35 or conflicting indicators
        if self.vov_thresholds["stable"] <= vov < self.vov_thresholds["transition"]:
            return "TRANSITION"
        
        # ADX > 35 = risky trend → TRANSITION
        if adx > self.adx_thresholds["trend_exploitable"]:
            return "TRANSITION"
            
        # 💤 RANGE_CALM : Low volatility, low ADX
        if adx < self.adx_thresholds["range_unstable"] and vov < self.vov_thresholds["stable"]:
            return "RANGE_CALM"
        
        # Default: TRANSITION (conservative)
        return "TRANSITION"

    def _apply_hysteresis(self, raw_state, atr_ratio=0.0, vov=0.0):
        # CHAOS override immédiat
        if raw_state == "CHAOS":
            if self.current_state != "CHAOS":
                logger.warning(f"🔥 CHAOS DETECTED (VoV: {vov:.4f}, ATR Ratio: {atr_ratio:.2f}) - Immediate state change")
            self.current_state = "CHAOS"
            self.buffer = []
            return "CHAOS"

        self.buffer.append(raw_state)
        if len(self.buffer) >= self.window:
            # Si le nouveau régime est stable sur 8 bars
            if all(s == raw_state for s in self.buffer):
                if self.current_state != raw_state:
                    logger.info(f"🔄 Regime change confirmed: {self.current_state} -> {raw_state}")
                    self.current_state = raw_state
            self.buffer.pop(0)
            
        return self.current_state
