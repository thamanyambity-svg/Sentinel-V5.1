# Audit Technique Complet — Robot de Trading Sentinel V5

**Rôle :** Architecte Logiciel Senior / Ingénieur Quantitatif  
**Périmètre :** `main_v5.py`, pont Python ↔ MQL5 (MT5 Bridge), Risk Management, flux de données, sécurité du capital.

---

## PHASE 1 : Bilan Macro & Avis Critique (Le Diagnostic)

### Points Forts (Avis Favorable)

| Élément | Détail |
|--------|--------|
| **Pont fichier Python ↔ MQL5** | Écriture atomique des commandes (fichier `.tmp` puis `rename`) et validation des champs (`validate_trade_command`) limitent la corruption et les commandes mal formées. |
| **Séparation des responsabilités** | `MarketIntelligence` (analyse), `MT5Bridge` (exécution), `ExperienceLogger` (apprentissage) et notifiers (Telegram/Discord) sont bien découplés. |
| **Risk côté EA** | Sentinel.mq5 implémente un Kill Switch (MaxDailyLoss en $), High Water Mark, et désactivation du trading avec persistance (`Sentinel_State.dat`). En cas de dépassement, `CloseAllPositions` + `tradingEnabled = false`. |
| **Aladdin AI côté EA** | Filtre par `MinAIConfidence`, ajustement du risque par `ai_risk_multiplier` (borné 0.1%–10%), calcul de volume par `CalculateTudorPositionSize` (équity, tick value, SL en pips). |
| **State persistant (Python)** | `active_trades` avec sauvegarde atomique dans `bot_state.json` (write temp + `os.replace`) évite la perte d’état au crash. |
| **Data feed direct MT5** | `MT5DataClient` lit `ticks_v3.json` avec gestion de race (JSON decode error → retry au cycle suivant) et calcul de `change_percent` via mémoire de prix. |
| **ProductionSecurityManager** | Validation IP, audit log, validation volume/direction des commandes (volume ≤ 10). Présent dans le projet mais non branché sur `main_v5`. |
| **MultiLevelKillSwitch (guard)** | Conception solide (daily/session/cluster/cooldown) dans `bot/risk/guard.py`, utilisée par `TradingManager` dans `bot/core/manager.py`. |

### Points Faibles (Avis Critique)

| Faille | Gravité | Description |
|--------|---------|-------------|
| **status.json absent dans Sentinel.mq5 principal** | Critique | Le fichier `bot/broker/mt5_bridge/Sentinel.mq5` **n’écrit pas** `status.json`. Seuls `Sentinel_v10_FIXED.mq5`, `Sentinel_v5_2_ULTIMATE.mq5`, etc. le font. `main_v5` appelle `bridge.get_raw_status()` à chaque cycle : si l’EA déployé est le Sentinel.mq5 actuel, **positions et balance ne remontent jamais** → détection de clôture et notifications impossibles. |
| **Aucun risk management Python dans main_v5** | Critique | `main_v5` n’utilise pas `RiskManager`, `MultiLevelKillSwitch`, `can_execute_trade`, ni `state.risk.limits` (increment_trades/add_pnl). Seul garde-fou : `risk_level == "HIGH"` (skip cycle). Pas de plafond de perte journalière côté Python, pas de limite de nombre de trades, pas de drawdown global. |
| **Limites risk en mémoire non alimentées** | Critique | `state/risk/limits.py` : `_TRADES_TODAY`, `_DAILY_PNL` ne sont jamais mis à jour par `main_v5`. `register_trade()` (qui appelle `increment_trades`/`add_pnl`) n’est pas appelé. Même si on branchait `can_execute_trade`, les compteurs resteraient à 0 / -100. |
| **Double source de vérité pour les positions** | Élevée | Positions suivies dans `main_v5` via `known_positions` (dérivé de `status.json`) et optionnellement dans `active_trades` (rempli uniquement par `DerivBroker.execute` en mode Bridge). `main_v5` envoie les ordres via `bridge.send_tudor_trade()` **sans** appeler `add_active_trade` → incohérence et impossible de réconcilier avec `bot_state.json`. |
| **Lock global non utilisé** | Moyenne | `state/lock.py` expose `lock()`/`unlock()` mais n’est jamais appelé dans `main_v5`. Aucune protection contre deux processus (ou deux boucles) qui enverraient des ordres en parallèle. |
| **Race lecture status.json** | Moyenne | `get_raw_status()` lit le fichier sans boucle de retry ni backoff. Si l’EA écrit au même instant (surtout avec Delete+Move dans d’autres EAs), lecture JSON peut échouer et retourner `{}` → cycle perdu. |
| **Gestion d’erreur trop large** | Moyenne | `except Exception` dans la boucle principale et dans `get_raw_status()` avale toute erreur et retourne `{}`. Risque de masquer des bugs (fichier manquant, permissions, encoding). |
| **SL en pips synthétiques** | Moyenne | Dans `main_v5`, `sl_pips = int(price * 0.00025 * (100 if "JPY" in asset else 10000))` pour des indices type "Volatility 100 Index" peut donner des valeurs inadaptées (pas de JPY). Formule fragile. |
| **Guard : PnL en valeur absolue** | Moyenne | `guard.py` utilise `day_pnl < -2.0` et `session_pnl < -3.0` en dollars fixes au lieu de % du capital. Non scalable selon la taille du compte. |
| **Pas de heartbeat / timeout EA** | Moyenne | Aucune détection côté Python si l’EA s’arrête ou ne met plus à jour les fichiers. Le bot continue d’envoyer des ordres dans le vide. |

