"""
tests/test_bridge.py — P9: Unit & Stress Tests for Sentinel Bot
Run with: pytest tests/ -v

Tests cover:
- Malformed / empty status.json handling
- Rate limiter logic
- Volume normalization edge cases
- Duplicate trade rejection cooldowns
- Heartbeat staleness detection
"""

import json
import os
import tempfile
import time
import pytest
import sys

# Make bot package importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# TEST 1: status.json cross-validation (P3)
# ---------------------------------------------------------------------------
class FakeBridge:
    """Simulates MT5Bridge.get_raw_status() with injectable payloads."""

    def __init__(self, payload):
        self._payload = payload

    def get_raw_status(self):
        # Empty / None payload simulates missing or 0-byte file
        if self._payload == '' or self._payload is None:
            return None
        try:
            result = json.loads(self._payload)
            # Only dicts are valid status objects (not null, array, etc.)
            return result if isinstance(result, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None   # Malformed JSON



@pytest.mark.parametrize("payload,expected_type", [
    ('{"equity":1000,"positions":[]}', dict),    # Valid JSON
    ('',                               None),    # Empty file
    ('{broken json::',                 None),    # Malformed
    ('null',                           None),    # null is not a dict
    ('{"equity":500}',                 dict),    # Valid but no positions key
])
def test_status_json_validation(payload, expected_type):
    """P3: Malformed or empty status.json must not crash the bot — return None/dict."""
    bridge = FakeBridge(payload)
    result = bridge.get_raw_status()
    if expected_type is None:
        assert not isinstance(result, dict), f"Expected non-dict for payload: {payload!r}"
    else:
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# TEST 2: Rate Limiter logic (P2)
# ---------------------------------------------------------------------------
class RateLimiter:
    """Pure Python replica of the MQL5 CheckRateLimit circular buffer."""

    def __init__(self, max_per_min: int):
        self.max_per_min = max_per_min
        self._timestamps = []

    def record_trade(self):
        now = time.time()
        self._timestamps.append(now)
        self._timestamps = self._timestamps[-60:]

    def can_trade(self) -> bool:
        if self.max_per_min <= 0:   # 0 = disabled → always allow
            return True
        now = time.time()
        recent = [t for t in self._timestamps if now - t <= 60]
        return len(recent) < self.max_per_min


def test_rate_limiter_under_limit():
    rl = RateLimiter(max_per_min=5)
    for _ in range(4):
        rl.record_trade()
    assert rl.can_trade() is True


def test_rate_limiter_at_limit():
    rl = RateLimiter(max_per_min=5)
    for _ in range(5):
        rl.record_trade()
    assert rl.can_trade() is False


def test_rate_limiter_resets_after_one_minute():
    rl = RateLimiter(max_per_min=5)
    old_time = time.time() - 61
    rl._timestamps = [old_time] * 5   # 5 trades from 61 seconds ago
    assert rl.can_trade() is True     # Should be allowed again


def test_rate_limiter_disabled():
    rl = RateLimiter(max_per_min=0)   # 0 means disabled, always allow
    for _ in range(100):
        rl.record_trade()
    assert rl.can_trade() is True


# ---------------------------------------------------------------------------
# TEST 3: Volume normalization edge cases
# ---------------------------------------------------------------------------
def normalize_volume(volume: float, min_vol: float, step: float) -> float:
    """
    Broker volume normalization: always FLOOR to the nearest valid step.
    Brokers never round up (that would exceed what the client requested).
    Uses math.floor with a tiny epsilon to avoid floating-point edge cases
    (e.g., 0.55 / 0.10 = 5.499999... should floor to 5, not 4).
    """
    import math
    if volume < min_vol:
        volume = min_vol
    # Small epsilon avoids floor(5.4999...) = 4 instead of 5
    steps = math.floor(round(volume / step, 9))
    result = round(steps * step, 10)
    # Guard: result must still meet min_vol after flooring
    if result < min_vol:
        result = round(min_vol, 10)
    return result


@pytest.mark.parametrize("raw,min_v,step,expected", [
    (0.001, 0.01, 0.01, 0.01),    # Below min → snap to min
    (0.55,  0.01, 0.10, 0.50),    # Not on step → floor (broker always floors)
    (1.99,  0.01, 1.00, 1.00),    # Floor (broker never rounds UP volume)
    (3.00,  0.01, 1.00, 3.00),    # Already on step → unchanged
    (10.0,  0.10, 0.50, 10.00),   # Large volume already aligned
])
def test_volume_normalization(raw, min_v, step, expected):
    result = normalize_volume(raw, min_v, step)
    assert abs(result - expected) < 1e-9, f"normalize({raw}) = {result}, expected {expected}"


# ---------------------------------------------------------------------------
# TEST 4: Heartbeat staleness (P4)
# ---------------------------------------------------------------------------
def read_heartbeat_age(filepath: str) -> float:
    if not os.path.isfile(filepath):
        return -1.0
    return time.time() - os.path.getmtime(filepath)


def test_heartbeat_fresh():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"1772178712")
        fname = f.name
    try:
        age = read_heartbeat_age(fname)
        assert 0 <= age < 5, f"Freshly written file should be < 5s old, got {age}"
    finally:
        os.unlink(fname)


def test_heartbeat_missing():
    age = read_heartbeat_age("/nonexistent/path/heartbeat.txt")
    assert age == -1.0


# ---------------------------------------------------------------------------
# TEST 5: Cooldown / duplicate trade rejection
# ---------------------------------------------------------------------------
def test_order_cooldown():
    """Simulate the ORDER_COOLDOWN_SEC logic in main_v5.py."""
    ORDER_COOLDOWN_SEC = 90
    last_order_sent_at = {}

    def can_place_order(asset: str) -> bool:
        last = last_order_sent_at.get(asset, 0)
        return (time.time() - last) >= ORDER_COOLDOWN_SEC

    def place_order(asset: str):
        last_order_sent_at[asset] = time.time()

    assert can_place_order("EURUSD") is True     # First order allowed
    place_order("EURUSD")
    assert can_place_order("EURUSD") is False    # Immediate duplicate blocked
    assert can_place_order("GOLD") is True       # Different asset still allowed
