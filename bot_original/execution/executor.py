from bot.workflow.pre_trade import pre_trade
from bot.broker.factory import get_broker


def propose_trade(market, risk, stats):
    """
    Génère une proposition de trade (ou un blocage)
    """

    decision = pre_trade(market, risk, stats)

    if decision["decision"] != "APPROVE":
        return {
            "status": "BLOCKED",
            "reason": decision["reason"]
        }

    return {
        "status": "READY",
        "asset": market["asset"],
        "side": market["side"],
        "confidence": decision["confidence"],
        "summary": {
            "score": market["score"],
            "details": market["details"],
            "win_rate": stats["win_rate"],
            "expectancy": stats["expectancy"],
            "samples": stats["samples"]
        }
    }


def execute_trade(trade, mode="paper"):
    """
    Exécution via broker (paper / réel)
    """

    broker = get_broker(mode)
    return broker.execute(trade)
