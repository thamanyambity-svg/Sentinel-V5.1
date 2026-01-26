from bot.state.risk import register_trade, can_execute_trade

for i in range(10):
    print(i, can_execute_trade())
    register_trade(1.0)
