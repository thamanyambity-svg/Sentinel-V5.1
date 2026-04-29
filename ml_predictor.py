"""
ALADDIN PRO V6 — ml_predictor.py
Scoring live XGBoost — lit ticks_v3.json, écrit ml_signal.json

Usage:
  python ml_predictor.py                        # Mode standalone (boucle)
  from ml_predictor import MLPredictor          # Intégration dans engine.py
"""
import json
import pickle
import sys
import time
import logging
import os
import threading
import datetime as lib_dt
from datetime import datetime
try:
    from datetime import UTC
except ImportError:
    UTC = lib_dt.timezone.utc



from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

# Charger les variables d'environnement (.env)
load_dotenv()

# Import AutoTrainer depuis le même dossier
sys.path.insert(0, str(Path(__file__).parent))
try:
    from auto_trainer import AutoTrainer, TrainerConfig
    from ml_engine import LivePredictor as GBPredictor, MLConfig
    _AUTO_TRAINER_AVAILABLE = True
except ImportError:
    _AUTO_TRAINER_AVAILABLE = False
    log_tmp = logging.getLogger("MLPredictor")
    log_tmp.warning("auto_trainer.py introuvable — re-entraînement auto désactivé")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("MLPredictor")

try:
    sys.path.insert(0, str(Path(__file__).parent / "bot/ai_agents"))
    from massive_feature_injector import get_macro_features
except ImportError:
    get_macro_features = lambda s, t: {}

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

MT5_FILES_DEFAULT = os.getenv(
    "MT5_FILES_PATH",
    "/Users/macbookpro/Library/Application Support/"
    "net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/"
    "MetaQuotes/Terminal/Common/Files"
)

MIN_CONFIDENCE  = 0.65    # Raised from 0.52 to stop bleeding trades
HIGH_CONFIDENCE = 0.75    # Raised
POLL_INTERVAL   = 0.5     # Secondes entre chaque lecture ticks_v3.json
MODEL_TTL_DAYS  = 7       # Expiration du modèle après 7 jours
SIGNAL_LOG_COOLDOWN = 60  # Secondes minimum entre deux logs du même signal par symbole


# ══════════════════════════════════════════════════════════════════
#  CHARGEMENT DU MODÈLE
# ══════════════════════════════════════════════════════════════════

class ModelLoader:

    def __init__(self, model_path: Path, threshold_path: Path):
        self.model_path    = model_path
        self.threshold_path = threshold_path
        self.model         = None
        self.threshold     = MIN_CONFIDENCE
        self.backend       = None
        self.trained_at    = None
        self.loaded        = False

    def load(self) -> bool:
        if not self.model_path.exists():
            log.warning("model_xgb.pkl introuvable — fallback rule-based actif")
            return False
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            self.model      = data.get("model")
            self.threshold  = data.get("threshold", MIN_CONFIDENCE)
            self.backend    = data.get("backend", "unknown")
            self.trained_at = data.get("trained_at", "?")
            self.loaded     = True
            log.info("Modèle chargé: %s (seuil=%.2f, entraîné=%s)",
                     self.backend, self.threshold, self.trained_at)

            # Vérifier expiration
            try:
                trained_dt = datetime.fromisoformat(self.trained_at)
                age_days   = (datetime.now() - trained_dt).days
                if age_days > MODEL_TTL_DAYS:
                    log.warning("Modèle expire (%d jours) — re-entraîner avec ml_trainer.py", age_days)
            except Exception:
                pass
            return True
        except Exception as e:
            log.error("Erreur chargement modèle: %s", e)
            return False

    def predict(self, features: Dict, tick_data: Dict = None) -> float:
        """Retourne proba [0.0–1.0] ou 0.5 si modèle absent."""
        if not self.loaded or self.model is None:
            return 0.5
        try:
            if tick_data is None: tick_data = {}
            rsi = float(tick_data.get("rsi", features.get("rsi_at_entry", 50)))
            adx = float(tick_data.get("adx", features.get("adx_at_entry", 25)))
            atr = float(tick_data.get("atr", features.get("atr_at_entry", 0.001)))
            spread = float(tick_data.get("spread", features.get("spread_entry", 20)))
            ema_f = float(tick_data.get("ema_fast", 0.0))
            ema_s = float(tick_data.get("ema_slow", 0.0))
            regime = float(tick_data.get("regime", features.get("regime", 0.0)))
            volume = float(tick_data.get("volume", tick_data.get("lot", 0.1)))
            duration = float(tick_data.get("duration", 0.0))
            
            X = [[rsi, adx, atr, spread, ema_f, ema_s, regime, volume, duration]]
            return float(self.model.predict_proba(X)[0][1])
        except Exception as e:
            log.debug("Erreur predict: %s", e)
            return 0.5