---

## PHASE 2 : Audit de la Mécanique et du Flux de Données

### Logique d’exécution des ordres

1. **Boucle principale (`main_v5.run_bot`)**  
   - Toutes les `FAST_SCAN_INTERVAL` secondes (10 s) :  
     - Lecture `bridge.get_raw_status()` → `current_positions`.  
     - Différence avec `known_positions` pour détecter les clôtures → log + experience_logger + SaaS + Telegram/Discord.  
     - Mise à jour de `known_positions` (nouveaux tickets + `last_profit`).  
   - Analyse globale `brain.analyze_market_conditions()` → si `risk_level == "HIGH"`, sleep et continue.  
   - Pour chaque actif de `scan_list` : `brain.get_symbol_analysis(asset)` → trend (STRONG_UP/DOWN, WEAK_UP/DOWN) → signal BUY/SELL.  
   - Contrôle naïf : max 5 positions par actif (`open_count >= 5`).  
   - Envoi **fire-and-forget** : `bridge.send_tudor_trade(...)` (écrit un JSON dans `Command/`). Aucune attente de confirmation, aucun ticket retourné.

2. **Côté EA (Sentinel.mq5)**  
   - `OnTimer()` (1 s) : `Processing()` → `CheckRiskManagement()` puis, si `tradingEnabled`, `ScanForCommands()`, `ExportTickData()`, `ManageOpenPositions()`.  
   - `ScanForCommands()` : énumère `Command\*.json`, lit le fichier, parse `action`.  
     - `TUDOR_TRADE` → `ExecuteTudorTrade` (volume calculé par risque %, SL en pips, filtre AI confidence).  
     - `TRADE` → `ExecutePythonTrade` (volume et SL/TP explicites, plafonné à `MaxLotSize`).  
   - Fichier de commande **supprimé** après traitement. Pas d’accusé de réception vers Python (pas de "command_ack" ou ticket écrit côté Python).

3. **Data Feed**  
   - **Prix / signaux :** `MT5DataClient.get_candles(symbol)` lit `ticks_v3.json` (ou status selon implémentation) pour bid/ask/change.  
   - **Positions / équité :** censé provenir de `status.json`. Si l’EA ne l’écrit pas (cas du Sentinel.mq5 actuel), ce flux est **cassé**.

### Synchronisation entre composants

