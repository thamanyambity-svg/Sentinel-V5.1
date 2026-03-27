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
    "imbalance": 0.35,
    "trend": 0.25,
    "ml": 0.25,
    "volatility": 0.15,
}

CONFLUENCE_THRESHOLD = 0.55


def compute_confluence(signals: dict) -> float:
    """
    Weighted confluence score ∈ [0, 1].
    Each signal component should be normalized to [0, 1] before calling.

    signals keys: 'imbalance', 'trend', 'ml', 'volatility'
    """
    score = 0.0
    for key, weight in CONFLUENCE_WEIGHTS.items():
        score += weight * signals.get(key, 0.0)
    return round(score, 4)


def normalize_imbalance_signal(imbalance: float, direction: str) -> float:
    """
    Normalize imbalance to [0, 1] based on alignment with direction.
    BUY: positive imbalance = good → higher score
    SELL: negative imbalance = good → higher score
    """
    if direction == "BUY":
        return max(0.0, min(1.0, 0.5 + imbalance))
    else:
        return max(0.0, min(1.0, 0.5 - imbalance))


def normalize_trend_signal(rsi: float, direction: str) -> float:
    """
    Normalize trend alignment to [0, 1].
    BUY: RSI > 50 is favorable
    SELL: RSI < 50 is favorable
    """
    if direction == "BUY":
        return max(0.0, min(1.0, rsi / 100.0))
    else:
        return max(0.0, min(1.0, 1.0 - rsi / 100.0))


def normalize_volatility_signal(atr_ratio: float) -> float:
    """
    Normalize volatility regime to [0, 1].
    Normal volatility (ratio ~1.0) = high score.
    Extreme volatility (ratio > 2.0) = low score (risky).
    Very low volatility (ratio < 0.5) = medium score.
    """
    if atr_ratio < 0.5:
        return 0.5
    elif atr_ratio > 2.0:
        return max(0.0, 1.0 - (atr_ratio - 1.0) * 0.5)
    else:
        return max(0.0, min(1.0, 1.0 - abs(atr_ratio - 1.0) * 0.3))


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
        Full signal evaluation pipeline.

        Args:
            tick_data: enriched tick/candle data dict
            direction: 'BUY' or 'SELL'

        Returns:
            dict with 'confluence', 'ml_prob', 'regime', 'params', 'decision'
        """
        # 1. Build features
        features = build_features(tick_data)

        # 2. ML prediction
        ml_prob = self.ml_model.predict_proba(features)

        # 3. Normalize signals for confluence
        imb_signal = normalize_imbalance_signal(
            features["imbalance"], direction
        )
        trend_signal = normalize_trend_signal(
            features["rsi"], direction
        )
        vol_signal = normalize_volatility_signal(features["atr_ratio"])

        # ML signal: predict_proba gives P(win) which is direction-agnostic
        # (model is trained on win/loss outcomes for both BUY and SELL trades)
        ml_signal = ml_prob

        # 4. Compute confluence
        signals = {
            "imbalance": imb_signal,
            "trend": trend_signal,
            "ml": ml_signal,
            "volatility": vol_signal,
        }
        confluence = compute_confluence(signals)

        # 5. Detect regime and get adaptive params
        trend_strength = (features["rsi"] - 50.0) / 50.0  # Proxy [-1, +1]
        regime = detect_market_regime(features["atr_ratio"], trend_strength)
        params = REGIME_PARAMS[regime]

        # 6. Decision
        decision = "EXECUTE" if confluence >= CONFLUENCE_THRESHOLD else "IGNORE"

        result = {
            "direction": direction,
            "confluence": confluence,
            "threshold": CONFLUENCE_THRESHOLD,
            "ml_prob": round(ml_prob, 4),
            "signals": {k: round(v, 4) for k, v in signals.items()},
            "regime": regime,
            "params": params,
            "decision": decision,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"[PIPELINE] {direction} | Confluence={confluence:.3f} "
            f"(threshold={CONFLUENCE_THRESHOLD}) | ML={ml_prob:.3f} | "
            f"Regime={regime} | → {decision}"
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
        """Run a demo backtest on synthetic data."""
        logger.info(f"[PIPELINE] Running demo backtest ({n_bars} bars)...")

        np.random.seed(42)
        price = 2000.0
        data = []
        for _ in range(n_bars):
            change = np.random.randn() * 2.0
            h = price + abs(np.random.randn() * 1.5)
            l = price - abs(np.random.randn() * 1.5)
            c = price + change
            data.append({
                "open": price, "high": h, "low": l, "close": c,
                "atr": 3.0 + np.random.randn() * 0.5,
                "rsi": 50 + np.random.randn() * 15,
                "spread": 0.5,
                "imbalance": np.random.randn() * 0.3,
            })
            price = c

        def strategy(window):
            last = window[-1]
            rsi = last.get("rsi", 50)
            imb = last.get("imbalance", 0)
            if rsi < 35 and imb > 0:
                return {"action": "BUY"}
            elif rsi > 65 and imb < 0:
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
        # Demo prediction
        tick_data = {
            "closes": [2000 + i * 0.5 for i in range(20)],
            "atr": 3.0,
            "atr_hist": [2.8, 3.0, 3.2, 2.9, 3.1] * 4,
            "high": 2010.5,
            "low": 2009.0,
            "imbalance": 0.25,
            "rsi": 42.0,
            "spread": 0.5,
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
