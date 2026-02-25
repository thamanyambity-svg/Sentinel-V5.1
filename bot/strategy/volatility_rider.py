"""
Volatility Rider Strategy — Volatility 100 Index (M10)
======================================================
Indicateur VolaRider (stochastique de l'écart-type) 0-100%.
Entrée: VolaRider franchit le seuil 21% (Fibonacci).
Direction: filtre tendance EMA (9/21).
SL: 3 × ATR(24).
Seuils: 21% (entrée), 89% (pic volatilité).
"""
import logging
import math
from typing import Dict, List, Optional, Any

logger = logging.getLogger("VOLA_RIDER")

# Paramètres stratégie
VOLARIDER_PERIOD = 14
VOLARIDER_K = 3
EMA_FAST = 9
EMA_SLOW = 21
ATR_PERIOD = 24
THRESHOLD_ENTRY = 21.0   # % - franchir au-dessus pour signal
THRESHOLD_PEAK = 89.0    # % - pic volatilité (pour sortie future)
SL_ATR_MULT = 3.0
MIN_M10_BARS = 30        # ~5h de M10


def _aggregate_m5_to_m10(candles: List[Dict]) -> List[Dict]:
    """Agrège M5 en M10. candles: [newest..oldest]. Retourne [oldest..newest]."""
    if len(candles) < 2:
        return []
    rev = list(reversed(candles))
    m10 = []
    for i in range(0, len(rev) - 1, 2):
        c1, c2 = rev[i], rev[i + 1]
        t1 = int(c1.get("t", 0))
        t2 = int(c2.get("t", 0))
        o1 = float(c1.get("o", 0))
        h1, l1, c1v = float(c1.get("h", 0)), float(c1.get("l", 0)), float(c1.get("c", 0))
        h2, l2, c2v = float(c2.get("h", 0)), float(c2.get("l", 0)), float(c2.get("c", 0))
        m10.append({
            "t": min(t1, t2),
            "o": o1,
            "h": max(h1, h2),
            "l": min(l1, l2),
            "c": c2v,
        })
    return m10


def _std_dev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var) if var > 0 else 0.0


def _ema(prices: List[float], period: int) -> float:
    if not prices or period < 1:
        return 0.0
    k = 2.0 / (period + 1)
    ema_val = prices[0]
    for p in prices[1:]:
        ema_val = p * k + ema_val * (1 - k)
    return ema_val


def _atr(bars: List[Dict], period: int = 14) -> float:
    if len(bars) < period + 1:
        return 0.0
    tr_sum = 0.0
    for i in range(len(bars) - period, len(bars)):
        h = float(bars[i].get("h", 0))
        l_ = float(bars[i].get("l", 0))
        prev_c = float(bars[i - 1].get("c", l_)) if i > 0 else l_
        tr = max(h - l_, abs(h - prev_c), abs(l_ - prev_c))
        tr_sum += tr
    return tr_sum / period if period > 0 else 0.0


def _vola_rider(bars: List[Dict], period: int = VOLARIDER_PERIOD, k_smooth: int = VOLARIDER_K) -> List[float]:
    """
    VolaRider = Stochastique appliquée à l'écart-type des closes.
    Retourne liste des valeurs VolaRider (0-100) pour chaque bar où calculable.
    """
    closes = [float(b.get("c", 0)) for b in bars]
    if len(closes) < period + k_smooth:
        return []

    std_values = []
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        std_values.append(_std_dev(window))

    if len(std_values) < k_smooth:
        return []

    # Stochastique: (current - min) / (max - min) * 100
    result = []
    for i in range(k_smooth - 1, len(std_values)):
        window = std_values[i - k_smooth + 1 : i + 1]
        mn = min(window)
        mx = max(window)
        if mx - mn > 1e-12:
            stoch = (std_values[i] - mn) / (mx - mn) * 100.0
        else:
            stoch = 50.0
        result.append(max(0.0, min(100.0, stoch)))
    return result


def _crosses_above(series: List[float], threshold: float, last_idx: int = 0) -> bool:
    """Vérifie si la série vient de franchir le seuil à la hausse (avant < seuil, maintenant >= seuil)."""
    if last_idx < 1 or last_idx >= len(series):
        return False
    prev = series[last_idx - 1]
    curr = series[last_idx]
    return prev < threshold <= curr


def get_volatility_rider_signal(
    symbol: str,
    m5_candles: List[Dict],
    point: float = 0.01,
) -> Optional[Dict[str, Any]]:
    """
    Analyse M5 candles, agrège en M10, applique Volatility Rider.
    Entrée: VolaRider franchit 21%, direction = filtre EMA.

    Retourne: { "side": "BUY"|"SELL", "sl_pips", "confidence", "reason", "strategy" } ou None.
    """
    if "Volatility 100" not in symbol and symbol != "Volatility 100 Index":
        return None

    m10 = _aggregate_m5_to_m10(m5_candles)
    if len(m10) < MIN_M10_BARS:
        return None

    # VolaRider (index 0 = oldest in our m10, last = newest)
    vr_series = _vola_rider(m10, VOLARIDER_PERIOD, VOLARIDER_K)
    if len(vr_series) < 2:
        return None

    current_vr = vr_series[-1]
    if not _crosses_above(vr_series, THRESHOLD_ENTRY, len(vr_series) - 1):
        return None

    # Filtre tendance EMA
    closes = [float(b.get("c", 0)) for b in m10]
    ema_fast = _ema(closes, EMA_FAST)
    ema_slow = _ema(closes, EMA_SLOW)
    if ema_fast <= 0 and ema_slow <= 0:
        return None

    if ema_fast > ema_slow:
        side = "BUY"
        trend = "BULLISH"
    else:
        side = "SELL"
        trend = "BEARISH"

    # SL = 3 × ATR(24)
    atr_val = _atr(m10, ATR_PERIOD)
    if atr_val <= 0:
        atr_val = (float(m10[-1].get("h", 0)) - float(m10[-1].get("l", 0))) * 2
    sl_dist = SL_ATR_MULT * atr_val
    sl_pips = int(round(sl_dist / point)) if point and point > 0 else 50
    sl_pips = max(15, min(80, sl_pips))

    return {
        "side": side,
        "sl_pips": sl_pips,
        "confidence": 0.78,
        "reason": f"VOLARIDER_CROSS21_{trend}",
        "strategy": "VOLATILITY_RIDER",
        "vola_rider": current_vr,
    }