# ══════════════════════════════════════════════════════════════════
#  RULE-BASED FALLBACK (si modèle absent)
# ══════════════════════════════════════════════════════════════════

def rule_based_score(tick_data: Dict) -> float:
    """
    Scoring heuristique simple — utilisé si aucun modèle ML disponible.
    Retourne une pseudo-probabilité entre 0.40 et 0.80.
    """
    score = 0.50

    rsi    = float(tick_data.get("rsi",    50))
    adx    = float(tick_data.get("adx",    20))
    spread = float(tick_data.get("spread", 50))
    atr    = float(tick_data.get("atr",    1.0))

    if adx > 25:  score += 0.06
    if adx > 35:  score += 0.04
    if spread < atr * 20: score += 0.05
    if 35 < rsi < 65: score += 0.04
    if spread > 100: score -= 0.12
    if adx < 15:  score -= 0.08

    return round(max(0.35, min(0.85, score)), 4)


# ══════════════════════════════════════════════════════════════════
#  EXTRACTION DE FEATURES DEPUIS TICKS_V3
# ══════════════════════════════════════════════════════════════════

def extract_features_from_tick(tick_data: Dict, prev_rsi: float = 50.0) -> Dict:
    """
    Construit le vecteur de features depuis un enregistrement ticks_v3.json.
    Doit correspondre exactement aux features de ml_feature_engine.py.
    """
    atr    = float(tick_data.get("atr",    0) or 0)
    rsi    = float(tick_data.get("rsi",    50) or 50)
    adx    = float(tick_data.get("adx",    20) or 20)
    spread = float(tick_data.get("spread", 50) or 50)
    ema_f  = float(tick_data.get("ema_fast", 0) or 0)
    ema_s  = float(tick_data.get("ema_slow", 0) or 0)

    now     = datetime.now(UTC)
    hour    = now.hour
    dow     = now.weekday()

    ema_gap = ((ema_f - ema_s) / ema_s * 100) if ema_s != 0 else 0.0

    return {
        "atr_at_entry":     atr,
        "rsi_at_entry":     rsi,
        "adx_at_entry":     adx,
        "spread_entry":     spread,
        "rr_ratio":         float(tick_data.get("rr", 2.0) or 2.0),
        "regime":           int(tick_data.get("regime", 0) or 0),
        "direction":        int(tick_data.get("direction", 1) or 1),
        "lot":              float(tick_data.get("lot", 0.01) or 0.01),
        "hour_utc":         hour,
        "day_of_week":      dow,
        "session_london":   1 if 7  <= hour <= 16 else 0,
        "session_ny":       1 if 13 <= hour <= 21 else 0,
        "atr_rolling_mean": atr,   # Simplifié en live (pas de fenêtre)
        "atr_rolling_std":  0.0,
        "rsi_momentum":     rsi - prev_rsi,
        "ema_gap_pct":      ema_gap,
        "spread_ratio":     spread / max(atr, 0.001),
        "win_rate_rolling": 0.50,  # Neutre si pas d'historique live
        "hit_be":           0,
        "hit_trail":        0,
        "hit_tp_prev":      0,
        "be_triggered":     0,
        "duration_prev":    0,
    }


# ══════════════════════════════════════════════════════════════════
#  PREDICTOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════

