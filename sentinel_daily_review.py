"""
🧠 SENTINEL DAILY REVIEW - Autopsie des trades du jour
Analyse chaque trade, identifie les erreurs, et entraîne le réseau PyTorch.
"""
from sentinel_rl import RLEngine
from sentinel_brain import FundamentalAnalyzer
import json
from datetime import datetime

print("=" * 60)
print("🔬 AUTOPSIE DES TRADES DU 22-23 FÉVRIER 2026")
print("=" * 60)

# ============================================================
# DONNÉES RÉELLES EXTRAITES DE METATRADER 5
# ============================================================
real_trades = [
    # --- 22 Février (Soirée) ---
    {"time": "22/02 20:57", "signal": "BUY",  "lots": 1.0, "open": 832.87, "close": 833.95, "sl": 827.50, "tp": 844.20, "profit": 1.08,  "result": "TP partiel"},
    {"time": "22/02 21:31", "signal": "BUY",  "lots": 1.0, "open": 838.24, "close": 838.71, "sl": 831.91, "tp": 850.89, "profit": 0.47,  "result": "TP partiel"},
    {"time": "22/02 21:55", "signal": "BUY",  "lots": 1.0, "open": 840.53, "close": 834.83, "sl": 835.04, "tp": 851.50, "profit": -5.70, "result": "⛔ SL TOUCHÉ"},
    {"time": "22/02 21:57", "signal": "SELL", "lots": 1.0, "open": 833.09, "close": 832.90, "sl": 0,      "tp": 0,      "profit": 0.19,  "result": "Scalp rapide"},
    
    # --- 23 Février (Matin) ---
    {"time": "23/02 09:29", "signal": "SELL", "lots": 1.0, "open": 821.36, "close": 819.30, "sl": 826.83, "tp": 810.42, "profit": 2.06,  "result": "TP partiel"},
    {"time": "23/02 09:59", "signal": "SELL", "lots": 1.0, "open": 818.75, "close": 814.03, "sl": 813.99, "tp": 807.73, "profit": 4.72,  "result": "Trailing SL"},
    {"time": "23/02 10:08", "signal": "BUY",  "lots": 1.0, "open": 820.57, "close": 822.74, "sl": 814.46, "tp": 832.80, "profit": 2.17,  "result": "TP partiel"},
    {"time": "23/02 10:13", "signal": "BUY",  "lots": 1.0, "open": 823.13, "close": 816.88, "sl": 817.03, "tp": 835.33, "profit": -6.25, "result": "⛔ SL TOUCHÉ"},
    {"time": "23/02 10:29", "signal": "BUY",  "lots": 1.0, "open": 824.59, "close": 829.74, "sl": 817.77, "tp": 838.23, "profit": 5.15,  "result": "TP partiel"},
    {"time": "23/02 10:31", "signal": "BUY",  "lots": 1.0, "open": 830.20, "close": 830.70, "sl": 823.48, "tp": 843.65, "profit": 0.50,  "result": "Scalp"},
    {"time": "23/02 10:45", "signal": "SELL", "lots": 1.0, "open": 821.05, "close": 820.72, "sl": 827.89, "tp": 807.38, "profit": 0.33,  "result": "Scalp"},
]

# ============================================================
# 1. DIAGNOSTIC COMPLET
# ============================================================
total_pnl = sum(t["profit"] for t in real_trades)
winners = [t for t in real_trades if t["profit"] > 0]
losers = [t for t in real_trades if t["profit"] <= 0]
win_rate = len(winners) / len(real_trades) * 100

print(f"\n📊 STATISTIQUES GLOBALES:")
print(f"   Trades total: {len(real_trades)}")
print(f"   ✅ Gagnants:  {len(winners)} ({win_rate:.0f}%)")
print(f"   ❌ Perdants:  {len(losers)} ({100-win_rate:.0f}%)")
print(f"   💰 P&L Total: ${total_pnl:+.2f}")
print(f"   📈 Plus gros gain:  ${max(t['profit'] for t in real_trades):+.2f}")
print(f"   📉 Plus grosse perte: ${min(t['profit'] for t in real_trades):+.2f}")

# Analyse des pertes
print(f"\n🔴 AUTOPSIE DES PERTES:")
for t in losers:
    print(f"\n   ❌ {t['time']} | {t['signal']} @ {t['open']}")
    print(f"      Fermé @ {t['close']} | Perte: ${t['profit']}")
    
    # Diagnostic spécifique
    if t['signal'] == 'BUY':
        drop = t['open'] - t['close']
        print(f"      📉 Le prix a chuté de {drop:.2f} points après l'achat")
        
        # Vérifier si c'était un achat contre-tendance
        if t['open'] > 835:  # Prix déjà élevé
            print(f"      🧠 DIAGNOSTIC: Achat à un sommet ({t['open']}). Le prix était déjà en extension haussière.")
            print(f"      💡 LEÇON: Ne pas acheter quand le prix est trop loin de la moyenne (RSI probablement > 65)")
        elif t['open'] > 820:
            print(f"      🧠 DIAGNOSTIC: Achat rejeté violemment. Probable retournement de tendance.")
            print(f"      💡 LEÇON: Vérifier la macro-tendance (FinBERT) avant d'acheter dans un marché incertain.")

