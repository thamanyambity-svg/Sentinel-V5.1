"""
Mapping trade interne -> payload Deriv.
Lecture seule (proposal).
"""

SYMBOL_MAP = {
    "V75": "R_75",
}

SIDE_MAP = {
    "BUY": "CALL",
    "SELL": "PUT",
}

def map_to_proposal(trade: dict) -> dict:
    if trade["asset"] not in SYMBOL_MAP:
        raise ValueError("UNSUPPORTED_ASSET")

    if trade["side"] not in SIDE_MAP:
        raise ValueError("UNSUPPORTED_SIDE")

    return {
        "proposal": 1,
        "amount": trade.get("amount", 1),
        "basis": "stake",
        "contract_type": SIDE_MAP[trade["side"]],
        "currency": "USD",
        "symbol": SYMBOL_MAP[trade["asset"]],
        "duration": 1,
        "duration_unit": "t",
    }

# 🔒 Alias de compatibilité (broker.py)
def map_trade(trade: dict) -> dict:
    return map_to_proposal(trade)
