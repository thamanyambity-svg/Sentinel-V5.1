"""
sentinel_ml.py — V9 XGBoost ML Model for Sentinel (XAUUSD Gold Optimized)
==========================================================================
Production-grade XGBoost classifier with XAUUSD-optimized features:
  1. Volatility Regime   (atr, atr_ratio, range_ratio, vol_compression)
  2. Liquidity/Imbalance (imbalance, wick_ratio, liquidity_grab)
  3. Session Timing      (london, newyork, asia)
  4. Momentum Structure  (ret_5, ret_10, momentum_acc, break_high, break_low)

Architecture:
    Feature Engine → StandardScaler → XGBClassifier → predict_proba → Confluence Engine

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

try:
    from sklearn.preprocessing import StandardScaler
except ImportError:
    StandardScaler = None

logger = logging.getLogger("SENTINEL_ML")

MODEL_PATH = "sentinel_xgb_model.joblib"
SCALER_PATH = "sentinel_scaler.joblib"

FEATURE_NAMES = [
    # Bloc 0 — Trend Confirmation (NIVEAU 1 addition - Critical filters)
    "ema_20", "ema_50", "ema_slope", "rsi", "macd_histogram",
    # Bloc 1 — Volatility
    "atr", "atr_ratio", "range_ratio", "vol_compression",
    # Bloc 2 — Liquidity / Imbalance
    "imbalance", "wick_ratio", "liquidity_grab",
    # Bloc 3 — Session Timing
    "london", "newyork", "asia",
    # Bloc 4 — Momentum Structure
    "ret_5", "ret_10", "momentum_acc", "break_high", "break_low",
    # Bloc 5 — Orderflow (V9.1 Hedge Fund addition)
    "delta", "absorption",
]


def _ema(series: list, period: int) -> float:
    """Calculate Exponential Moving Average."""
    if len(series) < period:
        return series[-1] if series else 0.0

    multiplier = 2.0 / (period + 1)
    ema = float(np.mean(series[-period:]))

    for price in series[-period:]:
        ema = price * multiplier + ema * (1 - multiplier)

    return float(ema)


def _rsi(series: list, period: int = 14) -> float:
    """Calculate Relative Strength Index."""
    if len(series) < period + 1:
        return 50.0

    deltas = np.diff(series[-period-1:])
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period

    rs = up / (down + 1e-9)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    return float(rsi)


def _macd(series: list) -> float:
    """Calculate MACD histogram (difference between 12 and 26 EMA)."""
    if len(series) < 26:
        return 0.0

    ema12 = _ema(series, 12)
    ema26 = _ema(series, 26)
    macd_line = ema12 - ema26

    # Signal line (9-period EMA of MACD)
    # For simplicity, approximate with recent MACD values
    signal = _ema([ema12 - ema26], 9) if len(series) >= 35 else macd_line

    return float(macd_line - signal)


def _trend_confirmation_features(tick_data: dict) -> dict:
    """
    Bloc 0 — Trend Confirmation (NIVEAU 1 - Critical for filtering false breaks)

    Features:
      - ema_20: Short-term trend (entry confirmation)
      - ema_50: Medium-term trend
      - ema_slope: Trend strength (avoid dying trends)
      - rsi: Momentum extremes (overbought/oversold)
      - macd_histogram: Momentum acceleration
    """
    closes = tick_data.get("closes", [])

    if len(closes) < 26:
        return {
            "ema_20": 0.0,
            "ema_50": 0.0,
            "ema_slope": 0.0,
            "rsi": 50.0,
            "macd_histogram": 0.0,
        }

    # EMA calculations
    ema_20 = _ema(closes, 20)
    ema_50 = _ema(closes, 50)

    # EMA slope (trend strength): (EMA20_now - EMA20_10bars_ago) / EMA20
    ema_20_history = [_ema(closes[:max(1, i-19)], 20) for i in range(10, len(closes))]
    if len(ema_20_history) >= 2:
        ema_slope = (ema_20 - ema_20_history[-10]) / (abs(ema_20) + 1e-9) if ema_20 != 0 else 0.0
    else:
        ema_slope = 0.0

    # RSI (momentum extremes)
    rsi = _rsi(closes, 14)

    # MACD histogram
    macd_hist = _macd(closes)

    return {
        "ema_20": float(ema_20),
        "ema_50": float(ema_50),
        "ema_slope": float(ema_slope),
        "rsi": float(rsi),
        "macd_histogram": float(macd_hist),
    }


def _volatility_features(tick_data: dict) -> dict:
    """Bloc 1 — Volatility regime features (XAUUSD priority #1)."""
    atr = tick_data.get("atr", 0.0)
    atr_hist = tick_data.get("atr_hist", [])
    high = tick_data.get("high", 0.0)
    low = tick_data.get("low", 0.0)
    closes = tick_data.get("closes", [])

    atr_mean = float(np.mean(atr_hist[-50:])) if len(atr_hist) >= 1 else atr
    atr_ratio = (atr / atr_mean) if atr_mean > 1e-10 else 1.0

    candle_range = high - low
    range_ratio = (candle_range / atr) if atr > 1e-10 else 1.0

    vol_compression = float(np.std(closes[-20:])) if len(closes) >= 20 else 0.0

    return {
        "atr": atr,
        "atr_ratio": atr_ratio,
        "range_ratio": range_ratio,
        "vol_compression": vol_compression,
    }


def _liquidity_features(tick_data: dict) -> dict:
    """Bloc 2 — Liquidity / Imbalance features (main competitive edge)."""
    opens = tick_data.get("opens", [])
    closes = tick_data.get("closes", [])
    highs = tick_data.get("highs", [])
    lows = tick_data.get("lows", [])
    high = tick_data.get("high", 0.0)

    window = 30
    n = min(window, len(opens), len(closes), len(highs), len(lows))

    buy_score = 0.0
    sell_score = 0.0

    if n > 0:
        for j in range(-n, 0):
            body_top = max(opens[j], closes[j])
            body_bot = min(opens[j], closes[j])
            wick_up = highs[j] - body_top
            wick_down = body_bot - lows[j]
            r = highs[j] - lows[j] + 1e-9
            sell_score += wick_up / r
            buy_score += wick_down / r

    raw_imbalance = (buy_score - sell_score) / max(n, 1)
    imbalance = float(np.tanh(raw_imbalance * 3))

    wick_ratio = (sell_score + buy_score) / max(n, 1)

    # Liquidity grab detection: current high breaks recent swing high
    # Compare current bar high against the max of the previous n candles
    liquidity_grab = 0
    if n >= 2 and high > 0:
        recent_high = max(highs[-n:-1])
        if recent_high > 0 and high > recent_high:
            liquidity_grab = 1

    return {
        "imbalance": imbalance,
        "wick_ratio": float(wick_ratio),
        "liquidity_grab": liquidity_grab,
    }


def _session_features(tick_data: dict) -> dict:
    """Bloc 3 — Session timing features (critical for XAUUSD)."""
    hour = tick_data.get("hour", -1)

    # If no hour provided, try to extract from timestamp
    if hour < 0:
        ts = tick_data.get("timestamp", "")
        if ts:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(str(ts))
                hour = dt.hour
            except (ValueError, TypeError):
                hour = -1

    return {
        "london": 1 if 8 <= hour <= 12 else 0,
        "newyork": 1 if 13 <= hour <= 17 else 0,
        "asia": 1 if 0 <= hour <= 6 else 0,
    }


def _momentum_features(tick_data: dict) -> dict:
    """Bloc 4 — Momentum structure features."""
    closes = tick_data.get("closes", [])
    highs = tick_data.get("highs", [])
    lows = tick_data.get("lows", [])

    c = closes[-1] if closes else 0.0
    ret_5 = (c - closes[-5]) if len(closes) >= 5 else 0.0
    ret_10 = (c - closes[-10]) if len(closes) >= 10 else 0.0

    # Momentum acceleration (2nd derivative)
    mom_recent = (c - closes[-5]) if len(closes) >= 5 else 0.0
    mom_prior = (closes[-5] - closes[-10]) if len(closes) >= 10 else 0.0
    momentum_acc = mom_recent - mom_prior

    # Break structure
    break_high = 0
    break_low = 0
    if len(highs) >= 10 and c > 0:
        if c > max(highs[-10:]):
            break_high = 1
    if len(lows) >= 10 and c > 0:
        if c < min(lows[-10:]):
            break_low = 1

    return {
        "ret_5": ret_5,
        "ret_10": ret_10,
        "momentum_acc": momentum_acc,
        "break_high": break_high,
        "break_low": break_low,
    }


def _orderflow_features(tick_data: dict) -> dict:
    """
    Bloc 5 — Orderflow features (V9.1 Hedge Fund Addition)

    Delta: Directional pressure from candle body vs wicks over window
    Absorption: Smart money absorption pattern (large wicks + small body)
    """
    opens = tick_data.get("opens", [])
    closes = tick_data.get("closes", [])
    highs = tick_data.get("highs", [])
    lows = tick_data.get("lows", [])

    # Default values
    delta = 0.0
    absorption = 0

    window = 20
    n = min(window, len(opens), len(closes), len(highs), len(lows))

    if n >= 2:
        # === DELTA: Net buying vs selling pressure ===
        delta_sum = 0.0
        vol_sum = 0.0

        for j in range(-n, 0):
            direction = 1.0 if closes[j] > opens[j] else -1.0
            body = abs(closes[j] - opens[j])
            candle_range = highs[j] - lows[j] + 1e-9

            # Weight = volume proxy (candle body size) × efficiency (body/range)
            weight = body * (body / candle_range)

            delta_sum += direction * weight
            vol_sum += weight

        delta = float(delta_sum / (vol_sum + 1e-9))

        # === ABSORPTION: Detect smart money absorption ===
        # Current candle: large wicks + small body = absorption
        if len(closes) > 0 and len(opens) > 0:
            curr_open = opens[-1]
            curr_close = closes[-1]
            curr_high = highs[-1] if highs else 0.0
            curr_low = lows[-1] if lows else 0.0

            curr_body = abs(curr_close - curr_open)
            curr_range = curr_high - curr_low + 1e-9

            # Absorption: body < 30% of range
            if curr_range > 0 and (curr_body / curr_range) < 0.30:
                absorption = 1

    return {
        "delta": float(delta),
        "absorption": absorption,
    }



def build_features(tick_data: dict) -> dict:
    """
    Build XAUUSD-optimized feature vector from live tick/candle data.

    Expected tick_data keys (from ticks_v3.json or enriched context):
        closes    : list of recent close prices (≥20 elements)
        opens     : list of recent open prices (≥30 elements)
        highs     : list of recent high prices (≥30 elements)
        lows      : list of recent low prices (≥30 elements)
        atr       : current ATR value (float)
        atr_hist  : list of recent ATR values (≥20 elements)
        high      : current candle high
        low       : current candle low
        hour      : current hour (0-23) for session detection
        timestamp : ISO timestamp string (fallback for hour)
    """
    features = {}
    features.update(_trend_confirmation_features(tick_data))  # Bloc 0 — NIVEAU 1 Critical filters
    features.update(_volatility_features(tick_data))
    features.update(_liquidity_features(tick_data))
    features.update(_session_features(tick_data))
    features.update(_momentum_features(tick_data))
    features.update(_orderflow_features(tick_data))  # V9.1 Orderflow addition
    return features


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
    XAUUSD-optimized with StandardScaler normalization.
    """

    def __init__(self, model_path: str = MODEL_PATH, scaler_path: str = SCALER_PATH):
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.model = None
        self.scaler = None
        self._load_model()

    def _load_model(self):
        """Load saved model and scaler from disk if available."""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                logger.info(f"[ML] Model loaded from {self.model_path}")
            except Exception as e:
                logger.warning(f"[ML] Failed to load model: {e}")
                self.model = None

        if os.path.exists(self.scaler_path):
            try:
                self.scaler = joblib.load(self.scaler_path)
                logger.info(f"[ML] Scaler loaded from {self.scaler_path}")
            except Exception as e:
                logger.warning(f"[ML] Failed to load scaler: {e}")
                self.scaler = None

        if self.model is None:
            logger.info("[ML] No saved model found — will need training first")

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """
        Train XGBoost on feature matrix X and binary target y.
        Applies StandardScaler normalization before training.
        Returns training metrics dict.
        """
        if XGBClassifier is None:
            logger.error("[ML] xgboost not installed — cannot train")
            return {"error": "xgboost not installed"}

        if len(X) < 30:
            logger.warning(f"[ML] Only {len(X)} samples — minimum 30 required for training")
            return {"error": f"insufficient data ({len(X)} samples)"}

        # Fit and apply StandardScaler normalization
        if StandardScaler is not None:
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            joblib.dump(self.scaler, self.scaler_path)
            logger.info(f"[ML] Scaler fitted and saved to {self.scaler_path}")
        else:
            X_scaled = X
            logger.warning("[ML] sklearn not available — training without normalization")

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
        self.model.fit(X_scaled, y)

        # Save model
        joblib.dump(self.model, self.model_path)
        logger.info(f"[ML] Model trained on {len(X)} samples ({len(FEATURE_NAMES)} features), saved to {self.model_path}")

        # Return basic training metrics
        preds = self.model.predict(X_scaled)
        train_acc = float(np.mean(preds == y))
        return {
            "train_accuracy": round(train_acc, 4),
            "n_samples": len(X),
            "n_features": X.shape[1],
            "feature_names": FEATURE_NAMES,
        }

    def predict_proba(self, features: dict) -> float:
        """
        Predict probability of profitable trade (class 1).
        Returns float in [0, 1]. Falls back to 0.5 if no model.
        """
        if self.model is None:
            return 0.5

        arr = np.array([features_to_array(features)])

        # Apply scaler if available
        if self.scaler is not None:
            try:
                arr = self.scaler.transform(arr)
            except Exception as e:
                logger.warning(f"[ML] Scaler transform failed: {e}")

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

    # Build feature matrix and targets using XAUUSD-optimized features.
    # Each trade record should contain the features captured at entry time.
    X_list = []
    y_list = []
    for t in closed:
        feat = {
            # Bloc 0 — Trend Confirmation (NIVEAU 1 addition)
            "ema_20": t.get("ema_20", 0.0),
            "ema_50": t.get("ema_50", 0.0),
            "ema_slope": t.get("ema_slope", 0.0),
            "rsi": t.get("rsi", 50.0),
            "macd_histogram": t.get("macd_histogram", 0.0),
            # Bloc 1 — Volatility
            "atr": t.get("atr", 0.0),
            "atr_ratio": t.get("atr_ratio", 1.0),
            "range_ratio": t.get("range_ratio", 1.0),
            "vol_compression": t.get("vol_compression", 0.0),
            # Bloc 2 — Liquidity
            "imbalance": t.get("imbalance", 0.0),
            "wick_ratio": t.get("wick_ratio", 0.0),
            "liquidity_grab": t.get("liquidity_grab", 0),
            # Bloc 3 — Session
            "london": t.get("london", 0),
            "newyork": t.get("newyork", 0),
            "asia": t.get("asia", 0),
            # Bloc 4 — Momentum
            "ret_5": t.get("ret_5", 0.0),
            "ret_10": t.get("ret_10", 0.0),
            "momentum_acc": t.get("momentum_acc", 0.0),
            "break_high": t.get("break_high", 0),
            "break_low": t.get("break_low", 0),
            # Bloc 5 — Orderflow (V9.1)
            "delta": t.get("delta", 0.0),
            "absorption": t.get("absorption", 0),
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
