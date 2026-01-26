from datetime import date
from bot.journal.logger import load_trades

MAX_DAILY_LOSS = -5.0  # %
 

def daily_loss_exceeded():
    today = date.today().isoformat()
    trades = load_trades()

    pnl_today = sum(
        t["pnl"] for t in trades
        if t["timestamp"].startswith(today)
    )

    return pnl_today <= MAX_DAILY_LOSS
