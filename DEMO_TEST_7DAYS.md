# 📊 TEST DEMO 7 JOURS - XM GLOBAL

**Période**: 11 février - 18 février 2026  
**Broker**: XM Global (Compte DEMO)  
**Objectif**: Valider les performances avant passage en RÉEL

---

## ✅ **CHECKLIST DE DÉMARRAGE**

### 1. Configuration MT5
- [ ] Compte DEMO XM configuré (ID: 167933585)
- [ ] Mot de passe MT5 ajouté dans `.env`
- [ ] MT5 connecté au serveur "XMGlobal-MT5 2"
- [ ] Symboles EURUSD, XAUUSD, US500 disponibles

### 2. Configuration Bot
- [ ] Mode DEMO confirmé dans `.env`
- [ ] Bridge MT5 testé (lecture status.json)
- [ ] Telegram notifications actives
- [ ] Discord rapports configurés

### 3. Paramètres de Trading
```env
EXECUTION_MODE=REAL          # Exécution réelle (sur DEMO)
TRADING_RISK_PERCENT=1.0     # 1% par trade
MAX_TRADES_PER_DAY=10        # Limite quotidienne
```

---

## 📈 **MÉTRIQUES À SURVEILLER**

### Performance
- **Win Rate**: > 55%
- **Profit Factor**: > 1.5
- **Max Drawdown**: < 10%
- **ROI Journalier**: > 2%

### Risque
- **Respect des Stops**: 100%
- **Slippage Moyen**: < 2 pips
- **Max Loss per Day**: < 5%

### Technique
- **Uptime Bot**: > 99%
- **Latence Bridge**: < 500ms
- **Erreurs de connexion**: 0

---

## 📅 **RAPPORT QUOTIDIEN**

### Jour 1 (11 Fév)
- Capital Initial: $________
- Trades Exécutés: ___
- P/L Jour: $______ (__%)
- Incidents: ________________

### Jour 2 (12 Fév)
- Capital: $________
- Trades: ___
- P/L Jour: $______ (__%)
- Incidents: ________________

### Jour 3 (13 Fév)
- Capital: $________
- Trades: ___
- P/L Jour: $______ (__%)
- Incidents: ________________

### Jour 4 (14 Fév)
- Capital: $________
- Trades: ___
- P/L Jour: $______ (__%)
- Incidents: ________________

### Jour 5 (15 Fév)
- Capital: $________
- Trades: ___
- P/L Jour: $______ (__%)
- Incidents: ________________

### Jour 6 (16 Fév)
- Capital: $________
- Trades: ___
- P/L Jour: $______ (__%)
- Incidents: ________________

### Jour 7 (17 Fév)
- Capital Final: $________
- Total Trades: ___
- P/L Total: $______ (__%)
- Incidents Totaux: __

---

## 🚦 **CRITÈRES DE VALIDATION (GO/NO-GO RÉEL)**

### ✅ VALIDATION (Passage en RÉEL autorisé)
- [ ] Win Rate > 55%
- [ ] Profit Factor > 1.5
- [ ] Max Drawdown < 10%
- [ ] Aucun incident critique
- [ ] Uptime > 99%

### ❌ ÉCHEC (Révision nécessaire)
- [ ] Win Rate < 50%
- [ ] Profit Factor < 1.2
- [ ] Max Drawdown > 15%
- [ ] Incidents critiques (> 3)
- [ ] Uptime < 95%

---

## 🛠️ **COMMANDES DE MONITORING**

```bash
# Vérifier status MT5
python test_bridge_xm.py

# Voir les logs en direct
tail -f bot_full.log

# Rapport de performance
python analyze_log_performance.py

# État du bot
python check_status.py
```

---

## 📝 **NOTES & OBSERVATIONS**

### Points à Tester
1. Comportement weekend (Synthetics vs Forex)
2. Réaction aux news économiques
3. Gestion des slippages XM
4. Stabilité du Bridge pendant 7 jours
5. Cohérence AI (Aladdin) vs Marché

### Améliorations Potentielles
*À compléter pendant les 7 jours*

---

**🔴 RAPPEL CRITIQUE**: Ce test est en DEMO. Aucun argent réel n'est risqué.
Le passage en RÉEL n'aura lieu QUE si tous les critères de validation sont remplis.
