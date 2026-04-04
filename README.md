# 🏰 SENTINEL V5.3 INDUSTRIAL — Documentation Système

> Bot de trading algorithmique hybride Python + MQL5 pour MetaTrader 5.
> Architecte : Ambity Project | Stack Python : 5.3 | **EA MT5 actuel : Aladdin Pro V7.19** (`Aladdin_Pro_V7_19_Live.mq5`) | Date : Février 2026

---

## 📐 Architecture Globale

```
┌─────────────────────────────────────────────────────────────┐
│                        PYTHON SIDE                          │
│                                                             │
│  main_v5.py ──→ MT5Bridge ──→ Command/xxxx.json (write)    │
│       │                ↑                                     │
│       │          status.json (read)  heartbeat.txt (read)   │
│       │          metrics.json (read)                        │
│       │                                                     │
│  AI Agents:  LearningBrain | ProfessorAgent | RiskManager  │
│  Notifiers:  Telegram | Discord                             │
│  Watchdog:   watchdog.py (independent process)             │
└───────────────────────┬─────────────────────────────────────┘
                        │  File Bridge (MT5_FILES_PATH)
┌───────────────────────▼─────────────────────────────────────┐
│                       MQL5 SIDE (MT5)                       │
│                                                             │
│  Python_Aladdin_Bridge.mq5                                  │
│   ├── OnTimer():  CheckSafety | ScanCommands | Heartbeat   │
│   ├── OnTick():   Scalper (RSI+EMA signals)                │
│   ├── ExportFullStatus()  → status.json                    │
│   ├── ExportMetrics()     → metrics.json (every 5s)        │
│   ├── WriteHeartbeat()    → heartbeat.txt (every 10s)      │
│   ├── ExecuteTrade()      → ATR-based SL/TP auto-calc      │
│   └── GenerateReport()    → report_<ticket>.json (enriched)│
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Fichiers Échangés (File Bridge)

| Fichier | Direction | Fréquence | Contenu |
|---|---|---|---|
| `Command/xxxx.json` | Python → MT5 | Sur signal | Action: TRADE, CLOSE, RESET_RISK |
| `status.json` | MT5 → Python | Chaque seconde | Balance, equity, positions ouvertes |
| `heartbeat.txt` | MT5 → Python | Chaque 10s | Timestamp Unix |
| `metrics.json` | MT5 → Python | Chaque 5s | Spread, ATR, losses streak, pending cmds |
| `ticks_v3.json` | MT5 → Python | Chaque tick | Prix, spread, bougies M5 |
| `report_<id>.json` | MT5 → Python | À la clôture | Détail complet trade (enrichi P7) |
| `simulated_trades.log` | MT5 local | Si Sim=true | Trades simulés sans exécution réelle |

---

## ⚙️ Paramètres EA (Inputs `Python_Aladdin_Bridge.mq5`)

### Groupe Sécurité Institutionnelle
| Input | Défaut | Description |
|---|---|---|
| `MaxDailyLoss` | 500.0 | Stop total si perte > ce montant ($) |
| `MaxDailyDrawdown` | 15.0 | Drawdown journalier max (%) |
| `MaxConsecutiveLosses` | 6 | Stop après N pertes consécutives |
| `EmergencyCooldownHours` | 4 | Pause forcée après arrêt d'urgence |
| `EnableHardStop` | true | Clôturer toutes les positions à l'arrêt |

### Groupe Scalper Autonome
| Input | Défaut | Description |
|---|---|---|
| `EnableScalper` | true | Active le scalper RSI+EMA interne |
| `TargetProfit` | 1.50 | Objectif de gain par scalp ($) |
| `BaseLotSize` | 0.01 | Volume de base |
| `RSIPeriod` | 7 | Période RSI |
| `EMAPeriod` | 50 | Période EMA |

### Groupe Intelligence Adaptative
| Input | Défaut | Description |
|---|---|---|
| `EnableAdaptiveLots` | true | Ajuster les lots selon performance |
| `MaxLotMultiplier` | 2.0 | Multiplicateur maximum |
| `EnableProfitProtector` | true | Breakeven automatique |
| `EnableTimeExit` | true | Fermeture trades stagnants |
| `MaxTradeDuration` | 600 | Durée max d'un trade (secondes) |

### Groupe Hardening Industriel (P1–P8)
| Input | Défaut | Description |
|---|---|---|
| `MagicNumber` | 202601 | ID unique de cet EA (isolation P1) |
| `MaxTradesPerMin` | 5 | Limite anti-emballement (P2) |
| `SimulationMode` | false | Mode test sans vrais ordres (P8) |

---

## 🚀 Démarrage

### Prérequis
```bash
pip install -r requirements.txt
cp bot/.env.example bot/.env   # Remplir les variables
```

### Variables d'environnement (`.env`)
```env
MT5_FILES_PATH=/path/to/MetaTrader5/MQL5/Files
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
EA_HEARTBEAT_TIMEOUT_SEC=90
WATCHDOG_AUTO_RESTART=0
TESTING_MODE=1
TRADING_ASSETS=Volatility 100 Index,EURUSD
```

### Lancer le bot
```bash
# Terminal 1: Bot principal
python bot/main_v5.py

# Terminal 2: Watchdog (optionnel mais recommandé)
python watchdog.py

# MetaTrader 5: Charger Python_Aladdin_Bridge.mq5 sur un graphique
```

### Tests unitaires
```bash
pytest tests/ -v
```

---

## 🔒 Modules de Sécurité Industrielle

| # | Module | Statut |
|---|---|---|
| P1 | Magic Number isolation | ✅ Actif |
| P2 | Rate Limiter (5 trades/min) | ✅ Actif |
| P3 | JSON Cross-Validation Python | ✅ Actif |
| P4 | Heartbeat + Watchdog | ✅ Actif |
| P5 | Metrics JSON temps réel | ✅ Actif |
| P6 | State persistant (power-safe) | ✅ Actif |
| P7 | Rapport audit enrichi | ✅ Actif |
| P8 | Simulation Mode | ✅ Disponible |
| P9 | Tests unitaires | ✅ `pytest tests/` |

---

## 📊 Deep Learning & Rapports

- Données d'audit : `bot/journal/ai_audit.jsonl`
- Base SQLite : `bot/data/sentinel.db`
- Rapport Professor Agent : `python -c "from bot.ai_agents.professor_agent import ProfessorAgent; print(ProfessorAgent().analyze_24h_window())"`
