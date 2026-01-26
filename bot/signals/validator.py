def validate_signal(
    risk_allowed: bool,
    risk_reason: str,
    score: float,
    win_rate: float,
    expectancy: float,
    samples: int,
    losing_streak: int,
    daily_dd: float,
    trades_today: int
):
    """
    Retourne une recommandation humaine :
    APPROVE / WAIT / REJECT
    """

    # 1) Blocage risque
    if not risk_allowed:
        return {
            "decision": "REJECT",
            "confidence": "NONE",
            "reason": risk_reason
        }

    # 2) Qualité statistique
    if samples < 50:
        return {
            "decision": "WAIT",
            "confidence": "LOW",
            "reason": "Pas assez d'historique"
        }

    if win_rate < 55 or expectancy <= 0:
        return {
            "decision": "WAIT",
            "confidence": "LOW",
            "reason": "Stats insuffisantes"
        }

    # 3) Fatigue trading
    if trades_today >= 4:
        return {
            "decision": "WAIT",
            "confidence": "MEDIUM",
            "reason": "Trop de trades aujourd'hui"
        }

    if losing_streak >= 2:
        return {
            "decision": "WAIT",
            "confidence": "MEDIUM",
            "reason": "Série négative en cours"
        }

    # 4) Score marché
    if score >= 80:
        return {
            "decision": "APPROVE",
            "confidence": "HIGH",
            "reason": "Setup fort validé"
        }

    if score >= 65:
        return {
            "decision": "WAIT",
            "confidence": "MEDIUM",
            "reason": "Setup moyen, attendre confirmation"
        }

    return {
        "decision": "REJECT",
        "confidence": "LOW",
        "reason": "Score marché trop faible"
    }