# ============================================================
# 2. PATTERNS DÉTECTÉS
# ============================================================
print(f"\n🧩 PATTERNS DÉTECTÉS:")

# Pattern 1: Achats consécutifs qui finissent en perte
buy_streak = [t for t in real_trades if t['signal'] == 'BUY']
sell_streak = [t for t in real_trades if t['signal'] == 'SELL']
print(f"   • {len(buy_streak)} BUY vs {len(sell_streak)} SELL → Biais acheteur détecté ({len(buy_streak)}/{len(real_trades)})")

# Pattern 2: Les 2 pertes sont des BUY
buy_losses = [t for t in losers if t['signal'] == 'BUY']
print(f"   • Les {len(buy_losses)} pertes sont TOUTES des BUY → Le marché punissait les acheteurs")
print(f"   • Les SELL sont à 100% de win rate → Le marché récompensait la vente")

# Pattern 3: Ratio Risk/Reward
avg_win = sum(t['profit'] for t in winners) / len(winners)
avg_loss = abs(sum(t['profit'] for t in losers) / len(losers)) if losers else 0
print(f"   • Gain moyen: ${avg_win:.2f} | Perte moyenne: ${avg_loss:.2f}")
print(f"   • Ratio R:R réel = 1:{avg_win/avg_loss:.1f}" if avg_loss > 0 else "   • Aucune perte")

# ============================================================
# 3. ENTRAÎNEMENT DU RÉSEAU NEURONAL SUR CES DONNÉES RÉELLES
# ============================================================
print(f"\n{'='*60}")
print(f"🎓 ENTRAÎNEMENT DU RÉSEAU NEURONAL PYTORCH")
print(f"{'='*60}")

# Charger le score fondamental du jour
try:
    with open('fundamental_state.json', 'r') as f:
        funds = json.load(f)
    finbert_score = funds.get('aggregate_score', 0)
    print(f"\n📰 Contexte FinBERT du jour: {funds.get('market_mood', 'N/A')} (Score: {finbert_score})")
except:
    finbert_score = -0.5  # Estimation conservatrice
    print(f"\n📰 Pas de données FinBERT. Estimation conservatrice: {finbert_score}")

# Convertir les trades réels en format d'entraînement
training_data = []
for t in real_trades:
    training_data.append({
        "tech_signal": t["signal"],
        "finbert_score": finbert_score,
        "profit": t["profit"]
    })

# Entraîner le réseau
engine = RLEngine()

# Avant l'entraînement
prob_buy_before = engine.predict_success_probability("BUY", finbert_score)
prob_sell_before = engine.predict_success_probability("SELL", finbert_score)
print(f"\n🔮 AVANT ENTRAÎNEMENT:")
print(f"   P(Win | BUY,  Score={finbert_score}) = {prob_buy_before*100:.1f}%")
print(f"   P(Win | SELL, Score={finbert_score}) = {prob_sell_before*100:.1f}%")

# Entraînement sur les trades réels
engine.train_on_daily_trades(training_data)

# Après l'entraînement
prob_buy_after = engine.predict_success_probability("BUY", finbert_score)
prob_sell_after = engine.predict_success_probability("SELL", finbert_score)
print(f"\n🔮 APRÈS ENTRAÎNEMENT (Les leçons du jour):")
print(f"   P(Win | BUY,  Score={finbert_score}) = {prob_buy_after*100:.1f}% (était {prob_buy_before*100:.1f}%)")
print(f"   P(Win | SELL, Score={finbert_score}) = {prob_sell_after*100:.1f}% (était {prob_sell_before*100:.1f}%)")

# Verdict final
print(f"\n{'='*60}")
print(f"📋 VERDICT FINAL DE L'IA:")
print(f"{'='*60}")
if prob_buy_after < prob_buy_before:
    print(f"   ⚠️ L'IA a BAISSÉ sa confiance dans les BUY ({prob_buy_before*100:.1f}% → {prob_buy_after*100:.1f}%)")
    print(f"   → Demain, elle sera plus prudente sur les achats.")
if prob_sell_after > prob_sell_before:
    print(f"   ✅ L'IA a AUGMENTÉ sa confiance dans les SELL ({prob_sell_before*100:.1f}% → {prob_sell_after*100:.1f}%)")
    print(f"   → Demain, elle favorisera les ventes dans ce contexte macro.")
print(f"\n   💾 Poids neuronaux sauvegardés dans sentinel_brain_weights.pth")
print(f"   → Le bot sera plus intelligent demain grâce à cette session.")
