"""
RSI Extreme Reversal — Vol 100 Mean Reversion
==============================================
RSI suracheté (>75) → SELL | RSI survendu (<25) → BUY
Adapté au caractère mean-reverting du Vol 100.
"""
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("RSI_REV")

RSI_PERIOD = 14
RSI_OVERBOUGHT = 75
RSI_OVERSOLD = 25
MIN_BARS = RSI_PERIOD + 5


def _rsi(closes: List[float], period: int = RSI_PERIOD) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(len(closes) - period, len(closes)):
        chg = closes[i] - closes[i - 1]
        gains.append(max(0, chg))
        losses.append(max(0, -chg))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def get_rsi_extreme_signal(
    symbol: str,
    candles: List[Dict],
    point: float = 0.01,
) -> Optional[Dict[str, Any]]:
    """
    Signal mean reversion: RSI extrême → contre-tendance.
    Retourne { side, sl_pips, confidence, reason, strategy } ou None.
    """
    if "Volatility 100" not in symbol and symbol != "Volatility 100 Index":
        return None
    if not candles or len(candles) < MIN_BARS:
        return None

    closes = [float(c.get("c", 0)) for c in candles]
    rsi_val = _rsi(closes, RSI_PERIOD)
    if rsi_val is None:
        return None

    if rsi_val > RSI_OVERBOUGHT:
        side = "SELL"
        reason = f"RSI_OVERBOUGHT_{rsi_val:.0f}"
    elif rsi_val < RSI_OVERSOLD:
        side = "BUY"
        reason = f"RSI_OVERSOLD_{rsi_val:.0f}"
    else:
        return None

    # SL dynamique: plus extrême = SL plus serré (correction potentiellement violente)
    extreme = abs(rsi_val - 50) / 50.0
    sl_mult = 1.5 if extreme < 0.6 else 1.2
    atr_sum = 0.0
    for i in range(len(candles) - 15, len(candles)):
        if i > 0:
            h = float(candles[i].get("h", 0))
            l_ = float(candles[i].get("l", 0))
            prev_c = float(candles[i - 1].get("c", 0))
            atr_sum += max(h - l_, abs(h - prev_c), abs(l_ - prev_c))
    atr_val = atr_sum / 14 if atr_sum > 0 else 2.0
    sl_pips = max(20, min(80, int(round(atr_val * sl_mult / point))))

    # Confiance: RSI très extrême = confiance plus haute
    confidence = 0.72
    if rsi_val > 85 or rsi_val < 15:
        confidence = 0.80

    return {
        "side": side,
        "sl_pips": sl_pips,
        "confidence": confidence,
        "reason": reason,
        "strategy": "RSI_EXTREME_REVERSAL",
        "rsi": rsi_val,
    }