class MLPredictor:
    """
    Predictor en temps réel.
    Lit ticks_v3.json toutes les 500ms → écrit ml_signal.json.

    Intégration dans engine.py:
        predictor = MLPredictor(mt5_path=str(cfg.MT5_FILES_PATH))
        predictor.start()
        # Pour lire le signal depuis Python:
        signal = predictor.get_latest_signal("XAUUSD")
    """

    def __init__(self, mt5_path: str = None, model_dir: str = ".",
                 enable_auto_trainer: bool = True):
        self.mt5_path  = Path(mt5_path or os.getenv("MT5_FILES_PATH", MT5_FILES_DEFAULT))
        self.model_dir = Path(model_dir)
        self.loader    = ModelLoader(
            self.model_dir / "model_xgb.pkl",
            self.model_dir / "threshold.json",
        )
        self._running    = False
        self._prev_rsi   = {}         # Par symbole
        self._last_signal: Dict = {}  # Cache dernier signal par symbole
        self._last_signal_log: Dict = {}  # Cooldown anti-spam: ts du dernier log par symbole
        self.predictions_count = 0
        self.signals_emitted   = 0

        # ── AutoTrainer (re-entraînement automatique) ───────────────
        self.auto_trainer: Optional["AutoTrainer"] = None
        if enable_auto_trainer and _AUTO_TRAINER_AVAILABLE:
            trainer_cfg = TrainerConfig()
            trainer_cfg.MT5_FILES_PATH = self.mt5_path
            self.auto_trainer = AutoTrainer(
                cfg      = trainer_cfg,
                mt5_path = str(self.mt5_path),
            )
            log.info("AutoTrainer initialisé (re-train tous les %d jours)",
                     trainer_cfg.RETRAIN_INTERVAL_DAYS)
        else:
            if not _AUTO_TRAINER_AVAILABLE:
                log.info("AutoTrainer non disponible — mode règles seul")

        # ── GradientBoosting Predictor (ml_engine.py) ───────────────
        self.gb_predictor: Optional["GBPredictor"] = None
        if _AUTO_TRAINER_AVAILABLE:
            self.gb_predictor = GBPredictor(
                cfg      = MLConfig(),
                mt5_path = str(self.model_dir),
            )
            if self.gb_predictor.load():
                log.info("GBPredictor chargé (aladdin_model.json)")
            else:
                log.info("GBPredictor: pas de modèle — lancer: python ml_engine.py --demo")
                self.gb_predictor = None

    def start(self):
        self.loader.load()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True, name="MLPredictor")
        t.start()
        log.info("MLPredictor démarré (interval=%.1fs)", POLL_INTERVAL)
        # Démarrer l'AutoTrainer en arrière-plan
        if self.auto_trainer is not None:
            self.auto_trainer.predictor = self.gb_predictor  # Lien pour hot-swap
            self.auto_trainer.start()
            log.info("AutoTrainer démarré en background")

    def stop(self):
        self._running = False
        if self.auto_trainer is not None:
            self.auto_trainer.stop()
            log.info("AutoTrainer arrêté")

    def get_latest_signal(self, symbol: str) -> Optional[Dict]:
        """Retourne le dernier signal ML pour un symbole."""
        return self._last_signal.get(symbol.upper())

    def is_signal_ok(self, symbol: str, direction: int) -> bool:
        """True si le ML confirme l'entrée (proba >= MIN_CONFIDENCE)."""
        sig = self.get_latest_signal(symbol)
        if sig is None:
            return True  # Fallback: autoriser si pas de signal
        if sig.get("signal", 0) == 0:
            return False
        if sig.get("signal") != direction:
            return False
        return sig.get("proba", 0) >= MIN_CONFIDENCE

    def _loop(self):
        while self._running:
            try:
                self._process_tick()
            except Exception as e:
                log.debug("Erreur loop: %s", e)
            time.sleep(POLL_INTERVAL)

    def _process_tick(self):
        tick_path = self.mt5_path / "ticks_v3.json"
        if not tick_path.exists():
            return

        with open(tick_path, encoding="utf-8") as f:
            ticks = json.load(f)

        if not isinstance(ticks, list):
            ticks = [ticks]

        signals_out = {}
        
        # ── Sentiment Filtering (Fundamental Bias) ───────────────────
        sentiment_score = 0
        sentiment_path = Path("gold_sentiment.json")
        if sentiment_path.exists():
            try:
                with open(sentiment_path, encoding="utf-8") as sf:
                    sdata = json.load(sf)
                    sentiment_score = float(sdata.get("analysis", {}).get("score", 0))
            except: pass

        # Lire les assets autorisés depuis .env (TRADING_ASSETS)
        allowed_assets = set(
            s.strip().upper()
            for s in os.getenv("TRADING_ASSETS", "XAUUSD").split(",")
            if s.strip()
        )

        for tick in ticks:
            sym = tick.get("symbol", tick.get("sym", "XAUUSD")).upper()
            
            # Filtrer uniquement les assets configurés dans TRADING_ASSETS
            if sym not in allowed_assets:
                continue
                
            prev_rsi = self._prev_rsi.get(sym, 50.0)

            if self.gb_predictor is not None and self.gb_predictor.model is not None:
                # High-dimensional prediction via gb_predictor logic
                dir_str = "BUY" if tick.get("direction", 1) == 1 else "SELL"
                pred_dict = self.gb_predictor.predict(
                    sym=sym, direction=dir_str, hour=datetime.now(UTC).hour,
                    rsi=float(tick.get("rsi", 50) or 50), adx=float(tick.get("adx", 20) or 20),
                    atr=float(tick.get("atr", 0.001) or 0.001), spread=float(tick.get("spread", 20) or 20),
                    rr=float(tick.get("rr", 2.0) or 2.0), regime=int(tick.get("regime", 0) or 0),
                    ema_fast=float(tick.get("ema_fast", 0) or 0), ema_slow=float(tick.get("ema_slow", 0) or 0),
                )
                proba = pred_dict.get("prob", 0.5)
                self.loader.backend = "Aladdin_GBM_Macro"
            elif self.loader.loaded:
                features = extract_features_from_tick(tick, prev_rsi)
                proba    = self.loader.predict(features, tick)
            else:
                proba = rule_based_score(tick)

            self.predictions_count += 1

            # Détermination du signal
            if proba >= MIN_CONFIDENCE:
                # Direction selon EMA/regime
                regime = int(tick.get("regime", 0) or 0)
                rsi    = float(tick.get("rsi", 50) or 50)
                ema_f  = float(tick.get("ema_fast", 0) or 0)
                ema_s  = float(tick.get("ema_slow", 0) or 0)

                if regime == 0 or (ema_f > ema_s and rsi < 65):
                    signal = 1   # BUY
                elif regime == 1 or (ema_f < ema_s and rsi > 35):
                    signal = -1  # SELL
                else:
                    signal = 0   # NO_TRADE
            else:
                signal = 0

            # ── Decision making based on AI Fundamental Sentiment ─────
            if sym in ["XAUUSD", "GOLD"]:
                if sentiment_score <= -7 and signal == 1:
                    log.warning(f"🚫 BLOCAGE FONDAMENTAL: Sentiment Baissier ({sentiment_score}) bloque BUY Gold")
                    signal = 0
                elif sentiment_score >= 7 and signal == -1:
                    log.warning(f"🚫 BLOCAGE FONDAMENTAL: Sentiment Haussier ({sentiment_score}) bloque SELL Gold")
                    signal = 0

            confidence = ("HIGH"   if proba >= HIGH_CONFIDENCE  else
                          "MED"    if proba >= MIN_CONFIDENCE    else
                          "LOW")

            sig_entry = {
                "sym":        sym,
                "signal":     signal,
                "proba":      round(proba, 4),
                "confidence": confidence,
                "threshold":  self.loader.threshold,
                "ts":         datetime.now(UTC).isoformat(),
                "model":      self.loader.backend or "rule_based",
            }
            signals_out[sym] = sig_entry
            self._last_signal[sym] = sig_entry

            if signal != 0:
                # Cooldown: ne pas réémettre le même signal avant 5 minutes
                import time as _time
                last = self._last_signal.get(sym + "_logged")
                now_ts = _time.time()
                if last is None or (now_ts - last.get("logged_at", 0)) >= 300 or last.get("signal") != signal:
                    self.signals_emitted += 1
                    log.info("SIGNAL %s %s — proba=%.3f [%s]",
                             "BUY" if signal == 1 else "SELL",
                             sym, proba, confidence)
                    self._last_signal[sym + "_logged"] = {"signal": signal, "logged_at": now_ts}

            self._prev_rsi[sym] = float(tick.get("rsi", 50) or 50)

        # Export ml_signal.json (lu par MQL5)
        output = {
            "updated": datetime.now(UTC).isoformat(),
            "model":   self.loader.backend or "rule_based",
            "signals": list(signals_out.values()),
        }
        out_path = self.mt5_path / "ml_signal.json"
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2)
        except IOError as e:
            log.error("Export ml_signal.json: %s", e)

    def status(self) -> str:
        return (
            f"MLPredictor — modèle: {self.loader.backend or 'none'} "
            f"| prédictions: {self.predictions_count} "
            f"| signaux émis: {self.signals_emitted} "
            f"| seuil: {self.loader.threshold:.2f}"
        )