| Liaison | Mécanisme | Problème |
|---------|-----------|----------|
| Python → EA | Fichiers JSON dans `Command/` (write atomique) | OK. Pas de séquence number ni de TTL : vieux fichiers non consommés peuvent être rejoués après redémarrage EA. |
| EA → Python (positions) | `status.json` lu par `get_raw_status()` | **Manquant** dans le Sentinel.mq5 principal. À corriger ou utiliser un EA qui écrit le status (ex. Sentinel_v10_FIXED). |
| EA → Python (ticks) | `ticks_v3.json` (ExportTickData) | Présent. Race gérée dans `_read_broker_status` (decode error → None, retry au prochain cycle). |
| Python état métier | `known_positions` (RAM) + `bot_state.json` (active_trades) | `main_v5` ne met pas à jour `active_trades`; `known_positions` dépend entièrement de `status.json`. |

**Verdict :** Le flux « ordre envoyé → exécution MT5 → remontée positions/PnL → clôture détectée » est **incomplet** tant que `status.json` n’est pas émis par l’EA effectivement utilisé. La mécanique fichier est saine, mais la chaîne de données est rompue côté status.

---

## PHASE 3 : Audit du Risk Management (Sécurité)

### Sécurités en place

| Couche | Où | Ce qui est fait |
|--------|-----|------------------|
| **EA (MQL5)** | Sentinel.mq5 | MaxDailyLoss ($), High Water Mark, désactivation trading, CloseAllPositions sur dépassement. Volume plafonné (MaxLotSize), risque % borné 0.1–10%. |
| **Python (main_v5)** | Boucle | Uniquement : skip cycle si `risk_level == "HIGH"` (calendrier/sentiment). Max 5 positions par actif (comptage basé sur status). |
| **Python (non utilisé par main_v5)** | risk_manager.py | `RiskManager.check_health(initial_balance, current_balance)` → Kill Switch si drawdown ≥ max_dd. Jamais appelé. |
| **Python (non utilisé)** | guard.py + manager.py | MultiLevelKillSwitch (daily/session/cluster/cooldown) + TradingManager.validate_signal. Utilisé par un autre flux (manager), pas par main_v5. |
| **Python (non utilisé)** | state/risk | can_execute_trade (max trades, max daily loss) + register_trade. Compteurs jamais incrémentés dans V5. |
| **Bridge** | mt5_interface_v2 | Validation commande (action, type, volume), min trade value, volume min 0.50 pour certains symboles. |

### Drawdown, Stop Loss, Kill Switch, Marges

- **Drawdown :** Côté EA : drawdown en $ (MaxDailyLoss). Côté Python : aucun calcul de drawdown ni Kill Switch dans main_v5.  
- **Stop Loss :** Envoyé en pips dans `send_tudor_trade`; l’EA calcule le prix SL et l’applique. Formule SL dans main_v5 fragile pour non-Forex (voir Phase 1).  
- **Kill Switch :** Présent uniquement dans l’EA (dollars). Aucun Kill Switch côté Python (ni balance, ni %).  
- **Marges :** Pas de vérification marge/équité avant envoi d’ordre dans main_v5. L’EA s’appuie sur MT5 pour le rejet d’ordre.

### Black Swan (krach soudain)

- **EA :** Réagit une fois par seconde (timer). En cas de gap ou de chute très rapide, les SL peuvent être dépassés (slippage, requotes). Le plafond en $ (MaxDailyLoss) coupe le trading après seuil, mais pas “à la tick”.  
- **Python :** Pas de circuit breaker sur chute brutale de l’équité (pas de lecture temps réel de la balance dans la boucle de décision).  
- **Conclusion :** Le système **ne peut pas** être considéré comme protégé contre un black swan au sens “arrêt immédiat sur chute X% en 1 minute”. La couche EA limite les dégâts après coup (daily loss), pas en temps réel.

---

## PHASE 4 : Plan d’Amélioration Architecturale

Pour chaque point, format : Problème → Solution technique → Pourquoi → Impact concret.

---

### 1. status.json manquant dans l’EA utilisé

**Le Problème :** Le Sentinel.mq5 dans `bot/broker/mt5_bridge/` n’écrit pas `status.json`. Python suppose que positions et balance sont disponibles ; sans ce fichier, détection des clôtures et suivi PnL sont impossibles.

**La Solution Technique :** Ajouter dans Sentinel.mq5 une fonction `BroadcastStatus()` (comme dans Sentinel_v10_FIXED.mq5) et l’appeler dans `OnTimer()` après `Processing()` (et éventuellement dans `OnTick()` si vous voulez une mise à jour plus fréquente). Exemple de contenu :

