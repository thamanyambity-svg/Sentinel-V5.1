from agents.base import call_llm
from news_filter import NewsFilter
import json
import os

def run() -> str:
    """
    Rôle : Sentiment & News Specialist
    Mission : Analyser le calendrier économique et le sentiment de marché.
    """
    
    nf = NewsFilter()
    # On force un refresh pour avoir les dernières news
    nf._refresh()
    
    upcoming_news = nf.get_upcoming(24)
    news_text = ""
    if upcoming_news:
        for e in upcoming_news:
            news_text += f"- {e.dt.strftime('%H:%M')} : [{e.currency}] {e.title} (Impact: {e.impact.name})\n"
    else:
        news_text = "Aucune news majeure (HIGH) dans les prochaines 24h."

    # Tentative de lecture du sentiment Gold si disponible
    gold_sentiment = "Neutre (pas de données spécifiques)"
    if os.path.exists("gold_sentiment.json"):
        try:
            with open("gold_sentiment.json", "r") as f:
                data = json.load(f)
                gold_sentiment = data.get("sentiment", "Neutre")
        except:
            pass

    prompt = f"""
    Tu es le SENTIMENT & NEWS SPECIALIST du fonds BlackRock. 
    Ton rôle est d'analyser l'impact psychologique des nouvelles économiques sur l'OR (XAUUSD).
    
    CALENDRIER ÉCONOMIQUE (24h) :
    {news_text}
    
    SENTIMENT ACTUEL (Flux) :
    {gold_sentiment}
    
    INSTRUCTIONS :
    1. Évalue si le marché est en mode "Risk-On" ou "Risk-Off" basé sur les news.
    2. Identifie les pièges potentiels (ex: volatilité post-NFP).
    3. Donne un score de sentiment global pour l'OR.
    
    RÉPONDRE UNIQUEMENT EN FRANÇAIS (3 lignes max).
    FORMAT :
    SENTIMENT : [BULLISH / BEARISH / NEUTRE]
    ALERTE NEWS : (la news la plus dangereuse à venir)
    ANALYSE : (ton interprétation rapide)
    """
    
    return call_llm(prompt, tier=2)
