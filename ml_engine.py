"""
╔══════════════════════════════════════════════════════════════════════╗
║  ALADDIN PRO V6 — ml_engine.py                                      ║
║                                                                      ║
║  Couche Machine Learning — 100% stdlib Python (aucune dépendance)   ║
║                                                                      ║
║  MODULES:                                                            ║
║  1. FeatureEngineer   — Construit 25+ features depuis les logs      ║
║  2. DecisionTree      — Arbre de décision CART from scratch         ║
║  3. GradientBoosting  — XGBoost-like boosting from scratch          ║
║  4. SignalClassifier  — Classifie TRADE/NO-TRADE + proba            ║
║  5. ModelTrainer      — Entraînement, validation, persistance       ║
║  6. LivePredictor     — Intégration temps réel avec engine.py       ║
║                                                                      ║
║  PIPELINE:                                                           ║
║    trade_log_all.jsonl                                               ║
║         ↓                                                            ║
║    FeatureEngineer.build_dataset()                                   ║
║         ↓                                                            ║
║    GradientBoosting.fit(X, y)                                        ║
║         ↓                                                            ║
║    model.json (persistance)                                          ║
║         ↓                                                            ║
║    LivePredictor.predict(tick_data) → {"trade": 0/1, "prob": 0.73}  ║
║                                                                      ║
║  Usage:                                                              ║
║    python ml_engine.py --train --data trade_log_all.jsonl           ║
║    python ml_engine.py --evaluate                                    ║
║    python ml_engine.py --predict --sym XAUUSD --rsi 52 --adx 28    ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import math
import random
import argparse
import statistics
import os
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict


# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

class MLConfig:
    # Chemins
    MODEL_FILE          = "aladdin_model.json"
    FEATURE_STATS_FILE  = "feature_stats.json"
    MT5_PREDICT_FILE    = "ml_signal.json"   # Lu par le bot MQL5

    # Gradient Boosting
    N_ESTIMATORS        = 80      # Nombre d'arbres
    MAX_DEPTH           = 4       # Profondeur max par arbre
    LEARNING_RATE       = 0.12    # Shrinkage (eta)
    MIN_SAMPLES_SPLIT   = 8       # Min samples pour splitter un nœud
    MIN_SAMPLES_LEAF    = 4       # Min samples dans une feuille
    SUBSAMPLE           = 0.8     # Fraction de données par arbre
    COLSAMPLE           = 0.8     # Fraction de features par split

    # Entraînement
    TEST_SIZE           = 0.25    # 75% train, 25% test
    POSITIVE_LABEL      = 1       # Trade = 1 si net_profit > MIN_WIN
    MIN_WIN_THRESHOLD   = 0.0     # net_profit > 0 → win

    # Seuil de décision
    DEFAULT_THRESHOLD   = 0.55    # prob > 0.55 → recommander le trade

    # Features
    REGIME_NAMES = {0:"TREND_UP", 1:"TREND_DOWN", 2:"RANGING", 3:"VOLATILE"}


# ══════════════════════════════════════════════════════════════════
#  FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════

@dataclass
class FeatureVector:
    """Un vecteur de features normalisé pour un trade."""
    # Indicateurs bruts
    rsi:             float   # RSI à l'entrée
    adx:             float   # ADX à l'entrée
    atr_norm:        float   # ATR normalisé (ATR / prix * 1000)
    spread_norm:     float   # Spread / ATR
    rr_ratio:        float   # Ratio R:R
    ema_diff:        float   # (EMA_fast - EMA_slow) / ATR — momentum EMA
    # Contexte marché
    regime_up:       float   # One-hot: régime haussier
    regime_down:     float   # One-hot: régime baissier
    regime_ranging:  float   # One-hot: ranging
    regime_volatile: float   # One-hot: volatile
    is_buy:          float   # Direction: 1=BUY, 0=SELL
    # Contexte temporel
    hour_sin:        float   # Heure encodée sin (cyclique)
    hour_cos:        float   # Heure encodée cos
    is_london:       float   # 1 si session Londres (07-16 UTC)
    is_ny:           float   # 1 si session New York (13-21 UTC)
    is_overlap:      float   # 1 si overlap Londres/NY (13-16 UTC)
    # Features dérivées
    rsi_extreme:     float   # |RSI - 50| / 50 (proximité zones extrêmes)
    adx_strength:    float   # ADX > 25 → 1.0, sinon proportion
    momentum:        float   # ema_diff signé (positif = trend haussier)
    vol_regime:      float   # ATR vs ATR moyen historique (z-score approx)
    # Historique récent (contexte)
    recent_win_rate: float   # Win rate des 5 derniers trades
    recent_pnl_norm: float   # PnL cumulé 5 derniers / balance
    consec_losses:   float   # Pertes consécutives normalisées (0-1)
    # Symbole
    sym_gold:        float   # 1 si XAUUSD
    sym_forex:       float   # 1 si paire Forex
    sym_index:       float   # 1 si indice
    # Massive API Macro Features
    massive_volume_d1: float # Volume quotidien réel
    daily_trend:       float # Variation du prix quotidien (Close - Open)
    macro_spy_trend:   float # Tendance du S&P 500 (Close - Open)
    macro_spy_volume:  float # Volume quotidien S&P 500

    def to_list(self) -> List[float]:
        return list(asdict(self).values())

    @staticmethod
    def feature_names() -> List[str]:
        return list(FeatureVector.__dataclass_fields__.keys())


class FeatureEngineer:
    """
    Construit les features depuis les logs de trades JSONL.
    Normalise et gère le contexte glissant (recent_win_rate, etc.)
    """

    def __init__(self, config: MLConfig = None):
        self.cfg   = config or MLConfig()
        self.stats = {}   # Stats de normalisation (mean, std)

    def _parse_hour(self, time_str: str) -> int:
        """Extrait l'heure UTC depuis 'YYYY.MM.DD HH:MM:SS' ou ISO."""
        try:
            for fmt in ["%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(time_str, fmt).hour
                except ValueError:
                    continue
        except Exception:
            pass
        return 12   # Valeur neutre par défaut

    def _sym_type(self, sym: str) -> Tuple[float, float, float]:
        """Retourne (is_gold, is_forex, is_index)."""
        s = sym.upper()
        if "XAU" in s or "GOLD" in s:
            return 1.0, 0.0, 0.0
        if any(x in s for x in ["US30","NAS","SPX","DAX","FTSE","CAC","DJ"]):
            return 0.0, 0.0, 1.0
        return 0.0, 1.0, 0.0

    def build_dataset(self, trades: List[dict]) -> Tuple[List[List[float]], List[int]]:
        """
        Construit X (features) et y (labels) depuis les trades loggés.
        y = 1 si le trade était profitable, 0 sinon.
        """
        if not trades:
            return [], []

        # Trier chronologiquement
        trades = sorted(trades, key=lambda t: t.get("open_time", ""))

        # Calculer l'ATR moyen global pour normalisation
        atrs = [t.get("atr_at_entry", 0) for t in trades if t.get("atr_at_entry", 0) > 0]
        atr_mean = statistics.mean(atrs) if atrs else 1.0
        atr_std  = statistics.stdev(atrs) if len(atrs) > 1 else 1.0

        X, y = [], []
        recent_results = []   # Fenêtre glissante des 10 derniers résultats

        for t in trades:
            try:
                fv = self._build_feature_vector(t, atr_mean, atr_std, recent_results)
                label = 1 if t.get("net_profit", t.get("profit", 0)) > self.cfg.MIN_WIN_THRESHOLD else 0
                X.append(fv.to_list())
                y.append(label)
                # Mise à jour du contexte glissant
                recent_results.append(label)
                if len(recent_results) > 10:
                    recent_results.pop(0)
            except Exception:
                continue

        return X, y

    def _build_feature_vector(self, t: dict, atr_mean: float, atr_std: float,
                               recent: List[int]) -> FeatureVector:
        rsi    = float(t.get("rsi_at_entry", 50))
        adx    = float(t.get("adx_at_entry", 20))
        atr    = float(t.get("atr_at_entry", atr_mean))
        spread = float(t.get("spread_entry", 20))
        rr     = float(t.get("rr_ratio", 1.5))
        regime = int(t.get("regime", 2))
        sym    = t.get("symbol", "")
        direction = t.get("direction", "BUY")
        open_price = float(t.get("open_price", 1.0)) or 1.0

        ema_fast = float(t.get("ema_fast", 0))
        ema_slow = float(t.get("ema_slow", 0))
        consec   = float(t.get("consec_before", 0))  # pertes avant ce trade
        balance  = float(t.get("balance", 1000))      or 1000.0

        # Session
        hour = self._parse_hour(t.get("open_time", ""))
        is_london  = 1.0 if 7  <= hour < 16 else 0.0
        is_ny      = 1.0 if 13 <= hour < 21 else 0.0
        is_overlap = 1.0 if 13 <= hour < 16 else 0.0

        # Normalisation ATR
        atr_norm    = (atr / open_price) * 1000    # en ‰ du prix
        spread_norm = spread / (atr * 10000 + 1e-10)  # spread relatif à ATR

        # Momentum EMA
        ema_diff = 0.0
        if ema_fast > 0 and ema_slow > 0 and atr > 0:
            ema_diff = (ema_fast - ema_slow) / atr

        # Régime one-hot
        r_up   = 1.0 if regime == 0 else 0.0
        r_down = 1.0 if regime == 1 else 0.0
        r_rang = 1.0 if regime == 2 else 0.0
        r_vol  = 1.0 if regime == 3 else 0.0

        # Features dérivées
        rsi_extreme   = abs(rsi - 50) / 50.0
        adx_strength  = min(adx / 25.0, 1.5)
        momentum      = ema_diff * (1 if direction == "BUY" else -1)
        vol_regime    = min(max((atr - atr_mean) / (atr_std + 1e-10), -2), 2) / 2.0

        rwr = statistics.mean(recent) if recent else 0.5
        rpnl = 0.0  # simplifié — non disponible sans historique complet
        cl_norm = min(consec / 5.0, 1.0)

        # Symbole
        sg, sf, si = self._sym_type(sym)

        # Massive Data
        mv_d1 = float(t.get("massive_volume_d1", 0.0))
        d_trend = float(t.get("daily_trend", 0.0))
        sp_trend = float(t.get("macro_spy_trend", 0.0))
        sp_vol = float(t.get("macro_spy_volume", 0.0))

        # Normalisations basiques pour éviter des valeurs immenses (XGBoost supporte mais c'est mieux)
        mv_d1 = math.log1p(mv_d1) / 15.0 if mv_d1 > 0 else 0.0
        sp_vol = math.log1p(sp_vol) / 15.0 if sp_vol > 0 else 0.0

        return FeatureVector(
            rsi=rsi / 100.0,
            adx=adx / 50.0,
            atr_norm=min(atr_norm / 10.0, 1.0),
            spread_norm=min(spread_norm, 1.0),
            rr_ratio=min(rr / 4.0, 1.0),
            ema_diff=math.tanh(ema_diff),
            regime_up=r_up, regime_down=r_down,
            regime_ranging=r_rang, regime_volatile=r_vol,
            is_buy=1.0 if direction == "BUY" else 0.0,
            hour_sin=math.sin(2 * math.pi * hour / 24),
            hour_cos=math.cos(2 * math.pi * hour / 24),
            is_london=is_london, is_ny=is_ny, is_overlap=is_overlap,
            rsi_extreme=rsi_extreme,
            adx_strength=adx_strength,
            momentum=momentum,
            vol_regime=vol_regime,
            recent_win_rate=rwr,
            recent_pnl_norm=rpnl,
            consec_losses=cl_norm,
            sym_gold=sg, sym_forex=sf, sym_index=si,
            massive_volume_d1=mv_d1,
            daily_trend=math.tanh(d_trend * 1000), 
            macro_spy_trend=math.tanh(sp_trend),
            macro_spy_volume=sp_vol
        )

    def build_live_features(self, sym: str, direction: str, hour: int,
                             rsi: float, adx: float, atr: float, spread: float,
                             rr: float, regime: int, ema_fast: float, ema_slow: float,
                             open_price: float = 1.0,
                             recent_results: List[int] = None,
                             consec_losses: int = 0,
                             massive_macro: dict = None) -> List[float]:
        """
        Construit le vecteur de features pour une prédiction en temps réel
        (depuis engine.py ou MQL5 via fichier JSON).
        """
        if recent_results is None:
            recent_results = []

        atr_mean = atr   # Approximation sans historique
        atr_std  = atr * 0.3

        if massive_macro is None:
            massive_macro = {}

        mock = {
            "rsi_at_entry": rsi, "adx_at_entry": adx,
            "atr_at_entry": atr, "spread_entry": spread,
            "rr_ratio": rr, "regime": regime,
            "symbol": sym, "direction": direction,
            "ema_fast": ema_fast, "ema_slow": ema_slow,
            "open_price": open_price,
            "consec_before": consec_losses,
            "open_time": f"2024-01-01 {hour:02d}:00:00",
            # Inject Massive Macro
            "massive_volume_d1": massive_macro.get("massive_volume_d1", 0.0),
            "daily_trend":       massive_macro.get("daily_trend", 0.0),
            "macro_spy_trend":   massive_macro.get("macro_spy_trend", 0.0),
            "macro_spy_volume":  massive_macro.get("macro_spy_volume", 0.0)
        }
        fv = self._build_feature_vector(mock, atr_mean, atr_std, recent_results)
        return fv.to_list()


# ══════════════════════════════════════════════════════════════════
#  ARBRE DE DÉCISION CART (Classification And Regression Tree)
# ══════════════════════════════════════════════════════════════════

class Node:
    """Nœud d'un arbre de décision."""
    __slots__ = ["feature","threshold","left","right","value","n_samples"]
    def __init__(self):
        self.feature   = None
        self.threshold = None
        self.left      = None
        self.right     = None
        self.value     = 0.0
        self.n_samples = 0


class DecisionTree:
    """
    Arbre CART pour gradient boosting.
    Optimise la réduction de perte L2 (régression sur les résidus).
    """

    def __init__(self, max_depth: int = 4, min_samples_split: int = 8,
                 min_samples_leaf: int = 4, colsample: float = 1.0,
                 n_features: int = None):
        self.max_depth         = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf  = min_samples_leaf
        self.colsample         = colsample
        self.n_features_total  = n_features
        self.root              = None
        self.feature_subset    = None

    def fit(self, X: List[List[float]], residuals: List[float]):
        """Fit l'arbre sur les résidus du boosting."""
        n_features = len(X[0]) if X else 0
        # Sélection aléatoire de features (comme XGBoost colsample)
        k = max(1, int(n_features * self.colsample))
        self.feature_subset = sorted(random.sample(range(n_features), k))
        self.root = self._build(X, residuals, depth=0)

    def _build(self, X, y, depth) -> Node:
        node = Node()
        node.n_samples = len(y)
        node.value     = statistics.mean(y) if y else 0.0

        if (depth >= self.max_depth or len(y) < self.min_samples_split
                or len(set(y)) == 1):
            return node

        best_feat, best_thr, best_gain = None, None, -1e18
        best_left_idx, best_right_idx  = [], []

        for feat in self.feature_subset:
            vals = sorted(set(X[i][feat] for i in range(len(X))))
            thresholds = [(vals[j] + vals[j+1]) / 2 for j in range(len(vals)-1)]

            for thr in thresholds[:20]:  # Max 20 splits par feature
                left_idx  = [i for i in range(len(X)) if X[i][feat] <= thr]
                right_idx = [i for i in range(len(X)) if X[i][feat] >  thr]

                if len(left_idx) < self.min_samples_leaf or len(right_idx) < self.min_samples_leaf:
                    continue

                ly = [y[i] for i in left_idx]
                ry = [y[i] for i in right_idx]

                # Gain = réduction de la variance pondérée (MSE)
                parent_mse = statistics.variance(y) if len(y) > 1 else 0
                l_mse = statistics.variance(ly) if len(ly) > 1 else 0
                r_mse = statistics.variance(ry) if len(ry) > 1 else 0
                gain  = parent_mse - (len(ly)/len(y))*l_mse - (len(ry)/len(y))*r_mse

                if gain > best_gain:
                    best_gain      = gain
                    best_feat      = feat
                    best_thr       = thr
                    best_left_idx  = left_idx
                    best_right_idx = right_idx

        if best_feat is None or best_gain <= 1e-10:
            return node

        node.feature   = best_feat
        node.threshold = best_thr

        lX = [X[i] for i in best_left_idx]
        ly = [y[i] for i in best_left_idx]
        rX = [X[i] for i in best_right_idx]
        ry = [y[i] for i in best_right_idx]

        node.left  = self._build(lX, ly, depth + 1)
        node.right = self._build(rX, ry, depth + 1)
        return node

    def predict_one(self, x: List[float]) -> float:
        node = self.root
        while node.feature is not None:
            node = node.left if x[node.feature] <= node.threshold else node.right
        return node.value

    def predict(self, X: List[List[float]]) -> List[float]:
        return [self.predict_one(x) for x in X]


# ══════════════════════════════════════════════════════════════════
#  GRADIENT BOOSTING CLASSIFIER (XGBoost-like)
# ══════════════════════════════════════════════════════════════════

class GradientBoostingClassifier:
    """
    Gradient Boosting from scratch — équivalent XGBoost simplifié.
    Optimise la log-loss (cross-entropy) via descente de gradient.

    Chaque arbre prédit les résidus du modèle précédent.
    La prédiction finale est F(x) = Σ η * h_t(x) converti en probabilité.
    """

    def __init__(self, n_estimators: int = 80, max_depth: int = 4,
                 learning_rate: float = 0.12, min_samples_split: int = 8,
                 min_samples_leaf: int = 4, subsample: float = 0.8,
                 colsample: float = 0.8):
        self.n_estimators      = n_estimators
        self.max_depth         = max_depth
        self.learning_rate     = learning_rate
        self.min_samples_split = min_samples_split
        self.min_samples_leaf  = min_samples_leaf
        self.subsample         = subsample
        self.colsample         = colsample

        self.trees:     List[DecisionTree] = []
        self.base_score: float             = 0.5  # Prédiction initiale
        self.train_log:  List[Dict]        = []
        self.feature_importance: List[float] = []
        self.n_features: int               = 0

    @staticmethod
    def _sigmoid(x: float) -> float:
        x = max(-500, min(500, x))
        return 1.0 / (1.0 + math.exp(-x))

    @staticmethod
    def _log_loss(y: List[int], probs: List[float]) -> float:
        eps = 1e-10
        return -statistics.mean(
            y[i] * math.log(max(probs[i], eps)) + (1-y[i]) * math.log(max(1-probs[i], eps))
            for i in range(len(y))
        )

    def _compute_residuals(self, y: List[int], F: List[float]) -> List[float]:
        """Gradient de la log-loss = y_pred - y_true (résidus pour boosting)."""
        return [self._sigmoid(F[i]) - y[i] for i in range(len(y))]

    def fit(self, X: List[List[float]], y: List[int], verbose: bool = True):
        """Entraîne le modèle complet."""
        n = len(X)
        self.n_features = len(X[0]) if X else 0
        self.feature_importance = [0.0] * self.n_features

        # Initialisation: log-odds du taux de positifs
        pos_rate = sum(y) / n if n > 0 else 0.5
        pos_rate = max(0.01, min(0.99, pos_rate))
        self.base_score = math.log(pos_rate / (1 - pos_rate))

        # F(x) = prédiction courante (en espace log-odds)
        F = [self.base_score] * n

        for t in range(self.n_estimators):
            # Sous-échantillonnage (subsample)
            sample_size = max(1, int(n * self.subsample))
            sample_idx  = sorted(random.sample(range(n), sample_size))

            X_sub = [X[i] for i in sample_idx]
            y_sub = [y[i] for i in sample_idx]
            F_sub = [F[i] for i in sample_idx]

            # Calcul des résidus (négatif du gradient)
            residuals = self._compute_residuals(y_sub, F_sub)
            # Inverser: on prédit le négatif du gradient
            neg_grad = [-r for r in residuals]

            # Construire l'arbre sur les résidus
            tree = DecisionTree(
                max_depth         = self.max_depth,
                min_samples_split = self.min_samples_split,
                min_samples_leaf  = self.min_samples_leaf,
                colsample         = self.colsample,
                n_features        = self.n_features,
            )
            tree.fit(X_sub, neg_grad)

            # Mettre à jour F sur TOUT le dataset
            for i in range(n):
                F[i] += self.learning_rate * tree.predict_one(X[i])

            self.trees.append(tree)

            # Accumulation de l'importance des features
            self._update_importance(tree)

            # Log toutes les 10 itérations
            if verbose and (t + 1) % 10 == 0:
                probs    = [self._sigmoid(f) for f in F]
                loss     = self._log_loss(y, probs)
                preds    = [1 if p > 0.5 else 0 for p in probs]
                acc      = sum(1 for i in range(n) if preds[i] == y[i]) / n
                self.train_log.append({"iter": t+1, "loss": round(loss,4), "acc": round(acc,4)})
                print(f"  iter {t+1:3d}/{self.n_estimators}  loss={loss:.4f}  acc={acc:.1%}")

    def _update_importance(self, tree: DecisionTree):
        """Accumule l'importance des features depuis un arbre."""
        def _traverse(node):
            if node is None or node.feature is None:
                return
            self.feature_importance[node.feature] += 1
            _traverse(node.left)
            _traverse(node.right)
        _traverse(tree.root)

    def predict_proba_one(self, x: List[float]) -> float:
        """Probabilité d'appartenir à la classe 1 (trade profitable)."""
        F = self.base_score
        for tree in self.trees:
            F += self.learning_rate * tree.predict_one(x)
        return self._sigmoid(F)

    def predict_proba(self, X: List[List[float]]) -> List[float]:
        return [self.predict_proba_one(x) for x in X]

    def predict(self, X: List[List[float]], threshold: float = 0.5) -> List[int]:
        return [1 if p > threshold else 0 for p in self.predict_proba(X)]

    def feature_importance_ranked(self, feature_names: List[str]) -> List[Tuple[str, float]]:
        total = sum(self.feature_importance) or 1
        ranked = [(feature_names[i], round(self.feature_importance[i] / total * 100, 2))
                  for i in range(min(len(feature_names), len(self.feature_importance)))]
        return sorted(ranked, key=lambda x: -x[1])


# ══════════════════════════════════════════════════════════════════
#  PERSISTANCE DU MODÈLE (JSON — sans dépendances)
# ══════════════════════════════════════════════════════════════════

def _node_to_dict(node) -> Optional[dict]:
    if node is None:
        return None
    return {
        "f": node.feature,
        "t": node.threshold,
        "v": node.value,
        "n": node.n_samples,
        "l": _node_to_dict(node.left),
        "r": _node_to_dict(node.right),
    }

def _dict_to_node(d) -> Optional[Node]:
    if d is None:
        return None
    node = Node()
    node.feature   = d["f"]
    node.threshold = d["t"]
    node.value     = d["v"]
    node.n_samples = d["n"]
    node.left      = _dict_to_node(d["l"])
    node.right     = _dict_to_node(d["r"])
    return node

def save_model(model: GradientBoostingClassifier, path: str):
    data = {
        "version":     "AladdinML_v1",
        "generated":   datetime.now().isoformat(),
        "base_score":  model.base_score,
        "n_features":  model.n_features,
        "n_trees":     len(model.trees),
        "learning_rate": model.learning_rate,
        "feature_importance": model.feature_importance,
        "trees": [
            {
                "colsample": t.colsample,
                "feat_subset": t.feature_subset,
                "root": _node_to_dict(t.root),
            }
            for t in model.trees
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"  Modèle sauvegardé: {path} ({len(model.trees)} arbres)")

def load_model(path: str) -> Optional[GradientBoostingClassifier]:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    model = GradientBoostingClassifier(
        n_estimators  = data["n_trees"],
        learning_rate = data["learning_rate"],
    )
    model.base_score         = data["base_score"]
    model.n_features         = data["n_features"]
    model.feature_importance = data.get("feature_importance", [])
    model.trees = []
    for td in data["trees"]:
        tree = DecisionTree()
        tree.colsample      = td["colsample"]
        tree.feature_subset = td["feat_subset"]
        tree.root           = _dict_to_node(td["root"])
        model.trees.append(tree)
    print(f"  Modèle chargé: {path} ({len(model.trees)} arbres)")
    return model


# ══════════════════════════════════════════════════════════════════
#  MÉTRIQUES D'ÉVALUATION
# ══════════════════════════════════════════════════════════════════

def evaluate_model(model: GradientBoostingClassifier, X_test: List[List[float]],
                   y_test: List[int], threshold: float = 0.5) -> Dict:
    probs = model.predict_proba(X_test)
    preds = [1 if p > threshold else 0 for p in probs]
    n     = len(y_test)

    tp = sum(1 for i in range(n) if preds[i]==1 and y_test[i]==1)
    tn = sum(1 for i in range(n) if preds[i]==0 and y_test[i]==0)
    fp = sum(1 for i in range(n) if preds[i]==1 and y_test[i]==0)
    fn = sum(1 for i in range(n) if preds[i]==0 and y_test[i]==1)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1        = 2*precision*recall / (precision+recall) if (precision+recall) > 0 else 0
    accuracy  = (tp + tn) / n if n > 0 else 0

    # AUC-ROC via trapezoïdes
    thresholds = sorted(set(probs), reverse=True)
    tprs, fprs = [0.0], [0.0]
    pos = sum(y_test); neg = n - pos
    for thr in thresholds:
        tp_ = sum(1 for i in range(n) if probs[i] >= thr and y_test[i] == 1)
        fp_ = sum(1 for i in range(n) if probs[i] >= thr and y_test[i] == 0)
        tprs.append(tp_ / pos if pos > 0 else 0)
        fprs.append(fp_ / neg if neg > 0 else 0)
    tprs.append(1.0); fprs.append(1.0)
    auc = sum(abs(fprs[i]-fprs[i-1]) * (tprs[i]+tprs[i-1])/2
              for i in range(1, len(fprs)))

    # Calibration: prob moyenne des positifs vs négatifs
    pos_probs = [probs[i] for i in range(n) if y_test[i] == 1]
    neg_probs = [probs[i] for i in range(n) if y_test[i] == 0]

    return {
        "accuracy":    round(accuracy,   4),
        "precision":   round(precision,  4),
        "recall":      round(recall,     4),
        "f1_score":    round(f1,         4),
        "auc_roc":     round(auc,        4),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "n_test":      n,
        "pos_rate":    round(sum(y_test)/n, 3),
        "avg_prob_pos":round(statistics.mean(pos_probs) if pos_probs else 0, 3),
        "avg_prob_neg":round(statistics.mean(neg_probs) if neg_probs else 0, 3),
    }


def format_evaluation_report(metrics: Dict, feat_importance: List[Tuple[str,float]]) -> str:
    SEP = "=" * 58
    lines = [
        "", SEP, "  ALADDIN ML — RAPPORT D'ÉVALUATION", SEP, "",
        "  MÉTRIQUES DE CLASSIFICATION",
        f"  Accuracy:     {metrics['accuracy']:.1%}",
        f"  Precision:    {metrics['precision']:.1%}  (évite les faux BUY)",
        f"  Recall:       {metrics['recall']:.1%}   (capture les vrais profits)",
        f"  F1-Score:     {metrics['f1_score']:.4f}",
        f"  AUC-ROC:      {metrics['auc_roc']:.4f}  (> 0.65 = utile)",
        "",
        "  MATRICE DE CONFUSION",
        f"  TP (bon trade détecté):    {metrics['tp']:>5}",
        f"  TN (mauvais évité):        {metrics['tn']:>5}",
        f"  FP (mauvais pris):         {metrics['fp']:>5}  ← coût en capital",
        f"  FN (bon manqué):           {metrics['fn']:>5}  ← coût en opportunité",
        "",
        "  CALIBRATION DES PROBABILITÉS",
        f"  Prob moy. trades gagnants: {metrics['avg_prob_pos']:.3f}",
        f"  Prob moy. trades perdants: {metrics['avg_prob_neg']:.3f}",
        f"  Séparation:               {metrics['avg_prob_pos']-metrics['avg_prob_neg']:.3f}  (> 0.10 = bon)",
        "",
        "  INTERPRÉTATION INSTITUTIONNELLE:",
    ]

    auc = metrics["auc_roc"]
    if auc >= 0.70:
        lines.append(f"  AUC={auc:.3f} → Signal prédictif fort — déploiement possible")
    elif auc >= 0.60:
        lines.append(f"  AUC={auc:.3f} → Signal modéré — utiliser comme filtre secondaire")
    elif auc >= 0.55:
        lines.append(f"  AUC={auc:.3f} → Signal faible — augmenter le dataset (> 200 trades)")
    else:
        lines.append(f"  AUC={auc:.3f} → Pas mieux que l'aléatoire — vérifier les features")

    if feat_importance:
        lines += ["", "  TOP 10 FEATURES LES PLUS IMPORTANTES:"]
        for name, imp in feat_importance[:10]:
            bar = "█" * int(imp / 2)
            lines.append(f"  {name:<22}  {imp:>5.1f}%  {bar}")

    lines.append(SEP)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
#  TRAINER — PIPELINE COMPLET
# ══════════════════════════════════════════════════════════════════

class ModelTrainer:
    """Orchestre l'entraînement complet: load → features → split → train → eval → save."""

    def __init__(self, cfg: MLConfig = None):
        self.cfg = cfg or MLConfig()
        self.engineer = FeatureEngineer(cfg)
        self.model: Optional[GradientBoostingClassifier] = None

    def run(self, trades: List[dict], verbose: bool = True) -> Dict:
        n = len(trades)
        print(f"\n  Trades chargés: {n}")
        if n < 30:
            print("  ATTENTION: Minimum 30 trades recommandé pour l'entraînement.")
            print("  Continuez à logger les trades — revenez lorsque vous avez 100+.")

        # 1. Construction des features
        print(f"\n  Construction des features ({len(FeatureVector.feature_names())} features)...")
        X, y = self.engineer.build_dataset(trades)
        if not X:
            print("  Erreur: aucun vecteur de feature construit.")
            return {}

        pos = sum(y); neg = len(y) - pos
        print(f"  Dataset: {len(X)} samples | {pos} positifs ({pos/len(y):.1%}) | {neg} négatifs")

        # 2. Train/Test split (chronologique — respecte la temporalité)
        split = int(len(X) * (1 - self.cfg.TEST_SIZE))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        print(f"  Split: {len(X_train)} train | {len(X_test)} test (OOS chronologique)")

        # 3. Entraînement
        print(f"\n  Entraînement Gradient Boosting ({self.cfg.N_ESTIMATORS} arbres)...")
        self.model = GradientBoostingClassifier(
            n_estimators      = self.cfg.N_ESTIMATORS,
            max_depth         = self.cfg.MAX_DEPTH,
            learning_rate     = self.cfg.LEARNING_RATE,
            min_samples_split = self.cfg.MIN_SAMPLES_SPLIT,
            min_samples_leaf  = self.cfg.MIN_SAMPLES_LEAF,
            subsample         = self.cfg.SUBSAMPLE,
            colsample         = self.cfg.COLSAMPLE,
        )
        self.model.fit(X_train, y_train, verbose=verbose)

        # 4. Évaluation OOS
        print("\n  Évaluation Out-of-Sample...")
        metrics = evaluate_model(self.model, X_test, y_test, self.cfg.DEFAULT_THRESHOLD)
        feat_imp = self.model.feature_importance_ranked(FeatureVector.feature_names())

        print(format_evaluation_report(metrics, feat_imp))

        # 5. Sauvegarde
        save_model(self.model, str(self.cfg.MODEL_FILE) + ".candidate")

        return {"metrics": metrics, "n_train": len(X_train), "n_test": len(X_test)}


# ══════════════════════════════════════════════════════════════════
#  LIVE PREDICTOR — Intégration temps réel
# ══════════════════════════════════════════════════════════════════

class LivePredictor:
    """
    Prédicteur temps réel — chargé par engine.py.
    Reçoit les données du tick courant et retourne une recommandation.
    Exporte aussi un fichier JSON lu par MQL5.
    """

    def __init__(self, cfg: MLConfig = None, mt5_path: str = "."):
        self.cfg       = cfg or MLConfig()
        self.mt5_path  = mt5_path
        self.engineer  = FeatureEngineer(cfg)
        self.model: Optional[GradientBoostingClassifier] = None
        self.recent_results: List[int] = []
        self.n_predictions = 0
        self.n_trades_signaled = 0

    def load(self) -> bool:
        self.model = load_model(self.cfg.MODEL_FILE)
        return self.model is not None

    def predict(self, sym: str, direction: str, hour: int,
                rsi: float, adx: float, atr: float, spread: float,
                rr: float, regime: int, ema_fast: float = 0.0,
                ema_slow: float = 0.0, open_price: float = 1.0,
                consec_losses: int = 0) -> Dict:
        """
        Retourne:
            {
              "trade":    1 ou 0,
              "prob":     0.73,
              "signal":   "TRADE" ou "SKIP",
              "reason":   "ADX fort + RSI zone neutre + bon R:R",
              "threshold": 0.55,
            }
        """
        if self.model is None:
            return {"trade": 1, "prob": 0.5, "signal": "MODEL_NOT_LOADED",
                    "reason": "Modèle non chargé — passer en mode règles", "threshold": 0.5}

        features = self.engineer.build_live_features(
            sym=sym, direction=direction, hour=hour,
            rsi=rsi, adx=adx, atr=atr, spread=spread,
            rr=rr, regime=regime, ema_fast=ema_fast, ema_slow=ema_slow,
            open_price=open_price, recent_results=self.recent_results,
            consec_losses=consec_losses,
        )

        prob      = self.model.predict_proba_one(features)
        do_trade  = 1 if prob >= self.cfg.DEFAULT_THRESHOLD else 0
        self.n_predictions += 1
        if do_trade:
            self.n_trades_signaled += 1

        # Génération d'une explication lisible
        reason = self._explain(prob, rsi, adx, rr, regime, spread, atr)

        result = {
            "sym":       sym,
            "direction": direction,
            "trade":     do_trade,
            "prob":      round(prob, 4),
            "signal":    "TRADE" if do_trade else "SKIP",
            "reason":    reason,
            "threshold": self.cfg.DEFAULT_THRESHOLD,
            "ts":        int(datetime.now().timestamp()),
        }

        # Export JSON pour MQL5
        self._export_mt5(result)
        return result

    def update_result(self, was_profitable: bool):
        """Mettre à jour le contexte après fermeture d'un trade."""
        self.recent_results.append(1 if was_profitable else 0)
        if len(self.recent_results) > 10:
            self.recent_results.pop(0)

    def _explain(self, prob: float, rsi: float, adx: float, rr: float,
                  regime: int, spread: float, atr: float) -> str:
        parts = []
        if prob >= 0.70:   parts.append("signal fort")
        elif prob >= 0.55: parts.append("signal modéré")
        else:              parts.append("signal faible")

        if adx > 28:  parts.append(f"ADX={adx:.0f} (tendance forte)")
        elif adx > 20: parts.append(f"ADX={adx:.0f} (tendance modérée)")
        else:          parts.append(f"ADX={adx:.0f} (tendance faible)")

        if 40 <= rsi <= 60:   parts.append("RSI zone neutre")
        elif rsi > 65:        parts.append("RSI suracheté")
        elif rsi < 35:        parts.append("RSI survendu")

        parts.append(f"R:R={rr:.1f}")
        if spread > atr * 0.3: parts.append("spread élevé")

        regime_names = {0:"TREND_UP",1:"TREND_DOWN",2:"RANGING",3:"VOLATILE"}
        parts.append(regime_names.get(regime, "?"))

        return " | ".join(parts)

    def _export_mt5(self, result: dict):
        """Export vers news_block-like JSON pour MQL5."""
        try:
            path = os.path.join(self.mt5_path, self.cfg.MT5_PREDICT_FILE)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f)
        except IOError:
            pass

    def stats(self) -> Dict:
        return {
            "n_predictions":    self.n_predictions,
            "n_signaled":       self.n_trades_signaled,
            "signal_rate":      round(self.n_trades_signaled / max(1,self.n_predictions) * 100, 1),
            "recent_win_rate":  round(statistics.mean(self.recent_results)*100, 1) if self.recent_results else 0,
        }


# ══════════════════════════════════════════════════════════════════
#  GÉNÉRATEUR DE DONNÉES SYNTHÉTIQUES
# ══════════════════════════════════════════════════════════════════

def generate_synthetic_trades(n: int = 200, seed: int = 42) -> List[dict]:
    """
    Génère des trades synthétiques avec PATTERNS APPRENABLES:
    - ADX > 25 + RSI 40-60 + R:R > 1.8 → win rate 65%
    - ADX < 18 → win rate 38%
    - Regime RANGING → win rate 42%
    - Session overlap → win rate 60%
    """
    random.seed(seed)
    SYMS  = ["XAUUSD","EURUSD","GBPUSD","US30Cash","Nasdaq"]
    DIRS  = ["BUY","SELL"]
    trades= []
    base  = datetime(2024,1,3,8,0)

    for i in range(n):
        sym  = random.choice(SYMS)
        dir_ = random.choice(DIRS)
        open_t = base + timedelta(hours=i*1.5 + random.uniform(0,1))
        dur  = random.randint(4,25)
        hour = open_t.hour

        # Features
        adx    = random.uniform(10, 45)
        rsi    = random.uniform(25, 75)
        atr    = {"XAUUSD":2.5,"EURUSD":0.0008,"GBPUSD":0.0012,"US30Cash":80,"Nasdaq":120}.get(sym,1.0)
        atr   *= random.uniform(0.7, 1.4)
        regime = random.choice([0,1,2,3])
        rr     = random.uniform(1.0, 3.5)
        spread = random.uniform(5, 60) if sym=="XAUUSD" else random.uniform(1,25)
        ef     = 2000 + random.gauss(0, atr)
        es     = ef - atr * random.uniform(-2, 2)

        # Win rate conditionnel — les patterns que le ML doit apprendre
        p_win = 0.50  # base
        if adx > 25:          p_win += 0.12
        if adx < 18:          p_win -= 0.14
        if 40 <= rsi <= 60:   p_win += 0.08
        if rsi > 65 and dir_=="BUY":   p_win -= 0.12
        if rsi < 35 and dir_=="SELL":  p_win -= 0.12
        if rr  > 1.8:         p_win += 0.06
        if regime == 2:       p_win -= 0.10   # ranging = mauvais
        if regime == 3:       p_win -= 0.08   # volatile = dangereux
        if 13 <= hour < 16:   p_win += 0.07   # overlap London/NY
        if spread > atr*0.2*1000: p_win -= 0.09

        p_win = max(0.15, min(0.85, p_win))
        is_win = random.random() < p_win

        lot   = 0.01
        sl    = atr * 1.5
        tp    = atr * rr
        pnl   = (tp - spread/10000) * lot * 10 if is_win else -(sl) * lot * 10

        close_t = open_t + timedelta(minutes=dur)
        trades.append({
            "symbol":        sym,
            "direction":     dir_,
            "open_time":     open_t.strftime("%Y-%m-%d %H:%M:%S"),
            "close_time":    close_t.strftime("%Y-%m-%d %H:%M:%S"),
            "open_price":    2000.0 if sym=="XAUUSD" else 1.1,
            "close_price":   2000.0 + pnl/lot/10,
            "lot":           lot,
            "profit":        round(pnl, 2),
            "net_profit":    round(pnl - 0.07, 2),
            "sl_distance":   sl,
            "rr_ratio":      rr,
            "atr_at_entry":  atr,
            "rsi_at_entry":  rsi,
            "adx_at_entry":  adx,
            "ema_fast":      ef,
            "ema_slow":      es,
            "spread_entry":  spread,
            "regime":        regime,
            "duration_min":  dur,
            "hit_tp":        is_win,
            "hit_sl":        not is_win,
            "be_triggered":  random.random() < 0.2,
            "trail_triggered": random.random() < 0.15,
            "close_reason":  "TP" if is_win else "SL",
            "balance":       1000.0 + i * 0.5,
        })
    return trades


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE CLI
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aladdin Pro ML Engine")
    parser.add_argument("--train",    action="store_true",  help="Entraîner le modèle")
    parser.add_argument("--evaluate", action="store_true",  help="Évaluer modèle existant")
    parser.add_argument("--predict",  action="store_true",  help="Prédiction manuelle")
    parser.add_argument("--demo",     action="store_true",  help="Mode démo (données synthétiques)")
    parser.add_argument("--data",     default="trade_log_all.jsonl", help="Fichier JSONL des trades")
    parser.add_argument("--n-demo",   type=int, default=200, help="Nb de trades synthétiques")
    # Paramètres pour --predict
    parser.add_argument("--sym",    default="XAUUSD")
    parser.add_argument("--dir",    default="BUY")
    parser.add_argument("--hour",   type=int,   default=14)
    parser.add_argument("--rsi",    type=float, default=52.0)
    parser.add_argument("--adx",    type=float, default=28.0)
    parser.add_argument("--atr",    type=float, default=2.5)
    parser.add_argument("--spread", type=float, default=25.0)
    parser.add_argument("--rr",     type=float, default=2.0)
    parser.add_argument("--regime", type=int,   default=0)
    args = parser.parse_args()

    cfg = MLConfig()

    # ── TRAIN ────────────────────────────────────────────────────
    if args.train or args.demo:
        if args.demo:
            print(f"\n[DEMO] Génération de {args.n_demo} trades synthétiques...")
            trades = generate_synthetic_trades(args.n_demo)
        else:
            print(f"\nChargement: {args.data}")
            trades = []
            p = Path(args.data)
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:   trades.append(json.loads(line))
                        except: continue
            print(f"{len(trades)} trades chargés")
            if not trades:
                print("Aucun trade — utiliser --demo pour tester")
                return

        trainer = ModelTrainer(cfg)
        trainer.run(trades)

    # ── EVALUATE ─────────────────────────────────────────────────
    elif args.evaluate:
        model = load_model(cfg.MODEL_FILE)
        if not model:
            print(f"Modèle non trouvé: {cfg.MODEL_FILE}. Lancer --train d'abord.")
            return
        print("\n[DEMO évaluation sur données synthétiques]")
        trades = generate_synthetic_trades(100, seed=99)
        eng = FeatureEngineer(cfg)
        X, y = eng.build_dataset(trades)
        if X:
            metrics  = evaluate_model(model, X, y, cfg.DEFAULT_THRESHOLD)
            feat_imp = model.feature_importance_ranked(FeatureVector.feature_names())
            print(format_evaluation_report(metrics, feat_imp))

    # ── PREDICT ──────────────────────────────────────────────────
    elif args.predict:
        predictor = LivePredictor(cfg)
        if not predictor.load():
            print(f"Modèle non trouvé: {cfg.MODEL_FILE}. Lancer --train d'abord.")
            return
        result = predictor.predict(
            sym=args.sym, direction=args.dir, hour=args.hour,
            rsi=args.rsi, adx=args.adx, atr=args.atr,
            spread=args.spread, rr=args.rr, regime=args.regime,
        )
        SEP = "="*50
        print(f"\n{SEP}")
        print(f"  ML SIGNAL — {args.sym} {args.dir}")
        print(SEP)
        print(f"  Probabilité:  {result['prob']:.1%}")
        print(f"  Décision:     {result['signal']}")
        print(f"  Raison:       {result['reason']}")
        print(f"  Seuil:        {result['threshold']:.0%}")
        print(SEP)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
