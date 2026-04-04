"""
Compteur de rejets par type (RSI_GATE, BOOKMAP_MR, BOOKMAP_TREND, etc.).

Permet de surveiller le % de rejet par filtre et d’ajuster les seuils.
"""
from collections import Counter
from typing import Dict

_counts: Counter = Counter()

REJECTION_TYPES = (
    "RSI_GATE",
    "ADX_MR",
    "FREQUENCY",
    "COOLDOWN",
    "FATIGUE",
    "BOOKMAP_SPREAD",
    "BOOKMAP_MR",
    "BOOKMAP_TREND",
)


def record_rejection(reason_type: str) -> None:
    """Enregistre un rejet pour le type donné."""
    if reason_type in REJECTION_TYPES:
        _counts[reason_type] += 1
    else:
        _counts["OTHER"] = _counts.get("OTHER", 0) + 1


def get_rejection_counts() -> Dict[str, int]:
    """Retourne les compteurs par type (copie)."""
    return dict(_counts)


def get_total_rejections() -> int:
    """Total des rejets enregistrés."""
    return sum(_counts.values())


def reset() -> None:
    """Remet les compteurs à zéro (ex. en début de session)."""
    _counts.clear()
