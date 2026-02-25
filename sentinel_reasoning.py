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

    def evaluate_bayesian_arbitrage(self, asset, tech_signal, imbalance=0.0):
        """Fusion Bayésienne : P(Win | Tech, Fund, OrderFlow)"""
        print(f"\n[SOVEREIGN] 🏛️ Inférence Bayésienne (+Liquidité) sur {asset}...")
        
        vanguard = self.load_vanguard_spm()
        spm = vanguard.get('spm_score', 0)
        mood = vanguard.get('market_mood', 'NEUTRAL')
        
        # 1. Probabilité NEXUS (Maintenant avec Order Flow intégré)
        prior_prob = self.nexus.predict_quantum_success(tech_signal, spm, imbalance)
        
        # 2. Analyse de la Divergence (Z-Score)
        z_div = self.calculate_z_score_divergence(tech_signal, spm)
        
        # 3. Decision Logic (Arbitre)
        decision = "IGNORE"
        risk_lot_multiplier = 0.0
        reason = "Arbitrage : Liquidité insuffisante."

        # ANALYSE DE LIQUIDITÉ (Vision Bookmap)
        # Si imbalance > 0.4 => Forts acheteurs | imbalance < -0.4 => Forts vendeurs
        liq_confirm = "NEUTRAL"
        if imbalance > 0.4: liq_confirm = "BUY"
        if imbalance < -0.4: liq_confirm = "SELL"

        # ============================================================
        # STRATÉGIE HYBRIDE : TREND FOLLOWING & INVERSION LIQUIDE
        # ============================================================
        contra_signal = "SELL" if tech_signal == "BUY" else "BUY"
        tech_val = 1.0 if tech_signal == "BUY" else -1.0
        
        # Cas 1 : ALIGNEMENT PRO-TREND (Technique et Sentiment sont d'accord)
        # Si Tech=BUY et SPM > 0.1, et pas de mur de vente massif (imbalance < -0.7)
        if (tech_signal == "BUY" and spm > 0.1 and imbalance > -0.7) or \
           (tech_signal == "SELL" and spm < -0.1 and imbalance < 0.7):
            decision = tech_signal
            risk_lot_multiplier = 0.75
            reason = f"🚀 CONFLUENCE PRO : Technique et Sentiment ({mood}) alignés. Trade de tendance validé."

        # Cas 2 : INVERSION INSTITUTIONNELLE (Le piège retail exposé par Bookmap)
        # Si Tech est contraire au Sentiment ET confirmé par la Liquidité
        elif contra_signal == liq_confirm and (
            (contra_signal == "BUY" and spm > 0.05) or (contra_signal == "SELL" and spm < -0.05)
        ):
            decision = contra_signal
            risk_lot_multiplier = 0.85 
            reason = f"💎 VISION QUANTUM : Inversion {tech_signal}->{contra_signal} CONFIRMÉE par Order Flow ({imbalance:.2f}) et Sentiment."

        # Cas 3 : Mode Bootstrap Nexus (Capture d'opportunité divergente sans Bookmap)
        elif len(self.nexus.accuracy_history) < 20: 
            # On tente l'inversion si le sentiment est très fort contre le signal technique
            if (contra_signal == "BUY" and spm > 0.3) or (contra_signal == "SELL" and spm < -0.3):
                decision = contra_signal
                risk_lot_multiplier = 0.5
                reason = f"🎭 ANTI-BRUIT (Bootstrap) : Inversion {tech_signal}->{contra_signal} via Sentiment Fort."
            else:
                decision = "IGNORE"
                reason = "⏳ ATTENTE : Pas de confluence claire (Tendance vs Inversion)."

        # Cas 4 : Nexus Autonome (Probabilité IA supérieure à 65%)
        elif prior_prob >= 0.65:
            decision = tech_signal if prior_prob > 0.75 else contra_signal
            risk_lot_multiplier = 0.6
            reason = f"🏛️ NEXUS DECISION : Arbitrage IA validé (P={prior_prob:.2f})."

        # Kill Switch Security
        if self.nexus.solve_kill_switch():
            decision = "IGNORE"
            risk_lot_multiplier = 0.0
            reason = "🚨 KILL SWITCH NEXUS ACTIVÉ (Précision dégradée)."

        action_plan = {
            "timestamp": datetime.now().isoformat(),
            "asset": asset,
            "spm_score": spm,
            "nexus_prob": prior_prob,
            "z_score": z_div,
            "decision": decision,
            "kelly_risk": risk_lot_multiplier,
            "reasoning": reason
        }

        with open('action_plan.json', 'w') as f:
            json.dump(action_plan, f, indent=4)

        status_icon = "✅ EXÉCUTION" if decision != "IGNORE" else "🛑 VERDICT"
        print(f"[SOVEREIGN] {status_icon} : {decision} | Kelly Load : {risk_lot_multiplier:.2f}x")
        print(f"[SOVEREIGN] ✍️ Intelligence : {reason}")

        return action_plan

if __name__ == "__main__":
    s = SovereignGovernor()
    s.evaluate_bayesian_arbitrage("EURUSD", "BUY")
