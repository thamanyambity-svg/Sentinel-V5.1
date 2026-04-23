# CHANGELOG — Aladdin Pro V7 / Sentinel

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
- ✅ Add missing prototypes (AnalyseEndOfDay_V7, ExecuteOvernightHedge_V7, ApplyManualProtection_V7)
- ✅ Désactiver BE pour GOLD (BE_TriggerUSD ajusté + trailing tight)
- ✅ Améliorer ApplyTrailingStop_V7() (fallback ATR, logs GOLD-TIGHT)