# ══════════════════════════════════════════════════════════════════
#  SNIPPET MQL5 — IsMLSignalOK() à ajouter dans V6.00
# ══════════════════════════════════════════════════════════════════

MQL5_SNIPPET = """
// Ajouter dans OnTick(), AVANT ExecuteEntry():

bool IsMLSignalOK(string symbol, int direction)
{
   // direction: 1=BUY, -1=SELL
   string path = "ml_signal.json";
   if(!FileIsExist(path)) return true;  // Fallback: autoriser
   
   int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) return true;
   string content = "";
   while(!FileIsEnding(h)) content += FileReadString(h);
   FileClose(h);
   
   // Chercher le symbole dans "signals"
   string search = "\\"sym\\":\\"" + symbol + "\\"";
   int pos = StringFind(content, search);
   if(pos < 0) return true;   // Symbole pas dans le JSON = autorisé
   
   // Lire le signal après pos
   int sig_pos = StringFind(content, "\\"signal\\":", pos);
   if(sig_pos < 0 || sig_pos > pos + 200) return true;
   sig_pos += 9;  // sauter "signal":
   int sig_val = (int)StringToInteger(StringSubstr(content, sig_pos, 2));
   
   // Lire la proba
   int pr_pos = StringFind(content, "\\"proba\\":", pos);
   double proba = 0.0;
   if(pr_pos > 0 && pr_pos < pos + 300) {
      proba = StringToDouble(StringSubstr(content, pr_pos+8, 6));
   }
   
   if(sig_val == 0) {
      if(EnableLogs) Print("[ML] NO_TRADE signal — skip");
      return false;
   }
   if(sig_val != direction) {
      if(EnableLogs) Print("[ML] Signal contrarien — skip (sig=",sig_val," dir=",direction,")");
      return false;
   }
   if(proba < 0.58) {
      if(EnableLogs) Print("[ML] Confiance insuffisante: ", proba);
      return false;
   }
   return true;
}

// Avant ExecuteEntry():
// if(EnableMLFilter && !IsMLSignalOK(sym, signal)) { LogSignalRejected(sym,"ML_LOW", ...); continue; }
"""

# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE STANDALONE
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Aladdin Pro — ML Predictor Live")
    parser.add_argument("--mt5-path",   default=None)
    parser.add_argument("--model-dir",  default=".")
    parser.add_argument("--once",       action="store_true", help="Un seul passage (debug)")
    args = parser.parse_args()

    predictor = MLPredictor(
        mt5_path  = args.mt5_path,
        model_dir = args.model_dir,
    )
    predictor.loader.load()

    if args.once:
        predictor._process_tick()
        print(predictor.status())
        print("\nMQL5 Snippet:")
        print(MQL5_SNIPPET)
    else:
        predictor.start()
        try:
            while True:
                time.sleep(10)
                log.info(predictor.status())
        except KeyboardInterrupt:
            predictor.stop()
            print("\nArret MLPredictor.")
