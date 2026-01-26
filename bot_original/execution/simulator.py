def execute_trade_simulated(trade):
    """
    Exécution simulée déterministe (R-multiple)
    """

    score = trade["summary"]["score"]

    # règle simple et reproductible
    r_multiple = 1.0 if score >= 70 else -1.0

    result = {
        "asset": trade["asset"],
        "side": trade["side"],
        "r_multiple": r_multiple,
        "pnl": r_multiple  # 1R = 1.0
    }

    return result
