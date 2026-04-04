import json
import os
import math
from datetime import datetime

# Fix macOS fork() segfault with PyTorch/numpy
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from sentinel_rl import NexusArchitect

# V9 — ML Pipeline integration (XGBoost + Confluence)
try:
    from sentinel_pipeline import SentinelPipeline, compute_confluence, CONFLUENCE_THRESHOLD
    from sentinel_pipeline import normalize_liquidity_signal, normalize_momentum_signal
    from sentinel_pipeline import normalize_volatility_signal, detect_market_regime, REGIME_PARAMS
    from sentinel_ml import build_features
    _V9_AVAILABLE = True
except ImportError:
    _V9_AVAILABLE = False

class SovereignGovernor:
    """
    SOVEREIGN (Module d'Arbitrage Bayésien & Exécution)
    Fusion de données par Inférence Bayésienne et Position Sizing (Kelly Criterion).
    V9: Integrated XGBoost ML + Weighted Confluence + Market Regime Detection.
    """
    def __init__(self):
        self.fundamental_file = 'fundamental_state.json'
        self.nexus = NexusArchitect()
        # Rolling history for real Z-score computation (max 100 observations)
        self._divergence_history = []
        # V9 — ML Pipeline (lazy init, graceful fallback)
        self._pipeline = None
        if _V9_AVAILABLE:
            try:
                self._pipeline = SentinelPipeline()
                print("[SOVEREIGN] 🧠 V9 ML Pipeline loaded (XGBoost + Confluence)")
            except Exception as e:
                print(f"[SOVEREIGN] ⚠️ V9 ML Pipeline unavailable: {e}")
                self._pipeline = None

    def load_vanguard_spm(self):
        """Récupération du Score de Polarité du Marché (SPM) de Vanguard."""
        if os.path.exists(self.fundamental_file):
            with open(self.fundamental_file, 'r') as f:
                return json.load(f)
        return {"spm_score": 0, "market_mood": "NEUTRAL"}

    def _load_trade_stats(self, n: int = 30) -> dict:
        """
        Charge les statistiques réelles depuis trade_history.json.
        Retourne {'p': winrate, 'b': avg_win/avg_loss, 'n': nb_trades}.
        Utilisé par apply_kelly_criterion() pour remplacer le ratio hardcodé 1.5.
        """
        candidates = []
        mt5_path = os.getenv("MT5_FILES_PATH", "")
        if mt5_path:
            candidates.append(os.path.join(mt5_path, "trade_history.json"))
        candidates.append("trade_history.json")

        for path in candidates:
            try:
                if not os.path.exists(path):
                    continue
                with open(path, 'r') as f:
                    trades = json.load(f)
                if not isinstance(trades, list):
                    continue
                # Only closed trades, sorted by entry_time, last n
                closed = [t for t in trades if t.get('closed', False)]
                if len(closed) < 5:
                    continue
                closed = sorted(closed, key=lambda t: t.get('entry_time', 0))[-n:]
                pnls = [t.get('profit', t.get('pnl', 0.0)) for t in closed]
                wins   = [p for p in pnls if p > 0]
                losses = [abs(p) for p in pnls if p < 0]
                if not wins or not losses:
                    continue
                p = len(wins) / len(pnls)
                b = (sum(wins) / len(wins)) / (sum(losses) / len(losses))
                return {'p': round(p, 3), 'b': round(b, 3), 'n': len(closed)}
            except (json.JSONDecodeError, KeyError, TypeError, ValueError, ZeroDivisionError):
                pass
        # Default conservative fallback when no history available
        return {'p': 0.5, 'b': 1.5, 'n': 0}

    def apply_kelly_criterion(self, prob_win: float, win_loss_ratio: float = 1.5) -> float:
        """Calcule le % de capital à risquer selon le critère de Kelly (Fractional 25%)."""
        p = prob_win
        q = 1.0 - p
        b = win_loss_ratio
        kelly_f = (p * b - q) / b
        # Fractional Kelly (25%) — pratique institutionnelle standard (Thorp, Renaissance)
        return max(0.0, kelly_f * 0.25)

    def calculate_z_score_divergence(self, tech_signal: str, spm_score: float) -> float:
        """
        Z-score réel de la divergence Technique/Sentiment sur fenêtre glissante ≥ 30 obs.
        Remplace l'ancienne formule arbitraire abs(tech - spm/2) qui n'était pas un Z-score.
        Z > 1.5 → divergence statistiquement anormale (signal contre-tendance potentiel).

        Échelles : tech_val ∈ {-1, +1}, spm_score ∈ [-1, +1] (score de polarité marché).
        La divergence abs(tech_val - spm_score) ∈ [0, 2] mais le Z-score est relatif à
        sa propre distribution historique, donc l'échelle absolue n'affecte pas la validité.
        """
        tech_val = 1.0 if tech_signal == "BUY" else -1.0
        # Both tech_val and spm_score are in [-1, +1]; divergence ∈ [0, 2]
        divergence = abs(tech_val - spm_score)

        self._divergence_history.append(divergence)
        # Keep rolling window of last 100 observations
        if len(self._divergence_history) > 100:
            self._divergence_history = self._divergence_history[-100:]

        n = len(self._divergence_history)
        if n < 30:
            # Not enough history yet — return raw divergence as proxy
            return divergence

        mu = sum(self._divergence_history) / n
        variance = sum((x - mu) ** 2 for x in self._divergence_history) / (n - 1)
        sigma = variance ** 0.5
        if sigma < 1e-8:
            return 0.0
        return (divergence - mu) / sigma

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

    def _build_v9_tick_data(self, asset: str, imbalance: float) -> dict:
        """
        Build V9-compatible tick_data dict from ticks_v3.json for ML feature engine.
        Returns a dict with keys expected by sentinel_ml.build_features().
        Falls back to reasonable defaults if data unavailable.
        """
        tick_data = {
            "closes": [], "opens": [], "highs": [], "lows": [],
            "atr": 0.0, "atr_hist": [],
            "high": 0.0, "low": 0.0,
            "hour": datetime.now().hour,
        }

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
                if isinstance(ticks, list):
                    for tick in ticks:
                        if tick.get('sym') == asset:
                            bid = float(tick.get('bid', 0.0))
                            ask = float(tick.get('ask', 0.0))
                            atr = float(tick.get('atr', 0.0))

                            tick_data["atr"] = atr
                            tick_data["high"] = float(tick.get('high', bid))
                            tick_data["low"] = float(tick.get('low', bid))

                            # Synthesize OHLC history if not available
                            if not tick_data["closes"]:
                                price = bid if bid > 0 else ask
                                tick_data["closes"] = [price] * 30
                                tick_data["opens"] = [price] * 30
                                tick_data["highs"] = [price + atr * 0.3] * 30
                                tick_data["lows"] = [price - atr * 0.3] * 30
                            if not tick_data["atr_hist"]:
                                tick_data["atr_hist"] = [atr] * 50
                            break
                break
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass

        return tick_data

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

        # ============================================================
        # KELLY RÉEL — calibration sur données live (trade_history.json)
        # Remplace le win_loss_ratio hardcodé 1.5 par les valeurs réelles.
        # ============================================================
        stats = self._load_trade_stats(n=30)
        kelly_frac = self.apply_kelly_criterion(stats['p'], stats['b'])
        # Map Kelly fraction → lot_multiplier scale [0.3, 1.0].
        # Reference: 0.06 = Fractional Kelly (25%) at winrate=0.55, b=1.5 — typical solid
        # system. kelly_frac ≥ 0.06 → full scale 1.0; kelly_frac = 0 → minimum scale 0.3.
        if stats['n'] >= 10 and risk_lot_multiplier > 0.0:
            _KELLY_REFERENCE = 0.06  # Kelly fraction at normal profitable operation
            kelly_scale = max(0.3, min(1.0, kelly_frac / _KELLY_REFERENCE))
            risk_lot_multiplier = round(risk_lot_multiplier * kelly_scale, 2)
            print(f"[SOVEREIGN] 📊 Kelly réel: p={stats['p']:.2f}, b={stats['b']:.2f}, "
                  f"kelly={kelly_frac:.3f} → scale={kelly_scale:.2f}, lot_mult={risk_lot_multiplier:.2f}")
        else:
            print(f"[SOVEREIGN] 📊 Kelly fallback (données insuffisantes: {stats['n']} trades fermés)")

        # ============================================================
        # V9 — ML CONFLUENCE ENGINE (XGBoost + Weighted Scoring + Regime)
        # Runs in parallel with the existing Bayesian logic.
        # If the V9 pipeline is available AND confident, it overrides the
        # base decision. Otherwise the original Bayesian decision stands.
        # ============================================================
        v9_data = {}
        if self._pipeline is not None and _V9_AVAILABLE:
            try:
                tick_data = self._build_v9_tick_data(asset, imbalance)
                v9_result = self._pipeline.evaluate_signal(tick_data, tech_signal)
                v9_data = v9_result

                # V9 confluence can override IGNORE → EXECUTE or vice-versa
                v9_confluence = v9_result.get("confluence", 0.0)
                v9_decision = v9_result.get("decision", "IGNORE")
                v9_regime = v9_result.get("regime", "RANGE")
                v9_params = v9_result.get("params", {})

                print(f"[SOVEREIGN] 🧠 V9 Confluence={v9_confluence:.3f} "
                      f"(threshold={CONFLUENCE_THRESHOLD}) | Regime={v9_regime}")

                # Override logic: V9 confluence > threshold → upgrade to EXECUTE
                if v9_decision in ("EXECUTE", "EXECUTE_CAUTIOUS") and decision == "IGNORE":
                    decision = tech_signal
                    risk_lot_multiplier = 0.5 if v9_decision == "EXECUTE" else 0.35
                    reason = (f"🧠 V9 ML OVERRIDE: Confluence={v9_confluence:.3f} "
                              f"(ML={v9_result.get('ml_prob', 0):.2f}) — "
                              f"Regime={v9_regime}"
                              + (" [CAUTIOUS: low ATR]" if v9_decision == "EXECUTE_CAUTIOUS" else ""))

                # V9 says IGNORE but base says EXECUTE → downgrade
                elif v9_decision == "IGNORE" and decision != "IGNORE" and v9_confluence < 0.35:
                    decision = "IGNORE"
                    risk_lot_multiplier = 0.0
                    reason = (f"🧠 V9 ML VETO: Confluence={v9_confluence:.3f} too low — "
                              f"trade filtered by ML")

            except Exception as e:
                print(f"[SOVEREIGN] ⚠️ V9 evaluation error (fallback to base): {e}")

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
            # V9 ML data (empty dict if pipeline not available)
            "v9_confluence": v9_data.get("confluence", None),
            "v9_ml_prob": v9_data.get("ml_prob", None),
            "v9_regime": v9_data.get("regime", None),
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
