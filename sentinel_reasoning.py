import json
import os
import math
import pickle
import numpy as np
from datetime import datetime
from pathlib import Path
from sentinel_rl import NexusArchitect

# ── Chargement du modèle XGBoost entraîné ────────────────────────────
_MODEL_PATH = Path(__file__).parent / "model_xgb.pkl"
_xgb_model  = None

def _load_xgb_model():
    global _xgb_model
    if _xgb_model is not None:
        return _xgb_model
    if _MODEL_PATH.exists():
        try:
            with open(_MODEL_PATH, "rb") as f:
                _xgb_model = pickle.load(f)
            print(f"[SOVEREIGN] ✅ model_xgb.pkl chargé ({_MODEL_PATH.name})")
        except Exception as e:
            print(f"[SOVEREIGN] ⚠️ Erreur chargement XGB: {e}")
    return _xgb_model

def _xgb_predict(tech_signal: str, rsi: float = 50.0, adx: float = 25.0,
                  atr: float = 0.001, spread: float = 20.0,
                  ema_fast: float = 0.0, ema_slow: float = 0.0,
                  regime: float = 0.0, volume: float = 0.1,
                  duration: float = 300.0, hour: int = 12,
                  session: str = "OFF") -> float:
    """
    Calcule la probabilité de succès via le modèle XGBoost entraîné.
    Retourne une probabilité entre 0 et 1.
    """
    model = _load_xgb_model()
    if model is None:
        return 0.5  # Fallback neutre si modèle absent

    # Encodage session
    ses_map = {"ASIA": 0, "LONDON": 1, "LONDON_OPEN": 1, "NEW_YORK": 2, "NY": 2, "OFF": 3}
    ses_enc = ses_map.get(session.upper(), 3)

    # L'ordre exact des features attendu par le modèle (vérifié via les logs):
    # ['rsi', 'adx', 'atr', 'spread', 'ema_fast', 'ema_slow', 'regime', 'volume', 'duration_s']
    features = np.array([[
        rsi, adx, atr, spread, ema_fast, ema_slow, regime, volume, duration
    ]], dtype=float)

    try:
        xgb_clf = model.get("model")
        proba = float(xgb_clf.predict_proba(features)[0][1])
        return proba
    except Exception as e:
        print(f"[SOVEREIGN] ⚠️ Erreur prédiction XGB: {e}")
        return 0.5


