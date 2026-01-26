"""
Validation des réponses Deriv (proposal / order).
Aucune logique réseau ici.
"""

def validate_proposal(response: dict) -> bool:
    if not isinstance(response, dict):
        return False

    if "error" in response:
        return False

    return True

# 🔒 Alias de compatibilité pour broker.py
def validate_response(response: dict) -> bool:
    return validate_proposal(response)