```mql5
void BroadcastStatus() {
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   string json = "{\"updated\":" + IntegerToString(TimeCurrent()) +
                 ",\"balance\":" + DoubleToString(balance, 2) +
                 ",\"equity\":" + DoubleToString(equity, 2) +
                 ",\"trading_enabled\":" + (SystemState.tradingEnabled ? "true" : "false") +
                 ",\"positions\":[";
   // ... boucle PositionsTotal(), build JSON array ...
   json += "]}";
   int h = FileOpen("status.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h != INVALID_HANDLE) { FileWriteString(h, json); FileClose(h); }
}
```

**Le Pourquoi :** Python et EA doivent partager la même source de vérité pour les positions. Le protocole actuel (fichiers dans MQL5/Files) impose que l’EA émette explicitement cet état.

**L’Impact Concret :** Détection fiable des positions fermées, notifications Telegram/Discord, mise à jour de `known_positions` et du PnL pour experience_logger et SaaS.

---

### 2. Aucun risk management Python dans main_v5

**Le Problème :** main_v5 n’appelle ni RiskManager, ni MultiLevelKillSwitch, ni can_execute_trade. Tout le risque repose sur l’EA et sur un seul filtre (risk_level == "HIGH").

**La Solution Technique :** Avant d’envoyer un ordre dans main_v5 :

- Lire la balance/équité depuis `get_raw_status()` (ou un champ dédié).
- Appeler `RiskManager.check_health(balance_debut_journee, balance_actuelle)` et arrêter d’envoyer des ordres si retour False.
- Optionnel mais recommandé : appeler `can_execute_trade(trade)` (après avoir branché les compteurs, voir point 3) et ne pas envoyer si non autorisé.

Exemple d’intégration :

```python
# Au début du cycle, après get_raw_status()
balance = status.get("balance") or status.get("equity", 0)
if initial_balance and risk_manager.check_health(initial_balance, balance)[0] is False:
    logger.critical("Kill Switch: stopping orders"); await asyncio.sleep(FAST_SCAN_INTERVAL); continue
```

**Le Pourquoi :** Une couche de risque côté Python assure une double protection (EA + stratégie) et permet des règles en % du capital ou des plafonds de trades sans recompiler l’EA.

**L’Impact Concret :** Arrêt des ordres si drawdown journalier dépasse un seuil (ex. 10%), même si l’EA reste actif ; cohérence avec la philosophie “sécurité du capital”.

---

### 3. Compteurs risk (trades/jour, PnL journalier) jamais mis à jour

**Le Problème :** `state/risk/limits.py` garde `_TRADES_TODAY` et `_DAILY_PNL` en mémoire mais `increment_trades()` et `add_pnl()` ne sont jamais appelés par main_v5. `register_trade()` (state/risk/rules/engine.py) n’est pas utilisé.

**La Solution Technique :**  
- Lors de la **détection d’une clôture** (dans la boucle où vous faites `closed_tickets`), après avoir récupéré le PnL final : appeler `register_trade({"pnl": final_profit})`.  
- Au **démarrage** (ou à minuit UTC), appeler `reset_daily_limits()` (à ajouter si besoin en tâche planifiée ou au premier cycle après changement de jour).  
- Avant d’**envoyer un ordre**, appeler `can_execute_trade(trade)` et ne pas envoyer si `allowed` est False.

**Le Pourquoi :** Les règles `check_max_trades` et `check_max_loss` ne sont valides que si les compteurs reflètent la réalité. Sans mise à jour à la clôture, les limites sont inopérantes.

**L’Impact Concret :** Limite effective du nombre de trades par jour et de la perte journalière côté Python (ex. 1 trade/jour, -100$ max), en complément de l’EA.

---

### 4. Double source de vérité pour les positions (known_positions vs active_trades)

**Le Problème :** main_v5 suit les positions dans `known_positions` (issu de status.json) mais n’enregistre pas les nouveaux ordres dans `active_trades`. DerivBroker le fait uniquement quand on passe par lui. Donc bot_state.json et la logique “active_trades” sont désynchronisés.

