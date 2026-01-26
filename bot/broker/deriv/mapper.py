"""
Mapping trade interne -> payload Deriv.
Lecture seule (proposal).
"""

SYMBOL_MAP = {
    "V75": "R_75",
    "Vol_100_1s": "Volatility 100 (1s) Index",
    # EXNESS MAPPING
    "EURUSD": "EURUSD",
    "XAUUSD": "XAUUSDm", # Check if suffix 'm', 'z' etc needed on Exness Demo (or just XAUUSD)
    # Usually standard demo is XAUUSD or XAUUSDm
    "R_100": "R_100",
    "R_75": "R_75",
    "R_50": "R_50",
    "R_25": "R_25",
    "R_10": "R_10",
    "1HZ10V": "1HZ10V",
    "1HZ100V": "1HZ100V",
    "STP": "STP",
    "EURUSD": "frxEURUSD", # Exness -> Deriv Data
    "XAUUSD": "frxXAUUSD", # Exness -> Deriv Data
}

SIDE_MAP = {
    "BUY": "VANILLALONGCALL",
    "SELL": "VANILLALONGPUT",
}

def map_to_proposal(trade: dict) -> dict:
    # Debug log
    if trade["asset"] not in SYMBOL_MAP:
        print(f"DEBUG MAPPER ERROR: '{trade['asset']}' not in KEYS: {list(SYMBOL_MAP.keys())}")
        raise ValueError("UNSUPPORTED_ASSET")

    if trade["side"] not in SIDE_MAP:
        raise ValueError("UNSUPPORTED_SIDE")

    # Parse Duration (e.g., "1m", "5t")
    dur_str = str(trade.get("duration", "1m"))
    unit = dur_str[-1].lower()
    val = int(dur_str[:-1]) if dur_str[:-1].isdigit() else 1
    
    # Validation Unit
    if unit not in ['t', 's', 'm', 'h', 'd']:
        unit = 'm' # Default

    payload = {
        "proposal": 1,
        "amount": 0.50, # HARD LOCK: Strictly 0.50 USD
        "basis": "stake",
        "contract_type": SIDE_MAP[trade["side"]],
        "currency": "USD",
        "symbol": SYMBOL_MAP.get(trade["asset"], trade["asset"]),
        "duration": val,
        "duration_unit": unit,
    }
    
    # 🛡️ HARD SL (Parachute) - Only if supported by contract (e.g. Multipliers)
    # Binary Options do not support 'limit_order' in proposal typically.
    # But we add it generically if 'limit_order' is present in trade.
    if "limit_order" in trade:
        payload["limit_order"] = trade["limit_order"]

    return payload

# 🔒 Alias de compatibilité (broker.py)
def map_trade(trade: dict) -> dict:
    return map_to_proposal(trade)
