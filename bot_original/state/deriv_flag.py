DERIV_ENABLED = False

def enable_deriv():
    global DERIV_ENABLED
    DERIV_ENABLED = True

def disable_deriv():
    global DERIV_ENABLED
    DERIV_ENABLED = False

def is_deriv_enabled():
    return DERIV_ENABLED
