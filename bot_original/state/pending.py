"""
Gestion centralisée du trade en attente
H22 — Version canonique
"""

_PENDING_TRADE = None
_STATE = "IDLE"


# =========================
# State helpers
# =========================
def get_state():
    return _STATE


def _set_state(value):
    global _STATE
    _STATE = value


# =========================
# Pending trade helpers
# =========================
def set_pending_trade(trade):
    global _PENDING_TRADE
    _PENDING_TRADE = trade
    _set_state("PENDING")


def get_pending_trade():
    return _PENDING_TRADE


def confirm_trade():
    if not _PENDING_TRADE:
        return False
    _set_state("CONFIRMED")
    return True


def reject_trade():
    clear_trade()
    return True


def clear_trade():
    global _PENDING_TRADE
    _PENDING_TRADE = None
    _set_state("IDLE")

def has_pending_trade():
    """
    Indique s'il existe un trade en attente.
    Lecture seule, sans effet de bord.
    """
    return get_pending_trade() is not None

def pop_pending_trade():
    """
    Retourne le trade confirmé et le supprime atomiquement.
    Utilisé par l’orchestrator.
    """
    if get_state() != "CONFIRMED":
        return None

    trade = get_pending_trade()
    clear_trade()
    return trade
