from agents.base import call_llm

def run(market_context: str) -> str:
    prompt = f"""Tu es le Macro-Économiste d'un fonds institutionnel. Analyse ce contexte en FRANÇAIS.

Contexte : {market_context}

Réponds UNIQUEMENT avec ce format (3 lignes max) :
CLIMAT: [FAVORABLE / DÉFAVORABLE / NEUTRE]
RAISON: [1 phrase max]
RECOMMANDATION: [RISK-ON / RISK-OFF]"""
    return call_llm(prompt, tier=2)
