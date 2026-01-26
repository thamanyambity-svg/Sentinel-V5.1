_shadow_enabled = False
_shadow_broker = "paper"

def enable_shadow(broker="paper"):
    global _shadow_enabled, _shadow_broker
    _shadow_enabled = True
    _shadow_broker = broker

def disable_shadow():
    global _shadow_enabled
    _shadow_enabled = False

def is_shadow_enabled():
    return _shadow_enabled

def get_shadow_broker():
    return _shadow_broker
