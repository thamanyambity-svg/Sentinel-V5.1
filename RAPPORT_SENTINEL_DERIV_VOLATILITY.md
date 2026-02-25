# Rapport — Sentinel V5.51 & marchés Deriv Volatility Index

**Date :** Février 2025  
**Version EA :** Sentinel 5.51 (ALADDIN + DERIV Volatility Indices)

---

## 1. Objectif

Intégrer explicitement les **marchés Deriv Volatility 100 Index** et **Volatility 75 Index** dans la configuration de l’EA Sentinel, pour export des ticks vers Python et trading via le pont fichier.

---

## 2. Modifications apportées

### 2.1 Version et en-tête

- **Version** : 5.50 → **5.51**
- **Titre** : « VERSION 5.51 ALADDIN + DERIV VOLATILITY INDICES »
- Message d’init : « SENTINEL V5.51 ALADDIN + DERIV Volatility 100/75: INITIALIZED »

### 2.2 Nouveau groupe d’inputs (Deriv Volatility)

Dans les paramètres de l’EA, un groupe **« DERIV VOLATILITY INDICES »** a été ajouté :

| Input        | Valeur par défaut          | Rôle                          |
|-------------|----------------------------|-------------------------------|
| `SymbolVol100` | `"Volatility 100 Index"` | Symbole MT5 pour Volatility 100 (Deriv) |
| `SymbolVol75`  | `"Volatility 75 Index"`  | Symbole MT5 pour Volatility 75 (Deriv)  |

Vous pouvez les modifier si votre courtier utilise d’autres noms (ex. suffixe ou préfixe).

### 2.3 Export des ticks (`ExportTickData`)

- **Ordre des symboles** : Volatility 100 et Volatility 75 sont exportés **en premier**, puis EURUSD, GOLD, BTCUSD, ETHUSD.
- **Source des noms** : les deux premiers symboles viennent des inputs `SymbolVol100` et `SymbolVol75` (donc configurables sans recompiler si vous changez uniquement les paramètres).
- **Robustesse** : pour chaque symbole, on n’appelle `SymbolInfoDouble` que si le symbole est **dans la Market Watch** (`SYMBOL_SELECT`). Les symboles absents sont ignorés (pas de crash, pas de trou dans le JSON).

### 2.4 Fichier généré : `ticks_v3.json`

Le fichier contient notamment :

- `t`, `account_pnl`, `equity`, `strategy`, `last_pattern`, `signal_strength`
- **`ticks`** : cours (BID) pour chaque symbole disponible, dont :
  - `"Volatility 100 Index"`
  - `"Volatility 75 Index"`
  - puis les autres (EURUSD, GOLD, etc.) si présents en Market Watch

Le bot Python (`MT5DataClient`, `MarketIntelligence`) utilise déjà ces noms pour les synthétiques ; la configuration Sentinel est donc alignée.

---

## 3. Prérequis côté MT5 / Deriv

1. **Compte / connexion** : MT5 connecté à un broker qui propose les indices synthétiques Deriv (ex. Deriv, ou broker avec symboles « Volatility 100 Index » / « Volatility 75 Index »).
2. **Market Watch** : ajouter **Volatility 100 Index** et **Volatility 75 Index** à la Market Watch (clic droit dans la fenêtre Market Watch → Symboles, ou glisser-déposer).
3. **Compilation** : compiler l’EA dans MetaEditor (F7) et l’attacher au graphique (ou au chart d’un des symboles Volatility si le broker l’exige).

---

## 4. Compilation manuelle

1. Ouvrir **MetaEditor** (F4 dans MT5 ou via menu Outils).
2. Ouvrir le fichier **Sentinel.mq5** (dans `MQL5/Experts/` ou le chemin où vous l’avez copié).
3. **Compiler** (F7). Vérifier « 0 errors ».
4. L’exécutable généré (`.ex5`) se trouve dans le dossier indiqué par l’onglet « Toolbox » (généralement `MQL5/Experts/`).
5. Dans MT5, attacher l’EA au graphique souhaité ; les paramètres **DERIV VOLATILITY INDICES** sont modifiables dans la fenêtre des propriétés de l’EA.

---

## 5. Résumé

| Élément                    | Détail                                                                 |
|---------------------------|------------------------------------------------------------------------|
| Version Sentinel          | **5.51**                                                               |
| Marchés Deriv intégrés    | **Volatility 100 Index**, **Volatility 75 Index** (noms configurables) |
| Fichier modifié           | `bot/broker/mt5_bridge/Sentinel.mq5`                                  |
| Export ticks              | `ticks_v3.json` inclut Vol 100 et Vol 75 en tête de liste              |
| Compatibilité Python      | Aucun changement requis ; `main_v5` et `SYNTHETIC_INDICES` utilisent déjà ces noms. |

---

*Rapport généré pour la configuration Sentinel + Deriv Volatility 100/75.*
