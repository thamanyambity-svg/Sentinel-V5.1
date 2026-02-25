import os
import requests
import json
import torch
import numpy as np
from transformers import pipeline
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(".env")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

class VanguardAnalyzer:
    """
    VANGUARD (Module d'Analyse Sémantique Quantitative)
    Vectorisation du Sentiment, Filtrage du Bruit et Pondération Institutionnelle.
    """
    def __init__(self):
        print("\n[VANGUARD] 🛰️ Initialisation de l'Analyse Sémantique Quantitative...")
        # FinBERT: Vectorisation et Classification
        self.encoder = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        self.source_weights = {
            "federal reserve": 10.0,
            "central bank": 8.0,
            "reuters": 5.0,
            "bloomberg": 5.0,
            "goldman sachs": 4.0,
            "twitter": 0.5,
            "social": 0.2
        }
        print("[VANGUARD] ✅ Architecture Transformer opérationnelle.")

    def fetch_intelligence(self):
        """Extraction de données multi-sources avec filtrage du bruit."""
        # En mode démo sans NewsAPI, on simule des signaux institutionnels
        if not NEWS_API_KEY:
            return [
                {"text": "Federal Reserve officials signal higher-for-longer interest rate path.", "source": "REUTERS"},
                {"text": "US Dollar demand surges as geopolitical risks escalate in Europe.", "source": "BLOOMBERG"},
                {"text": "Retail traders on social media betting on a quick pivot by the Fed.", "source": "SOCIAL"}
            ]
            
        url = f"https://newsapi.org/v2/everything?q=forex OR gold OR fed OR inflation&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
        try:
            r = requests.get(url)
            articles = r.json().get('articles', [])[:10]
            return [{"text": a['title'], "source": a['source']['name']} for a in articles]
        except:
            return []

    def calculate_spm(self, signals):
        """Calcul du Score de Polarité du Marché (SPM)."""
        if not signals: return 0
        
        weighted_scores = []
        for signal in signals:
            analysis = self.encoder(signal['text'])[0]
            base_score = analysis['score'] if analysis['label'] == 'positive' else -analysis['score']
            
            # Application de la Pondération Institutionnelle
            source_name = signal['source'].lower()
            weight = 1.0
            for key, val in self.source_weights.items():
                if key in source_name:
                    weight = val
                    break
            
            weighted_scores.append(base_score * weight)
            
        return np.mean(weighted_scores)

    def run_vanguard_scan(self):
        """Exécution du cycle de Vectorisation Quantitative."""
        print(f"[VANGUARD] 📡 Cycle de Vectorisation Sémantique... [{datetime.now().strftime('%H:%M:%S')}]")
        signals = self.fetch_intelligence()
        spm = self.calculate_spm(signals)
        
        # Détection d'Anomalies (Simulée via volatilité du SPM)
        anomaly_detected = False
        if abs(spm) > 5.0: # Un score trop extrême sans volume réel
            anomaly_detected = True
            
        mood = "NEUTRAL"
        if spm > 0.3: mood = "BULLISH (CONFLUENCE)"
        elif spm < -0.3: mood = "BEARISH (CONFLUENCE)"
        
        final_state = {
            "timestamp": datetime.now().isoformat(),
            "spm_score": round(float(spm), 3),
            "market_mood": mood,
            "anomaly_flag": anomaly_detected,
            "sources_processed": len(signals)
        }
        
        with open('fundamental_state.json', 'w') as f:
            json.dump(final_state, f, indent=4)
            
        print(f"[VANGUARD] 📊 SPM (Polarité) : {spm:.3f} | Mood : {mood}")
        return final_state

if __name__ == "__main__":
    v = VanguardAnalyzer()
    v.run_vanguard_scan()
