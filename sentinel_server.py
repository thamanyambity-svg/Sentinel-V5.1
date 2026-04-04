import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from sentinel_brain import VanguardAnalyzer
from sentinel_reasoning import SovereignGovernor
from sentinel_apex import ApexArchitect

# --- INITIALISATION DE L'ARCHITECTURE QUANTIQUE VÉGÉTALE ---
app = FastAPI(title="SENTINEL APEX - L'ARCHITECTE ÉVOLUTIF")

print("\n" + "="*60)
print("     ⚡ SENTINEL : ARCHITECTURE QUANTIQUE VÉGÉTALE ⚡")
print("          (VANGUARD • NEXUS • SOVEREIGN • APEX)")
print("="*60)

vanguard = VanguardAnalyzer()
sovereign = SovereignGovernor()
# APEX supervise Nexus et Vanguard
apex = ApexArchitect(sovereign.nexus, vanguard)

class SignalInput(BaseModel):
    action: str
    asset: str
    tech_signal: str
    imbalance: float = 0.0

class TradeResult(BaseModel):
    ticket: int
    asset: str
    type: str
    profit: float
    spm_score: float
    nexus_prob: float
    imbalance: float = 0.0

@app.get("/status")
def status():
    return {"status": "APEX SYSTEM ONLINE", "evolution_stage": "CONSCIOUS"}

@app.post("/evaluate")
def evaluate(signal: SignalInput):
    """
    Interface d'Inférence Bayésienne sous supervision APEX.
    """
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] 📥 Entrée de Signal : {signal.asset} | {signal.tech_signal} | Imbalance: {signal.imbalance:.2f}")
    
    # 1. Mise à jour Vanguard
    vanguard.run_vanguard_scan()
    
    try:
        # 2. Arbitrage Souverain (Maintenant avec Conscience de Liquidité)
        plan = sovereign.evaluate_bayesian_arbitrage(signal.asset, signal.tech_signal, signal.imbalance)
        
        # 3. APEX observe la décision et lance un stress test si nécessaire
        if plan["decision"] != "IGNORE" and plan["kelly_risk"] > 0.8:
            apex.run_adversary_stress_test()
            
        return {
            "status": "success",
            "decision": plan["decision"],
            "lot_multiplier": round(float(plan["kelly_risk"]), 2),
            "probability": round(float(plan["nexus_prob"]), 2),
            "z_score": round(float(plan["z_score"]), 2),
            "imbalance": round(float(signal.imbalance), 2)
        }
    except Exception as e:
        print(f"[SOVEREIGN] ❌ Échec du processus d'arbitrage : {e}")
        raise HTTPException(status_code=500, detail="Internal Sovereign Failure")

@app.post("/feedback")
def feedback(result: TradeResult):
    """
    Endpoint crucial pour l'évolution : APEX analyse le résultat réel.
    Appelé par MT5 lors de la clôture d'un trade.
    """
    try:
        apex.perform_transactional_autopsy(result.dict())
        return {"status": "APEX INTELLIGENCE UPDATED"}
    except Exception as e:
        print(f"[APEX] ❌ Échec de l'autopsie : {e}")
        raise HTTPException(status_code=500, detail="Apex Autopsy Failure")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5555, log_level="error")
