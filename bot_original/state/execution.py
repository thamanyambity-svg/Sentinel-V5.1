_execution_lock = False


def is_executing():
    return _execution_lock


def set_executing():
    global _execution_lock
    _execution_lock = True


def clear_executing():
    global _execution_lock
    _execution_lock = False
