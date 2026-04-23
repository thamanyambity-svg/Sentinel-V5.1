# CHANGELOG — Aladdin Pro V7 / Sentinel

## 2026-04-23 — EA V7.22 Overnight Hedge GOLD

### Added
- **`ExecuteOvernightHedge_V7()`** : stratégie Overnight complète (remplace les stubs vides de V7.26).
  - Déclenche à **20h55 broker GMT+0** (configurable via `EOD_Hour` / `EOD_Minute`), fenêtre 4 min.
  - Direction automatique via EMA_fast vs EMA_slow sur **H1 GOLD** (handles dédiés `eod_handle_ema_fast_h1` / `eod_handle_ema_slow_h1`).
  - **3 DOMINANTS** dans le sens EMA : lot 0.01, SL=1.5×ATR, TP=4×ATR.
  - **2 HEDGES** sens opposé : lot 0.01, SL=0.3×ATR, TP=0.5×ATR.
  - **Magic distinct** = `MagicNumber + EOD_MagicOffset` (isolation : non touché par BE/Trailing/Cooldown).
  - Pop-up MT5 (`Alert`) à l'exécution si `EOD_Alert_Popup`.
  - Reset automatique du flag `eod_hedge_triggered_today` dans `CheckDailyReset_V7()`.
  - Libération des handles H1 dans `OnDeinit`.
- 14 nouveaux inputs groupés `=== OVERNIGHT HEDGE GOLD (V7.22) ===`.
- Helper `GetGoldSymbolIdx()` (résolution XAUUSD/GOLD/XAUUSDm).

### Notes
- Symbole **GOLD uniquement**. Les autres instruments ne sont pas concernés.
- Filtre horaire `Enable_Gold_TimeFilter` (V7.13) : 20h55 ∈ [07h, 23h] → pas de conflit.
- `ApplyBreakEven_V7` et `ApplyTrailingStop_V7` matchent uniquement `MagicNumber` ou 0 → les hedges (magic +100) sont préservés.

---

## 2026-04-23 — Housekeeping & EA V7.21

### Added
- `ApplyManualProtection_V7()` : ajoute SL/TP automatique aux trades manuels non protégés (magic=0), basé ATR.
- `ApplyBreakEven_V7()` accepte désormais les positions manuelles (magic=0) en plus du magic EA.
- Trailing stop GOLD-TIGHT (V7.20) : activation `min(ATR*0.10, 2.00)`, step `min(ATR*0.07, 1.50)` pour XAUUSD/GOLD.
- `ExportStatus_V7()` : expose `trading` basé sur TerminalInfo+MQL+Account (état réel), et `strategy_paused`.
- `BE_TriggerUSD` ajusté de 1.50 → 0.50 USD pour scalp GOLD.

### Archived (backups_archive/old_ea_versions_2026-04-23/)
- Sentinel.mq5, Sentinel_EA_FINAL.mq5, Sentinel_V6_SNIPER.mq5, Sentinel_V10_COMBAT.mq5
- Sentinel_v5_2_ULTIMATE.mq5, AonosSentinel_Full.mq5, AonosSentinel_V11_XM.mq5
- Aladdin_Pro_V7_16_Live.mq5, Aladdin_Pro_V7_19_Live.mq5, Aladdin_Pro_V7_19_Live_COMPILABLE.mq5
- Aladdin_Pro_V7_26_Live.mq5, AladdinPro_V719_TrapHunter.mq5
- logging_module.mq5

### Docs
- Fusion de `TODO.md` + `TODO_DASHBOARD.md` + `TODO_TRAILING_FIX.md` → `TODO.md` unique.
- Items complétés déplacés dans ce CHANGELOG.

### Completed (from previous TODOs)
- ✅ Verify/create SuperTrend_Filter.mqh & PythonBridge_Ratchet.mqh
- ✅ Merge mobile orders + fixes from COMPILABLE into Live.mq5
- ✅ Add ApplyManualProtection_V7 prototype + implementation
- ✅ Désactiver BE pour GOLD (BE_TriggerUSD ajusté + trailing tight)
- ✅ Améliorer ApplyTrailingStop_V7() (fallback ATR, logs GOLD-TIGHT)

> ExecuteOvernightHedge_V7 implémenté plus tard en V7.22 (stub V7.26 remplacé par logique réelle).
