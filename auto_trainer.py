"""
╔══════════════════════════════════════════════════════════════════════╗
║  ALADDIN PRO V6 — auto_trainer.py                                   ║
║                                                                      ║
║  Re-entraînement automatique hebdomadaire du modèle ML              ║
║                                                                      ║
║  FONCTIONNALITÉS:                                                    ║
║  • Re-entraîne toutes les semaines sur les 90 derniers jours        ║
║  • Détecte la dérive du modèle (performance dégradée → re-train)    ║
║  • Versioning: garde les 5 derniers modèles + meilleur historique   ║
║  • Rollback automatique si le nouveau modèle est moins bon          ║
║  • Rapport complet de chaque cycle d'entraînement                   ║
║  • Intégration plug-and-play dans AladdinEngine                     ║
║                                                                      ║
║  Usage standalone:                                                   ║
║    python auto_trainer.py --run                                      ║
║    python auto_trainer.py --status                                   ║
║    python auto_trainer.py --rollback                                 ║
║                                                                      ║
║  Intégration dans engine.py:                                        ║
║    from auto_trainer import AutoTrainer                              ║
║    self.auto_trainer = AutoTrainer(mt5_path=..., predictor=...)     ║
║    self.auto_trainer.start()                                         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import shutil
import logging
import threading
import statistics
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Import local depuis le même dossier
sys.path.insert(0, str(Path(__file__).parent))
from ml_engine import (
    GradientBoostingClassifier, ModelTrainer, LivePredictor,
    FeatureEngineer, evaluate_model, MLConfig,
    load_model, save_model, generate_synthetic_trades
)


log = logging.getLogger("AutoTrainer")


# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

class TrainerConfig:
    # Fréquence de re-entraînement
    RETRAIN_INTERVAL_DAYS   = 7       # Re-entraîner toutes les 7 jours
    DRIFT_CHECK_INTERVAL_H  = 6       # Vérifier la dérive toutes les 6h
    MIN_TRADES_TO_TRAIN     = 50      # Minimum de trades pour re-entraîner
    TRAINING_WINDOW_DAYS    = 90      # Utiliser les 90 derniers jours

    # Seuils de dérive (déclenchent un re-entraînement anticipé)
    DRIFT_AUC_DROP          = 0.06    # AUC baisse de 6% → re-train
    DRIFT_WIN_RATE_DROP     = 0.10    # Win rate baisse de 10% → re-train
    DRIFT_RECENT_WINDOW     = 20      # Évaluer sur les 20 derniers trades

    # Versioning
    MAX_MODEL_VERSIONS      = 5       # Garder 5 versions
    MODELS_DIR              = "models"
    MODEL_REGISTRY          = "model_registry.json"

    # Validation avant déploiement
    MIN_AUC_TO_DEPLOY       = 0.58    # AUC minimum pour déployer
    MIN_IMPROVEMENT         = 0.01    # Amélioration minimale vs modèle actuel

    # Fichiers
    MT5_FILES_PATH          = Path(os.getenv("MT5_FILES_PATH", "./mt5_files"))
    TRADE_LOG_FILE          = "trade_log_all.jsonl"
    TRAINING_LOG_FILE       = "training_history.json"


# ══════════════════════════════════════════════════════════════════
#  CHARGEUR DE TRADES DEPUIS JSONL
# ══════════════════════════════════════════════════════════════════

class TradeLoader:
    """Charge et filtre les trades depuis les fichiers JSONL."""

    def __init__(self, mt5_path: Path):
        self.mt5_path = mt5_path

    def load_recent(self, days: int = 90) -> List[dict]:
        """Charge les trades des N derniers jours depuis les fichiers journaliers."""
        trades = []
        seen   = set()
        today  = date.today()

        for i in range(days + 1):
            d    = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            path = self.mt5_path / f"trade_log_{d}.jsonl"
            if not path.exists():
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            t  = json.loads(line)
                            tk = t.get("ticket", 0)
                            if tk not in seen:
                                seen.add(tk)
                                trades.append(t)
                        except json.JSONDecodeError:
                            continue
            except IOError:
                continue

        # Aussi charger le fichier global si les journaliers sont insuffisants
        if len(trades) < 20:
            all_path = self.mt5_path / "trade_log_all.jsonl"
            if all_path.exists():
                try:
                    with open(all_path, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                t  = json.loads(line)
                                tk = t.get("ticket", 0)
                                if tk not in seen:
                                    seen.add(tk)
                                    trades.append(t)
                            except json.JSONDecodeError:
                                continue
                except IOError:
                    pass

        # Trier chronologiquement
        trades.sort(key=lambda t: t.get("open_time", ""))
        log.info("TradeLoader: %d trades chargés (%d jours)", len(trades), days)
        return trades

    def get_recent_results(self, n: int = 20) -> List[int]:
        """Retourne les N derniers résultats (1=win, 0=loss) pour détection de dérive."""
        trades = self.load_recent(days=7)[-n:]
        return [1 if t.get("net_profit", t.get("profit", 0)) > 0 else 0 for t in trades]


# ══════════════════════════════════════════════════════════════════
#  REGISTRE DE VERSIONS DE MODÈLES
# ══════════════════════════════════════════════════════════════════

class ModelRegistry:
    """Gère le versioning des modèles."""

    def __init__(self, cfg: TrainerConfig):
        self.cfg      = cfg
        self.dir      = Path(cfg.MODELS_DIR)
        self.dir.mkdir(exist_ok=True)
        self.registry = self._load_registry()

    def _load_registry(self) -> List[Dict]:
        path = Path(self.cfg.MODEL_REGISTRY)
        if not path.exists():
            return []
        try:
            with open(path) as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return []

    def _save_registry(self):
        with open(self.cfg.MODEL_REGISTRY, "w") as f:
            json.dump(self.registry, f, indent=2)

    def save_version(self, model: GradientBoostingClassifier, metrics: Dict,
                      n_trades: int) -> str:
        """Sauvegarde une nouvelle version et retourne son chemin."""
        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        version = f"model_v{len(self.registry)+1}_{ts}"
        path    = str(self.dir / f"{version}.json")

        save_model(model, path)

        entry = {
            "version":    version,
            "path":       path,
            "trained_at": datetime.now().isoformat(),
            "n_trades":   n_trades,
            "metrics":    metrics,
            "deployed":   False,
        }
        self.registry.append(entry)
        self._save_registry()
        self._cleanup_old_versions()
        return path

    def deploy(self, version_path: str, target: str = "aladdin_model.json"):
        """Copie une version vers le fichier actif."""
        shutil.copy2(version_path, target)
        for entry in self.registry:
            entry["deployed"] = (entry["path"] == version_path)
        self._save_registry()
        log.info("Modèle déployé: %s → %s", version_path, target)

    def get_current_deployed(self) -> Optional[Dict]:
        deployed = [e for e in self.registry if e.get("deployed")]
        return deployed[-1] if deployed else None

    def get_best_version(self) -> Optional[Dict]:
        if not self.registry:
            return None
        return max(self.registry, key=lambda e: e["metrics"].get("auc_roc", 0))

    def get_rollback_candidate(self) -> Optional[Dict]:
        deployed = self.get_current_deployed()
        if not deployed:
            return None
        candidates = [e for e in self.registry
                      if e["path"] != deployed["path"]
                      and e["metrics"].get("auc_roc", 0) > 0.55]
        return max(candidates, key=lambda e: e["metrics"].get("auc_roc", 0)) if candidates else None

    def _cleanup_old_versions(self):
        if len(self.registry) <= self.cfg.MAX_MODEL_VERSIONS:
            return
        deployed_path = (self.get_current_deployed() or {}).get("path", "")
        non_deployed  = [e for e in self.registry if e["path"] != deployed_path]
        to_delete     = non_deployed[:-self.cfg.MAX_MODEL_VERSIONS]
        for entry in to_delete:
            try:
                os.remove(entry["path"])
            except OSError:
                pass
            self.registry.remove(entry)
        self._save_registry()

    def format_history(self) -> str:
        if not self.registry:
            return "  Aucun modèle entraîné."
        lines = ["  VERSION  TRAINED_AT            TRADES  AUC    ACC    DEPLOYED"]
        lines.append("  " + "-"*65)
        for e in self.registry[-5:]:
            m   = e.get("metrics", {})
            dep = "✅" if e.get("deployed") else "  "
            lines.append(
                f"  {dep} {e['version'][:20]:<22}"
                f"  {e['n_trades']:>5}"
                f"  {m.get('auc_roc',0):.3f}"
                f"  {m.get('accuracy',0):.1%}"
            )
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  DÉTECTEUR DE DÉRIVE
# ══════════════════════════════════════════════════════════════════

class DriftDetector:
    """Surveille la dégradation du modèle en production."""

    def __init__(self, cfg: TrainerConfig):
        self.cfg            = cfg
        self.baseline_wr:   Optional[float] = None
        self.baseline_auc:  Optional[float] = None
        self.drift_alerts:  List[Dict]      = []

    def set_baseline(self, metrics: Dict):
        self.baseline_wr  = metrics.get("recall", 0.5)
        self.baseline_auc = metrics.get("auc_roc", 0.65)

    def check(self, recent_results: List[int]) -> Tuple[bool, str]:
        """Vérifie si la dérive est significative. Retourne (is_drifted, reason)."""
        if not recent_results or len(recent_results) < 10:
            return False, "Pas assez de données récentes"

        recent_wr = statistics.mean(recent_results)
        alerts = []
        drifted = False

        if self.baseline_wr and (self.baseline_wr - recent_wr) > self.cfg.DRIFT_WIN_RATE_DROP:
            alerts.append(
                f"Win rate: {recent_wr:.1%} vs baseline {self.baseline_wr:.1%} "
                f"(chute de {self.baseline_wr-recent_wr:.1%})"
            )
            drifted = True

        if len(recent_results) >= 5:
            last5_wr = statistics.mean(recent_results[-5:])
            if last5_wr < 0.3:
                alerts.append(f"Alerte: seulement {last5_wr:.0%} WR sur les 5 derniers trades")
                drifted = True

        losses_streak = 0
        for r in reversed(recent_results):
            if r == 0:
                losses_streak += 1
            else:
                break
        if losses_streak >= 7:
            alerts.append(f"Série de {losses_streak} pertes consécutives détectée")
            drifted = True

        reason = " | ".join(alerts) if alerts else "Aucune dérive détectée"

        if drifted:
            self.drift_alerts.append({
                "ts":       datetime.now().isoformat(),
                "reason":   reason,
                "recent_wr": round(recent_wr, 3),
            })

        return drifted, reason


# ══════════════════════════════════════════════════════════════════
#  AUTO TRAINER PRINCIPAL
# ══════════════════════════════════════════════════════════════════

class AutoTrainer:
    """
    Orchestre le cycle complet de re-entraînement automatique.
    Plug-and-play dans AladdinEngine.
    """

    def __init__(self, cfg: TrainerConfig = None,
                 mt5_path: str = None,
                 predictor: Optional[LivePredictor] = None):
        self.cfg = cfg or TrainerConfig()
        if mt5_path:
            self.cfg.MT5_FILES_PATH = Path(mt5_path)

        self.predictor = predictor
        self.loader    = TradeLoader(self.cfg.MT5_FILES_PATH)
        self.registry  = ModelRegistry(self.cfg)
        self.drift     = DriftDetector(self.cfg)
        self.trainer   = ModelTrainer(MLConfig())

        self._running  = False
        self._thread:  Optional[threading.Thread] = None
        self._lock     = threading.Lock()

        self.last_train_time: Optional[datetime] = None
        self.last_check_time: Optional[datetime] = None
        self.training_history: List[Dict]        = self._load_history()
        self.status_msg: str                     = "Non démarré"

    def start(self):
        """Démarre le thread de surveillance et re-entraînement."""
        self._running = True
        self._thread  = threading.Thread(
            target=self._main_loop, daemon=True, name="AutoTrainer"
        )
        self._thread.start()
        log.info("AutoTrainer démarré (interval: %d jours)", self.cfg.RETRAIN_INTERVAL_DAYS)
        self.status_msg = "Actif — en attente du prochain cycle"

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("AutoTrainer arrêté")

    def force_retrain(self) -> Dict:
        """Force un re-entraînement immédiat."""
        log.info("Re-entraînement forcé déclenché manuellement")
        return self._run_training_cycle(reason="MANUAL")

    # ── Boucle principale ──────────────────────────────────────────

    def _main_loop(self):
        time.sleep(60)  # Attente initiale

        while self._running:
            try:
                now = datetime.now()

                drift_interval = timedelta(hours=self.cfg.DRIFT_CHECK_INTERVAL_H)
                if (self.last_check_time is None or now - self.last_check_time > drift_interval):
                    self._check_drift()
                    self.last_check_time = now

                retrain_interval = timedelta(days=self.cfg.RETRAIN_INTERVAL_DAYS)
                if (self.last_train_time is None or now - self.last_train_time > retrain_interval):
                    self._run_training_cycle(reason="SCHEDULED_WEEKLY")

                time.sleep(3600)

            except Exception as e:
                log.error("AutoTrainer erreur: %s", e)
                self.status_msg = f"Erreur: {e}"
                time.sleep(300)

    # ── Vérification de dérive ─────────────────────────────────────

    def _check_drift(self):
        log.debug("Vérification de dérive...")
        recent = self.loader.get_recent_results(self.cfg.DRIFT_RECENT_WINDOW)
        drifted, reason = self.drift.check(recent)

        if drifted:
            log.warning("DÉRIVE DÉTECTÉE: %s", reason)
            self.status_msg = f"Dérive détectée: {reason}"
            n_trades = len(self.loader.load_recent(self.cfg.TRAINING_WINDOW_DAYS))
            if n_trades >= self.cfg.MIN_TRADES_TO_TRAIN:
                log.info("Re-entraînement anticipé déclenché (dérive)")
                self._run_training_cycle(reason=f"DRIFT: {reason}")
            else:
                log.warning("Dérive détectée mais seulement %d trades (min %d)",
                            n_trades, self.cfg.MIN_TRADES_TO_TRAIN)
        else:
            self.status_msg = f"Modèle stable — dernier check: {datetime.now().strftime('%H:%M')}"

    # ── Cycle de re-entraînement ───────────────────────────────────

    def _run_training_cycle(self, reason: str = "SCHEDULED") -> Dict:
        """Cycle complet: charge → entraîne → compare → déploie."""
        with self._lock:
            cycle_start = datetime.now()
            self.status_msg = f"Entraînement en cours ({reason})..."
            log.info("=== CYCLE ENTRAÎNEMENT: %s ===", reason)

            result = {
                "ts":       cycle_start.isoformat(),
                "reason":   reason,
                "success":  False,
                "deployed": False,
                "metrics":  {},
                "n_trades": 0,
                "message":  "",
            }

            # Étape 1: Chargement
            trades = self.loader.load_recent(self.cfg.TRAINING_WINDOW_DAYS)
            result["n_trades"] = len(trades)

            if len(trades) < self.cfg.MIN_TRADES_TO_TRAIN:
                msg = (f"Seulement {len(trades)} trades "
                       f"(min requis: {self.cfg.MIN_TRADES_TO_TRAIN}). "
                       f"Continuez à logger.")
                log.warning(msg)
                result["message"] = msg
                self.status_msg = f"En attente: {len(trades)}/{self.cfg.MIN_TRADES_TO_TRAIN} trades"
                self._save_history(result)
                return result

            # Integration Massive Data (Pipeline Enrichissement)
            try:
                import sys
                injector_path = os.path.join(os.path.dirname(__file__), "bot/ai_agents")
                if injector_path not in sys.path:
                    sys.path.append(injector_path)
                from massive_feature_injector import get_macro_features

                log.info("Injection des données macro Massive (S&P 500, Volume Global)...")
                for t in trades:
                    macro = get_macro_features(t.get("symbol", "EURUSD"), t.get("open_time", datetime.now().isoformat()))
                    t.update(macro)
            except Exception as e:
                log.error(f"Erreur lors de l'injection Massive API: {e}")

            # Étape 2: Entraînement
            log.info("Entraînement sur %d trades avec support Macro...", len(trades))
            train_result = self.trainer.run(trades, verbose=False)

            if not train_result or "metrics" not in train_result:
                result["message"] = "Entraînement échoué"
                self.status_msg   = "Erreur entraînement"
                self._save_history(result)
                return result

            new_metrics = train_result["metrics"]
            result["metrics"] = new_metrics
            result["success"] = True
            new_auc = new_metrics.get("auc_roc", 0)

            # Étape 3: Comparaison
            current     = self.registry.get_current_deployed()
            current_auc = (current or {}).get("metrics", {}).get("auc_roc", 0.0)

            should_deploy = False
            deploy_reason = ""

            if new_auc < self.cfg.MIN_AUC_TO_DEPLOY:
                deploy_reason = f"AUC {new_auc:.3f} < minimum {self.cfg.MIN_AUC_TO_DEPLOY:.3f} — rejeté"

            elif current_auc == 0.0:
                should_deploy = True
                deploy_reason = "Premier modèle — déploiement automatique"

            elif new_auc >= current_auc + self.cfg.MIN_IMPROVEMENT:
                should_deploy = True
                deploy_reason = f"Amélioration: {current_auc:.3f} → {new_auc:.3f} (+{new_auc-current_auc:.3f})"

            elif new_auc >= current_auc - 0.005:
                should_deploy = True
                deploy_reason = f"Modèle équivalent mis à jour (AUC {new_auc:.3f}) — données plus fraîches"

            else:
                deploy_reason = f"Régression: {new_auc:.3f} < actuel {current_auc:.3f} — conserve ancien"
                best = self.registry.get_best_version()
                if best and best.get("metrics", {}).get("auc_roc", 0) > current_auc:
                    log.info("Rollback vers meilleure version: AUC %.3f", best["metrics"]["auc_roc"])
                    self.registry.deploy(best["path"])
                    self._reload_predictor()

            # Étape 4: Sauvegarde et déploiement
            version_path = self.registry.save_version(self.trainer.model, new_metrics, len(trades))

            if should_deploy:
                self.registry.deploy(version_path)
                result["deployed"] = True
                self.drift.set_baseline(new_metrics)
                self._reload_predictor()
                log.info("✅ Déployé: %s", deploy_reason)
            else:
                log.info("⏭ Non déployé: %s", deploy_reason)

            result["message"]    = deploy_reason
            self.last_train_time = cycle_start
            duration = (datetime.now() - cycle_start).total_seconds()
            self.status_msg = (
                f"{'✅ Déployé' if result['deployed'] else '⏭ Conservé'} "
                f"— AUC {new_auc:.3f} — {len(trades)} trades — {duration:.1f}s"
            )

            log.info("=== CYCLE TERMINÉ en %.1fs: %s ===", duration, deploy_reason)
            self._save_history(result)
            return result

    # ── Rechargement du prédicteur live ───────────────────────────

    def _reload_predictor(self):
        if self.predictor is not None:
            loaded = self.predictor.load()
            if loaded:
                log.info("LivePredictor rechargé avec le nouveau modèle")
            else:
                log.error("Échec rechargement LivePredictor")
        else:
            log.info("(Pas de LivePredictor attaché — rechargement manuel requis)")

    # ── Persistance de l'historique ────────────────────────────────

    def _load_history(self) -> List[Dict]:
        try:
            with open(self.cfg.TRAINING_LOG_FILE) as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return []

    def _save_history(self, entry: Dict):
        self.training_history.append(entry)
        try:
            with open(self.cfg.TRAINING_LOG_FILE, "w") as f:
                json.dump(self.training_history, f, indent=2)
        except IOError as e:
            log.error("Sauvegarde historique: %s", e)

    # ── Rapport de statut ──────────────────────────────────────────

    def status_report(self) -> str:
        SEP = "=" * 60
        now = datetime.now()

        if self.last_train_time:
            next_train = self.last_train_time + timedelta(days=self.cfg.RETRAIN_INTERVAL_DAYS)
            next_str   = next_train.strftime("%Y-%m-%d %H:%M")
            eta_h      = max(0, (next_train - now).total_seconds() / 3600)
            next_info  = f"{next_str}  (dans {eta_h:.1f}h)"
        else:
            next_info  = f"Dès que {self.cfg.MIN_TRADES_TO_TRAIN} trades disponibles"

        deployed = self.registry.get_current_deployed()
        dep_str  = "Aucun"
        if deployed:
            dep_auc = deployed.get("metrics", {}).get("auc_roc", 0)
            dep_str = (f"{deployed['version'][:25]}"
                       f"  AUC:{dep_auc:.3f}"
                       f"  ({deployed['n_trades']} trades)")

        recent    = self.loader.get_recent_results(20)
        recent_wr = statistics.mean(recent) * 100 if recent else 0

        lines = [
            "", SEP,
            "  ALADDIN ML — Auto Trainer Status",
            SEP,
            f"  Statut:           {self.status_msg}",
            f"  Modèle déployé:   {dep_str}",
            f"  Dernier train:    {self.last_train_time.strftime('%Y-%m-%d %H:%M') if self.last_train_time else 'Jamais'}",
            f"  Prochain train:   {next_info}",
            f"  WR récent (20t):  {recent_wr:.1f}%",
            f"  Alertes dérive:   {len(self.drift.drift_alerts)}",
            "",
            "  VERSIONS ENREGISTRÉES:",
            self.registry.format_history(),
            "",
            "  HISTORIQUE D'ENTRAÎNEMENT:",
        ]

        if self.training_history:
            for entry in self.training_history[-5:]:
                m   = entry.get("metrics", {})
                dep = "✅" if entry.get("deployed") else "⏭"
                lines.append(
                    f"  {dep} {entry['ts'][:16]}"
                    f"  {entry['n_trades']:>4}t"
                    f"  AUC:{m.get('auc_roc',0):.3f}"
                    f"  [{entry['reason'][:20]}]"
                    f"  {entry.get('message','')[:35]}"
                )
        else:
            lines.append("  Aucun cycle entraîné.")

        lines.append(SEP)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  PATCH engine.py — CODE À AJOUTER
# ══════════════════════════════════════════════════════════════════

ENGINE_PATCH = """
# ── Dans engine.py, dans __init__() ──────────────────────────────

