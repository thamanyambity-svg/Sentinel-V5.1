# Parcours décision : quand le bot ouvre une position

Ce doc décrit **dans l’ordre** toutes les étapes qui mènent (ou bloquent) l’ouverture d’un trade.

---

## 1. Données et régime (par actif)

- **Bougies** : 100 chandeliers 1m via Deriv.
- **Indicateurs** : RSI, EMA20, ATR(14), ADX.
- **Régime** : `RegimeClassifier` → `RANGE_CALM`, `TREND_STABLE`, `CHAOS`, etc.
- **Contexte** : `context = { asset, price, indicators: { rsi, ema20 }, balance, atr }`.

---

## 2. Stratégies qui produisent un signal

Deux stratégies tournent en parallèle :

| Stratégie | Fichier | Condition signal | Type |
|-----------|---------|-------------------|------|
| **RSI** | `bot/strategy/rsi.py` | RSI < 35 → BUY ; RSI > 65 → SELL | `MEAN_REVERSION` |
| **Trend** | `bot/strategy/trend_following.py` | Prix > EMA20 → BUY ; Prix < EMA20 → SELL | `TREND_FOLLOWING` |

- Si une stratégie ne renvoie rien → pas de signal pour elle.
- Chaque signal a un **type** utilisé plus bas par les gates (régime, filtres).

---

## 3. Analyse IA (Market Structure + biais)

- **Market Structure** (LLM) : signal WAIT/BUY/SELL, trend, raison.
- **Market Intelligence** (stub) : trend / change_percent (optionnel).
- **Biais IA** : écrit dans le bridge MT5 (`ai_bias.json`) pour l’EA.
- Ces infos alimentent `ai_confirmation` et l’affichage ; elles **ne remplacent pas** les gates ci‑dessous.

---

## 4. Governance (TradingManager) – ordre des gates

Si **ENABLE_GOVERNANCE = True** (`bot/main.py` ~L171), chaque signal passe par `manager.validate_signal()` dans cet ordre :

| # | Gate | Fichier | Condition pour passer |
|---|------|---------|------------------------|
| 0 | **AI Supervision** | `bot/ai_agents/orchestrator.py` | `UnifiedGovernanceAgent` → vote APPROVED (sinon veto). Timeout 15s → fallback technique = approved. |
| 1 | **Régime CHAOS** | `bot/core/manager.py` | `current_regime != "CHAOS"`. |
| 2 | **Kill-Switch** | `bot/risk/guard.py` | Pas de HARD STOP (DD global < 9.5%), pas daily/session halt, pas cluster (3 pertes de suite même régime), pas cooldown 12h après 4 SL. |
| 3 | **Régime vs type** | `bot/core/manager.py` | **MEAN_REVERSION** → régime = `RANGE_CALM`. **TREND_FOLLOWING** → régime = `TREND_STABLE`. Sinon refus (ex. “Trend Rejection: Need TREND_STABLE”). |
| 4 | **Filtres avancés** | `bot/risk/advanced_filters.py` | RSI Gate (niveaux extrêmes), fréquence, cooldown après rejet, fatigue (false breakouts). |
| 5 | **Sizing** | `bot/risk/sizer.py` | Taille calculée > 0 (équité + ATR). |

Tout refus → log du motif, **pas d’exécution**.

---

## 5. Filtres dans main.py (après Governance)

Même si le signal est approuvé par le manager, il doit encore passer :

| Filtre | Condition |
|--------|-----------|
| **Score / confiance** | `score >= MIN_QUALITY_SCORE` (40) **et** `ai_conf >= MIN_AI_CONFIDENCE` (0.40). Sinon refus sauf `is_force_enabled()`. |
| **Circuit breaker** | `governor.can_trade()` (limite de perte / seuil). |
| **Single shot** | Au plus **1** position ouverte (bridge MT5) ; sinon attente. |
| **ADX** | ADX >= 15 (marché pas “endormi”). |
| **Anti-sleep** | Range moyen des 5 dernières bougies >= 0.05 (volatilité min). |
| **Balance** | Balance >= 1.00 USD. |
| **Project 100** | Nombre de trades du jour < 15 (`MAX_PROJECT_TRADES`). |
| **Kill switch V3** | PnL réel Sentinel > `governor.max_loss` (pas dépassement de la perte max). |

---

## 6. Exécution

- Stake forcé 0.50 USD (dans ce flow).
- Appel au **broker** (Deriv + bridge MT5 si actif) pour ouvrir la position.

---

## Résumé : conditions pour une “bonne” position (ce que le code impose)

1. **Régime cohérent** : RSI (mean reversion) uniquement en **RANGE_CALM** ; Trend uniquement en **TREND_STABLE**.
2. **Pas de CHAOS**, pas de kill-switch (daily/session/cluster/cooldown).
3. **IA** : Unified Governance approuve (ou timeout → fallback approuvé).
4. **Filtres avancés** : RSI extrême, fréquence, cooldown, fatigue OK.
5. **Score ≥ 40**, **confiance IA ≥ 0.40**.
6. **Une seule position** ouverte, **ADX ≥ 15**, marché pas “sleeping”, balance ≥ 1$, moins de 15 trades/jour, pas de dépassement du plafond de perte.

---

## Où modifier pour être plus (ou moins) sélectif

| Objectif | Fichier / variable | À modifier |
|----------|--------------------|------------|
| Moins de trades (plus sélectif) | `bot/main.py` | Augmenter `MIN_QUALITY_SCORE` (ex. 55–60), `MIN_AI_CONFIDENCE` (ex. 0.50–0.60). |
| Accepter plus de signaux | `bot/main.py` | Baisser ces seuils (attention au risque). |
| RSI plus extrême seulement | `bot/risk/advanced_filters.py` | RSIExtremeGate : seuils BUY/SELL (ex. 28/72). |
| Fréquence max par actif | `bot/risk/advanced_filters.py` | TradeFrequencyGovernor. |
| Régime plus strict | `bot/risk/regime.py` ou classifieur | Seuils / logique de `RANGE_CALM` vs `TREND_STABLE`. |
| Désactiver la gouvernance IA | `bot/main.py` | `ENABLE_GOVERNANCE = False` (tout signal technique approuvé par le manager passe, sauf les autres filtres). |

---

*Généré pour parcours décision – bot_project.*
