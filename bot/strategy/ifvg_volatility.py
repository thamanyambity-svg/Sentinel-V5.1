"""
IFVG Strategy — Volatility 100/75 Index (5 min)
Entry using Implied Fair Value Gap on M5 timeframe.
Steps: Market structure -> Impulsive candle -> IFVG zone -> Entry on rejection.
"""
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("IFVG_VOL")

# Bars to analyse (oldest first: [0] = oldest)
LOOKBACK_SWING = 15
LOOKBACK_IMPULSE = 5
MIN_BARS = 20
# Impulsive candle: body >= ATR * this ratio
IMPULSE_BODY_ATR_RATIO = 0.4
# FVG: min gap size (points) to count as valid
MIN_FVG_POINTS = 2.0
# Rejection: close beyond zone by at least this ratio of zone size
REJECTION_RATIO = 0.3


def _candle_body_size(c: Dict) -> float:
    o, c = float(c.get("o", 0)), float(c.get("c", 0))
    return abs(c - o)


def _atr(candles: List[Dict], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    tr_sum = 0.0
    for i in range(len(candles) - period, len(candles)):
        h = float(candles[i]["h"])
        l_ = float(candles[i]["l"])
        prev_c = float(candles[i - 1]["c"]) if i > 0 else l_
        tr = max(h - l_, abs(h - prev_c), abs(l_ - prev_c))
        tr_sum += tr
    return tr_sum / period


def _swing_highs_lows(candles: List[Dict], window: int = 3) -> tuple:
    """Return (list of swing_high indices, list of swing_low indices)."""
    highs, lows = [], []
    for i in range(window, len(candles) - window):
        h = float(candles[i]["h"])
        l_ = float(candles[i]["l"])
        is_high = all(float(candles[j]["h"]) <= h for j in range(i - window, i + window + 1) if j != i)
        is_low = all(float(candles[j]["l"]) >= l_ for j in range(i - window, i + window + 1) if j != i)
        if is_high:
            highs.append(i)
        if is_low:
            lows.append(i)
    return highs, lows


def _structure_bearish(highs: List[int], lows: List[int], candles: List[Dict]) -> bool:
    """LH/LL: lower highs and lower lows."""
    if len(highs) < 2 or len(lows) < 2:
        return False
    h1, h2 = float(candles[highs[-2]]["h"]), float(candles[highs[-1]]["h"])
    l1, l2 = float(candles[lows[-2]]["l"]), float(candles[lows[-1]]["l"])
    return h2 < h1 and l2 < l1


def _structure_bullish(highs: List[int], lows: List[int], candles: List[Dict]) -> bool:
    """HH/HL."""
    if len(highs) < 2 or len(lows) < 2:
        return False
    h1, h2 = float(candles[highs[-2]]["h"]), float(candles[highs[-1]]["h"])
    l1, l2 = float(candles[lows[-2]]["l"]), float(candles[lows[-1]]["l"])
    return h2 > h1 and l2 > l1


def _find_bearish_fvg(candles: List[Dict], atr_val: float) -> Optional[Dict]:
    """
    Bearish FVG: gap between candle[i] low and candle[i+1] high (impulsive down candle at i+1).
    Zone = (candle[i+1].high, candle[i].low). Price must have left the zone (rejection).
    """
    for i in range(len(candles) - 4, 0, -1):
        if i + 2 >= len(candles):
            continue
        c_prev = candles[i]
        c_imp = candles[i + 1]
        c_next = candles[i + 2]
        o_imp = float(c_imp["o"])
        c_imp_val = float(c_imp["c"])
        h_imp = float(c_imp["h"])
        l_prev = float(c_prev["l"])
        h_prev = float(c_prev["h"])
        # Bearish impulsive: close < open, body substantial
        if c_imp_val >= o_imp:
            continue
        body = o_imp - c_imp_val
        if atr_val > 0 and body < atr_val * IMPULSE_BODY_ATR_RATIO:
            continue
        # FVG: gap between prev low and imp high (down move leaves gap above)
        gap_high = min(h_imp, h_prev)
        gap_low = l_prev
        if gap_low <= gap_high:
            continue
        gap_size = gap_low - gap_high
        if gap_size < MIN_FVG_POINTS:
            continue
        # Next candle should not fully fill the FVG (body not covering zone)
        # Rejection: current/last bar closed below zone
        last = candles[-1]
        close_last = float(last["c"])
        if close_last >= gap_low:
            continue
        # Zone was tested and rejected (price came back into zone then closed below)
        return {
            "zone_high": gap_low,
            "zone_low": gap_high,
            "entry": close_last,
            "sl": gap_low + gap_size * 0.1,
            "tp": gap_low - gap_size * 1.5,
            "bar_index": i + 1,
        }
    return None


def _find_bullish_fvg(candles: List[Dict], atr_val: float) -> Optional[Dict]:
    """Bullish FVG: gap between candle[i] high and candle[i+1] low (impulsive up)."""
    for i in range(len(candles) - 4, 0, -1):
        if i + 2 >= len(candles):
            continue
        c_prev = candles[i]
        c_imp = candles[i + 1]
        o_imp = float(c_imp["o"])
        c_imp_val = float(c_imp["c"])
        l_imp = float(c_imp["l"])
        h_prev = float(c_prev["h"])
        l_prev = float(c_prev["l"])
        if c_imp_val <= o_imp:
            continue
        body = c_imp_val - o_imp
        if atr_val > 0 and body < atr_val * IMPULSE_BODY_ATR_RATIO:
            continue
        gap_low = max(l_imp, l_prev)
        gap_high = h_prev
        if gap_high <= gap_low:
            continue
        gap_size = gap_high - gap_low
        if gap_size < MIN_FVG_POINTS:
            continue
        last = candles[-1]
        close_last = float(last["c"])
        if close_last <= gap_high:
            continue
        return {
            "zone_high": gap_high,
            "zone_low": gap_low,
            "entry": close_last,
            "sl": gap_low - gap_size * 0.1,
            "tp": gap_high + gap_size * 1.5,
            "bar_index": i + 1,
        }
    return None


def get_ifvg_signal(symbol: str, candles: List[Dict], point: float = 0.01) -> Optional[Dict[str, Any]]:
    """
    Analyse M5 candles (oldest first) and return IFVG signal if conditions are met.
    candles: list of {"t", "o", "h", "l", "c"}
    point: symbol point (e.g. 0.01 for Volatility indices)
    Returns: { "side": "BUY"|"SELL", "entry", "sl", "tp", "sl_pips", "confidence", "reason" } or None
    """
    if not candles or len(candles) < MIN_BARS:
        return None
    # Normalise to list of dicts
    bars = []
    for c in candles:
        if isinstance(c, dict):
            bars.append(c)
        else:
            bars.append(dict(c))
    candles = bars

    atr_val = _atr(candles)
    if atr_val <= 0:
        atr_val = (float(candles[-1]["h"]) - float(candles[-1]["l"])) * 2

    highs, lows = _swing_highs_lows(candles, window=2)
    bearish_structure = _structure_bearish(highs, lows, candles)
    bullish_structure = _structure_bullish(highs, lows, candles)

    # Prefer SELL if bearish structure
    if bearish_structure:
        fvg = _find_bearish_fvg(candles, atr_val)
        if fvg:
            sl_dist = abs(fvg["sl"] - fvg["entry"])
            sl_pips = int(round(sl_dist / point)) if point and point > 0 else 50
            if sl_pips < 5:
                sl_pips = 5
            return {
                "side": "SELL",
                "entry": fvg["entry"],
                "sl": fvg["sl"],
                "tp": fvg["tp"],
                "sl_pips": sl_pips,
                "confidence": 0.75,
                "reason": "IFVG_SELL_M5",
                "strategy": "IFVG_SCALP",
            }

    if bullish_structure:
        fvg = _find_bullish_fvg(candles, atr_val)
        if fvg:
            sl_dist = abs(fvg["entry"] - fvg["sl"])
            sl_pips = int(round(sl_dist / point)) if point and point > 0 else 50
            if sl_pips < 5:
                sl_pips = 5
            return {
                "side": "BUY",
                "entry": fvg["entry"],
                "sl": fvg["sl"],
                "tp": fvg["tp"],
                "sl_pips": sl_pips,
                "confidence": 0.75,
                "reason": "IFVG_BUY_M5",
                "strategy": "IFVG_SCALP",
            }

    return None
