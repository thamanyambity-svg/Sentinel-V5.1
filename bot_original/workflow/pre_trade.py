from bot.signal.validator import validate_signal

def pre_trade(market, risk, stats):
    """
    Workflow PRE-TRADE central
    """

    # Si le risque bloque → rejet immédiat
    if not risk["allowed"]:
        return {
            "decision": "REJECT",
            "confidence": "NONE",
            "reason": risk["reason"]
        }

    # Validation du signal
    return validate_signal(
        risk_allowed=risk["allowed"],
        risk_reason=risk["reason"],
        score=market["score"],
        win_rate=stats["win_rate"],
        expectancy=stats["expectancy"],
        samples=stats["samples"],
        losing_streak=stats["losing_streak"],
        daily_dd=stats["daily_dd"],
        trades_today=stats["trades_today"]
    )
