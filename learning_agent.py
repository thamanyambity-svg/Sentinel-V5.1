#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  SENTINEL V10 — learning_agent.py                                    ║
║  Agent autonome d'apprentissage continu                              ║
║                                                                      ║
║  Missions :                                                          ║
║    1. Collecte chaque trade fermé en temps réel                      ║
║    2. Enrichit chaque trade avec données techniques (RSI/ADX/etc.)   ║
║    3. Déclenche l'entraînement ML dès 50 trades                      ║
║    4. Hot-swap du modèle sans redémarrer le bot                      ║
║    5. Garde l'ancien modèle si le nouveau est moins bon              ║
║    6. Rapport Discord après chaque cycle                             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os, json, time, pickle, logging, threading, shutil, requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("learning_agent.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("LearningAgent")

# ── Chemins ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
MT5_FILES = Path(os.environ.get(
    "MT5_FILES_PATH",
    os.path.expanduser(
        "~/Library/Application Support/net.metaquotes.wine.metatrader5"
        "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
    )
))

TRADES_DB       = BASE_DIR / "trades_learning.json"
MODEL_PATH      = BASE_DIR / "model_xgb.pkl"
MODEL_BACKUP    = BASE_DIR / "model_xgb_backup.pkl"
THRESHOLD_PATH  = BASE_DIR / "threshold.json"

# ── Config ───────────────────────────────────────────────────────────
MIN_TRADES_TO_TRAIN = 50        # Seuil minimum pour entraîner
POLL_INTERVAL       = 10        # Secondes entre chaque vérification
MIN_AUC_TO_REPLACE  = 0.0       # AUC minimum pour remplacer l'ancien modèle
                                 # (0.0 = le nouveau doit juste être meilleur)

# ── Discord (optionnel) ───────────────────────────────────────────────
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")


# ══════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════

def send_discord(msg: str):
    """Envoie une notification Discord si webhook configuré."""
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=5)
    except Exception as e:
        log.debug("Discord error: %s", e)


def load_json(path: Path, default=None):
    """Charge un fichier JSON avec fallback."""
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.debug("load_json %s: %s", path.name, e)
    return default if default is not None else {}


def save_json(path: Path, data):
    """Sauvegarde un fichier JSON de façon atomique."""
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)
    except Exception as e:
        log.error("save_json %s: %s", path.name, e)


# ══════════════════════════════════════════════════════════════════════
# COLLECTEUR DE TRADES
# ══════════════════════════════════════════════════════════════════════

