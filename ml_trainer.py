"""
ALADDIN PRO V6 — ml_trainer.py
Entraînement XGBoost + validation Walk-Forward + export modèle

Usage:
  python ml_trainer.py                        # Utilise features_train.pkl
  python ml_trainer.py --features-dir ./      # Dossier custom
  python ml_trainer.py --demo                 # Données synthétiques
"""
import json
import pickle
import argparse
import logging
import random
import math
import os
import statistics
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("MLTrainer")

MIN_CONFIDENCE  = 0.62
HIGH_CONFIDENCE = 0.72
MIN_TRADES      = 100


# ══════════════════════════════════════════════════════════════════
#  TENTATIVE D'IMPORT XGBOOST / FALLBACK LIGHTGBM / FALLBACK SKLEARN
# ══════════════════════════════════════════════════════════════════

def _load_model_backend():
    try:
        import xgboost as xgb
        # Forcer le chargement de la lib pour détecter l'erreur libomp immédiatement
        xgb.XGBClassifier() 
        log.info("Backend: XGBoost %s", xgb.__version__)
        return "xgboost", xgb
    except Exception as e:
        log.warning("XGBoost indisponible (libomp manquante?): %s", e)
    
    try:
        import lightgbm as lgb
        lgb.LGBMClassifier()
        log.info("Backend: LightGBM %s", lgb.__version__)
        return "lightgbm", lgb
    except Exception:
        pass
        
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        log.info("Backend: scikit-learn GradientBoosting (fallback)")
        return "sklearn", None
    except ImportError:
        pass
    
    raise ImportError("Aucun backend ML disponible (XGBoost, LightGBM, Sklearn).")


# ══════════════════════════════════════════════════════════════════
#  MÉTRIQUES
# ══════════════════════════════════════════════════════════════════

def _binary_metrics(y_true: List[int], y_pred_proba: List[float],
                    threshold: float) -> Dict:
    tp = fp = tn = fn = 0
    for yt, yp in zip(y_true, y_pred_proba):
        pred = 1 if yp >= threshold else 0
        if   yt == 1 and pred == 1: tp += 1
        elif yt == 0 and pred == 1: fp += 1
        elif yt == 0 and pred == 0: tn += 1
        else:                       fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy  = (tp + tn) / len(y_true) if y_true else 0

    # ROC-AUC approximation (Mann-Whitney U)
    pos_scores = [yp for yt, yp in zip(y_true, y_pred_proba) if yt == 1]
    neg_scores = [yp for yt, yp in zip(y_true, y_pred_proba) if yt == 0]
    if pos_scores and neg_scores:
        u = sum(1 for p in pos_scores for n in neg_scores if p > n)
        auc = u / (len(pos_scores) * len(neg_scores))
    else:
        auc = 0.5

    return {
        "precision": round(precision, 4),
        "recall":    round(recall,    4),
        "f1":        round(f1,        4),
        "accuracy":  round(accuracy,  4),
        "auc":       round(auc,       4),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }


def optimal_threshold(y_true: List[int], y_pred_proba: List[float]) -> float:
    """Trouve le seuil qui maximise le F1 sur la liste donnée."""
    best_f1, best_thr = 0, 0.5
    for thr in [i / 100 for i in range(40, 85)]:
        m = _binary_metrics(y_true, y_pred_proba, thr)
        if m["f1"] > best_f1:
            best_f1  = m["f1"]
            best_thr = thr
    return best_thr


# ══════════════════════════════════════════════════════════════════
#  ENTRAÎNEUR XGBOOST
# ══════════════════════════════════════════════════════════════════

