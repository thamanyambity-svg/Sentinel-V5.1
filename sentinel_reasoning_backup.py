import json
import os
import math
from datetime import datetime
from sentinel_rl import NexusArchitect

class SovereignGovernor:
    """
    SOVEREIGN (Module d'Arbitrage Bayésien & Exécution)
    Fusion de données par Inférence Bayésienne et Position Sizing (Kelly Criterion).
    """
    def __init__(self):
        self.fundamental_file = 'fundamental_state.json'
        self.nexus = NexusArchitect()
        
    def load_vanguard_spm(self):
        """Récupération du Score de Polarité du Marché (SPM) de Vanguard."""
        if os.path.exists(self.fundamental_file):
            with open(self.fundamental_file, 'r') as f:
                return json.load(f)
        return {"spm_score": 0, "market_mood": "NEUTRAL"}

    def apply_kelly_criterion(self, prob_win, win_loss_ratio=1.5):
        """Calcule le % de capital à risquer selon le critère de Kelly."""
        # Kelly % = (p * b - q) / b  où b = win/loss ratio, p = prob_win, q = prob_loss
        p = prob_win
        q = 1 - p
        b = win_loss_ratio
        
        kelly_f = (p * b - q) / b
        # On applique un "Fractional Kelly" (25% du résultat) pour la sécurité institutionnelle
        return max(0, kelly_f * 0.25)

    def calculate_z_score_divergence(self, tech_signal, spm_score):
        """Calcule l'écart statistique (Z-Score) entre Technique et Sémantique."""
        # Modèle simplifié : On compare l'alignement des vecteurs
        tech_val = 1.0 if tech_signal == "BUY" else -1.0
        # Normalisation arbitraire pour le calcul de l'écart
        divergence = abs(tech_val - (spm_score / 2.0))
        return divergence # Si > 1.5, on considère une déviation significative

    def evaluate_bayesian_arbitrage(self, asset, tech_signal):
        """Fusion Bayésienne : P(Win | Tech, Fund)"""
        print(f"\n[SOVEREIGN] 🏛️ Inférence Bayésienne en cours sur {asset}...")
        
        vanguard = self.load_vanguard_spm()
        spm = vanguard.get('spm_score', 0)
        mood = vanguard.get('market_mood', 'NEUTRAL')
        
        # 1. Probabilité NEXUS (Prior)
        prior_prob = self.nexus.predict_quantum_success(tech_signal, spm)
        
        # 2. Analyse de la Divergence (Z-Score)
        z_div = self.calculate_z_score_divergence(tech_signal, spm)
        
        # 3. Decision Logic (Arbitre)
        decision = "IGNORE"
        risk_lot_multiplier = 0.0
        reason = "Arbitrage : Probabilité Bayésienne insuffisante."

        # ============================================================
        # PHASE 1 — MODE BOOTSTRAP (Nexus vierge, < 5 trades réels)
        # SOVEREIGN délègue à Vanguard SPM directement
        # ============================================================
        nexus_is_trained = len(self.nexus.accuracy_history) >= 5

        if not nexus_is_trained:
            # Alignement : Signal technique + Sentiment Vanguard
            signal_aligned = (
                (tech_signal == "BUY"  and ("BULLISH" in mood or spm > 0.1)) or
                (tech_signal == "SELL" and ("BEARISH" in mood or spm < -0.1))
            )
            if signal_aligned:
                decision = tech_signal
                risk_lot_multiplier = 0.6  # Risque conservateur phase apprentissage
                reason = f"🌱 BOOTSTRAP (SPM={spm:.3f}, {mood}) : Nexus en formation. Vanguard valide le signal."
            else:
                decision = "IGNORE"
                reason = f"🌱 BOOTSTRAP : Signal {tech_signal} contre le sentiment ({mood}). Ignoré."

        else:
            # ============================================================
            # PHASE 2 — MODE AUTONOME (Nexus formé)
            # NEXUS + SOVEREIGN arbitrent ensemble
            # ============================================================
            # Contrarian (Z-Score extrême)
            if z_div > 1.8:
                decision = "SELL" if tech_signal == "BUY" else "BUY"
                risk_lot_multiplier = 0.5
                reason = f"🎭 CONTRE-TENDANCE (Z={z_div:.2f}) : Inversion sur déviation statistique extrême."

            elif prior_prob >= 0.55:
                decision = tech_signal
                risk_lot_multiplier = self.apply_kelly_criterion(prior_prob) * 10.0
                reason = f"🏛️ NEXUS VALIDE (P={prior_prob:.2f}) : Signal autorisé par le moteur Deep RL."

            else:
                reason = f"⏳ NEXUS INCERTAIN ({prior_prob:.2f} < 0.55) : Confluence insuffisante."

            # Kill Switch
            if self.nexus.solve_kill_switch():
                decision = "IGNORE"
                risk_lot_multiplier = 0.0
                reason = "🚨 KILL SWITCH NEXUS : Précision dégradée. Mode observation."

        action_plan = {
            "timestamp": datetime.now().isoformat(),
            "asset": asset,
            "spm_score": spm,
            "nexus_prob": prior_prob,
            "z_score": z_div,
            "decision": decision,
            "kelly_risk": risk_lot_multiplier,
            "lot_multiplier": round(risk_lot_multiplier, 2),  # Field read by MQL5 EA
            "reasoning": reason
        }

        # Write to MT5 Common/Files directory so EA can read it
        mt5_path = os.getenv("MT5_FILES_PATH", ".")
        action_plan_path = os.path.join(mt5_path, "action_plan.json")
        
        with open(action_plan_path, 'w') as f:
            json.dump(action_plan, f, indent=4)

        status_icon = "✅ EXÉCUTION" if decision != "IGNORE" else "🛑 VERDICT"
        print(f"[SOVEREIGN] {status_icon} : {decision} | Kelly Load : {risk_lot_multiplier:.2f}x")
        print(f"[SOVEREIGN] ✍️ Intelligence : {reason}")

        return action_plan

if __name__ == "__main__":
    s = SovereignGovernor()
    s.evaluate_bayesian_arbitrage("EURUSD", "BUY")