class TradeCollector:
    """
    Surveille les fichiers MT5 et capture chaque trade fermé
    avec ses données techniques enrichies.
    """

    def __init__(self):
        self._known_tickets: set = set()
        self._load_known_tickets()

    def _load_known_tickets(self):
        """Charge les tickets déjà enregistrés pour éviter les doublons."""
        db = load_json(TRADES_DB, {"trades": []})
        self._known_tickets = {
            str(t.get("ticket")) for t in db.get("trades", [])
        }
        log.info("TradeCollector: %d trades existants chargés", len(self._known_tickets))

    def collect(self) -> List[Dict]:
        """
        Vérifie les nouveaux trades fermés dans MT5.
        Retourne la liste des nouveaux trades collectés.
        """
        new_trades = []

        # Lire l'historique des trades depuis MT5
        history_path = MT5_FILES / "trade_history.json"
        history_raw = load_json(history_path, [])
        if isinstance(history_raw, dict):
            history = history_raw.get("trades", [])
        else:
            history = history_raw

        if not history:
            # Fallback: lire status.json pour trades récents
            history = self._extract_from_status()

        for trade in history:
            ticket = str(trade.get("ticket", trade.get("id", "")))
            if not ticket or ticket in self._known_tickets:
                continue

            # Trade nouveau — enrichir avec données techniques
            enriched = self._enrich_trade(trade)
            if enriched:
                new_trades.append(enriched)
                self._known_tickets.add(ticket)
                log.info(
                    "✅ Nouveau trade collecté: %s %s %s | P&L: %+.2f$ | Résultat: %s",
                    enriched.get("symbol"), enriched.get("type"),
                    enriched.get("volume"), enriched.get("pnl", 0),
                    enriched.get("result")
                )

        if new_trades:
            self._save_trades(new_trades)

        return new_trades

    def _extract_from_status(self) -> List[Dict]:
        """Extrait les trades fermés depuis status.json."""
        status_path = MT5_FILES / "status.json"
        data = load_json(status_path, {})
        
        # Ancienne version: liste de trades directs
        if isinstance(data, list):
            return data
            
        # Nouvelle version: dict {"closed_trades": [...]} ou {"trades": [...]}
        return data.get("closed_trades", data.get("trades", []))

    def _enrich_trade(self, trade: Dict) -> Optional[Dict]:
        """
        Enrichit un trade avec les données techniques disponibles.
        Utilise ticks_v3.json pour RSI, ADX, ATR, Spread, Régime.
        """
        sym = trade.get("symbol", trade.get("sym", "")).upper()
        if not sym:
            return None

        # Données techniques depuis ticks_v3.json
        ticks = load_json(MT5_FILES / "ticks_v3.json", [])
        tech = {}
        for tick in (ticks if isinstance(ticks, list) else [ticks]):
            if tick.get("sym", tick.get("symbol", "")).upper() == sym:
                tech = tick
                break

        # Données de marché
        pnl   = float(trade.get("profit", trade.get("pnl", 0)))
        entry = float(trade.get("price_open", trade.get("entry", 0)))
        close = float(trade.get("price_close", trade.get("exit", 0)))

        enriched = {
            # Identifiants
            "ticket":     str(trade.get("ticket", trade.get("id", ""))),
            "symbol":     sym,
            "type":       trade.get("type", "buy"),
            "volume":     float(trade.get("volume", trade.get("lots", 0.01))),

            # Prix
            "entry":      entry,
            "exit":       close,
            "sl":         float(trade.get("sl", 0)),
            "tp":         float(trade.get("tp", 0)),

            # Performance
            "pnl":        pnl,
            "pnl_pips":   float(trade.get("pnl_pips", 0)),
            "duration_s": int(trade.get("duration", 0)),
            "result":     "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE"),

            # Données techniques à l'entrée
            "rsi":        float(tech.get("rsi", 50)),
            "adx":        float(tech.get("adx", 0)),
            "atr":        float(tech.get("atr", 0)),
            "spread":     int(tech.get("spread", 0)),
            "bid":        float(tech.get("bid", entry)),
            "ema_fast":   float(tech.get("ema_fast", 0)),
            "ema_slow":   float(tech.get("ema_slow", 0)),
            "regime":     int(tech.get("regime", 0)),

            # Contexte
            "session":    _get_session(),
            "collected_at": datetime.now(timezone.utc).isoformat(),

            # Label pour ML (1=WIN, 0=LOSS)
            "label":      1 if pnl > 0 else 0,
        }

        return enriched

    def _save_trades(self, new_trades: List[Dict]):
        """Ajoute les nouveaux trades à la base de données."""
        db = load_json(TRADES_DB, {"trades": [], "stats": {}})
        db["trades"].extend(new_trades)

        # Stats mises à jour
        all_trades = db["trades"]
        wins  = sum(1 for t in all_trades if t.get("result") == "WIN")
        total = len(all_trades)
        db["stats"] = {
            "total":      total,
            "wins":       wins,
            "losses":     total - wins,
            "win_rate":   round(wins / total * 100, 1) if total > 0 else 0,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }

        save_json(TRADES_DB, db)
        log.info("DB: %d trades total | WR: %.1f%%",
                 db["stats"]["total"], db["stats"]["win_rate"])


def _get_session() -> str:
    """Détermine la session de marché actuelle."""
    h = datetime.now(timezone.utc).hour
    if 7 <= h < 16:
        return "LONDON"
    elif 13 <= h < 21:
        return "NEW_YORK"
    elif 0 <= h < 8:
        return "ASIA"
    return "OFF"


# ══════════════════════════════════════════════════════════════════════
# ENTRAÎNEUR ML
# ══════════════════════════════════════════════════════════════════════

