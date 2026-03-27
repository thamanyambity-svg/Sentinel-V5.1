"""
sentinel_ml.py — V9 XGBoost ML Model for Sentinel
===================================================
Replaces the Nexus LSTM placeholder with a robust, interpretable XGBoost
classifier trained on real trade history (trade_history.json).

Architecture:
    Feature Engine → XGBClassifier → predict_proba → Confluence Engine

Features (8 dimensions):
    return_5, return_20, atr, atr_ratio, candle_range, imbalance, rsi, spread

Target:
    Binary classification: 1 = trade hit TP before SL, 0 = otherwise
"""

import json
import os
import logging
import joblib
import numpy as np

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None

logger = logging.getLogger("SENTINEL_ML")

MODEL_PATH = "sentinel_xgb_model.joblib"
FEATURE_NAMES = [
    "return_5", "return_20", "atr", "atr_ratio",
    "candle_range", "imbalance", "rsi", "spread"
]


def build_features(tick_data: dict) -> dict:
    """
    Build feature vector from live tick/candle data.

    Expected tick_data keys (from ticks_v3.json or enriched context):
        closes   : list of recent close prices (≥20 elements)
        atr      : current ATR value (float)
        atr_hist : list of recent ATR values (≥20 elements)
        high     : current candle high
        low      : current candle low
        imbalance: wick imbalance from EA (-1..+1)
        rsi      : RSI value (0..100)
        spread   : current spread
    """
    closes = tick_data.get("closes", [])
    atr = tick_data.get("atr", 0.0)
    atr_hist = tick_data.get("atr_hist", [])
    high = tick_data.get("high", 0.0)
    low = tick_data.get("low", 0.0)
    imbalance = tick_data.get("imbalance", 0.0)
    rsi = tick_data.get("rsi", 50.0)
    spread = tick_data.get("spread", 0.0)

    # Return features as percentage changes (normalized across instruments)
    return_5 = ((closes[-1] - closes[-5]) / closes[-5]) if len(closes) >= 5 and closes[-5] != 0 else 0.0
    return_20 = ((closes[-1] - closes[-20]) / closes[-20]) if len(closes) >= 20 and closes[-20] != 0 else 0.0

    # ATR ratio = current ATR / mean of recent ATR history
    atr_mean = float(np.mean(atr_hist)) if atr_hist else atr
    atr_ratio = (atr / atr_mean) if atr_mean > 1e-10 else 1.0

    # Candle range
    candle_range = high - low

    return {
        "return_5": return_5,
        "return_20": return_20,
        "atr": atr,
        "atr_ratio": atr_ratio,
        "candle_range": candle_range,
        "imbalance": imbalance,
        "rsi": rsi,
        "spread": spread,
    }


def features_to_array(features: dict) -> list:
    """Convert feature dict to ordered list matching FEATURE_NAMES."""
    return [features.get(name, 0.0) for name in FEATURE_NAMES]


def build_target(trade: dict) -> int:
    """
    Binary target from trade outcome.
    1 = trade hit TP before SL (preferred), or profitable if tp_hit unknown
    0 = trade was a loss or scratch
    """
    if "tp_hit" in trade:
        return 1 if trade["tp_hit"] else 0
    return 1 if trade.get("profit", 0.0) > 0 else 0


class SentinelMLModel:
    """
    XGBoost classifier for trade outcome prediction.
    Replaces the Nexus LSTM placeholder with a production-grade model.
    """

    def __init__(self, model_path: str = MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load saved model from disk if available."""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                logger.info(f"[ML] Model loaded from {self.model_path}")
            except Exception as e:
                logger.warning(f"[ML] Failed to load model: {e}")
                self.model = None
        else:
            logger.info("[ML] No saved model found — will need training first")

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """
        Train XGBoost on feature matrix X and binary target y.
        Returns training metrics dict.
        """
        if XGBClassifier is None:
            logger.error("[ML] xgboost not installed — cannot train")
            return {"error": "xgboost not installed"}

        if len(X) < 30:
            logger.warning(f"[ML] Only {len(X)} samples — minimum 30 required for training")
            return {"error": f"insufficient data ({len(X)} samples)"}

        self.model = XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            use_label_encoder=False,
            random_state=42,
        )
        self.model.fit(X, y)

        # Save model
        joblib.dump(self.model, self.model_path)
        logger.info(f"[ML] Model trained on {len(X)} samples, saved to {self.model_path}")

        # Return basic training metrics
        preds = self.model.predict(X)
        train_acc = float(np.mean(preds == y))
        return {"train_accuracy": round(train_acc, 4), "n_samples": len(X)}

    def predict_proba(self, features: dict) -> float:
        """
        Predict probability of profitable trade (class 1).
        Returns float in [0, 1]. Falls back to 0.5 if no model.
        """
        if self.model is None:
            return 0.5

        arr = np.array([features_to_array(features)])
        try:
            proba = self.model.predict_proba(arr)[0][1]
            return float(proba)
        except Exception as e:
            logger.warning(f"[ML] Prediction failed: {e}")
            return 0.5

    def is_ready(self) -> bool:
        """Check if model is trained and ready for inference."""
        return self.model is not None


def train_from_trade_history(history_path: str = "trade_history.json",
                             model_path: str = MODEL_PATH) -> dict:
    """
    Convenience function: load trade_history.json, build features + targets,
    train model, save to disk. Called by the weekly retraining loop.

    Returns metrics dict or error.
    """
    # Find trade history file
    candidates = []
    mt5_path = os.getenv("MT5_FILES_PATH", "")
    if mt5_path:
        candidates.append(os.path.join(mt5_path, history_path))
    candidates.append(history_path)

    trades = None
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    trades = json.load(f)
                break
            except (json.JSONDecodeError, OSError):
                continue

    if not trades or not isinstance(trades, list):
        return {"error": "trade_history.json not found or empty"}

    # Filter closed trades only
    closed = [t for t in trades if t.get("closed", False)]
    if len(closed) < 30:
        return {"error": f"Only {len(closed)} closed trades — need ≥30 for training"}

    # Build feature matrix and targets
    # Each trade record should contain the features captured at entry time.
    # For trades that only have basic fields, we synthesize minimal features.
    X_list = []
    y_list = []
    for t in closed:
        feat = {
            "return_5": t.get("return_5", 0.0),
            "return_20": t.get("return_20", 0.0),
            "atr": t.get("atr", 0.0),
            "atr_ratio": t.get("atr_ratio", 1.0),
            "candle_range": t.get("candle_range", 0.0),
            "imbalance": t.get("imbalance", 0.0),
            "rsi": t.get("rsi", 50.0),
            "spread": t.get("spread", 0.0),
        }
        X_list.append(features_to_array(feat))
        y_list.append(build_target(t))

    X = np.array(X_list, dtype=np.float64)
    y = np.array(y_list, dtype=np.int32)

    ml = SentinelMLModel(model_path=model_path)
    return ml.train(X, y)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = train_from_trade_history()
    print(f"[ML] Training result: {result}")
