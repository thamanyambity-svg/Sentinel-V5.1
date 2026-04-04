# ALADDIN PRO V6.00 — Guide d'Intégration Complet
## Système de Trading Institutionnel Multi-Instruments

---

## ARCHITECTURE DU SYSTÈME

```
MT5 (MQL5)                    Python Engine
──────────────────────────    ──────────────────────────────────────
Aladdin_Pro_V6.00.mq5         engine.py          — Moteur central
  │                             ├── news_filter.py — Calendrier éco
  │── status.json ──────────►   ├── optimizer.py   — Optimiseur WFO
  │── ticks_v3.json ─────────►  ├── backtest_analyzer.py — Métriques
  │── metrics.json ──────────►  └── dashboard.py   — Interface CLI
  │
  │◄─ news_block.json ──────── NewsFilter (export toutes les heures)
  │◄─ Command/*.json ─────────  engine.send_command("PAUSE") etc.
```

---

## INSTALLATION

### 1. Prérequis
```bash
pip install rich      # Dashboard terminal
# pandas, numpy, matplotlib — optionnels pour les graphiques
```

### 2. Configuration du chemin MT5
```bash
# Windows — Chercher le dossier dans MetaTrader 5: File > Open Data Folder
set MT5_FILES_PATH=C:\Users\<user>\AppData\Roaming\MetaQuotes\Terminal\<ID>\MQL5\Files

# Ou dans engine.py, modifier:
Config.MT5_FILES_PATH = Path("C:/Users/.../MQL5/Files")
```

### 3. Déploiement du bot MQL5
1. Copier `Aladdin_Pro_V6.00.mq5` dans le dossier `MQL5/Experts/`
2. Compiler dans MetaEditor (F7)
3. Glisser sur le graphique XAUUSD M5
4. **Activer `SimulationMode = true` pour les premiers tests**
5. Activer `Allow automated trading`

---

## INTÉGRATION COMPLÈTE — engine.py

```python
from pathlib import Path
from engine import AladdinEngine, Config
from news_filter import NewsFilter

# Configuration
cfg = Config()
cfg.MT5_FILES_PATH = Path("C:/Users/.../MQL5/Files")

# Démarrage du moteur
engine = AladdinEngine(cfg)

# Ajout du filtre news
engine.news_filter = NewsFilter(mt5_path=str(cfg.MT5_FILES_PATH))
engine.news_filter.start()

# Callbacks (optionnel — pour UI custom)
engine.on_alert = lambda alert: print(f"ALERTE: {alert}")

# Démarrage
engine.start()
```

---

## MODULE NEWS FILTER — Fonctionnement

### Fenêtres de protection par défaut
| Événement        | Avant  | Après  |
|-----------------|--------|--------|
| Standard HIGH   | 30 min | 60 min |
| Tier1 (NFP, FOMC, CPI, ECB, BOE, BOJ) | 60 min | 120 min |

### Instruments bloqués par devise
| Devise | Instruments bloqués |
|--------|---------------------|
| USD    | EURUSD, GBPUSD, USDJPY, XAUUSD, US30, NAS100... |
| EUR    | EURUSD, EURGBP, EURJPY... |
| GBP    | GBPUSD, EURGBP, GBPJPY... |
| JPY    | USDJPY, EURJPY, GBPJPY... |

### Intégration dans MQL5 (snippet à ajouter dans OnTick)
```cpp
bool IsNewsBlocked(string symbol)
{
   string path = "news_block.json";
   if(!FileIsExist(path)) return false;
   int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) return false;
   string content = "";
   while(!FileIsEnding(h)) content += FileReadString(h);
   FileClose(h);
   string search = "\"" + symbol + "\"";
   int pos = StringFind(content, search);
   if(pos < 0) return false;
   int bl_pos = StringFind(content, "\"blocked\":true", pos);
   return (bl_pos > pos && bl_pos < pos + 200);
}

// Dans la boucle de scan OnTick, avant ExecuteEntry():
if(IsNewsBlocked(symbols[i].symbol)) {
   Print("[NEWS] Trade bloqué: ", symbols[i].symbol);
   continue;
}
```

---

## MODULE OPTIMISEUR — Walk-Forward Optimization

### Lancement
```bash
# Mode démo (120 trades synthétiques)
python optimizer.py --demo

# Avec données réelles (exporter l'historique MT5 en JSON)
python optimizer.py --history my_trades.json --capital 1000

# Split IS/OOS personnalisé
python optimizer.py --demo --is-pct 0.65  # 65% IS, 35% OOS
```

