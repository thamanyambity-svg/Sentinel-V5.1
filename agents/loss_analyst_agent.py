from agents.base import call_llm

def run(account_data: dict) -> str:
    drawdown = account_data.get('drawdown', 0)
    positions = account_data.get('positions_count', 0)
    prompt = f"""Tu es l'Analyste des Pertes d'un fonds institutionnel. Réponds en FRANÇAIS.

Drawdown: {drawdown}% | Positions ouvertes: {positions}

Réponds UNIQUEMENT avec ce format (3 lignes max) :
DRAWDOWN: [EXCELLENT / ACCEPTABLE / PRÉOCCUPANT / CRITIQUE]
SURTRADING: [OUI / NON]
AMÉLIORATION: [1 conseil concret en 1 phrase]"""
    return call_llm(prompt)