class XGBTrainer:

    PARAM_GRID = {
        "max_depth":       [3, 5, 7],
        "n_estimators":    [100, 200, 300],
        "learning_rate":   [0.05, 0.10, 0.15],
        "subsample":       [0.8],
        "colsample_bytree":[0.8],
        "min_child_weight":[3],
        "gamma":           [0.1],
    }

    def __init__(self, backend_name: str, xgb_lib):
        self.backend = backend_name
        self.xgb_lib = xgb_lib
        self.model     = None
        self.threshold = MIN_CONFIDENCE

    def _rows_to_matrices(self, rows: List[dict]):
        if not rows: return [], []
        feat_names = list(rows[0]["features"].keys())
        X = [[r["features"][fn] for fn in feat_names] for r in rows]
        y = [r["label"] for r in rows]
        return X, y

    def train(self, train_rows: List[dict], val_rows: List[dict]) -> Dict:
        X_tr, y_tr = self._rows_to_matrices(train_rows)
        X_va, y_va = self._rows_to_matrices(val_rows)

        if not X_tr:
            raise ValueError("Aucune donnée d'entraînement")

        log.info("Grid Search: %d configs × %d paramètres...",
                 3*3*3, len(self.PARAM_GRID))

        best_score, best_params, best_model = -1, {}, None

        for max_depth in self.PARAM_GRID["max_depth"]:
          for n_est in self.PARAM_GRID["n_estimators"]:
            for lr in self.PARAM_GRID["learning_rate"]:
                params = {
                    "max_depth":        max_depth,
                    "n_estimators":     n_est,
                    "learning_rate":    lr,
                    "subsample":        0.8,
                    "colsample_bytree": 0.8,
                    "min_child_weight": 3,
                    "gamma":            0.1,
                    "use_label_encoder": False,
                    "eval_metric":      "logloss",
                    "random_state":     42,
                }

                if self.backend == "xgboost":
                    import xgboost as xgb
                    clf = xgb.XGBClassifier(**params)
                elif self.backend == "lightgbm":
                    import lightgbm as lgb
                    params_lgb = {k: v for k, v in params.items()
                                  if k not in ["use_label_encoder","eval_metric"]}
                    clf = lgb.LGBMClassifier(**params_lgb)
                else:
                    from sklearn.ensemble import GradientBoostingClassifier
                    clf = GradientBoostingClassifier(
                        max_depth=max_depth, n_estimators=n_est, learning_rate=lr)

                try:
                    clf.fit(X_tr, y_tr)
                    proba_va = [p[1] for p in clf.predict_proba(X_va)]
                    thr   = optimal_threshold(y_va, proba_va)
                    score = _binary_metrics(y_va, proba_va, thr)["f1"]
                    if score > best_score:
                        best_score  = score
                        best_params = params
                        best_model  = clf
                        self.threshold = thr
                except Exception as e:
                    log.debug("Erreur config %s: %s", params, e)
                    continue

        self.model = best_model
        log.info("Meilleur modèle — F1 val: %.4f | Seuil: %.2f", best_score, self.threshold)

        # Métriques finales
        if self.model and X_va:
            proba_va = [p[1] for p in self.model.predict_proba(X_va)]
            proba_tr = [p[1] for p in self.model.predict_proba(X_tr)]
            m_tr = _binary_metrics(y_tr, proba_tr, self.threshold)
            m_va = _binary_metrics(y_va, proba_va, self.threshold)
            wfe  = m_va["f1"] / m_tr["f1"] if m_tr["f1"] > 0 else 0

            return {
                "train": m_tr, "val": m_va,
                "wfe": round(wfe, 3),
                "threshold": self.threshold,
                "best_params": best_params,
                "backend": self.backend,
            }
        return {}

    def predict_proba(self, features: Dict) -> float:
        if self.model is None: return 0.5
        feat_names = list(features.keys())
        X = [[features[fn] for fn in feat_names]]
        try:
            return float(self.model.predict_proba(X)[0][1])
        except Exception:
            return 0.5

    def feature_importance(self) -> Dict:
        if self.model is None: return {}
        try:
            fi = self.model.feature_importances_
            return {f"f{i}": round(float(v), 4) for i, v in enumerate(fi)}
        except Exception:
            return {}


# ══════════════════════════════════════════════════════════════════
#  RAPPORT TEXTE
# ══════════════════════════════════════════════════════════════════

def format_report(metrics: Dict, n_train: int, n_val: int, n_test: int) -> str:
    SEP = "=" * 52
    m_tr = metrics.get("train", {})
    m_va = metrics.get("val",   {})
    wfe  = metrics.get("wfe",   0)
    thr  = metrics.get("threshold", MIN_CONFIDENCE)

    def is_ok(v, threshold): return "✅" if v >= threshold else "❌"

    return "\n".join([
        "", SEP,
        "  ALADDIN PRO V6 — ML TRAINER RAPPORT",
        SEP,
        f"  Backend:     {metrics.get('backend', '?')}",
        f"  Train trades: {n_train}  |  Val: {n_val}  |  Test: {n_test}",
        f"  Seuil optimal: {thr:.2f}",
        "",
        "  TRAIN (In-Sample):",
        f"  Precision:  {m_tr.get('precision',0):.3f}   Recall: {m_tr.get('recall',0):.3f}",
        f"  F1:         {m_tr.get('f1',0):.3f}   AUC:    {m_tr.get('auc',0):.3f}",
        "",
        "  VALIDATION (Out-of-Sample):",
        f"  Precision:  {m_va.get('precision',0):.3f}   {is_ok(m_va.get('precision',0), 0.58)}",
        f"  Recall:     {m_va.get('recall',0):.3f}   {is_ok(m_va.get('recall',0), 0.52)}",
        f"  F1:         {m_va.get('f1',0):.3f}",
        f"  ROC-AUC:    {m_va.get('auc',0):.3f}   {is_ok(m_va.get('auc',0), 0.62)}",
        f"  WFE:        {wfe:.3f}   {is_ok(wfe, 0.50)}",
        "",
        "  SEUILS DE DÉPLOIEMENT:",
        f"  Precision > 0.58:  {is_ok(m_va.get('precision',0), 0.58)}",
        f"  Recall > 0.52:     {is_ok(m_va.get('recall',0), 0.52)}",
        f"  AUC > 0.62:        {is_ok(m_va.get('auc',0), 0.62)}",
        f"  WFE > 0.50:        {is_ok(wfe, 0.50)}",
        SEP,
    ])