class MLTrainer:
    """
    Entraîne un modèle XGBoost/GradientBoosting à partir des trades collectés.
    Hot-swap automatique si le nouveau modèle est meilleur.
    """

    FEATURES = [
        "rsi", "adx", "atr", "spread",
        "ema_fast", "ema_slow", "regime",
        "volume", "duration_s",
    ]

    def __init__(self):
        self._training_lock = threading.Lock()
        self._best_auc = self._load_best_auc()

    def _load_best_auc(self) -> float:
        """Charge l'AUC du modèle actuel."""
        if MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    data = pickle.load(f)
                return float(data.get("auc", 0.0))
            except Exception:
                pass
        return 0.0

    def should_train(self) -> bool:
        """Vérifie si on a assez de trades pour entraîner."""
        db = load_json(TRADES_DB, {"trades": []})
        total = len(db.get("trades", []))
        log.info("Trades disponibles: %d / %d requis", total, MIN_TRADES_TO_TRAIN)
        return total >= MIN_TRADES_TO_TRAIN

    def train(self) -> Optional[Dict]:
        """
        Entraîne le modèle. Retourne les métriques ou None si échec.
        """
        if not self._training_lock.acquire(blocking=False):
            log.warning("Entraînement déjà en cours — ignoré")
            return None

        try:
            log.info("🧠 Début entraînement ML...")
            db = load_json(TRADES_DB, {"trades": []})
            trades = db.get("trades", [])

            # Préparer les features
            X, y = [], []
            for t in trades:
                features = [float(t.get(f, 0) or 0) for f in self.FEATURES]
                label = int(t.get("label", 0))
                X.append(features)
                y.append(label)

            if len(X) < MIN_TRADES_TO_TRAIN:
                log.warning("Pas assez de données: %d trades", len(X))
                return None

            # Entraînement avec sklearn GradientBoosting
            metrics = self._train_gradient_boosting(X, y)
            return metrics

        except Exception as e:
            log.error("Erreur entraînement: %s", e)
            return None
        finally:
            self._training_lock.release()

    def _train_gradient_boosting(self, X: List, y: List) -> Optional[Dict]:
        """Entraîne un GradientBoosting et retourne les métriques."""
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import roc_auc_score, accuracy_score
            import numpy as np
        except ImportError:
            log.error("sklearn non disponible — installer: pip install scikit-learn")
            return None

        X_arr = np.array(X, dtype=float)
        y_arr = np.array(y, dtype=int)

        # Split train/validation
        X_train, X_val, y_train, y_val = train_test_split(
            X_arr, y_arr, test_size=0.2, random_state=42, stratify=y_arr
        )

        # Entraînement
        model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )
        model.fit(X_train, y_train)

        # Métriques
        proba_val = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, proba_val)
        acc = accuracy_score(y_val, model.predict(X_val))

        # Trouver le meilleur threshold
        best_thr, best_f1 = 0.5, 0.0
        from sklearn.metrics import f1_score
        for thr in [i / 100 for i in range(40, 80)]:
            preds = (proba_val >= thr).astype(int)
            f1 = f1_score(y_val, preds, zero_division=0)
            if f1 > best_f1:
                best_f1, best_thr = f1, thr

        metrics = {
            "auc":        round(auc, 4),
            "accuracy":   round(acc, 4),
            "threshold":  round(best_thr, 2),
            "n_trades":   len(X),
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "backend":    "gradient_boosting",
            "features":   self.FEATURES,
        }

        log.info("📊 Résultats: AUC=%.3f | ACC=%.3f | THR=%.2f",
                 auc, acc, best_thr)

        # Décision : remplacer ou garder l'ancien modèle
        if auc > self._best_auc + MIN_AUC_TO_REPLACE:
            self._deploy_model(model, metrics)
            self._best_auc = auc
            log.info("✅ Nouveau modèle déployé (AUC %.3f > %.3f)", auc, self._best_auc)
            return metrics
        else:
            log.warning(
                "⚠️ Nouveau modèle inférieur (AUC %.3f ≤ %.3f) — ancien conservé",
                auc, self._best_auc
            )
            metrics["deployed"] = False
            return metrics

    def _deploy_model(self, model, metrics: Dict):
        """
        Déploie le nouveau modèle avec backup de l'ancien.
        Hot-swap sans redémarrer le bot.
        """
        # Backup de l'ancien modèle
        if MODEL_PATH.exists():
            shutil.copy2(MODEL_PATH, MODEL_BACKUP)
            log.info("Backup ancien modèle → model_xgb_backup.pkl")

        # Sauvegarde nouveau modèle
        model_data = {
            "model":      model,
            "backend":    metrics["backend"],
            "threshold":  metrics["threshold"],
            "auc":        metrics["auc"],
            "trained_at": metrics["trained_at"],
            "features":   metrics["features"],
        }
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model_data, f)

        # Sauvegarder le threshold séparément (lu par ml_predictor.py)
        save_json(THRESHOLD_PATH, {
            "threshold":  metrics["threshold"],
            "auc":        metrics["auc"],
            "trained_at": metrics["trained_at"],
        })

        metrics["deployed"] = True
        log.info("🚀 Modèle hot-swappé: %s", MODEL_PATH)


# ══════════════════════════════════════════════════════════════════════
# AGENT PRINCIPAL
# ══════════════════════════════════════════════════════════════════════

