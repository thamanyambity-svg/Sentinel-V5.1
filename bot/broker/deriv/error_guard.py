"""
Error guard Deriv
Coupe le broker après trop d'erreurs consécutives
"""
import time

_MAX_ERRORS = 3
_WINDOW = 60  # secondes

_errors = []


def record_deriv_error():
    now = time.time()
    _errors.append(now)

    # purge anciennes erreurs
    while _errors and now - _errors[0] > _WINDOW:
        _errors.pop(0)


def reset_deriv_errors():
    _errors.clear()


def deriv_error_limit_reached() -> bool:
    return len(_errors) >= _MAX_ERRORS
