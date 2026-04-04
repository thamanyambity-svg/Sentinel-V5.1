"""
ALADDIN PRO V6 — ml_feature_engine.py
Construit les features ML depuis les logs JSONL du bot

Usage:
  python ml_feature_engine.py
  python ml_feature_engine.py --input trade_log_all.jsonl --output features.pkl
"""
import json
import pickle
import argparse
import logging
import os
import statistics
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from collections import deque

import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("FeatureEngine")

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

MT5_FILES_DEFAULT = (
    "/Users/macbookpro/Library/Application Support/"
    "net.metaquotes.wine.metatrader5/drive_c/Program Files/"
    "MetaTrader 5/MQL5/Files"
)

FEATURE_WINDOW = 10       # Rolling stats sur N trades
TRAIN_PCT      = 0.70
VAL_PCT        = 0.15
TEST_PCT       = 0.15


# ══════════════════════════════════════════════════════════════════
#  LECTURE JSONL
# ══════════════════════════════════════════════════════════════════

def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        log.warning("Fichier introuvable: %s", path)
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# ══════════════════════════════════════════════════════════════════
#  CONSTRUCTION DES FEATURES (23 features)
# ══════════════════════════════════════════════════════════════════

REGIME_MAP = {"TREND_UP": 0, "TREND_DOWN": 1, "RANGING": 2, "VOLATILE": 3}

