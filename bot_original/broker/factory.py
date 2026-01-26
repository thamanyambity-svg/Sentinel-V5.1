import os
from bot.broker.paper import PaperBroker
from bot.broker.deriv.broker import DerivBroker
from tests.mocks.mock_deriv import MockDerivBroker

BROKER_REGISTRY = {
    "paper": PaperBroker,
    "deriv": DerivBroker,
}

def get_broker(name: str):
    if name not in BROKER_REGISTRY:
        raise ValueError(f"Unknown broker: {name}")
    return BROKER_REGISTRY[name]()
