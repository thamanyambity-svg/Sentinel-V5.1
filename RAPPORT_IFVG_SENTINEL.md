# Rapport — Stratégie IFVG + Mise à jour Sentinel 5.52

**Date :** Février 2025  
**Version Sentinel :** 5.52 (ALADDIN + DERIV Volatility + IFVG M5 Bars)

---

## 1. Résumé

La stratégie **IFVG (Implied Fair Value Gap)** sur **M5** pour les indices **Volatility 100** et **Volatility 75** est intégrée au bot. L’EA Sentinel exporte désormais les chandeliers M5 vers Python ; le module IFVG analyse structure, bougie impulsive, zone FVG et rejet pour générer des signaux BUY/SELL avec SL/TP.

---

## 2. Modifications Sentinel (MQL5)

### 2.1 Version 5.52

- **Fichier :** `bot/broker/mt5_bridge/Sentinel.mq5`
- **Changements :**
  - Export **M5** : nouvelle fonction `ExportM5Bars()`.
  - Fichier généré : **`m5_bars.json`** à la racine MQL5/Files (même dossier que `status.json`).
  - Contenu : `{ "updated": <timestamp>, "symbols": { "Volatility 100 Index": [ { "t", "o", "h", "l", "c" }, ... ], "Volatility 75 Index": [ ... ] } }`.
  - Les barres sont les **100 dernières M5** (ordre : plus ancienne en premier).
  - Appel de `ExportM5Bars()` dans `Processing()` après `ExportTickData()`.
- **Compilation :** recompiler l’EA dans MetaEditor (F7) et le réattacher au graphique.

---

## 3. Côté Python

### 3.1 Bridge

- **Fichier :** `bot/bridge/mt5_interface_v2.py`
- **Méthode :** `get_m5_bars()` → lit `m5_bars.json`, retourne le dict `symbols` (clé = nom symbole, valeur = liste de barres `{ t, o, h, l, c }`). Jusqu’à 3 tentatives en cas de lecture pendant écriture.

### 3.2 Stratégie IFVG

- **Fichier :** `bot/strategy/ifvg_volatility.py`
- **Logique (résumée) :**
  1. **Structure de marché :** swing highs/lows sur les dernières barres → tendance (HH/HL = bull, LH/LL = bear).
  2. **Bougie impulsive :** corps ≥ ATR × 0.4.
  3. **Zone IFVG :** gap (bearish : entre high bougie impulsive et low bougie précédente ; bullish : symétrique). Taille minimale 2 points.
  4. **Entrée :** rejet de la zone (dernière barre qui ferme en dehors de la zone dans le sens du mouvement).
  5. **SL/TP :** SL juste au-dessus/sous la zone + marge ; TP = zone ± multiple de la taille du gap.
- **Fonction exposée :** `get_ifvg_signal(symbol, candles, point=0.01)` → retourne `None` ou `{ "side", "entry", "sl", "tp", "sl_pips", "confidence", "reason", "strategy": "IFVG_SCALP" }`.

### 3.3 Intégration main_v5

- **Fichier :** `bot/main_v5.py`
- **Comportement :**
  - À chaque cycle, lecture de **M5** via `bridge.get_m5_bars()`.
  - Pour chaque actif dans **SYNTHETIC_INDICES** (Volatility 100 Index, Volatility 75 Index) :
    - Si au moins 20 barres M5 sont disponibles → appel à **IFVG**.
    - Si IFVG renvoie un signal → utilisation de ce signal (side, sl_pips, confidence, strategy `IFVG_SCALP`, pattern ex. `IFVG_SELL_M5`).
    - Sinon → **fallback** sur la logique ALADDIN (trend + change %).
  - Les ordres IFVG sont envoyés via le même pont (`send_tudor_trade`) avec `strategy="IFVG_SCALP"` ; l’EA les exécute comme les autres TUDOR_TRADE (volume calculé par risque %, SL en pips).

---

## 4. Flux de données

```
MT5 (Sentinel 5.52)
  → ExportM5Bars() → m5_bars.json (100 barres M5 par symbole Vol 100/75)
  → BroadcastStatus() → status.json
  → ExportTickData() → ticks_v3.json

Python (main_v5)
  → bridge.get_m5_bars() → { "Volatility 100 Index": [...], "Volatility 75 Index": [...] }
  → get_ifvg_signal(asset, candles, point) → signal ou None
  → si signal: bridge.send_tudor_trade(..., strategy="IFVG_SCALP", stop_loss_pips=...)
  → sinon: logique ALADDIN (trend)
```

---

## 5. Fichiers modifiés / créés

| Fichier | Action |
|---------|--------|
| `bot/broker/mt5_bridge/Sentinel.mq5` | Modifié (v5.52, ExportM5Bars) |
| `bot/bridge/mt5_interface_v2.py` | Modifié (get_m5_bars) |
| `bot/strategy/ifvg_volatility.py` | Créé (stratégie IFVG) |
| `bot/main_v5.py` | Modifié (IFVG + fallback ALADDIN) |
| `RAPPORT_IFVG_SENTINEL.md` | Créé (ce rapport) |

---

## 6. Vérifications recommandées

1. **MT5 :** Vérifier que **Volatility 100 Index** et **Volatility 75 Index** sont dans la Market Watch et que l’historique M5 est chargé (sinon `CopyRates` peut retourner 0).
2. **Fichier M5 :** Après démarrage de l’EA, contrôler la présence de **m5_bars.json** dans le dossier MQL5/Files et son contenu (updated récent, tableaux non vides).
3. **Logs Python :** Rechercher les lignes `IFVG ... SELL/BUY | SL ... pips | IFVG_*_M5` pour confirmer que l’IFVG produit des signaux quand le marché le permet.
4. **Fallback :** En l’absence de signal IFVG (ou de M5), le bot continue avec ALADDIN (trend) sur les mêmes actifs.

---

*Rapport généré après intégration IFVG et mise à jour Sentinel 5.52.*
