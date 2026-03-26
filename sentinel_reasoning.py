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

    def _read_live_imbalance(self, asset: str) -> float:
        """
        Lit l'imbalance calculée par l'EA (Wick Rejection) depuis ticks_v3.json.
        Remplace l'ancien paramètre statique imbalance=0.0 par une valeur live.
        V7.19 Trap Hunter — branché sur ComputeWickImbalance() de l'EA.
        Cherche d'abord dans MT5_FILES_PATH, puis dans le répertoire courant.
        """
        candidates = []
        mt5_path = os.getenv("MT5_FILES_PATH", "")
        if mt5_path:
            candidates.append(os.path.join(mt5_path, "ticks_v3.json"))
        candidates.append("ticks_v3.json")

        for ticks_path in candidates:
            try:
                if not os.path.exists(ticks_path):
                    continue
                with open(ticks_path, 'r') as f:
                    ticks = json.load(f)
                # AladdinPro V7.19 format: array of {sym, bid, ask, spread, imbalance, ...}
                if isinstance(ticks, list):
                    for tick in ticks:
                        if tick.get('sym') == asset:
                            return float(tick.get('imbalance', 0.0))
                # Legacy format fallback
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass
        return 0.0

    def evaluate_bayesian_arbitrage(self, asset, tech_signal, imbalance=0.0):
        """Fusion Bayésienne : P(Win | Tech, Fund, OrderFlow)"""
        print(f"\n[SOVEREIGN] 🏛️ Inférence Bayésienne (+Liquidité) sur {asset}...")

        # V7.19 Trap Hunter : Lecture automatique depuis ticks_v3.json si non fourni
        if imbalance == 0.0:
            imbalance = self._read_live_imbalance(asset)
            if imbalance != 0.0:
                print(f"[SOVEREIGN] 🎯 Imbalance live chargée: {imbalance:.3f} (Wick Rejection EA)")

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

        # ============================================================
        # CAS 0 : TRAP HUNTER — Détection de Fakeout Institutionnel
        # (V7.19) — S'active avant le Cas 1 si signature de piège détectée
        # ============================================================
        # Signature d'un Bull/Bear Trap :
        #   - imbalance faible (pas de vraie liquidité derrière la cassure)
        #   - Signal technique en direction contraire à l'imbalance
        fakeout_detected = False
        fakeout_reason = ""

        if tech_signal == "BUY" and imbalance < -0.35:
            # Signal BUY mais pression vendeuse dominante dans les mèches → Bull Trap probable
            # Seuil -0.35 : imbalance < -0.35 indique >67% de pression vendeuse nette
            fakeout_detected = True
            fakeout_reason = f"🎯 TRAP HUNTER : Wick Rejet vendeur ({imbalance:.2f}) contre signal BUY — Bull Trap probable"
        elif tech_signal == "SELL" and imbalance > 0.35:
            # Signal SELL mais pression acheteuse dominante → Bear Trap probable
            # Seuil +0.35 : imbalance > 0.35 indique >67% de pression acheteuse nette
            fakeout_detected = True
            fakeout_reason = f"🎯 TRAP HUNTER : Wick Rejet acheteur ({imbalance:.2f}) contre signal SELL — Bear Trap probable"

        if fakeout_detected:
            decision = contra_signal
            risk_lot_multiplier = 0.50  # Taille réduite — mode expérimental
            reason = fakeout_reason
            print(f"[SOVEREIGN] ⚡ {reason}")

        # Cas 1 : ALIGNEMENT PRO-TREND (Technique et Sentiment sont d'accord)
        # Si Tech=BUY et SPM > 0.1, et pas de mur de vente massif (imbalance < -0.7)
        elif (tech_signal == "BUY" and spm > 0.1 and imbalance > -0.7) or \
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
            "lot_multiplier": round(risk_lot_multiplier, 2),  # champ lu par l'EA MQL5
            "reasoning": reason,
            "fakeout_detected": fakeout_detected,
            "imbalance": imbalance,
        }

        # Écrire dans le dossier MT5 Common/Files pour que l'EA puisse lire le fichier
        mt5_path = os.getenv("MT5_FILES_PATH", ".")
        action_plan_path = os.path.join(mt5_path, "action_plan.json")
        with open(action_plan_path, 'w') as f:
            json.dump(action_plan, f, indent=4)

        status_icon = "✅ EXÉCUTION" if decision != "IGNORE" else "🛑 VERDICT"
        print(f"[SOVEREIGN] {status_icon} : {decision} | Kelly Load : {risk_lot_multiplier:.2f}x")
        print(f"[SOVEREIGN] ✍️ Intelligence : {reason}")

        return action_plan

def _run_polling_loop(interval: int = 15):
    """
    Boucle de polling automatique : lit ticks_v3.json toutes les `interval` secondes,
    dérive le tech_signal depuis active_strat, puis appelle evaluate_bayesian_arbitrage().

    L'EA (AladdinPro_V719) exige que action_plan.json soit mis à jour toutes les
    30 secondes max — cette boucle garantit un rafraîchissement toutes les ~15 s.

    Usage : python3 sentinel_reasoning.py --poll [--interval 15]
    """
    import time
    s = SovereignGovernor()
    mt5_path = os.getenv("MT5_FILES_PATH", ".")
    ticks_candidates = [os.path.join(mt5_path, "ticks_v3.json"), "ticks_v3.json"]

    print(f"[SOVEREIGN] 🔄 Démarrage du polling automatique (intervalle={interval}s)")
    print(f"[SOVEREIGN] 📂 MT5_FILES_PATH = {mt5_path}")

    while True:
        try:
            ticks = None
            for path in ticks_candidates:
                if os.path.exists(path):
                    try:
                        with open(path, 'r') as f:
                            ticks = json.load(f)
                        break
                    except (json.JSONDecodeError, OSError):
                        pass

            if not ticks or not isinstance(ticks, list):
                print(f"[SOVEREIGN] ⚠️  ticks_v3.json absent ou vide — action_plan.json non rafraîchi")
            else:
                for tick in ticks:
                    sym = tick.get("sym", "")
                    active_strat = tick.get("active_strat", "WAIT")
                    if not sym or active_strat == "WAIT":
                        continue
                    # Dériver le tech_signal depuis active_strat (ex: "MOM_BUY" → "BUY")
                    if "BUY" in active_strat:
                        tech_signal = "BUY"
                    elif "SELL" in active_strat:
                        tech_signal = "SELL"
                    else:
                        continue
                    imbalance = float(tick.get("imbalance", 0.0))
                    s.evaluate_bayesian_arbitrage(sym, tech_signal, imbalance)
                    break  # Premier actif avec signal actif suffit

        except Exception as e:
            print(f"[SOVEREIGN] ❌ Erreur polling : {e}")

        time.sleep(interval)


if __name__ == "__main__":
    import sys
    if "--poll" in sys.argv:
        interval_arg = 15
        if "--interval" in sys.argv:
            idx = sys.argv.index("--interval")
            if idx + 1 < len(sys.argv):
                interval_arg = int(sys.argv[idx + 1])
        _run_polling_loop(interval=interval_arg)
    else:
        s = SovereignGovernor()
        s.evaluate_bayesian_arbitrage("EURUSD", "BUY")
