from agents.base import call_llm

def run(market_conditions: str) -> str:
    prompt = f"""Tu es l'Analyste Technique d'un fonds institutionnel. Réponds en FRANÇAIS.

Données marché : {market_conditions}

Réponds UNIQUEMENT avec ce format (3 lignes max) :
TENDANCE: [HAUSSIÈRE / BAISSIÈRE / LATÉRALE]
ZONE: [SUR-ACHAT / SUR-VENTE / NEUTRE]
SIGNAL: [BUY / SELL / WAIT]"""
    return call_llm(prompt)
