from bot.journal.logger import log_trade, load_trades
from bot.journal.metrics import win_rate, expectancy
from bot.discord.report import send_post_trade


def post_trade(trade: dict, webhook: str | None = None) -> dict:
    asset = trade["asset"]
    side = trade["side"]
    pnl = trade.get("pnl", 0.0)

    # 1. Log
    log_trade(asset, side, pnl)

    trades = load_trades()

    # 2. Report normalisé
    report = {
        "status": "EXECUTED",
        "asset": asset,
        "side": side,
        "pnl": pnl,
        "stats": {
            "win_rate": round(win_rate(trades), 2),
            "expectancy": round(expectancy(trades), 2),
            "samples": len(trades)
        }
    }

    # 3. Discord (optionnel)
    if webhook:
        send_post_trade(webhook, report)

    return report
