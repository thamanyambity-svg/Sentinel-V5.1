import os
import json
import logging
import sys
from datetime import datetime

# Importer le résolveur de chemin du projet
try:
    # On ajoute le dossier racine au path pour les imports relatifs
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if BASE_DIR not in sys.path:
        sys.path.append(BASE_DIR)
    from bot.bridge.mt5_path_resolver import resolve_mt5_files_path
except ImportError:
    resolve_mt5_files_path = None

# Optional imports handled gracefully
try:
    import yfinance as yf
    import pandas as pd
    HAS_DATA_LIBS = True
except ImportError:
    HAS_DATA_LIBS = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - MACRO - %(message)s')

def get_output_path():
    """Détermine le dossier MQL5/Files ou Common/Files correct."""
    if resolve_mt5_files_path:
        mt5_dir, reason = resolve_mt5_files_path()
        logging.info(f"Dossier MT5 resolu via {reason}: {mt5_dir}")
        return os.path.join(mt5_dir, "macro_bias.json")
    
    # Fallback si le résolveur échoue
    fallback = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "macro_bias.json")
    logging.warning(f"Utilisation du fallback local: {fallback}")
    return fallback

OUTPUT_FILE = get_output_path()

def analyze_macro():
    """
    Analyse croisée : DXY (Dollar) + US10Y (Taux) + Bougie D1 (Gold).
    Retourne STRONG_BULLISH, STRONG_BEARISH, ou NEUTRAL.
    """
    bias = "NEUTRAL"
    score = 0
    
    if not HAS_DATA_LIBS:
        logging.warning("yfinance / pandas introuvable. Installation requise (pip3 install yfinance pandas).")
        return bias
    
    try:
        # 1. Analyse du Dollar (DXY)
        logging.info("Analyse du Dollar Index (DXY)...")
        dxy = yf.Ticker("DX-Y.NYB")
        dxy_hist = dxy.history(period="5d")
        if len(dxy_hist) >= 2:
            dxy_change = dxy_hist['Close'].iloc[-1] - dxy_hist['Close'].iloc[-2]
            score += 1 if dxy_change < 0 else -1
            logging.info(f"DXY Change: {dxy_change:.4f}")
            
        # 2. Analyse des Taux US (10 Ans)
        logging.info("Analyse des Taux US10Y...")
        us10 = yf.Ticker("^TNX")
        us10_hist = us10.history(period="5d")
        if len(us10_hist) >= 2:
            us10_change = us10_hist['Close'].iloc[-1] - us10_hist['Close'].iloc[-2]
            score += 1 if us10_change < 0 else -1
            logging.info(f"US10Y Change: {us10_change:.4f}")
            
        # 3. Daily Bias Or (Bougie D1)
        logging.info("Analyse de la bougie D1 (Gold Futures)...")
        gold = yf.Ticker("GC=F")
        gold_hist = gold.history(period="5d")
        if len(gold_hist) >= 2:
            prev_open = gold_hist['Open'].iloc[-2]
            prev_close = gold_hist['Close'].iloc[-2]
            score += 1 if prev_close > prev_open else -1
            logging.info(f"Gold D1: {'BULL' if prev_close > prev_open else 'BEAR'}")

        logging.info(f"Score Total: {score} / 3")

        if score >= 2:
            bias = "STRONG_BULLISH"
        elif score <= -2:
            bias = "STRONG_BEARISH"
        else:
            bias = "NEUTRAL"
            
    except Exception as e:
        logging.error(f"Erreur d'analyse Macro : {e}")
        bias = "NEUTRAL"

    return bias

def main():
    verb = analyze_macro()
    logging.info(f"VERDICT FINAL : {verb}")
    
    data = {
        "timestamp": datetime.now().isoformat(),
        "macro_bias": verb,
        "source": "Sentinel Macro Engine V1.0"
    }
    
    try:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(data, f)
        logging.info(f"Fichier macro_bias.json mis a jour: {OUTPUT_FILE}")
    except Exception as e:
        logging.error(f"Impossible d'ecrire le JSON : {e}")

if __name__ == "__main__":
    main()