**La Solution Technique :**  
- Lors de l’envoi d’un ordre dans main_v5 (après `send_tudor_trade`), ajouter un enregistrement “en attente” soit dans `active_trades` avec un id temporaire (ex. `pending_<timestamp>_<uuid>`), soit dans une structure dédiée “pending_orders”.  
- Lors de la mise à jour de `known_positions` à partir de `status.json`, faire la correspondance (par symbole + side + temps ouvert) pour mettre à jour ou fermer l’entrée dans `active_trades` et appeler `register_trade` avec le PnL.  
- À défaut de ticket retourné par l’EA, utiliser une clé (symbol, side, open_time) pour matcher.

**Le Pourquoi :** Une seule source de vérité (idéalement status.json + réconciliation avec active_trades) évite les doublons, les “fantômes” et permet d’alimenter correctement risk (register_trade) et reporting.

**L’Impact Concret :** État cohérent entre EA, Python et bot_state.json ; possibilité de limites par trade actif et d’audit fiable.

---

### 5. Lock global non utilisé (exécutions parallèles)

**Le Problème :** `state/lock.py` n’est pas utilisé. Un second lancement de main_v5 (ou un script externe) pourrait envoyer des ordres en parallèle.

**La Solution Technique :** Utiliser un fichier lock (ex. `sentinel_v5.lock`) avec PID et timestamp, créé au démarrage de `run_bot()` et supprimé dans un `finally`. Avant de créer le lock, vérifier si le fichier existe et si le PID est encore actif (sinon considérer le lock orphelin et le supprimer). En alternative, utiliser `fcntl.flock` sur un fichier dédié (Unix). Ne pas se contenter d’un booléen en mémoire (inefficace pour plusieurs processus).

**Le Pourquoi :** En production, un seul “pilot” doit envoyer des ordres. Un lock fichier/PID garantit l’exclusivité entre processus.

**L’Impact Concret :** Évite les doublons d’ordres et les états incohérents en cas de double démarrage ou de scripts concurrents.

---

### 6. Race lecture status.json et gestion d’erreur

**Le Problème :** Une lecture de `status.json` pendant l’écriture par l’EA peut donner un JSON invalide ; `get_raw_status()` retourne `{}` et masque l’erreur.

**La Solution Technique :**  
- Lire dans une boucle avec retry (ex. 3 tentatives, 50–100 ms entre chaque). En cas de `JSONDecodeError`, réessayer au lieu de retourner immédiatement `{}`.  
- Logger en WARNING uniquement après échec de toutes les tentatives.  
- Optionnel : l’EA écrit dans un fichier temporaire puis rename (comme pour les commandes Python), pour réduire la fenêtre de race.

**Le Pourquoi :** Sur des filesystems partagés (Wine, réseau), la lecture pendant l’écriture est fréquente. Un retry simple améliore la robustesse sans changer le protocole.

**L’Impact Concret :** Moins de cycles “vides” (positions vues à 0 à tort), moins de fausses détections de clôture et logs plus explicites en cas de problème durable.

---

### 7. Heartbeat / timeout EA

**Le Problème :** Si l’EA ou MT5 s’arrête, Python continue d’envoyer des commandes dans un dossier que personne ne lit. Aucune alerte.

**La Solution Technique :**  
- Vérifier que `status.json` (ou `ticks_v3.json`) a été modifié dans les N dernières secondes (ex. 60 s). Utiliser `os.path.getmtime(status_file)`.  
- Si timeout : logger CRITICAL, envoyer une alerte Telegram/Discord “EA heartbeat lost”, et soit arrêter l’envoi d’ordres (mode safe), soit continuer en loguant (selon politique).

**Le Pourquoi :** En production, une panne silencieuse de l’EA ne doit pas laisser croire que le système trade normalement.

**L’Impact Concret :** Détection rapide d’un EA arrêté ou MT5 déconnecté, réduction du risque d’accumulation de commandes non traitées et alerte opérationnelle.

---

### 8. Kill Switch côté Python en % du capital

**Le Problème :** Aujourd’hui, le Kill Switch effectif est côté EA en dollars. Côté Python, MultiLevelKillSwitch utilise des seuils en $ (-2, -3) non adaptables à la taille du compte.

