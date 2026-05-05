import json
import os

def run(tick_data: dict) -> str:
    """
    Rôle : Regime Detector
    Mission : Identifier l'état du marché pour adapter le consensus.
    """
    
    # Extraction des métriques avec sécurité sur le type de données (V7.0 FIX)
    if not isinstance(tick_data, dict):
        # Fallback sur des valeurs neutres si c'est une chaîne de caractères
        adx, atr, spread, rsi = 20.0, 5.0, 50, 50.0
    else:
        adx = float(tick_data.get('adx', 20))
        atr = float(tick_data.get('atr', 5))
        spread = int(tick_data.get('spread', 999))
        rsi = float(tick_data.get('rsi', 50))
    
    # Logique de détection de régime
    regime = "NORMAL"
    reason = "Liquidité et volatilité stables."
    
    # 1. Détection de CRISE (Spread énorme ou Volatilité extrême)
    if spread > 250 or atr > 15:
        regime = "CRISIS"
        reason = "Spread/Volatilité hors normes. Danger extrême."
    
    # 2. Détection de VOLATILITÉ
    elif atr > 10 or abs(rsi - 50) > 20:
        regime = "VOLATILE"
        reason = "Forte amplitude de mouvement détectée."
    
    # 3. Détection de TENDANCE (Trending)
    elif adx > 30:
        regime = "TRENDING"
        reason = "Tendance forte confirmée (ADX > 30)."
    
    # 4. Détection de RANGE (Ranging)
    elif adx < 20:
        regime = "RANGING"
        reason = "Marché latéral, peu de momentum."

    prompt = f"""
    Tu es le REGIME DETECTOR du fonds BlackRock. 
    Ton rôle est de catégoriser le marché actuel pour guider le CIO.
    
    DONNÉES :
    - ADX : {adx}
    - ATR : {atr}
    - RSI : {rsi}
    - Spread : {spread}
    
    VERDICT :
    RÉGIME : {regime}
    RAISON : {reason}
    
    INSTRUCTIONS :
    - Si CRISIS : Recommande l'arrêt total (UNANIMITÉ REQUISE).
    - Si VOLATILE : Recommande prudence et consensus élevé (75%).
    - Si TRENDING : Recommande de suivre le flux.
    - Si RANGING : Recommande d'attendre les cassures.
    
    RÉPONDRE UNIQUEMENT EN FRANÇAIS (2 lignes max).
    FORMAT : [RÉGIME] : (ton explication technique courte)
    """
    
    return prompt