class SovereignGovernor:
    """
    SOVEREIGN (Module d'Arbitrage Bayésien & Exécution)
    Fusion Bayésienne : XGBoost (AUC 0.933) + Nexus RL + Vanguard SPM
    PATCH : model_xgb.pkl injecté dans prior_prob
    """
    def __init__(self):
        self.fundamental_file = 'fundamental_state.json'
        self.nexus = NexusArchitect()
        _load_xgb_model()  # Pré-chargement au démarrage

    def load_vanguard_spm(self):
        if os.path.exists(self.fundamental_file):
            with open(self.fundamental_file, 'r') as f:
                return json.load(f)
        return {"spm_score": 0, "market_mood": "NEUTRAL"}

    def apply_kelly_criterion(self, prob_win, win_loss_ratio=1.5):
        p = prob_win
        q = 1 - p
        b = win_loss_ratio
        kelly_f = (p * b - q) / b
        return max(0, kelly_f * 0.25)

    def calculate_z_score_divergence(self, tech_signal, spm_score):
        tech_val   = 1.0 if tech_signal == "BUY" else -1.0
        divergence = abs(tech_val - (spm_score / 2.0))
        return divergence

    def _read_live_imbalance(self, asset: str) -> float:
        """
        Lit l'imbalance calculée par l'EA (Wick Rejection) depuis ticks_v3.json.
        Remplace l'ancien paramètre statique imbalance=0.0 par une valeur live.
        V7.19 Trap Hunter — branché sur ComputeWickImbalance() de l'EA.
        """
        try:
            ticks_path = 'ticks_v3.json'
            if not os.path.exists(ticks_path):
                return 0.0
            with open(ticks_path, 'r') as f:
                ticks = json.load(f)
            
            if not isinstance(ticks, list):
                ticks = [ticks]
                
            for tick in ticks:
                if tick.get('sym', tick.get('symbol')) == asset:
                    val = float(tick.get('imbalance', 0.0))
                    print(f"[SOVEREIGN] 🎯 Imbalance live chargée: {val:.3f} (Wick Rejection EA)")
                    return val
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
        return 0.0

    def evaluate_bayesian_arbitrage(self, asset, tech_signal, imbalance=0.0,
                                     rsi=50.0, adx=25.0, atr=0.001,
                                     spread=20.0, ema_fast=0.0, ema_slow=0.0,
                                     regime=0.0, volume=0.1, session="OFF"):
        """
        Fusion Bayésienne : P(Win | XGB, Nexus, Vanguard, OrderFlow)
        PATCH : prior_prob = 70% XGB + 30% Nexus (weighted fusion)
        """
        print(f"\n[SOVEREIGN] 🏛️ Inférence Bayésienne sur {asset} ({tech_signal})...")

        vanguard = self.load_vanguard_spm()
        spm  = vanguard.get('spm_score', 0)
        mood = vanguard.get('market_mood', 'NEUTRAL')

        # ── PATCH : Probabilité fusionnée XGB + Nexus ────────────────
        hour = datetime.now().hour

        # 1. XGBoost (modèle entraîné sur VOS trades réels — AUC 0.933)
        xgb_prob = _xgb_predict(
            tech_signal=tech_signal,
            rsi=rsi, adx=adx, atr=atr,
            spread=spread, ema_fast=ema_fast, ema_slow=ema_slow,
            regime=regime, volume=volume, hour=hour,
            session=session
        )

        # 2. Nexus RL (fallback comportemental)
        nexus_prob = self.nexus.predict_quantum_success(tech_signal, spm, imbalance)

        # 3. Fusion pondérée : 70% XGB + 30% Nexus
        if _xgb_model is not None:
            prior_prob = 0.70 * xgb_prob + 0.30 * nexus_prob
            source = f"XGB({xgb_prob:.3f}) × 0.7 + Nexus({nexus_prob:.3f}) × 0.3"
        else:
            prior_prob = nexus_prob
            source = f"Nexus uniquement (XGB absent)"

        print(f"[SOVEREIGN] 📊 Probabilité fusionnée : {prior_prob:.3f} | {source}")

        # ── Logique d'arbitrage ─────────────────────────────────────
        z_div = self.calculate_z_score_divergence(tech_signal, spm)

        decision            = "IGNORE"
        risk_lot_multiplier = 0.0
        reason              = "Arbitrage : Liquidité insuffisante."

        liq_confirm = "NEUTRAL"
        if imbalance > 0.4:  liq_confirm = "BUY"
        if imbalance < -0.4: liq_confirm = "SELL"

        contra_signal = "SELL" if tech_signal == "BUY" else "BUY"

        # ============================================================
        # CAS 0 : TRAP HUNTER — Détection de Fakeout Institutionnel
        # (V7.19) — S'active avant le Cas 1 si signature de piège détectée
        # ============================================================
        fakeout_detected = False
        fakeout_reason = ""
        
        # V7.19 Trap Hunter
        if imbalance == 0.0:
            imbalance = self._read_live_imbalance(asset)
            
        if tech_signal == "BUY" and imbalance < -0.35:
            fakeout_detected = True
            fakeout_reason = f"🎯 TRAP HUNTER : Wick Rejet vendeur ({imbalance:.2f}) contre signal BUY — Bull Trap probable"
        elif tech_signal == "SELL" and imbalance > 0.35:
            fakeout_detected = True
            fakeout_reason = f"🎯 TRAP HUNTER : Wick Rejet acheteur ({imbalance:.2f}) contre signal SELL — Bear Trap probable"
            
        if fakeout_detected:
            decision            = contra_signal
            risk_lot_multiplier = 0.50
            reason              = fakeout_reason
            print(f"[SOVEREIGN] ⚡ {reason}")

        # Cas 1 : ALIGNEMENT PRO-TREND
        elif (tech_signal == "BUY"  and spm > 0.1 and imbalance > -0.7) or \
           (tech_signal == "SELL" and spm < -0.1 and imbalance < 0.7):
            decision            = tech_signal
            risk_lot_multiplier = 0.75
            reason = f"🚀 CONFLUENCE PRO : Technique + Sentiment ({mood}) alignés."

        # Cas 2 : INVERSION INSTITUTIONNELLE
        elif contra_signal == liq_confirm and (
            (contra_signal == "BUY"  and spm > 0.05) or
            (contra_signal == "SELL" and spm < -0.05)
        ):
            decision            = contra_signal
            risk_lot_multiplier = 0.85
            reason = f"💎 VISION QUANTUM : Inversion {tech_signal}→{contra_signal} confirmée."

        # Cas 3 : Bootstrap Nexus
        elif len(self.nexus.accuracy_history) < 20:
            if (contra_signal == "BUY"  and spm > 0.3) or \
               (contra_signal == "SELL" and spm < -0.3):
                decision            = contra_signal
                risk_lot_multiplier = 0.5
                reason = f"🎭 ANTI-BRUIT (Bootstrap) : Inversion via Sentiment Fort."
            else:
                decision = "IGNORE"
                reason   = "⏳ ATTENTE : Pas de confluence claire."

        # Cas 4 : PATCH — XGBoost autonome (prior_prob >= 0.58)
        elif prior_prob >= 0.58:
            decision            = tech_signal
            risk_lot_multiplier = round(self.apply_kelly_criterion(prior_prob) * 2, 2)
            reason = f"🤖 XGB DECISION : P={prior_prob:.3f} ≥ 0.58 | Kelly={risk_lot_multiplier:.2f}x"

        # Kill Switch
        if self.nexus.solve_kill_switch():
            decision            = "IGNORE"
            risk_lot_multiplier = 0.0
            reason = "🚨 KILL SWITCH NEXUS ACTIVÉ."

        action_plan = {
            "timestamp":      datetime.now().isoformat(),
            "asset":          asset,
            "spm_score":      spm,
            "nexus_prob":     round(prior_prob, 4),
            "xgb_prob":       round(xgb_prob, 4),
            "nexus_raw_prob": round(nexus_prob, 4),
            "z_score":        z_div,
            "decision":       decision,
            "kelly_risk":     risk_lot_multiplier,
            "lot_multiplier": round(risk_lot_multiplier, 2),  # Field read by MQL5 EA
            "reasoning":      reason,
            "probability":    round(prior_prob, 4),
            "fakeout_detected": fakeout_detected,
            "imbalance":      imbalance,
        }

        # Write to MT5 Common/Files directory so EA can read it
        mt5_path = os.getenv("MT5_FILES_PATH", ".")
        action_plan_path = os.path.join(mt5_path, "action_plan.json")

        with open(action_plan_path, 'w') as f:
            json.dump(action_plan, f, indent=4)

        status_icon = "✅ EXÉCUTION" if decision != "IGNORE" else "🛑 VERDICT"
        print(f"[SOVEREIGN] {status_icon} : {decision} | P={prior_prob:.3f} | Kelly={risk_lot_multiplier:.2f}x")
        print(f"[SOVEREIGN] ✍️  {reason}")

        return action_plan


if __name__ == "__main__":
    s = SovereignGovernor()
    s.evaluate_bayesian_arbitrage("USDJPY", "BUY", rsi=52, adx=28, atr=0.05)
