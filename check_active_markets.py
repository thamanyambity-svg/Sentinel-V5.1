#!/usr/bin/env python3
"""
Affiche les marchés actifs en temps réel
"""
from datetime import datetime
import pytz

# Heure actuelle
now = datetime.now(pytz.timezone('Europe/Paris'))
print(f"🕐 Heure Actuelle: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"   Jour: {now.strftime('%A')}")
print("\n" + "="*60)

# Déterminer les sessions forex
hour_utc = datetime.now(pytz.UTC).hour
day_of_week = now.weekday()  # 0=Lundi, 6=Dimanche

print("\n📊 ÉTAT DES MARCHÉS\n")

# 1. MARCHÉS FOREX (XM Global)
print("🌍 FOREX SPOTS (XM Global):")
if day_of_week == 6:  # Dimanche
    if hour_utc >= 22:
        print("   ✅ OUVERT (Pré-ouverture Sydney)")
    else:
        print("   ❌ FERMÉ (Weekend)")
elif day_of_week == 5 and hour_utc >= 21:  # Vendredi après 21h UTC
    print("   ❌ FERMÉ (Clôture weekend)")
elif day_of_week < 5 or (day_of_week == 5 and hour_utc < 21):
    print("   ✅ OUVERT - Trading actif")
    
    # Déterminer la session active
    if 22 <= hour_utc or hour_utc < 8:
        print("      🌏 Session: ASIE (Tokyo, Sydney)")
    elif 8 <= hour_utc < 16:
        print("      🇪🇺 Session: EUROPE (Londres, Francfort)")
    elif 16 <= hour_utc < 22:
        print("      🇺🇸 Session: AMÉRIQUE (New York)")
else:
    print("   ❌ FERMÉ")

print(f"\n      Paires configurées: EURUSD, XAUUSD")
print(f"      Liquidité: {'ÉLEVÉE' if 8 <= hour_utc < 16 else 'MOYENNE'}")

# 2. OR / GOLD
print("\n💰 OR (XAUUSD / GOLD):")
if day_of_week < 5 or (day_of_week == 5 and hour_utc < 21):
    print("   ✅ OUVERT")
    print("      Horaires: 24h/5j (Dim 23h - Ven 22h UTC)")
else:
    print("   ❌ FERMÉ (Weekend)")

# 3. INDICES US
print("\n📈 INDICES US (US500):")
if day_of_week < 5:
    if 14 <= hour_utc < 21:
        print("   ✅ OUVERT - Session Principale (NYSE)")
    elif 21 <= hour_utc or hour_utc < 14:
        print("   🟡 FUTURES UNIQUEMENT (Liquidité réduite)")
    else:
        print("   ❌ FERMÉ")
elif day_of_week == 6:
    print("   ❌ FERMÉ (Weekend)")
else:
    print("   🟡 FUTURES (Dimanche soir)")

# 4. CRYPTO (si activé)
print("\n₿ CRYPTO (BTC, ETH):")
print("   ✅ OUVERT 24/7")
print("      Aucune fermeture weekend")

# 5. INDICES SYNTHÉTIQUES DERIV
print("\n🎲 INDICES SYNTHÉTIQUES (Deriv):")
print("   ✅ OUVERT 24/7/365")
print("      Volatility 100, 75, 50 Index")
print("      Aucune fermeture, liquidité constante")

# RECOMMANDATIONS
print("\n" + "="*60)
print("\n💡 RECOMMANDATIONS ACTUELLES:\n")

if 8 <= hour_utc < 16 and day_of_week < 5:
    print("   🟢 CONDITIONS IDÉALES:")
    print("      - Session européenne (spreads serrés)")
    print("      - Tous les marchés Forex ouverts")
    print("      - Volatilité modérée à élevée")
    print("\n   🎯 Paires recommandées: EURUSD, XAUUSD, US500")
elif 16 <= hour_utc < 21 and day_of_week < 5:
    print("   🟢 SESSION US (Haute volatilité):")
    print("      - Overlap Europe/US (16h-17h)")
    print("      - US500 très actif")
    print("\n   🎯 Focus: US500, XAUUSD")
elif day_of_week >= 5:
    print("   🟡 WEEKEND - FOREX FERMÉ")
    print("      - Forex/Indices fermés")
    print("      - Seuls les synthétiques fonctionnent")
    print("\n   🎯 Focus: Volatility 100, Volatility 75 (Deriv)")
else:
    print("   🟡 SESSION ASIE (Volatilité faible):")
    print("      - Spreads plus larges")
    print("      - Liquidité réduite")
    print("\n   🎯 Réduire exposition ou attendre Europe")

print("\n" + "="*60 + "\n")
