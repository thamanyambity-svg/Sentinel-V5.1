import logging
import os
import joblib
import pandas as pd
import numpy as np

logger = logging.getLogger("ML_SIGNAL_FILTER")

class MLSignalFilter:
    """
    Inference Engine for the Signal Quality Model.
    Loads the trained HistGradientBoostingClassifier.
    Input: RSI, ATR, QualityScore, Regime
    Output: Probability of Win (0.0 to 1.0)
    """
    
    MODEL_PATH = "bot/models/signal_filter_sklearn.pkl"
    
    def __init__(self):
        self.model = None
        self._load_model()
        
    def _load_model(self):
        if os.path.exists(self.MODEL_PATH):
            try:
                self.model = joblib.load(self.MODEL_PATH)
                logger.info(f"🧠 [ML] Loaded Signal Filter Model from {self.MODEL_PATH}")
            except Exception as e:
                logger.error(f"❌ [ML] Failed to load model: {e}")
        else:
            logger.warning(f"⚠️ [ML] Model not found at {self.MODEL_PATH}. Inference disabled.")
            
    def predict_quality(self, rsi: float, atr: float, score: float, regime: str) -> float:
        """
        Returns probability of success.
        If model missing, returns 0.5 (Neutral).
        """
        if not self.model:
            return 0.5
            
        try:
            # Prepare Input Vector
            # Order MUST match training: [rsi, atr, score, regime_val]
            
            # Map Regime
            regime_map = {
                "RANGE_CALM": 0,
                "TREND_STABLE": 1, 
                "VOLATILE_FAST": 2, 
                "CRASH_CHAOS": 3,
                "UNKNOWN": 0 
            }
            regime_val = regime_map.get(str(regime), 0)
            
            # Create DataFrame with correct feature names (Sklearn uses feature names if available)
            features = pd.DataFrame([{
                'rsi': float(rsi),
                'atr': float(atr),
                'score': float(score),
                'regime_val': int(regime_val)
            }])
            
            # Predict Probability [Loss_Prob, Win_Prob]
            probs = self.model.predict_proba(features)
            win_prob = probs[0][1] # Probability of Class 1
            
            return float(win_prob)
            
        except Exception as e:
            logger.error(f"🔮 [ML] Inference Error: {e}")
            return 0.5 # Fail safe
