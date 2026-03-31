"""
sentinel_pipeline.py — V9 Full Quant Pipeline for Sentinel
==========================================================
Orchestrates the complete data → ML → confluence → risk → execution pipeline
with a weekly retraining feedback loop.

Architecture:
    DATA → Feature Engine → ML Model → Confluence Engine → Risk (Kelly) → MT5 Execution
                              ↑
                       Backtest Engine
                              ↑
                       Trade History (feedback loop)

Usage:
    python3 sentinel_pipeline.py --retrain        # Retrain ML from trade_history.json
    python3 sentinel_pipeline.py --backtest       # Run backtest on synthetic data demo
    python3 sentinel_pipeline.py --validate       # Walk-forward validation
    python3 sentinel_pipeline.py --predict        # Single prediction from ticks_v3.json
"""

import json
import os
import sys
import logging
import numpy as np
from datetime import datetime

from sentinel_ml import (
    SentinelMLModel, build_features, features_to_array,
    train_from_trade_history, FEATURE_NAMES
)
from sentinel_backtest import (
    BacktestEngine, compute_metrics, validate_system,
    walk_forward, aggregate_walk_forward, simulate_trade
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("SENTINEL_PIPELINE")


# ============================================================
# §3 — Confluence V9 (ML + Imbalance + Trend + Volatility)
# ============================================================

CONFLUENCE_WEIGHTS = {
    "liquidity": 0.30,
    "volatility": 0.25,
    "ml": 0.25,
    "momentum": 0.20,
}

CONFLUENCE_THRESHOLD = 0.55


def compute_confluence(signals: dict) -> float:
    """
    Weighted confluence score ∈ [0, 1].
    Each signal component should be normalized to [0, 1] before calling.

    XAUUSD-optimized weights:
      liquidity (30%) + volatility (25%) + ML (25%) + momentum (20%)
    """
    score = 0.0
    for key, weight in CONFLUENCE_WEIGHTS.items():
        score += weight * signals.get(key, 0.0)
    return round(score, 4)


def normalize_liquidity_signal(imbalance: float, wick_ratio: float,
                               liquidity_grab: int, direction: str) -> float:
    """
    Normalize liquidity/imbalance signals to [0, 1] for XAUUSD.
    Combines wick imbalance, wick ratio intensity, and grab detection.
    """
    # Imbalance alignment: BUY favors positive, SELL favors negative
    if direction == "BUY":
        imb_score = max(0.0, min(1.0, 0.5 + imbalance * 0.5))
    else:
        imb_score = max(0.0, min(1.0, 0.5 - imbalance * 0.5))

    # Wick ratio: higher = more rejection activity = stronger signal
    wick_score = max(0.0, min(1.0, wick_ratio / 2.0))

    # Liquidity grab: strong confirmation
    grab_bonus = 0.15 if liquidity_grab else 0.0

    return max(0.0, min(1.0, 0.5 * imb_score + 0.3 * wick_score + grab_bonus + 0.05))


def normalize_volatility_signal(atr_ratio: float, range_ratio: float) -> float:
    """
    Normalize volatility regime to [0, 1] for XAUUSD.
    Expansion phases (atr_ratio > 1.2) = exploitable.
    Extreme compression or explosion = caution.
    """
    # ATR ratio sweet spot: 1.0-2.0 is favorable for XAUUSD
    if atr_ratio < 0.5:
        atr_score = 0.3  # Too compressed — wait
    elif atr_ratio > 3.0:
        atr_score = 0.2  # Extreme vol — dangerous
    elif atr_ratio > 1.2:
        atr_score = min(1.0, 0.6 + (atr_ratio - 1.0) * 0.2)  # Expansion = good
    else:
        atr_score = max(0.3, min(0.7, 1.0 - abs(atr_ratio - 1.0) * 0.5))

    # Range ratio confirms the current candle is impulsive
    range_score = max(0.0, min(1.0, range_ratio / 2.0))

    return 0.6 * atr_score + 0.4 * range_score


def normalize_momentum_signal(ret_5: float, momentum_acc: float,
                              break_high: int, break_low: int,
                              direction: str) -> float:
    """
    Normalize momentum structure to [0, 1] for XAUUSD.
    Combines return direction, acceleration, and structure breaks.
    """
    # Directional momentum alignment
    if direction == "BUY":
        mom_score = 0.5 + min(0.5, max(-0.5, ret_5 * 0.1))
        break_bonus = 0.2 if break_high else 0.0
    else:
        mom_score = 0.5 - min(0.5, max(-0.5, ret_5 * 0.1))
        break_bonus = 0.2 if break_low else 0.0

    # Acceleration confirmation
    acc_score = 0.5 + min(0.3, max(-0.3, momentum_acc * 0.05))

    return max(0.0, min(1.0, 0.4 * mom_score + 0.3 * acc_score + break_bonus + 0.1))


# ============================================================
# §4.2 — Market Regime Detection
# ============================================================

def detect_market_regime(atr_ratio: float, trend_strength: float) -> str:
    """
    Classify market regime for adaptive SL/TP/Risk.

    Returns: 'TREND', 'RANGE', or 'HIGH_VOL'
    """
    if atr_ratio > 2.0:
        return "HIGH_VOL"
    if abs(trend_strength) > 0.6:
        return "TREND"
    return "RANGE"


REGIME_PARAMS = {
    "TREND":    {"sl_mult": 1.2, "tp_mult": 3.0, "max_exposure": 6.0},
    "RANGE":    {"sl_mult": 0.8, "tp_mult": 1.5, "max_exposure": 3.0},
    "HIGH_VOL": {"sl_mult": 2.5, "tp_mult": 4.0, "max_exposure": 2.0},
}


# ============================================================
# §8 — Full Pipeline Orchestrator
# ============================================================

class SentinelPipeline:
    """
    Complete V9 quant pipeline: data → features → ML → confluence → execution.
    """

    def __init__(self):
        self.ml_model = SentinelMLModel()
        logger.info("[PIPELINE] V9 Sentinel Pipeline initialized")

    def evaluate_signal(self, tick_data: dict, direction: str) -> dict:
        """
        Full signal evaluation pipeline (XAUUSD-optimized).

        Args:
            tick_data: enriched tick/candle data dict
            direction: 'BUY' or 'SELL'

        Returns:
            dict with 'confluence', 'ml_prob', 'regime', 'params', 'decision'
        """
        # 1. Build XAUUSD-optimized features
        features = build_features(tick_data)

        # 2. ML prediction
        ml_prob = self.ml_model.predict_proba(features)

        # 3. Normalize signals for confluence (XAUUSD-optimized)
        liquidity_signal = normalize_liquidity_signal(
            features["imbalance"],
            features["wick_ratio"],
            features["liquidity_grab"],
            direction,
        )
        vol_signal = normalize_volatility_signal(
            features["atr_ratio"],
            features["range_ratio"],
        )
        momentum_signal = normalize_momentum_signal(
            features["ret_5"],
            features["momentum_acc"],
            features["break_high"],
            features["break_low"],
            direction,
        )

        # ML signal: predict_proba gives P(win) which is direction-agnostic
        ml_signal = ml_prob

        # 4. Compute confluence
        signals = {
            "liquidity": liquidity_signal,
            "volatility": vol_signal,
            "ml": ml_signal,
            "momentum": momentum_signal,
        }
        confluence = compute_confluence(signals)

        # 5. Detect regime and get adaptive params
        trend_strength = features.get("ret_5", 0.0) / (features.get("atr", 1.0) + 1e-9)
        regime = detect_market_regime(features["atr_ratio"], trend_strength)
        params = REGIME_PARAMS[regime]

        # 6. Decision — XAUUSD filter: require atr_ratio > 1.2 for high-confidence trades
        if confluence >= CONFLUENCE_THRESHOLD and features["atr_ratio"] > 1.2:
            decision = "EXECUTE"
        elif confluence >= CONFLUENCE_THRESHOLD:
            decision = "EXECUTE_CAUTIOUS"
        else:
            decision = "IGNORE"

        result = {
            "direction": direction,
            "confluence": confluence,
            "threshold": CONFLUENCE_THRESHOLD,
            "ml_prob": round(ml_prob, 4),
            "signals": {k: round(v, 4) for k, v in signals.items()},
            "features": {
                "atr_ratio": round(features["atr_ratio"], 4),
                "imbalance": round(features["imbalance"], 4),
                "wick_ratio": round(features["wick_ratio"], 4),
                "liquidity_grab": features["liquidity_grab"],
                "vol_compression": round(features["vol_compression"], 4),
                "break_high": features["break_high"],
                "break_low": features["break_low"],
                "session": {
                    "london": features["london"],
                    "newyork": features["newyork"],
                    "asia": features["asia"],
                },
            },
            "regime": regime,
            "params": params,
            "decision": decision,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"[PIPELINE] {direction} | Confluence={confluence:.3f} "
            f"(threshold={CONFLUENCE_THRESHOLD}) | ML={ml_prob:.3f} | "
            f"ATR_Ratio={features['atr_ratio']:.2f} | Regime={regime} | → {decision}"
        )

        return result

    def retrain(self, history_path: str = "trade_history.json") -> dict:
        """Retrain ML model from trade history (weekly feedback loop)."""
        logger.info("[PIPELINE] Starting ML retraining...")
        result = train_from_trade_history(history_path)
        if "error" not in result:
            # Reload model
            self.ml_model = SentinelMLModel()
            logger.info(f"[PIPELINE] Retraining complete: {result}")
        else:
            logger.warning(f"[PIPELINE] Retraining failed: {result}")
        return result

    def run_backtest_demo(self, n_bars: int = 500) -> dict:
        """Run a demo backtest on synthetic XAUUSD data."""
        logger.info(f"[PIPELINE] Running XAUUSD demo backtest ({n_bars} bars)...")

        np.random.seed(42)
        price = 2000.0
        data = []
        for i in range(n_bars):
            change = np.random.randn() * 2.0
            h = price + abs(np.random.randn() * 1.5)
            l = price - abs(np.random.randn() * 1.5)
            c = price + change
            hour = i % 24  # simulate hourly bars
            data.append({
                "open": price, "high": h, "low": l, "close": c,
                "atr": 3.0 + np.random.randn() * 0.5,
                "rsi": 50 + np.random.randn() * 15,
                "spread": 0.5,
                "imbalance": np.random.randn() * 0.3,
                "hour": hour,
            })
            price = c

        def strategy(window):
            last = window[-1]
            rsi = last.get("rsi", 50)
            imb = last.get("imbalance", 0)
            hour = last.get("hour", 12)
            # XAUUSD: only trade during London/NY sessions
            in_session = 8 <= hour <= 17
            if in_session and rsi < 35 and imb > 0:
                return {"action": "BUY"}
            elif in_session and rsi > 65 and imb < 0:
                return {"action": "SELL"}
            return None

        engine = BacktestEngine()
        trades, equity = engine.run(data, strategy)
        metrics = compute_metrics(trades)
        validation = validate_system(metrics)

        return {
            "trades": len(trades),
            "equity": equity,
            "metrics": metrics,
            "validation": validation,
        }


def main():
    pipeline = SentinelPipeline()

    if "--retrain" in sys.argv:
        result = pipeline.retrain()
        print(f"\n[PIPELINE] Retrain result: {json.dumps(result, indent=2)}")

    elif "--backtest" in sys.argv:
        result = pipeline.run_backtest_demo()
        print(f"\n[PIPELINE] Backtest result: {json.dumps(result, indent=2)}")

    elif "--predict" in sys.argv:
        # Demo prediction with XAUUSD-optimized features
        closes = [2000 + i * 0.5 for i in range(30)]
        highs = [c + 1.5 for c in closes]
        lows = [c - 1.2 for c in closes]
        opens = [c - 0.3 for c in closes]
        tick_data = {
            "closes": closes,
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "atr": 3.0,
            "atr_hist": [2.8, 3.0, 3.2, 2.9, 3.1] * 6,
            "high": 2015.5,
            "low": 2014.0,
            "hour": 10,  # London session
        }
        result = pipeline.evaluate_signal(tick_data, "BUY")
        print(f"\n[PIPELINE] Signal evaluation: {json.dumps(result, indent=2)}")

    else:
        print("Usage:")
        print("  python3 sentinel_pipeline.py --retrain    # Retrain ML model")
        print("  python3 sentinel_pipeline.py --backtest   # Run demo backtest")
        print("  python3 sentinel_pipeline.py --predict    # Demo prediction")
        print("  python3 sentinel_pipeline.py --validate   # Walk-forward validation")


if __name__ == "__main__":
    main()