**La Solution Technique :**  
- Dans main_v5 (ou dans un module risk unique), maintenir `balance_start_of_day` (mis à jour à minuit ou au premier cycle du jour).  
- Calculer `daily_drawdown_pct = (balance_start_of_day - current_balance) / balance_start_of_day`.  
- Si `daily_drawdown_pct >= MAX_DAILY_DD_PCT` (ex. 0.05 pour 5%), ne plus envoyer d’ordres, logger CRITICAL, notifier, et optionnellement envoyer une commande `CLOSE_ALL` ou `RESET_RISK` à l’EA (selon politique).

**Le Pourquoi :** Un drawdown en % est scalable (petit et gros comptes) et aligné avec les bonnes pratiques de gestion du risque.

**L’Impact Concret :** Protection du capital proportionnée à la taille du compte et cohérence avec un objectif “sécurité absolue du capital”.

---

### 9. Formule Stop Loss pour indices synthétiques

**Le Problème :** `sl_pips = int(price * 0.00025 * (100 if "JPY" in asset else 10000))` est pensé pour le Forex. Pour "Volatility 100 Index" (prix ~1000), cela donne un nombre de pips énorme et potentiellement incohérent avec le point du symbole.

**La Solution Technique :**  
- Pour les symboles contenant "Volatility" ou "Index", utiliser une logique dédiée : soit un pourcentage du prix (ex. SL à 0.1% ou 0.25%), soit un nombre de points fixe/paramétrable (ex. 50 points).  
- Exemple : `sl_distance_pct = 0.002` → `sl_price = price * (1 - sl_distance_pct)` (BUY) ou `price * (1 + sl_distance_pct)` (SELL), et envoyer à l’EA soit le prix SL, soit des pips convertis selon `SymbolInfoDouble(symbol, SYMBOL_POINT)` côté EA.

**Le Pourquoi :** Les indices synthétiques n’ont pas de “pip” Forex ; une règle en % ou en points du symbole évite des SL trop serrés ou trop larges.

**L’Impact Concret :** Stop Loss cohérents pour Volatility 100/75, moins de rejets ou de risques disproportionnés.

---

### 10. Utilisation de ProductionSecurityManager pour les commandes

**Le Problème :** La validation des commandes (volume, direction) existe dans ProductionSecurityManager mais n’est pas utilisée par le bridge avant d’écrire le fichier de commande.

**La Solution Technique :** Avant d’écrire la commande dans `send_order` ou `send_tudor_trade`, construire un dict au format attendu par `validate_trade_command` (ex. symbol, direction = type, volume) et appeler `ProductionSecurityManager().validate_trade_command(cmd)`. En cas de refus, ne pas écrire le fichier et logger un avertissement sécurité.

**Le Pourquoi :** Centraliser la validation (volume max 10, direction autorisée) évite qu’une couche en amont envoie une commande anormale au bridge.

**L’Impact Concret :** Rejet des commandes hors plage (ex. volume > 10) avant même d’atteindre l’EA, et traçabilité audit.

---

## Synthèse des priorités

| Priorité | Action | Impact |
|----------|--------|--------|
| P0 | Ajouter BroadcastStatus() dans Sentinel.mq5 (ou utiliser un EA qui l’écrit) | Rétablit le flux positions/balance. |
| P0 | Introduire RiskManager.check_health + Kill Switch % dans main_v5 | Sécurité du capital côté Python. |
| P1 | Alimenter register_trade à la clôture + can_execute_trade avant ordre | Limites trades/jour et perte/jour effectives. |
| P1 | Unifier suivi positions (known_positions + active_trades + status.json) | Cohérence d’état et reporting. |
| P2 | Lock fichier/PID au démarrage | Évite double exécution. |
| P2 | Retry + log sur lecture status.json | Robustesse et diagnostic. |
| P2 | Heartbeat status.json / ticks | Détection EA arrêté. |
| P3 | SL en % pour synthétiques + validation ProductionSecurityManager | Précision risque et sécurité des commandes. |

---

*Document généré dans le cadre d’un audit technique à vocation production et protection du capital. Recommandation : traiter les points P0 avant toute mise en production réelle.*
