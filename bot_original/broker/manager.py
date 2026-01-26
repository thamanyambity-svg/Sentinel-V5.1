from bot.broker.paper import PaperBroker
from bot.broker.errors import ExecutionError

ACTIVE_BROKER = PaperBroker()


def execute_trade(trade: dict) -> dict:
    try:
        return ACTIVE_BROKER.execute(trade)
    except Exception as e:
        raise ExecutionError(str(e))
