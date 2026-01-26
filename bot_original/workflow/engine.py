from bot.journal.logger import log_trade
from bot.journal.metrics import win_rate, expectancy, max_drawdown

def post_trade_report(asset, side, pnl, trades):
    log_trade(asset, side, pnl)

    return {
        "asset": asset,
        "side": side,
        "pnl": pnl,
        "updated_stats": {
            "win_rate": round(win_rate(trades), 2),
            "expectancy": round(expectancy(trades), 2),
            "max_dd": round(max_drawdown(trades), 2)
        }
    }
