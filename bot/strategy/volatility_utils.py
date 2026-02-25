"""
Volatility 100 — Utilitaires ATR dynamiques
============================================
SL basé sur ATR et ajustement du risque selon régime de volatilité.
"""
from typing import Dict, List, Optional

ATR_PERIOD = 14
ATR_MA_PERIOD = 20
ATR_SL_MULT = 1.5
ATR_HIGH_RISK_MULT = 0.5   # Réduire quand ATR élevé
ATR_LOW_RISK_MULT = 1.2    # Augmenter quand ATR calme


def _atr(candles: List[Dict], period: int = ATR_PERIOD) -> float:
    if len(candles) < period + 1:
        return 0.0
    tr_sum = 0.0
    for i in range(len(candles) - period, len(candles)):
        h = float(candles[i].get("h", 0))
        l_ = float(candles[i].get("l", 0))
        prev_c = float(candles[i - 1].get("c", l_)) if i > 0 else l_
        tr = max(h - l_, abs(h - prev_c), abs(l_ - prev_c))
        tr_sum += tr
    return tr_sum / period if period > 0 else 0.0


def get_atr_sl_pips(candles: List[Dict], point: float = 0.01, mult: float = ATR_SL_MULT) -> int:
    """
    SL dynamique = mult × ATR (convertis en pips).
    Évite les SL trop serrés pendant les pics et trop larges au calme.
    """
    if not candles or point <= 0:
        return 50
    atr_val = _atr(candles, ATR_PERIOD)
    if atr_val <= 0:
        return 50
    sl_dist = atr_val * mult
    sl_pips = int(round(sl_dist / point))
    return max(15, min(120, sl_pips))


def get_atr_risk_multiplier(candles: List[Dict]) -> float:
    """
    ATR > MA(ATR) → volatilité haute → réduire risque (0.5).
    ATR < MA(ATR) → volatilité calme → augmenter (1.2).
    """
    if len(candles) < ATR_PERIOD + ATR_MA_PERIOD:
        return 1.0
    atr_val = _atr(candles, ATR_PERIOD)
    atr_values = []
    for i in range(ATR_MA_PERIOD):
        start = len(candles) - ATR_MA_PERIOD - ATR_PERIOD + i
        if start >= 0:
            window = candles[start : start + ATR_PERIOD + 1]
            if len(window) >= ATR_PERIOD + 1:
                a = _atr(window, ATR_PERIOD)
                atr_values.append(a)
    if not atr_values:
        return 1.0
    ma_atr = sum(atr_values) / len(atr_values)
    if ma_atr <= 0:
        return 1.0
    if atr_val > ma_atr * 1.1:
        return ATR_HIGH_RISK_MULT
    if atr_val < ma_atr * 0.9:
        return ATR_LOW_RISK_MULT
    return 1.0