class LearningAgent:
    """
    Agent autonome orchestrant collecte + entraînement + déploiement.
    """

    def __init__(self):
        self.collector  = TradeCollector()
        self.trainer    = MLTrainer()
        self._running   = False
        self._cycles    = 0
        self._last_train_count = self._get_trade_count()

    def _get_trade_count(self) -> int:
        db = load_json(TRADES_DB, {"trades": []})
        return len(db.get("trades", []))

    def start(self):
        """Lance l'agent en arrière-plan."""
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True, name="LearningAgent")
        t.start()
        log.info("🤖 LearningAgent démarré (poll=%.0fs, min_trades=%d)",
                 POLL_INTERVAL, MIN_TRADES_TO_TRAIN)
        send_discord("🤖 **LearningAgent démarré** — collecte des trades en cours...")

    def stop(self):
        self._running = False
        log.info("LearningAgent arrêté")

    def _loop(self):
        while self._running:
            try:
                self._cycle()
            except Exception as e:
                log.error("Erreur cycle: %s", e)
            time.sleep(POLL_INTERVAL)

    def _cycle(self):
        self._cycles += 1

        # 1. Collecter nouveaux trades
        new_trades = self.collector.collect()

        if new_trades:
            current_count = self._get_trade_count()
            log.info("📥 %d nouveau(x) trade(s) | Total: %d",
                     len(new_trades), current_count)

            # Discord désactivé ici — sentinel_notifier gère les clôtures (anti-doublon)
            pass  # for t in new_trades: send_discord(...)

        # 2. Vérifier si on doit entraîner (Déplacé hors du bloc IF pour capter les injections manuelles)
        current_count = self._get_trade_count()
        if (current_count >= MIN_TRADES_TO_TRAIN and
                current_count > self._last_train_count):
            self._trigger_training(current_count)

        # Log périodique toutes les 10 minutes
        if self._cycles % (600 // POLL_INTERVAL) == 0:
            count = self._get_trade_count()
            log.info("📊 Status: %d trades | Prochain entraînement: %d",
                     count, max(0, MIN_TRADES_TO_TRAIN - count))

    def _trigger_training(self, trade_count: int):
        """Déclenche l'entraînement dans un thread séparé."""
        log.info("🧠 Déclenchement entraînement (%d trades)...", trade_count)
        # Discord notification removed from here as per user script, but I'll keep it as it's useful
        send_discord(
            f"🧠 **Entraînement ML déclenché** — {trade_count} trades disponibles\n"
            f"Calcul en cours..."
        )

        def _train_thread():
            metrics = self.trainer.train()
            if metrics:
                self._last_train_count = trade_count
                deployed = metrics.get("deployed", False)
                auc = metrics.get("auc", 0)

                if deployed:
                    msg = (
                        f"✅ **Nouveau modèle déployé !**\n"
                        f"AUC: `{auc:.3f}` | "
                        f"Accuracy: `{metrics.get('accuracy', 0):.1%}` | "
                        f"Threshold: `{metrics.get('threshold', 0.58):.2f}` | "
                        f"Trades: `{metrics.get('n_trades', 0)}`"
                    )
                else:
                    msg = (
                        f"⚠️ **Ancien modèle conservé** (nouveau AUC {auc:.3f} insuffisant)\n"
                        f"Le bot continue avec le modèle précédent."
                    )
                log.info(msg.replace("**", "").replace("`", ""))
                send_discord(msg)

        threading.Thread(target=_train_thread, daemon=True).start()

    def status(self) -> Dict:
        """Retourne le statut complet de l'agent."""
        db = load_json(TRADES_DB, {"trades": [], "stats": {}})
        stats = db.get("stats", {})
        return {
            "running":        self._running,
            "cycles":         self._cycles,
            "trades_total":   stats.get("total", 0),
            "win_rate":       stats.get("win_rate", 0),
            "next_train_at":  MIN_TRADES_TO_TRAIN,
            "model_deployed": MODEL_PATH.exists(),
            "best_auc":       self.trainer._best_auc,
        }


# ══════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════

def main():
    import signal

    agent = LearningAgent()
    agent.start()

    def _shutdown(sig, frame):
        log.info("Signal reçu — arrêt propre...")
        agent.stop()
        exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("=" * 60)
    log.info("  LEARNING AGENT ACTIF")
    log.info("  MT5 Path : %s", MT5_FILES)
    log.info("  DB Path  : %s", TRADES_DB)
    log.info("  Seuil    : %d trades pour entraîner", MIN_TRADES_TO_TRAIN)
    log.info("=" * 60)

    # Boucle principale (garder le process vivant)
    try:
        while True:
            time.sleep(60)
            status = agent.status()
            log.info(
                "💓 Heartbeat | Trades: %d | WR: %.1f%% | AUC: %.3f | Modèle: %s",
                status["trades_total"],
                status["win_rate"],
                status["best_auc"],
                "✅ actif" if status["model_deployed"] else "⏳ en attente",
            )
    except KeyboardInterrupt:
        agent.stop()


if __name__ == "__main__":
    main()