from auto_trainer import AutoTrainer, TrainerConfig
from ml_engine   import LivePredictor, MLConfig

# Prédicteur ML
self.ml_predictor = LivePredictor(cfg=MLConfig(), mt5_path=str(self.cfg.MT5_FILES_PATH))
ml_loaded = self.ml_predictor.load()
if not ml_loaded:
    self.log.warning("ML: Pas de modèle — lancer: python ml_engine.py --demo")
    self.ml_predictor = None

# Auto-trainer
trainer_cfg = TrainerConfig()
trainer_cfg.MT5_FILES_PATH = self.cfg.MT5_FILES_PATH
self.auto_trainer = AutoTrainer(
    cfg=trainer_cfg,
    mt5_path=str(self.cfg.MT5_FILES_PATH),
    predictor=self.ml_predictor,
)
self.auto_trainer.start()

# ── Dans stop() ──────────────────────────────────────────────────
if hasattr(self, "auto_trainer"):
    self.auto_trainer.stop()

# ── Dans _poll_ticks() — avant ExecuteEntry() ────────────────────
def _is_ml_allowed(self, sym, direction, rsi, adx, atr, spread, rr, regime, hour):
    if self.ml_predictor is None:
        return True
    result = self.ml_predictor.predict(
        sym=sym, direction=direction, hour=hour,
        rsi=rsi, adx=adx, atr=atr, spread=spread,
        rr=rr, regime=regime,
        consec_losses=self._state.consecutive_losses,
    )
    if result["trade"] == 0:
        self._raise_alert(AlertLevel.INFO,
            f"ML-SKIP {sym} {direction}: {result['prob']:.1%}", sym)
        return False
    return True

