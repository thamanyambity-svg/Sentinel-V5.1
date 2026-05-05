from agents.base import call_llm
import holidays
from datetime import datetime
import pytz

def run(current_time_str: str) -> str:
    """
    Rôle : Compliance Officer (Gardien du Calendrier)
    Mission : Vérifier que la session est propice au trading institutionnel.
    """
    
    # Parsing de l'heure
    try:
        now = datetime.strptime(current_time_str, '%d/%m/%Y %H:%M')
    except:
        now = datetime.now()

    # Jours fériés US et UK
    us_holidays = holidays.US()
    uk_holidays = holidays.UnitedKingdom()
    
    is_holiday = now in us_holidays or now in uk_holidays
    day_of_week = now.weekday() # 4 = Vendredi, 5 = Samedi, 6 = Dimanche
    hour = now.hour
    
    status = "VALIDE"
    reasons = []
    
    # 1. Check Week-end
    if day_of_week >= 5:
        status = "BLOQUÉ"
        reasons.append("Marché fermé (Week-end)")
    
    # 2. Check Vendredi après-midi (Clôture Broker / Manipulation)
    elif day_of_week == 4 and hour >= 16:
        status = "ALERTE"
        reasons.append("Clôture hebdomadaire (Risque de manipulation/Slippage)")
    
    # 3. Check Jours fériés
    elif is_holiday:
        status = "BLOQUÉ"
        reasons.append(f"Jour férié détecté: {us_holidays.get(now) or uk_holidays.get(now)}")
    
    # 4. Check Heures de faible liquidité (Gap 23h-01h)
    elif hour == 23 or hour == 0:
        status = "ALERTE"
        reasons.append("Faible liquidité (Rollover/Spread élevé)")

    prompt = f"""
    Tu es le COMPLIANCE OFFICER du fonds BlackRock. 
    Ton rôle est d'assurer que le trading se fait dans des conditions réglementaires et sécurisées.
    
    ANALYSE TEMPORELLE :
    - État : {status}
    - Raisons : {', '.join(reasons) if reasons else 'Aucune restriction détectée'}
    
    INSTRUCTIONS :
    - Si l'état est BLOQUÉ : Tu dois fermement déconseiller toute entrée.
    - Si l'état est ALERTE : Tu dois recommander une prudence extrême et une réduction de taille.
    - Si l'état est VALIDE : Tu confirmes que le calendrier est propre.
    
    RÉPONDRE UNIQUEMENT EN FRANÇAIS (2 lignes max).
    FORMAT : [STATUT] : (ton explication courte)
    """
    
    return call_llm(prompt, tier=1)
