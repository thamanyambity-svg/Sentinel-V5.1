_active_strategy = None

def set_active_strategy(name: str | None):
    global _active_strategy
    _active_strategy = name.upper() if name else None

def get_active_strategy():
    return _active_strategy
