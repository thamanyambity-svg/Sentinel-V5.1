from bot.journal.audit import audit

_state = {"force": False}


def enable_force(actor="admin"):
    _state["force"] = True
    audit("FORCE_ENABLED", actor)


def disable_force(actor="system"):
    _state["force"] = False
    audit("FORCE_DISABLED", actor)


def is_force_enabled():
    return _state["force"]