def parse_time(t: str) -> Optional[datetime]:
    for fmt in ["%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    return None


def build_features(trades: List[dict]) -> List[dict]:
    """
    Construit 23 features par trade pour l'entraînement XGBoost.
    Retourne une liste de dicts avec 'features' et 'label'.
    """
    if not trades:
        return []

    # Tri chronologique
    parsed = []
    for t in trades:
        dt = parse_time(t.get("open_time", ""))
        if dt:
            parsed.append((dt, t))
    parsed.sort(key=lambda x: x[0])

    # Historique glissant pour les rolling stats
    atr_window:   deque = deque(maxlen=FEATURE_WINDOW)
    result_window: deque = deque(maxlen=20)  # Pour win_rate rolling
    prev_rsi    = 50.0

    rows = []
    for dt, t in parsed:
        # Features brutes
        atr    = float(t.get("atr_at_entry",  0) or 0)
        rsi    = float(t.get("rsi_at_entry",  50) or 50)
        adx    = float(t.get("adx_at_entry",  20) or 20)
        spread = float(t.get("spread_entry",  0)  or 0)
        lot    = float(t.get("lot",           0.01) or 0.01)
        rr     = float(t.get("rr_ratio",      0)   or 0)
        regime = int(t.get("regime",          -1)  or -1)
        ema_f  = float(t.get("ema_fast",      0)   or 0)
        ema_s  = float(t.get("ema_slow",      0)   or 0)
        direction = 1 if t.get("direction", "BUY") == "BUY" else -1

        profit = float(t.get("net_profit", t.get("profit", 0)) or 0)
        label  = 1 if profit > 0 else 0

        # Features temporelles
        hour       = dt.hour
        dow        = dt.weekday()
        session_london = 1 if 7  <= hour <= 16 else 0
        session_ny     = 1 if 13 <= hour <= 21 else 0

        # Rolling stats ATR
        atr_roll_mean = statistics.mean(atr_window) if atr_window else atr
        atr_roll_std  = statistics.stdev(atr_window) if len(atr_window) > 1 else 0.0

        # Momentum RSI
        rsi_momentum = rsi - prev_rsi

        # EMA gap
        ema_gap_pct = ((ema_f - ema_s) / ema_s * 100) if ema_s != 0 else 0.0

        # Spread relatif
        spread_ratio = (spread / atr) if atr > 0 else 0.0

        # Win rate rolling
        wr_rolling = sum(result_window) / len(result_window) if result_window else 0.5

        # Normalisation Z-score (clip à ±3σ)
        def zclip(val, mu, sigma, clip=3.0):
            if sigma < 1e-10: return 0.0
            z = (val - mu) / sigma
            return max(-clip, min(clip, z))

        feature_vec = {
            # Brutes
            "atr_at_entry":     atr,
            "rsi_at_entry":     rsi,
            "adx_at_entry":     adx,
            "spread_entry":     spread,
            "rr_ratio":         rr,
            "regime":           regime,
            "direction":        direction,
            "lot":              lot,
            # Temporelles
            "hour_utc":         hour,
            "day_of_week":      dow,
            "session_london":   session_london,
            "session_ny":       session_ny,
            # Dérivées
            "atr_rolling_mean": atr_roll_mean,
            "atr_rolling_std":  atr_roll_std,
            "rsi_momentum":     rsi_momentum,
            "ema_gap_pct":      ema_gap_pct,
            "spread_ratio":     spread_ratio,
            "win_rate_rolling": wr_rolling,
            # Indicateurs boléens
            "hit_be":     int(bool(t.get("be_triggered"))),
            "hit_trail":  int(bool(t.get("trail_triggered"))),
            "hit_tp_prev": 0,  # Sera rempli au tour suivant
            # Stats
            "be_triggered":    int(bool(t.get("be_triggered"))),
            "duration_prev":   0,  # placeholder
        }

        rows.append({
            "dt":       dt,
            "features": feature_vec,
            "label":    label,
            "profit":   profit,
        })

        # Mise à jour des fenêtres
        atr_window.append(atr)
        result_window.append(label)
        prev_rsi = rsi

    log.info("Features construites: %d trades → %d features chacun",
             len(rows), len(rows[0]["features"]) if rows else 0)
    return rows


# ══════════════════════════════════════════════════════════════════
#  NORMALISATION + SPLIT
# ══════════════════════════════════════════════════════════════════

def normalize_features(rows: List[dict]) -> tuple:
    """
    Normalisation Z-score par feature. Retourne (rows_norm, scaler_dict).
    """
    if not rows: return rows, {}

    feat_names = list(rows[0]["features"].keys())
    scaler = {}
    for fn in feat_names:
        vals = [r["features"][fn] for r in rows]
        mu   = statistics.mean(vals)
        sigma = statistics.stdev(vals) if len(vals) > 1 else 1.0
        scaler[fn] = (mu, sigma)
        for r in rows:
            z = (r["features"][fn] - mu) / max(sigma, 1e-10)
            r["features"][fn] = max(-3.0, min(3.0, z))  # clip

    return rows, scaler


def chronological_split(rows: List[dict], train_pct=0.70, val_pct=0.15):
    n      = len(rows)
    i_val  = int(n * train_pct)
    i_test = int(n * (train_pct + val_pct))
    return rows[:i_val], rows[i_val:i_test], rows[i_test:]


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aladdin Pro — Feature Engine ML")
    parser.add_argument("--input",   default=None,
                        help="Fichier trade_log_all.jsonl (defaut: MT5_FILES_PATH)")
    parser.add_argument("--mt5-path", default=None)
    parser.add_argument("--output-dir", default=".", help="Dossier de sortie des .pkl")
    args = parser.parse_args()

    mt5_path = Path(args.mt5_path or os.getenv("MT5_FILES_PATH", MT5_FILES_DEFAULT))
    input_file = Path(args.input) if args.input else mt5_path / "trade_log_all.jsonl"
    out_dir    = Path(args.output_dir)
    out_dir.mkdir(exist_ok=True)

    log.info("Lecture: %s", input_file)
    trades = read_jsonl(input_file)
    if len(trades) < 20:
        log.error("Minimum 20 trades requis. Trouvé: %d", len(trades))
        return

    # Construction des features
    rows = build_features(trades)

    # Normalisation
    rows, scaler = normalize_features(rows)

    # Split chronologique
    train, val, test = chronological_split(rows, TRAIN_PCT, VAL_PCT)

    log.info("Split — Train: %d | Val: %d | Test: %d", len(train), len(val), len(test))

    # Export
    with open(out_dir / "features_train.pkl", "wb") as f:
        pickle.dump({"rows": train, "scaler": scaler}, f)
    with open(out_dir / "features_val.pkl", "wb") as f:
        pickle.dump({"rows": val,   "scaler": scaler}, f)
    with open(out_dir / "features_test.pkl", "wb") as f:
        pickle.dump({"rows": test,  "scaler": scaler}, f)
    with open(out_dir / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    log.info("Exported: features_train.pkl, features_val.pkl, features_test.pkl, scaler.pkl")
    log.info("Prochaine etape: python ml_trainer.py")

    # Résumé
    win_count = sum(1 for r in rows if r["label"] == 1)
    log.info("Distribution labels — WIN: %d (%.1f%%) | LOSS: %d (%.1f%%)",
             win_count, win_count/len(rows)*100,
             len(rows)-win_count, (len(rows)-win_count)/len(rows)*100)


if __name__ == "__main__":
    main()
