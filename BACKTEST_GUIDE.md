# ALADDIN PRO V6 — Guide Backtest Strategy Tester MT5

## Protocole de Validation sur 2 Ans de Données Historiques

---

## POURQUOI 2 ANS DE BACKTEST

Un backtest sérieux doit couvrir **plusieurs régimes de marché** :

| Période          | Régime dominant       | Ce que ça teste                        |
|------------------|-----------------------|----------------------------------------|
| Jan–Jun 2023     | Trending haussier     | Performances en tendance forte         |
| Jul–Oct 2023     | Consolidation         | Résistance au ranging                  |
| Nov 2023–Mar 2024| Impulsion XAUUSD      | Gestion des moves ATR extrêmes         |
| Avr–Jun 2024     | Volatilité mixte      | Circuit breakers, drawdown control     |
| Jul–Dec 2024     | Trending + corrections| Robustesse multi-instrument            |

**Si le bot survit à ces 6 régimes différents avec des métriques stables → déploiement autorisé.**

---

## CONFIGURATION DU BOT AVANT BACKTEST

### Paramètres de Test (mode conservateur)

```
// ── RISK ────────────────────────────────────────────────────────
RiskPerTrade         = 0.50    // 0.5% par trade (pas 0.75% en live)
MaxDailyLoss         = 2.50    // Circuit breaker journalier 2.5%
MaxDrawdown          = 10.0    // Stop global 10%
MaxConsecLosses      = 4       // Pause après 4 pertes consécutives

// ── SIGNAUX ─────────────────────────────────────────────────────
ATR_Period           = 14
ATR_SL_Multiplier    = 1.50    // ← Valeur conservatrice pour test
ATR_TP_Multiplier    = 2.50    // ← À ajuster après optimisation
RSI_Period           = 14
RSI_Overbought       = 65
RSI_Oversold         = 35
EMA_Fast             = 9
EMA_Slow             = 21
ADX_Period           = 14
ADX_MinStrength      = 20.0
MinRR_Ratio          = 1.80

// ── SPREAD ──────────────────────────────────────────────────────
MaxSpread_Gold       = 40      // Points — spread max XAUUSD
MaxSpread_Forex      = 25      // Paires forex
MaxSpread_Indices    = 80      // US30, NAS100

// ── INSTRUMENTS ─────────────────────────────────────────────────
EnableXAUUSD         = true
EnableEURUSD         = false   // Phase 1: XAUUSD seul
EnableUS30           = false

// ── SIMULATION ──────────────────────────────────────────────────
SimulationMode       = false
EnableMLFilter       = false   // Désactiver ML en backtest (pas de fichier)
BlockNewsWindow      = false   // Désactiver news filter en backtest
```

---

## PARAMÈTRES STRATEGY TESTER MT5

### Onglet Settings

```
Expert Advisor:   Aladdin_Pro_V6.00
Symbol:           XAUUSD
Period:           M5  (5 minutes — timeframe de travail du bot)
Model:            Every tick based on real ticks  ← OBLIGATOIRE
Date from:        2023.01.02
Date to:          2024.12.31
Deposit:          1000 USD
Leverage:         1:100
```

> ⚠️ **NE PAS utiliser "Open prices only"** — le bot utilise ATR et gestion en cours de barre.

---

## PHASE 1 — BACKTEST SIMPLE (XAUUSD seul, 2 ans)

### Objectifs minimum

| Métrique             | Seuil MINIMUM | Cible OPTIMALE |
|----------------------|---------------|----------------|
| Profit Factor        | > 1.25        | > 1.50         |
| Sharpe Ratio         | > 0.80        | > 1.50         |
| Max Drawdown         | < 20%         | < 10%          |
| Win Rate             | > 42%         | > 50%          |
| Total Trades         | > 200         | > 400          |
| Calmar Ratio         | > 0.50        | > 1.00         |
| Recovery Factor      | > 1.50        | > 3.00         |

---

## PHASE 2 — OPTIMISATION

### Paramètres à optimiser

```
ATR_SL_Multiplier   Start=1.0  Step=0.2  Stop=2.5   ← 8 valeurs
ATR_TP_Multiplier   Start=1.5  Step=0.3  Stop=4.0   ← 9 valeurs
ADX_MinStrength     Start=15   Step=5    Stop=35    ← 5 valeurs
MinRR_Ratio         Start=1.5  Step=0.3  Stop=2.5   ← 4 valeurs
```

Total: **1440 combinaisons** — Double validation Strategy Tester + optimizer.py

**WFE = PF_OOS / PF_IS > 0.50 requis**

---

## PHASE 3 — TEST MULTI-INSTRUMENT

```
Test 1: XAUUSD seul         (2 ans)
Test 2: XAUUSD + EURUSD     (1 an)
Test 3: + US30               (1 an)
Test 4: Full portfolio        (6 mois)
```

---

## PHASE 4 — STRESS TEST

- **Scénario A**: Spread spike (MaxSpread_Gold = 200)
- **Scénario B**: Volatilité extrême (ATR élevé mars 2020)
- **Scénario C**: Série de pertes consécutives (MaxConsecLosses = 3)
- **Scénario D**: Marché en range prolongé (jul–sep 2023)

---

## GRILLE DE DÉCISION

```
╔════════════════════════════════════════════════════════════════╗
║  PF > 1.40  +  MaxDD < 15%  +  WFE > 0.50  +  200+ trades   ║
║  → GO LIVE sur compte démo XM avec capital réel             ║
╠════════════════════════════════════════════════════════════════╣
║  PF 1.20-1.40  OU  MaxDD 15-20%  OU  WFE 0.35-0.50          ║
║  → 3 mois de démo supplémentaires avant live                 ║
╠════════════════════════════════════════════════════════════════╣
║  PF < 1.20  OU  MaxDD > 20%  OU  WFE < 0.35                 ║
║  → Re-optimiser les paramètres et retester                   ║
╠════════════════════════════════════════════════════════════════╣
║  Courbe d'équité avec "falaise" ou perte capitale > 30%      ║
║  → STOP — revoir la logique des signaux                      ║
╚════════════════════════════════════════════════════════════════╝
```

---

## CHECKLIST AVANT GO LIVE

```
BACKTEST (obligatoires)
□ Backtest 2 ans XAUUSD — PF > 1.25, MaxDD < 20%
□ Walk-Forward 2023 IS / 2024 OOS — WFE > 0.40
□ Stress test spread spike — bot ne trade pas si spread > max
□ Stress test circuit breaker — MaxDailyLoss coupe bien
□ Courbe équité OK — pas de falaise

DÉMO LIVE (minimum 3 mois)
□ Compte démo XM Standard — capital $500-$1000 simulé
□ engine.py actif avec dashboard
□ Minimum 100 trades loggés avant première optimisation ML

PREMIÈRE SEMAINE LIVE RÉEL
□ Capital initial $290
□ RiskPerTrade = 0.25% (diviser par 3 vs backtest)
□ MaxDailyLoss = 1.5%
```

---

## COMMANDES POST-BACKTEST

```bash
python ml_engine.py --data trade_log_all.jsonl
python optimizer.py --history trade_log_all.jsonl --capital 1000
python auto_trainer.py --status
```

---

## RÉSULTATS ATTENDUS

**Avec paramètres actuels (ATR_SL=1.0, ATR_TP=4.0, ADX>25) :**

- PF estimé: **1.30–1.60** sur XAUUSD M5
- MaxDD estimé: **8–15%**