### Format JSON des trades historiques
```json
{
  "trades": [
    {
      "symbol":        "XAUUSD",
      "direction":     "BUY",
      "open_time":     "2024-01-03T08:15:00",
      "close_time":    "2024-01-03T08:27:00",
      "open_price":    2040.50,
      "close_price":   2043.20,
      "lot":           0.01,
      "profit":        2.70,
      "sl_distance":   1.8,
      "atr_at_entry":  1.2,
      "rsi_at_entry":  52.3,
      "adx_at_entry":  28.5
    }
  ]
}
```

### Exporter l'ATR/RSI/ADX depuis MT5
```cpp
// Ajouter dans ExecuteEntry() pour logger les indicateurs:
string log_json = "{\"symbol\":\"" + sym
   + "\",\"atr\":" + DoubleToString(symbols[idx].lastATR, 5)
   + ",\"rsi\":" + DoubleToString(symbols[idx].lastRSI, 2)
   + ",\"adx\":" + DoubleToString(symbols[idx].lastADX, 2) + "}";
int h = FileOpen("entry_log.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
FileWriteString(h, log_json); FileClose(h);
```

### Grille de paramètres testés
| Paramètre         | Valeurs testées                        |
|------------------|----------------------------------------|
| ATR_SL_Multiplier | 1.0, 1.2, 1.5, 1.8, 2.0, 2.5          |
| ATR_TP_Multiplier | 1.5, 2.0, 2.5, 3.0, 3.5, 4.0          |
| ADX_MinStrength   | 15, 18, 20, 25, 30                     |
| MinRR_Ratio       | 1.5, 1.8, 2.0, 2.5                     |
| RSI_Overbought    | 60, 65, 70                             |
| RSI_Oversold      | 30, 35, 40                             |
| **Total combos**  | **~2700 (filtrées automatiquement)**   |

### Interprétation du WFE (Walk-Forward Efficiency)
| WFE Score | Interprétation | Action |
|-----------|----------------|--------|
| ≥ 0.5     | Robuste — stratégie généralisable | ✅ Déploiement possible |
| 0.3–0.5   | Acceptable — surveiller en démo | ⚠️ Tester 3 mois en démo |
| < 0.3     | Suroptimisé (curve-fitting) | ❌ Ne pas déployer |

---

## DASHBOARD TERMINAL

```bash
# Démarrage standard
python dashboard.py --mt5-path "C:/Users/.../MQL5/Files"

# Mode texte simple (sans Rich)
python dashboard.py --simple

# Raccourcis clavier dans le dashboard
# Q → Quitter
# P → Pause trading
# R → Reprendre trading
# C → Close All positions
# X → Reset Risk (pertes consécutives + multiplicateur)
# 1 → Lot mult × 0.5   (réduction exposition)
# 2 → Lot mult × 0.75
# 3 → Lot mult × 1.0   (normal)
# 4 → Lot mult × 1.25
# 5 → Lot mult × 1.5   (augmentation exposition)
```

---

## WORKFLOW DE DÉPLOIEMENT RECOMMANDÉ

```
Semaine 1-2:   SimulationMode=true  → Valider les signaux, vérifier les logs
Semaine 3-4:   Compte démo live     → Vérifier exécution, spread, slippage
Mois 2-3:      Compte réel micro    → RiskPerTrade=0.25%, MaxDailyLoss=1%
Mois 4+:       Paramètres normaux   → RiskPerTrade=0.75%, après validation WFO
```

---

## MÉTRIQUES CIBLES (GO LIVE)

| Métrique           | Minimum requis | Cible optimale |
|-------------------|----------------|----------------|
| Profit Factor      | > 1.30         | > 1.50         |
| Sharpe Ratio       | > 0.80         | > 1.50         |
| Max Drawdown       | < 15%          | < 8%           |
| Win Rate           | > 42%          | > 50%          |
| WFE Score          | > 0.40         | > 0.60         |
| Période de test    | 3 mois minimum | 6 mois         |

---

## FICHIERS DU SYSTÈME

| Fichier                    | Type   | Description |
|---------------------------|--------|-------------|
| Aladdin_Pro_V6.00.mq5     | MQL5   | Bot principal |
| engine.py                 | Python | Moteur de monitoring |
| news_filter.py            | Python | Filtre calendrier économique |
| optimizer.py              | Python | Optimiseur WFO automatique |
| backtest_analyzer.py      | Python | Analyseur de backtest |
| dashboard.py              | Python | Dashboard terminal Rich |
| status.json               | JSON   | État en temps réel (MT5→Python) |
| ticks_v3.json             | JSON   | Ticks multi-instruments |
| news_block.json           | JSON   | Bloquages news (Python→MT5) |
| Command/*.json            | JSON   | Commandes (Python→MT5) |
| metrics.json              | JSON   | Métriques de performance |
| heartbeat.txt             | TXT    | Watchdog MT5 |
