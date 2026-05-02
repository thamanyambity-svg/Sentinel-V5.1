from agents.base import call_llm

def run(account_data: dict) -> str:
    balance = account_data.get('balance', 0)
    equity = account_data.get('equity', balance)
    drawdown = account_data.get('drawdown', 0)
    pnl = round(float(equity) - float(balance), 2) if equity and balance else 0

    prompt = f"""Tu es le Comptable d'un fonds institutionnel. Réponds en FRANÇAIS.

Balance: {balance}$ | Équité: {equity}$ | P&L latent: {pnl}$ | Drawdown: {drawdown}%

Réponds UNIQUEMENT avec ce format (3 lignes max) :
SANTÉ: [SAINE / SURVEILLANCE / ALARME]
PNL: [gain/perte de X$]
VERDICT: [1 phrase comptable courte]"""
    return call_llm(prompt)