# ── Dans get_snapshot() ──────────────────────────────────────────
if hasattr(self, "auto_trainer"):
    snap["auto_trainer"] = {
        "status":     self.auto_trainer.status_msg,
        "last_train": (self.auto_trainer.last_train_time.isoformat()
                       if self.auto_trainer.last_train_time else None),
    }
if self.ml_predictor:
    snap["ml"] = self.ml_predictor.stats()
"""


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE STANDALONE
# ══════════════════════════════════════════════════════════════════

def main():
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="Aladdin Auto Trainer")
    parser.add_argument("--run",      action="store_true", help="Forcer un cycle maintenant")
    parser.add_argument("--status",   action="store_true", help="Afficher le statut")
    parser.add_argument("--rollback", action="store_true", help="Rollback vers meilleure version")
    parser.add_argument("--demo",     action="store_true", help="Demo avec données synthétiques")
    parser.add_argument("--mt5-path", default=None)
    args = parser.parse_args()

    cfg = TrainerConfig()
    if args.mt5_path:
        cfg.MT5_FILES_PATH = Path(args.mt5_path)

    trainer = AutoTrainer(cfg=cfg)

    if args.demo:
        print("\n[DEMO] Simulation d'un cycle d'entraînement complet...\n")
        from ml_engine import generate_synthetic_trades, ModelTrainer as MLTrainer, MLConfig

        trades = generate_synthetic_trades(200, seed=42)
        print(f"  {len(trades)} trades synthétiques générés")

        # Entraînement direct en mémoire (contourne le TradeLoader pour le démo)
        ml_trainer = MLTrainer(MLConfig())
        train_result = ml_trainer.run(trades, verbose=True)

        if train_result and "metrics" in train_result:
            new_metrics  = train_result["metrics"]
            version_path = trainer.registry.save_version(ml_trainer.model, new_metrics, len(trades))
            trainer.registry.deploy(version_path)
            trainer.drift.set_baseline(new_metrics)
            trainer.last_train_time = datetime.now()
            trainer.status_msg = (
                f"✅ Déployé (DEMO) — AUC {new_metrics.get('auc_roc',0):.3f} "
                f"— {len(trades)} trades synthétiques"
            )
            result = {"ts": datetime.now().isoformat(), "reason": "DEMO",
                      "success": True, "deployed": True,
                      "metrics": new_metrics, "n_trades": len(trades),
                      "message": "Déploiement démo réussi"}
            trainer._save_history(result)
        else:
            trainer.status_msg = "Erreur entraînement démo"
            result = {}

        print(trainer.status_report())

    elif args.run:
        result = trainer.force_retrain()
        print(trainer.status_report())

    elif args.rollback:
        candidate = trainer.registry.get_rollback_candidate()
        if candidate:
            print(f"\nRollback vers: {candidate['version']}")
            print(f"AUC: {candidate['metrics'].get('auc_roc', 0):.3f}")
            trainer.registry.deploy(candidate["path"])
            print("Rollback effectué.")
        else:
            print("Aucun candidat de rollback disponible.")

    elif args.status:
        print(trainer.status_report())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
