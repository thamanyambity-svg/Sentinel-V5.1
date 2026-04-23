#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V10 — continuous_trainer.py                                ║
║  Moteur d'Optimisation et Re-entraînement Continu                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os, json, time, pickle, logging, shutil, argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("continuous_trainer.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("ContinuousTrainer")

# ── Chemins ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
TRADES_DB  = BASE_DIR / "trades_learning.json"
MODEL_PATH = BASE_DIR / "model_xgb.pkl"
MODELS_DIR = BASE_DIR / "models_archive"
MODELS_DIR.mkdir(exist_ok=True)

# ── Config ───────────────────────────────────────────────────────────
RETRAIN_STEP   = 10      # Re-entraîner tous les 10 nouveaux trades
POLL_INTERVAL  = 300     # Vérifier toutes les 5 minutes
MIN_TRADES     = 50      # Minimum absolu (sauf si --force)

# ══════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════

def load_json(path: Path, default=None):
    try:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.error("Erreur lecture %s: %s", path.name, e)
    return default if default is not None else {}

def save_json(path: Path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error("Erreur écriture %s: %s", path.name, e)

# ══════════════════════════════════════════════════════════════════════
# MOTEUR D'ENTRAÎNEMENT
# ══════════════════════════════════════════════════════════════════════

class ContinuousTrainer:
    def __init__(self):
        self._last_trained_count = self._get_initial_count()
        self._running = False

    def _get_initial_count(self) -> int:
        model = self._load_model_metadata()
        return model.get("n_trades", 0)

    def _load_model_metadata(self) -> Dict:
        if MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    return pickle.load(f)
            except Exception: pass
        return {}

    def _get_trade_count(self) -> int:
        db = load_json(TRADES_DB, {"trades": []})
        return len(db.get("trades", []))

    def start(self):
        self._running = True
        log.info("🚀 ContinuousTrainer démarré | Last count: %d", self._last_trained_count)
        
        while self._running:
            try:
                self._cycle()
            except Exception as e:
                log.error("Erreur cycle: %s", e)
            time.sleep(POLL_INTERVAL)

    def _cycle(self):
        current_count = self._get_trade_count()
        if current_count >= MIN_TRADES and (current_count - self._last_trained_count >= RETRAIN_STEP):
            log.info("🎯 Seuil d'optimisation atteint (%d trades) | Lancement retraining...", current_count)
            self._run_training(current_count)

    def _run_training(self, n_trades: int):
        from ml_trainer import XGBTrainer, _load_model_backend
        
        try:
            db = load_json(TRADES_DB, {"trades": []})
            trades = db.get("trades", [])
            
            # ORDRE CRITIQUE (Doit matcher ml_predictor.py): 
            # [rsi, adx, atr, spread, ema_fast, ema_slow, regime, volume, duration]
            rows = []
            for t in trades:
                rows.append({
                    "features": {
                        "rsi":      float(t.get("rsi", 50)),
                        "adx":      float(t.get("adx", 25)),
                        "atr":      float(t.get("atr", 0.001)),
                        "spread":   float(t.get("spread", 20)),
                        "ema_fast": float(t.get("ema_fast", 0.0)),
                        "ema_slow": float(t.get("ema_slow", 0.0)),
                        "regime":   float(t.get("regime", 0)),
                        "volume":   float(t.get("volume", 0.1)),
                        "duration": float(t.get("duration_s", 0.0))
                    },
                    "label": int(t.get("label", 1 if t.get("result") == "WIN" else 0))
                })
            
            if len(rows) < 2:
                log.warning("⚠️ Pas assez de data pour l'entraînement (min 2).")
                return

            split = int(len(rows) * 0.7)
            if split == 0: split = 1
            train_rows = rows[:split]
            val_rows = rows[split:]
            
            backend_name, xgb_lib = _load_model_backend()
            trainer = XGBTrainer(backend_name, xgb_lib)
            metrics = trainer.train(train_rows, val_rows)
            
            if not metrics:
                log.warning("⚠️ Entraînement échoué.")
                return

            new_auc = metrics.get("val", {}).get("auc", 0)
            new_f1  = metrics.get("val", {}).get("f1", 0)
            old_meta = self._load_model_metadata()
            old_auc = old_meta.get("auc", 0)
            old_n_trades = old_meta.get("n_trades", 0)
            
            # Score composite : priorise F1 quand AUC est peu fiable (peu de données)
            new_score = new_f1 * 0.6 + new_auc * 0.4
            old_score = old_meta.get("deploy_score", old_auc)
            
            # Anti-overfitting : un modèle sur plus de données est plus fiable
            if old_n_trades > 0 and n_trades >= old_n_trades * 2 and new_f1 >= 0.35:
                log.info("🔄 Ancien modèle (%d trades) → remplacé par modèle sur %d trades (F1=%.3f, AUC=%.3f)",
                         old_n_trades, n_trades, new_f1, new_auc)
                self._deploy_model(trainer.model, metrics, n_trades, new_score)
                self._last_trained_count = n_trades
            elif new_score >= old_score or old_score == 0:
                self._deploy_model(trainer.model, metrics, n_trades, new_score)
                self._last_trained_count = n_trades
                log.info("✅ Nouveau modèle déployé | F1: %.3f AUC: %.3f Score: %.3f (vs %.3f)", new_f1, new_auc, new_score, old_score)
            else:
                log.info("⏭ Rejeté | F1: %.3f AUC: %.3f Score: %.3f < %.3f", new_f1, new_auc, new_score, old_score)
                
        except Exception as e:
            log.error("Critical error in training: %s", e)

    def _deploy_model(self, model, metrics, n_trades, deploy_score=0):
        if MODEL_PATH.exists():
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                archive_path = MODELS_DIR / f"model_xgb_{ts}.pkl"
                shutil.copy2(MODEL_PATH, archive_path)
            except Exception: pass
        
        data = {
            "model": model,
            "auc": metrics.get("val", {}).get("auc", 0),
            "f1": metrics.get("val", {}).get("f1", 0),
            "deploy_score": deploy_score,
            "n_trades": n_trades,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "threshold": metrics.get("threshold", 0.58),
            "backend": "XGBoost"
        }
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(data, f)
            
        save_json(BASE_DIR / "threshold.json", {"threshold": data["threshold"]})

if __name__ == "__main__":
    import signal
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    trainer = ContinuousTrainer()
    
    if args.force:
        log.info("🚀 FORCE TRAINING REQUESTED")
        trainer._run_training(trainer._get_trade_count())
    else:
        def shutdown(sig, frame):
            log.info("Arrêt...")
            exit(0)
        signal.signal(signal.SIGINT, shutdown)
        trainer.start()
