
import numpy as np
import pandas as pd
import logging
import joblib
import os

logger = logging.getLogger("REGIME_CLASSIFIER")

class RegimeClassifier:
    """
     Phase 2: Market Regime Identification.
     Acts as a Gatekeeper for trading signals.
     
     Modes:
     - HEURISTIC (V1): Simple rules based on ATR and Bollinger Bands.
     - ML_HMM (V2): Gaussian Hidden Markov Model (if model exists).
    """
    
    REGIMES = {
        "RANGE_CALM": 0,      # Safe for Mean Reversion (RSI)
        "TREND_STABLE": 1,    # Safe for Trend Following
        "VOLATILE_FAST": 2,   # Dangerous (Reduce size)
        "CRASH_CHAOS": 3      # STOP TRADING
    }
    
    def __init__(self, use_hmm=True, model_path="bot/models/hmm_model.pkl"):
        self.use_hmm = use_hmm
        self.model_path = model_path
        self.model = None
        self._load_model()
        
    def _load_model(self):
        if self.use_hmm and os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                logger.info(f"🧠 [REGIME] HMM Model loaded from {self.model_path}")
            except Exception as e:
                logger.warning(f"⚠️ [REGIME] Failed to load HMM model: {e}")
        else:
            logger.info("ℹ️ [REGIME] HMM Model not found. Using Heuristics (V1).")


    # HEURISTIC THRESHOLDS
    ATR_RATIO_CHAOS = 2.5
    ATR_RATIO_VOLATILE = 1.5
    BB_WIDTH_THRESHOLD = 0.005  # Adjusted for Synthetic Indices (was 0.002)

    def detect_regime(self, candles: list) -> dict:
        """
        Analyze candles and return the current regime.
        Response: { "regime": "RANGE_CALM", "confidence": 0.9, "reason": "Low ATR" }
        """
        if not candles or len(candles) < 20:
            return {"regime": "UNKNOWN", "confidence": 0.0, "reason": "Insufficient Data"}
            
        df = pd.DataFrame(candles)
        cols = ['close', 'high', 'low']
        for c in cols: df[c] = df[c].astype(float)
        
        # 1. CALCULATE CORE METRICS
        # Returns
        df['returns'] = np.log(df['close'] / df['close'].shift(1))
        # Volatility (Rolling Std Dev of Returns)
        df['volatility'] = df['returns'].rolling(window=20).std()
        # ATR (Simplified close-close for speed, or High-Low)
        df['tr'] = df['high'] - df['low']
        current_atr = df['tr'].rolling(window=14).mean().iloc[-1]
        avg_atr = df['tr'].rolling(window=100).mean().iloc[-1] if len(df) > 100 else current_atr
        
        # Bollinger Band Width
        sma = df['close'].rolling(window=20).mean()
        std = df['close'].rolling(window=20).std()
        bb_width = ((sma + 2*std) - (sma - 2*std)) / sma
        current_bbw = bb_width.iloc[-1]
        
        # 2. HMM PREDICTION (V2)
        hmm_regime = None
        if self.model and len(df) > 10:
            try:
                # Prepare features same as training: [returns, volatility]
                X = df[['returns', 'volatility']].iloc[-10:].dropna().values
                if len(X) > 0:
                    hidden_states = self.model.predict(X)
                    hmm_regime = hidden_states[-1] # User trained 0=Volatile, 1=Normal usually? 
                    # Note: HMM states are not ordered. We need to map them.
                    # For this prototype we rely on V1 Heuristics primarily if HMM is murky.
            except: pass

        # 3. HEURISTIC CLASSIFICATION (V1 - The pragmatist)
        # We classify based on volatility relative to history
        
        atr_ratio = current_atr / (avg_atr if avg_atr > 0 else 1)
        
        regime = "RANGE_CALM"
        reason = "Normal Volatility"
        
        # RULE 1: CHAOS
        if atr_ratio > self.ATR_RATIO_CHAOS:
            regime = "CRASH_CHAOS"
            reason = f"Extreme Volatility (ATR x{atr_ratio:.1f})"
            
        # RULE 2: VOLATILE
        elif atr_ratio > self.ATR_RATIO_VOLATILE:
            regime = "VOLATILE_FAST"
            reason = f"High Volatility (ATR x{atr_ratio:.1f})"
            
        # RULE 3: TREND vs RANGE
        # If BB Width is expanding, likely trend.
        elif current_bbw > self.BB_WIDTH_THRESHOLD:
            regime = "TREND_STABLE"
            reason = "Bollinger Expansion"
            
        else:
            regime = "RANGE_CALM"
            reason = "Low Volatility & BB Squeeze"

        return {
            "regime": regime,
            "confidence": 0.85, # Heuristic confidence
            "reason": reason,
            "metrics": {
                "atr_ratio": round(atr_ratio, 2),
                "bb_width": round(current_bbw, 5)
            }
        }
