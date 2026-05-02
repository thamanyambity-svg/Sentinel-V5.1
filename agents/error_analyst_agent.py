from agents.base import call_llm

def run(all_reports: dict) -> str:
    devil = all_reports.get('devil', 'N/A')[:300]
    macro = all_reports.get('macro', 'N/A')[:200]
    quant = all_reports.get('quant', 'N/A')[:200]

    prompt = f"""Tu es l'Analyste des Erreurs d'un comité d'investissement. Réponds en FRANÇAIS.

Macro: {macro}
Technique: {quant}
Avocat du diable: {devil}

Réponds UNIQUEMENT avec ce format (3 lignes max) :
COHÉRENCE: [FIABLE / PARTIELLE / DÉFAILLANTE]
BIAIS DÉTECTÉ: [nom du biais ou "Aucun"]
DÉCISION: [CONTINUER / ANNULER et reanalysées]"""
    return call_llm(prompt)
