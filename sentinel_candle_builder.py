"""
Sentinel Candle Builder — NIVEAU 2 Multi-Timeframe Support
===========================================================
Constructs M5/M15/H1/D1 candles from M1 tick data for multi-timeframe bias features.

This solves the MT5 limitation: we only get M1 ticks, but need higher TF context.
"""

import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Tuple


class CandleBuilder:
    """
    Build higher timeframe candles from tick/candle data.
    """

    TIMEFRAME_MINUTES = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "H1": 60,
        "D1": 1440,
    }

    def __init__(self, base_timeframe: str = "M1"):
        self.base_tf = base_timeframe
        self.base_minutes = self.TIMEFRAME_MINUTES[base_timeframe]

    def build_candles(self, ticks: List[Dict], target_tf: str) -> List[Dict]:
        """
        Build target timeframe candles from tick data.

        Args:
            ticks: List of tick dicts with 'time', 'open', 'high', 'low', 'close'
            target_tf: Target timeframe ('M5', 'M15', 'H1', 'D1')

        Returns:
            List of candle dicts
        """
        if target_tf == self.base_tf:
            return ticks

        target_minutes = self.TIMEFRAME_MINUTES[target_tf]
        candles_dict = defaultdict(lambda: {
            'open': None,
            'high': -np.inf,
            'low': np.inf,
            'close': None,
            'volume': 0,
            'time': None,
        })

        for tick in ticks:
            if not tick.get('time') or not tick.get('close'):
                continue

            # Determine candle bucket (aligned to UTC)
            timestamp = tick['time']
            bucket_time = (timestamp // (target_minutes * 60)) * (target_minutes * 60)

            candle = candles_dict[bucket_time]

            # First tick of candle = open
            if candle['open'] is None:
                candle['open'] = tick.get('open', tick['close'])
                candle['time'] = bucket_time

            # Update OHLC
            candle['high'] = max(candle['high'], tick.get('high', tick['close']))
            candle['low'] = min(candle['low'], tick.get('low', tick['close']))
            candle['close'] = tick['close']
            candle['volume'] += tick.get('volume', 1)

        # Convert to sorted list
        result = []
        for bucket_time in sorted(candles_dict.keys()):
            candle = candles_dict[bucket_time]
            if candle['open'] is not None:
                # Fix infinities
                if candle['high'] == -np.inf:
                    candle['high'] = candle['close']
                if candle['low'] == np.inf:
                    candle['low'] = candle['close']
                result.append({
                    'time': int(candle['time']),
                    'open': float(candle['open']),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'close': float(candle['close']),
                    'volume': int(candle['volume']),
                })

        return result

    def build_all_timeframes(self, ticks: List[Dict]) -> Dict[str, List[Dict]]:
        """Build all standard timeframes from tick data."""
        return {
            'M1': ticks,
            'M5': self.build_candles(ticks, 'M5'),
            'M15': self.build_candles(ticks, 'M15'),
            'H1': self.build_candles(ticks, 'H1'),
            'D1': self.build_candles(ticks, 'D1'),
        }


def ema(series: List[float], period: int) -> float:
    """Calculate EMA of a series."""
    if len(series) < period:
        return np.mean(series) if series else 0.0

    multiplier = 2.0 / (period + 1)
    ema_val = float(np.mean(series[-period:]))

    for price in series[-period:]:
        ema_val = price * multiplier + ema_val * (1 - multiplier)

    return float(ema_val)


def compute_mtf_features(candles_by_tf: Dict[str, List[Dict]]) -> Dict[str, float]:
    """
    Compute multi-timeframe bias features from candles.

    NIVEAU 2: 8 features for institutional alignment
    """
    features = {}

    # Extract closes for each timeframe
    m1_closes = [c['close'] for c in candles_by_tf.get('M1', [])]
    m5_closes = [c['close'] for c in candles_by_tf.get('M5', [])]
    m15_closes = [c['close'] for c in candles_by_tf.get('M15', [])]
    h1_closes = [c['close'] for c in candles_by_tf.get('H1', [])]
    d1_closes = [c['close'] for c in candles_by_tf.get('D1', [])]

    # 1. HTF_bias (H1): EMA50 > EMA200?
    if len(h1_closes) >= 50:
        h1_ema50 = ema(h1_closes, 50)
        h1_ema200 = ema(h1_closes, min(200, len(h1_closes)))
        features['htf_bias'] = float(1.0 if h1_ema50 > h1_ema200 else -1.0)
    else:
        features['htf_bias'] = 0.0

    # 2. D1_trend: Daily direction
    if len(d1_closes) >= 2:
        d1_ema20 = ema(d1_closes, 20) if len(d1_closes) >= 20 else d1_closes[-1]
        d1_direction = float(1.0 if d1_closes[-1] > d1_ema20 else -1.0)
        features['d1_trend'] = d1_direction
    else:
        features['d1_trend'] = 0.0

    # 3. M5_structure: Price > EMA20 on M5?
    if len(m5_closes) >= 20:
        m5_ema20 = ema(m5_closes, 20)
        features['m5_structure'] = float(1.0 if m5_closes[-1] > m5_ema20 else -1.0)
    else:
        features['m5_structure'] = 0.0

    # 4. M15_confirmation: Price > EMA50 on M15?
    if len(m15_closes) >= 50:
        m15_ema50 = ema(m15_closes, 50)
        features['m15_confirmation'] = float(1.0 if m15_closes[-1] > m15_ema50 else -1.0)
    else:
        features['m15_confirmation'] = 0.0

    # 5. HTF_momentum: H1 momentum (ret_20)
    if len(h1_closes) >= 20:
        h1_ret = h1_closes[-1] - h1_closes[-20]
        features['htf_momentum'] = float(h1_ret / (abs(h1_closes[-20]) + 1e-9))
    else:
        features['htf_momentum'] = 0.0

    # 6. D1_resistance_distance: Distance to daily levels
    if len(d1_closes) >= 10:
        d1_high_10 = max(d1_closes[-10:])
        d1_low_10 = min(d1_closes[-10:])
        d1_mid = (d1_high_10 + d1_low_10) / 2
        current = m1_closes[-1] if m1_closes else d1_closes[-1]
        distance = (current - d1_mid) / ((d1_high_10 - d1_low_10) + 1e-9)
        features['d1_resistance_distance'] = float(np.clip(distance, -1.0, 1.0))
    else:
        features['d1_resistance_distance'] = 0.0

    # 7. HT_volatility_regime: H1 volatility compression (low vol = good entry)
    if len(h1_closes) >= 20:
        h1_ranges = []
        h1_candles = candles_by_tf.get('H1', [])
        for candle in h1_candles[-20:]:
            h1_ranges.append(candle['high'] - candle['low'])

        if h1_ranges:
            avg_range = np.mean(h1_ranges)
            current_range = h1_candles[-1]['high'] - h1_candles[-1]['low']
            compression = current_range / (avg_range + 1e-9)
            features['ht_volatility_regime'] = float(1.0 if compression < 0.7 else 0.0)
        else:
            features['ht_volatility_regime'] = 0.0
    else:
        features['ht_volatility_regime'] = 0.0

    # 8. Cross_TF_alignment: Do all TF agree? (M5, M15, H1 all bullish or all bearish)
    m5_bull = 1.0 if features.get('m5_structure', 0) > 0 else 0.0
    m15_bull = 1.0 if features.get('m15_confirmation', 0) > 0 else 0.0
    h1_bull = 1.0 if features.get('htf_bias', 0) > 0 else 0.0

    alignment = (m5_bull + m15_bull + h1_bull) / 3.0
    features['cross_tf_alignment'] = float(alignment)

    return features


if __name__ == "__main__":
    # Test: Build candles from synthetic M1 data
    import json
    from datetime import datetime

    # Generate test M1 ticks
    test_ticks = []
    base_price = 4570.0
    base_time = int(datetime.now().timestamp())

    for i in range(500):
        move = np.random.normal(0, 0.5)
        base_price += move
        test_ticks.append({
            'time': base_time + (i * 60),  # M1 spacing
            'open': base_price,
            'high': base_price + abs(move),
            'low': base_price - abs(move),
            'close': base_price + move,
            'volume': 1,
        })

    # Build candles
    builder = CandleBuilder()
    candles_by_tf = builder.build_all_timeframes(test_ticks)

    print("✅ Candle Builder Test:")
    for tf, candles in candles_by_tf.items():
        print(f"   {tf}: {len(candles)} candles")

    # Compute MTF features
    features = compute_mtf_features(candles_by_tf)
    print("\n✅ MTF Features (NIVEAU 2):")
    for name, value in features.items():
        print(f"   {name}: {value:.4f}")
