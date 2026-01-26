from typing import Dict, Type
from bot.strategy.base import BaseStrategy

_STRATEGIES: Dict[str, Type[BaseStrategy]] = {}


def register_strategy(cls: Type[BaseStrategy]):
    _STRATEGIES[cls.name] = cls
    return cls


def get_strategy(name: str) -> BaseStrategy:
    if name not in _STRATEGIES:
        raise ValueError(f"Strategy '{name}' not registered")
    return _STRATEGIES[name]()
