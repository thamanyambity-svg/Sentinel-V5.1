# Rapport d’améliorations — Sentinel V5

**Date :** Février 2025  
**Contexte :** Suite à l’audit technique (`AUDIT_TECHNIQUE_SENTINEL_V5.md`), les correctifs prioritaires (P0/P1/P2) ont été implémentés.

---

## 1. Résumé des changements

| Priorité | Amélioration | Fichiers modifiés / créés |
|----------|--------------|----------------------------|
| **P0** | L’EA écrit désormais `status.json` (positions + balance) | `bot/broker/mt5_bridge/Sentinel.mq5` |
| **P0** | Kill Switch côté Python (drawdown max en %) + RiskManager | `bot/main_v5.py` |
| **P1** | Compteurs risk alimentés : `register_trade` à la clôture, `can_execute_trade` avant ordre | `bot/main_v5.py` |
| **P2** | Verrou processus (un seul pilote) | `bot/core/process_lock.py` (nouveau) |
| **P2** | Lecture `status.json` avec retry + log après échec | `bot/bridge/mt5_interface_v2.py` |
| **P2** | Heartbeat EA (alerte si plus de mise à jour) | `bot/main_v5.py` + `get_status_mtime()` dans le bridge |
| **P3** | SL dédié pour indices synthétiques (points fixes) | `bot/main_v5.py` |
| **P3** | Validation des commandes Tudor (symbol, type, risk) | `bot/bridge/mt5_interface_v2.py` |

---

## 2. Détail par composant

### 2.1 Sentinel.mq5 — Broadcast status

- **Ajout** de la fonction `BroadcastStatus()` qui écrit `status.json` à chaque cycle du timer (après `CheckRiskManagement()`).
- **Contenu** : `updated`, `balance`, `equity`, `trading_enabled`, `positions[]` (ticket, symbol, type, volume, profit, price).
- **Effet** : Python reçoit positions et balance à chaque lecture de `get_raw_status()`, la détection des clôtures et le Kill Switch fonctionnent.

**À faire côté MT5 :** recompiler l’EA et le redéployer (ou remplacer par une version qui inclut déjà cette logique).

---

### 2.2 main_v5.py — Risk management et sécurité

- **Verrou processus**  
  - Au démarrage : `lock_acquire()`. Si un autre Sentinel tourne (fichier lock + PID actif), le processus sort.  
  - À la sortie : `lock_release()` dans un `finally` (et via `atexit` dans `process_lock`).

- **Kill Switch (drawdown journalier)**  
  - `balance_start_of_day` est initialisé au premier balance lu dans `status`, puis réinitialisé à minuit UTC.  
  - À chaque cycle : `risk_manager.check_health(balance_start_of_day, balance)`.  
  - Si drawdown ≥ `MAX_DAILY_DD_PCT` (défaut 5 %) : plus d’envoi d’ordres, log CRITICAL, notification Telegram, puis `continue`.

- **Limites journalières (state/risk)**  
  - À la **clôture** d’une position : `register_trade({"pnl": final_profit})` → mise à jour de `_TRADES_TODAY` et `_DAILY_PNL`.  
  - **Avant** d’envoyer un ordre : `can_execute_trade({"asset": asset})`. Si refus (ex. limite de trades ou perte max atteinte), le signal est ignoré.  
  - À **minuit UTC** : `reset_daily_limits()` et mise à jour de `balance_start_of_day`.

- **Heartbeat EA**  
  - Après chaque lecture de status : si `get_status_mtime()` indique que `status.json` n’a pas été modifié depuis plus de `EA_HEARTBEAT_TIMEOUT_SEC` (défaut 90 s), log CRITICAL + alerte Telegram.

- **Stop loss pour synthétiques**  
  - Pour les actifs contenant `"Volatility"` ou `"Index"` : `sl_pips = 50` (points fixes).  
  - Pour le Forex : formule existante (pips, avec cas JPY).

- **Clés de positions**  
  - Les tickets sont normalisés en string pour `current_positions` / `known_positions`, afin d’éviter des incohérences int/str.

---

### 2.3 Bridge (mt5_interface_v2.py)

- **get_raw_status(retries=3, retry_delay=0.05)**  
  - Jusqu’à 3 lectures avec 50 ms entre chaque.  
  - En cas de `JSONDecodeError` (écriture EA en cours) : retry puis log WARNING si échec final.

- **get_status_mtime()**  
  - Retourne le timestamp de dernière modification de `status.json` (pour le heartbeat).

- **send_tudor_trade**  
  - Vérifications avant écriture : symbol non vide, type dans BUY/SELL, `ai_risk_multiplier` dans une plage raisonnable. Sinon retour `False` et pas d’écriture du fichier de commande.

---

### 2.4 Nouveau module — process_lock.py

- Fichier lock : `sentinel_v5.lock` à la racine du projet, contenu = PID.  
- Si le fichier existe : lecture du PID ; si le processus est encore actif (`os.kill(pid, 0)`), abandon et sortie. Sinon suppression du lock orphelin et prise du lock.  
- Libération au `finally` de `run_bot()` et via `atexit`.

---

## 3. Configuration (variables d’environnement)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `MAX_DAILY_DD_PCT` | `0.05` | Drawdown journalier max (5 %) pour le Kill Switch Python. |
| `EA_HEARTBEAT_TIMEOUT_SEC` | `90` | Délai (secondes) sans mise à jour de `status.json` avant alerte heartbeat. |

Les limites “nombre de trades / jour” et “perte max en €” restent dans `bot/state/risk/limits.py` (`_MAX_TRADES`, `_MAX_DAILY_LOSS`). Vous pouvez les modifier ou les rendre configurables plus tard.

---

## 4. Fichiers impactés (liste)

- `bot/broker/mt5_bridge/Sentinel.mq5` — BroadcastStatus + appel dans Processing.
- `bot/main_v5.py` — Lock, RiskManager, Kill Switch %, register_trade, can_execute_trade, heartbeat, reset jour, SL synthétiques.
- `bot/bridge/mt5_interface_v2.py` — get_raw_status (retry), get_status_mtime, validation send_tudor_trade.
- `bot/core/process_lock.py` — Nouveau.

---

## 5. Vérifications recommandées

1. **MT5** : Recompiler et attacher l’EA Sentinel modifié ; vérifier que `status.json` apparaît et est mis à jour dans le dossier MQL5/Files.
2. **Un seul pilote** : Lancer deux fois `main_v5` ; le second doit quitter avec le message “Another Sentinel is already running”.
3. **Kill Switch** : En test, baisser `MAX_DAILY_DD_PCT` (ex. 0.001) et vérifier que les ordres s’arrêtent et qu’une alerte est envoyée.
4. **Limites journalières** : Vérifier dans `bot/state/risk/limits.py` que `_MAX_TRADES` et `_MAX_DAILY_LOSS` correspondent à votre politique (actuellement 1 trade/jour et -100 € de perte max en mémoire).

---

## 6. Suite possible (non implémentée)

- **ProductionSecurityManager** : brancher `validate_trade_command` (format direction/volume) sur un chemin d’ordre commun si vous ajoutez un autre point d’envoi d’ordres.
- **Unification active_trades** : faire correspondre les positions envoyées par `main_v5` avec `add_active_trade` / `bot_state.json` pour un suivi unique (optionnel).
- **Persistance des limites** : sauvegarder `_TRADES_TODAY` / `_DAILY_PNL` (ou balance_start_of_day) dans un fichier pour survivre au redémarrage du bot dans la même journée.

---

*Rapport généré après implémentation des améliorations issues de l’audit technique Sentinel V5.*
