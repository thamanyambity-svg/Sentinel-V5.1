from bot.journal.logger import load_trades
from bot.journal.metrics import win_rate, expectancy, max_drawdown
from bot.risk.series import series_status

def main():
    trades = load_trades()
    status = series_status(trades)

    print("Trading autorisé :", status["allowed"])
    print("Raison :", status["reason"])
    print("Trades aujourd’hui :", status["trades_today"])
    print("Série perdante :", status["losing_streak"])
    print("Drawdown journalier :", status["daily_drawdown"])

    print("Win rate :", win_rate(trades))
    print("Expectancy :", expectancy(trades))
    print("Max DD :", max_drawdown(trades))

if __name__ == "__main__":
    main()
from bot.signal.validator import validate_signal

result = validate_signal(
    risk_allowed=False,
    risk_reason="Série négative",
    score=72,
    win_rate=68,
    expectancy=0.4,
    samples=80,
    losing_streak=4,
    daily_dd=-4.4,
    trades_today=4
)

print("Validation signal :", result)
from discord.notifier import send_signal

WEBHOOK = "COLLE_TON_WEBHOOK_DISCORD_ICI"

send_signal(WEBHOOK, {
    "asset": "V75",
    "decision": result["decision"],
    "confidence": result["confidence"],
    "risk_allowed": status["allowed"],
    "risk_reason": status["reason"],
    "score": market["score"],
    "market_details": market["details"],
    "win_rate": round(win_rate(trades), 2),
    "expectancy": round(expectancy(trades), 2),
    "samples": len(trades),
    "trades_today": status["trades_today"],
    "losing_streak": status["losing_streak"],
    "daily_dd": status["daily_drawdown"]

