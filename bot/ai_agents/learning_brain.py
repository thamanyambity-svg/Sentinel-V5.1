"""
Learning Brain — Cerveau opérationnel pour apprentissage continu
===============================================================
- Log des signaux avant exécution (experience → outcome)
- Filtre ML optionnel (probabilité win)
- Boucle d'évolution (retrain périodique)
- Confiance adaptative par actif/stratégie
"""
import logging
import sqlite3
import os
from typing import Dict, Optional, Tuple

from bot.journal.experience_logger import experience_logger

logger = logging.getLogger("LEARNING_BRAIN")

# Régimes pour le modèle Quant (mapping trend → regime)
TREND_TO_REGIME = {
    "STRONG_UP": "TREND_STABLE",
    "WEAK_UP": "TREND_STABLE",
    "STRONG_DOWN": "TREND_STABLE",
    "WEAK_DOWN": "TREND_STABLE",
    "RANGE": "RANGE_CALM",
}


class LearningBrain:
    """
    Cerveau opérationnel : log des signaux, filtre ML, apprentissage.
    """

    def __init__(self, db_path: str = "bot/data/sentinel.db"):
        self.db_path = db_path
        self._ml_filter = None
        self._load_ml_filter()

    def _load_ml_filter(self):
        """Charge le filtre ML si disponible."""
        try:
            from bot.ai_agents.ml_signal_filter import MLSignalFilter
            self._ml_filter = MLSignalFilter()
            if self._ml_filter.model:
                logger.info("🧠 [LEARNING] ML Signal Filter activé.")
        except Exception as e:
            logger.debug("ML Filter non chargé: %s", e)
            self._ml_filter = None

    def log_signal(self, asset: str, side: str, analysis: Dict, risk_level: str, strategy: str = "SENTINEL_V5") -> Optional[str]:
        """
        Enregistre un signal AVANT exécution pour l'apprentissage.
        Returns signal_id ou None.
        """
        try:
            # Pour QuantTrainer: mapper trend → regime (RANGE_CALM, TREND_STABLE)
            a = dict(analysis)
            a["regime"] = TREND_TO_REGIME.get(a.get("trend", "RANGE"), "RANGE_CALM")
            return experience_logger.log_signal(asset, side, a, risk_level, strategy=strategy)
        except Exception as e:
            logger.error("Log signal error: %s", e)
            return None

    def predict_win_probability(self, change_pct: float, trend: str) -> float:
        """
        Probabilité de gain estimée (0..1).
        Si ML non dispo, retourne 0.5 (neutre).
        """
        if not self._ml_filter or not self._ml_filter.model:
            return 0.5
        regime = TREND_TO_REGIME.get(trend, "RANGE_CALM")
        return self._ml_filter.predict_quality(
            rsi=0.0, atr=0.0, score=float(change_pct), regime=regime
        )

    def should_skip_by_ml(self, change_pct: float, trend: str, min_prob: float = 0.35) -> Tuple[bool, float]:
        """
        Si prob < min_prob → skip le trade (trop risqué d'après le modèle).
        Returns (skip: bool, prob: float)
        """
        prob = self.predict_win_probability(change_pct, trend)
        skip = prob < min_prob and self._ml_filter and self._ml_filter.model
        return skip, prob

    def get_adaptive_confidence_boost(self, asset: str, strategy: str) -> float:
        """
        Bonus de confiance basé sur win rate récent (0.9 .. 1.1).
        Si pas de données, retourne 1.0.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT outcome, COUNT(*) FROM signals
                WHERE asset = ? AND strategy LIKE ? AND outcome IS NOT NULL
                ORDER BY timestamp DESC LIMIT 20
                GROUP BY outcome
            """, (asset, f"%{strategy[:10]}%"))
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return 1.0
            wins = sum(c for o, c in rows if o == 1)
            total = sum(c for _, c in rows)
            if total < 5:
                return 1.0
            win_rate = wins / total
            # Win rate > 0.6 → boost 1.05; < 0.4 → pénalité 0.95
            if win_rate >= 0.6:
                return 1.05
            if win_rate <= 0.4:
                return 0.95
            return 1.0
        except Exception as e:
            logger.debug("Adaptive confidence error: %s", e)
            return 1.0


learning_brain = LearningBrain()
