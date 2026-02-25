# Rapport diagnostic — Zéro trade

**Constat :** Le bot tourne mais n’ouvre aucun trade.

---

## 1. Checklist de vérification

### 1.1 MT5 & Sentinel

| Vérification | Commande / action | Si KO |
|--------------|-------------------|-------|
| MT5 ouvert | — | Ouvrir MT5 et se connecter au compte |
| Sentinel attaché | Onglet Experts sur le graphique | Attacher Sentinel à un graphique (ex. Volatility 100 M5) |
| AutoTrading activé | Bouton vert en haut de MT5 | Cliquer pour activer |
| Volatility 100 & 75 en Market Watch | Fenêtre Market Watch | Clic droit → Symboles → ajouter "Volatility 100 Index" et "Volatility 75 Index" |

### 1.2 Fichiers de données (MT5 → Python)

Les fichiers doivent être dans le dossier défini par **`MT5_FILES_PATH`** (`.env`).

| Fichier | Rôle | Vérifier |
|---------|------|----------|
| `ticks_v3.json` | Prix temps réel pour l’analyse | Existe et se met à jour toutes les secondes |
| `status.json` | Positions, balance | Existe |
| `m5_bars.json` | Barres M5 pour IFVG | Existe (pour IFVG) |
| `Command/` | Ordres envoyés par Python | Le dossier existe |

Commande utile pour voir si les fichiers existent et sont mis à jour :

```bash
ls -la "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/"
```

Ou avec le chemin de ton `.env` :

```bash
# Remplacer par ton MT5_FILES_PATH
MT5_PATH=$(grep MT5_FILES_PATH bot/.env | cut -d= -f2)
ls -la "$MT5_PATH"
```

### 1.3 Variable d’environnement

Vérifier que `bot/.env` contient :

```
MT5_FILES_PATH=/chemin/vers/MQL5/Files
```

Le chemin doit pointer vers le dossier où MT5 écrit ses fichiers (souvent sous Wine :  
`.../net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files`).

---

## 2. Causes probables du zéro trade

### A. Pas de données (ticks_v3.json manquant ou vide)

- **Symptôme :** Logs `⚠️ No tick data for Volatility 100 Index` ou `No Data`.
- **Cause :** EA non démarré, mauvais chemin, symboles absents de la Market Watch.
- **Action :** Vérifier que Sentinel tourne, que Vol 100/75 sont dans la Market Watch, et que `ticks_v3.json` existe et contient ces symboles.

### B. `change_percent` trop faible → pas de signal

- **Logique actuelle :** Pour Volatility, il faut `change > 0.05%` (WEAK_UP) ou `change < -0.05%` (WEAK_DOWN).
- **Problème :** Sur un cycle de 10 s, le prix bouge souvent moins de 0.05 % → tendance considérée comme RANGE → pas de signal.
- **Solution :** Baisser le seuil à **0.02%** ou **0.01%** pour générer plus de signaux en mode test.

### C. Analyse invalide

- **Symptôme :** `analysis.get('valid')` = False (retour "No Data", "Market Closed", spread trop élevé).
- **Action :** Contrôler les logs pour voir si `get_symbol_analysis` renvoie une erreur.

### D. IFVG sans barres M5

- **Logique :** IFVG nécessite `m5_bars.json` avec au moins 20 barres par symbole.
- **Symptôme :** Toujours fallback ALADDIN (trend), jamais IFVG.
- **Action :** S’assurer que `m5_bars.json` existe et que les symboles Vol 100/75 ont des barres.

### E. Logs de chaque cycle

Les logs devraient afficher à chaque cycle quelque chose comme :

```
🔍 Volatility 100 Index: 1234.56 | Trend: RANGE (0.012%)
💤 Volatility 100 Index: No Signal (Range/Flat)
```

Si tu vois `No Data` ou `Market Closed`, le problème est en amont (données ou configuration).

---

## 3. Modification recommandée : seuil plus bas pour les Volatility

Pour forcer plus de signaux en phase de test, réduire le seuil pour les indices Volatility.

**Fichier :** `bot/main_v5.py`  
**Bloc concerné :** Override pour les Volatility (fallback ALADDIN)

**Actuel :**
```python
if change > 0.05: trend = "WEAK_UP"
elif change < -0.05: trend = "WEAK_DOWN"
```

**Proposition (seuil 0.02 %) :**
```python
if change > 0.02: trend = "WEAK_UP"
elif change < -0.02: trend = "WEAK_DOWN"
```

Ajout possible d’une variable d’environnement, par exemple `VOLATILITY_CHANGE_THRESHOLD=0.02`, pour le rendre configurable.

---

## 4. Script de diagnostic rapide

Tu peux lancer ce script pour vérifier les données :

```bash
cd /Users/macbookpro/Downloads/bot_project
PYTHONPATH=. python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('bot/.env')
path = os.getenv('MT5_FILES_PATH', 'NON_DEFINI')
print('MT5_FILES_PATH:', path)
import json
for f in ['ticks_v3.json', 'status.json', 'm5_bars.json']:
    p = os.path.join(path, f)
    exists = os.path.exists(p)
    mtime = os.path.getmtime(p) if exists else 0
    print(f'  {f}: existe={exists}, mtime={mtime}')
if path != 'NON_DEFINI' and os.path.exists(os.path.join(path, 'ticks_v3.json')):
    with open(os.path.join(path, 'ticks_v3.json')) as f:
        d = json.load(f)
    print('  ticks keys:', list(d.get('ticks', {}).keys()))
"
```

---

## 5. Actions immédiates

1. Vérifier que MT5 + Sentinel tournent avec Vol 100/75 dans la Market Watch.
2. Vérifier que `ticks_v3.json` existe et contient les symboles.
3. Baisser le seuil de changement à 0.02 % pour les Volatility.
4. Relancer le bot et surveiller les logs (message par actif et par cycle).

---

*Rapport généré suite au diagnostic zéro trade.*