# ══════════════════════════════════════════════════════════════════
#  DEMO DATA
# ══════════════════════════════════════════════════════════════════

def generate_demo_features(n: int = 150, seed: int = 42):
    random.seed(seed)
    rows = []
    now  = datetime(2024, 1, 3, 8, 0)
    from datetime import timedelta

    for i in range(n):
        dt  = now + timedelta(hours=i * 2)
        atr = random.uniform(0.5, 3.5)
        rsi = random.uniform(25, 75)
        adx = random.uniform(12, 45)
        rr  = random.uniform(1.2, 3.5)
        spr = random.uniform(10, 80)

        # Logique de label réaliste
        score = 0
        if adx > 25: score += 1
        if rr  > 2:  score += 1
        if spr < 40: score += 1
        if 35 < rsi < 65: score += 1
        label = 1 if (score >= 3 and random.random() < 0.65) else (
                1 if random.random() < 0.35 else 0)

        rows.append({
            "dt": dt,
            "features": {
                "atr_at_entry": atr, "rsi_at_entry": rsi, "adx_at_entry": adx,
                "spread_entry": spr, "rr_ratio": rr, "regime": random.randint(0, 3),
                "direction": random.choice([1, -1]), "lot": 0.01,
                "hour_utc": dt.hour, "day_of_week": dt.weekday(),
                "session_london": 1 if 7 <= dt.hour <= 16 else 0,
                "session_ny": 1 if 13 <= dt.hour <= 21 else 0,
                "atr_rolling_mean": atr * random.uniform(0.8, 1.2),
                "atr_rolling_std":  atr * random.uniform(0.05, 0.3),
                "rsi_momentum":     random.uniform(-10, 10),
                "ema_gap_pct":      random.uniform(-0.5, 0.5),
                "spread_ratio":     spr / max(atr, 0.1),
                "win_rate_rolling": random.uniform(0.4, 0.7),
                "hit_be":           random.randint(0, 1),
                "hit_trail":        random.randint(0, 1),
                "hit_tp_prev":      random.randint(0, 1),
                "be_triggered":     random.randint(0, 1),
                "duration_prev":    random.randint(3, 25),
            },
            "label": label,
            "profit": random.uniform(0.5, 3.0) if label else random.uniform(-2.5, -0.5),
        })
    return rows


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aladdin Pro — ML Trainer")
    parser.add_argument("--features-dir", default=".", help="Dossier des .pkl features")
    parser.add_argument("--output-dir",   default=".", help="Dossier de sortie du modèle")
    parser.add_argument("--demo",         action="store_true")
    args = parser.parse_args()

    feat_dir = Path(args.features_dir)
    out_dir  = Path(args.output_dir)
    out_dir.mkdir(exist_ok=True)

    backend_name, xgb_lib = _load_model_backend()
    trainer = XGBTrainer(backend_name, xgb_lib)

    if args.demo:
        log.info("[DEMO] Génération de données synthétiques...")
        from datetime import timedelta
        all_rows = generate_demo_features(150)
        n = len(all_rows)
        i_val, i_test = int(n * 0.70), int(n * 0.85)
        train_rows = all_rows[:i_val]
        val_rows   = all_rows[i_val:i_test]
        test_rows  = all_rows[i_test:]
    else:
        train_path = feat_dir / "features_train.pkl"
        val_path   = feat_dir / "features_val.pkl"
        test_path  = feat_dir / "features_test.pkl"

        if not train_path.exists():
            log.error("features_train.pkl introuvable. Lancer ml_feature_engine.py d'abord.")
            return

        with open(train_path, "rb") as f: train_data = pickle.load(f)
        with open(val_path,   "rb") as f: val_data   = pickle.load(f)
        with open(test_path,  "rb") as f: test_data  = pickle.load(f)

        train_rows = train_data.get("rows", [])
        val_rows   = val_data.get("rows",   [])
        test_rows  = test_data.get("rows",  [])

    if len(train_rows) < 20:
        log.error("Pas assez de trades pour entraîner (min 20)")
        return

    log.info("Entraînement sur %d trades (val: %d, test: %d)",
             len(train_rows), len(val_rows), len(test_rows))

    metrics = trainer.train(train_rows, val_rows)

    # Rapport
    print(format_report(metrics, len(train_rows), len(val_rows), len(test_rows)))

    # Export modèle
    model_path = out_dir / "model_xgb.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({"model": trainer.model, "threshold": trainer.threshold,
                     "backend": backend_name, "trained_at": datetime.now().isoformat(),
                     "n_train": len(train_rows)}, f)

    thr_path = out_dir / "threshold.json"
    with open(thr_path, "w") as f:
        json.dump({"threshold": trainer.threshold,
                   "min_confidence": MIN_CONFIDENCE,
                   "high_confidence": HIGH_CONFIDENCE,
                   "backend": backend_name,
                   "trained_at": datetime.now().isoformat()}, f, indent=2)

    log.info("Modèle exporté: %s", model_path)
    log.info("Seuil exporté:  %s", thr_path)
    log.info("Prochaine étape: python ml_predictor.py")


if __name__ == "__main__":
    main()
