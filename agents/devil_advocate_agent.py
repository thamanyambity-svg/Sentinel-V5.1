from agents.base import call_llm

def run(phase1_reports: dict) -> str:
    macro = phase1_reports.get('macro', 'N/A')[:300]
    quant = phase1_reports.get('quant', 'N/A')[:300]
    prompt = f"""Tu es l'Avocat du Diable d'un comité d'investissement. Réponds en FRANÇAIS.

Rapport Macro: {macro}
Rapport Technique: {quant}

Réponds UNIQUEMENT avec ce format (3 lignes max) :
CONTRADICTION: [la principale contradiction détectée en 1 phrase]
RISQUE IGNORÉ: [1 risque que personne n'a mentionné]
VERDICT: [VALIDE / CONTESTE]"""
    return call_llm(prompt, tier=3)
