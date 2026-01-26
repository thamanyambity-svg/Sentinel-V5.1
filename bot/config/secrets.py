"""
Gestion des secrets sensibles (clé API Deriv).
Aucun print. Aucun log.
"""
import os

_DERIV_API_KEY = None


def set_deriv_api_key(key: str):
    global _DERIV_API_KEY
    _DERIV_API_KEY = key


def get_deriv_api_key():
    global _DERIV_API_KEY

    # Priorité 1 : clé injectée en runtime
    if _DERIV_API_KEY:
        return _DERIV_API_KEY

    # Priorité 2 : variable d'environnement
    env_key = os.getenv("DERIV_API_KEY") or os.getenv("DERIV_API_TOKEN")
    if env_key:
        _DERIV_API_KEY = env_key
        return _DERIV_API_KEY

    return None


def has_deriv_api_key() -> bool:
    return get_deriv_api_key() is not None
