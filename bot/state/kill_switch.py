_kill_switch = False

def enable_kill_switch():
    global _kill_switch
    _kill_switch = True

def disable_kill_switch():
    global _kill_switch
    _kill_switch = False

def is_kill_switch_enabled():
    return _kill_switch
