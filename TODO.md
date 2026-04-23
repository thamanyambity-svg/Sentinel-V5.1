# Aladdin Pro V7 — TODO (Unified)

> Fichier unique consolidé depuis TODO.md + TODO_DASHBOARD.md + TODO_TRAILING_FIX.md (2026-04-23).
> Items complétés → voir `CHANGELOG.md`.

---

## 1. EA Deployment (V7.x Live)

- [ ] Compiler `Aladdin_Pro_V7_Live_DEPLOYED.mq5` (V7.22)
- [ ] Tester OnInit/OnTimer
- [ ] **Valider Overnight Hedge (V7.22)** : vérifier pop-up + 5 ordres à 20h55 GMT+0, magic = MagicNumber+100
- [ ] GOLD backtest Deriv
- [ ] Deploy LIVE et vérifier status.json

## 2. Trailing Stop / Break-Even

- [ ] Monitor logs/status.json après patch GOLD-TIGHT
- [ ] Ouvrir position OR de validation
- [ ] Vérifier trailing suit à ~1.50 pts
- [ ] Test gap protection

## 3. Dashboard (Gold Predator V7)

- [ ] Mobile-first responsivity (stack <640px, hamburger sidebar)
- [ ] Gold Predator theme (canvas particles BG, 3D tilt cards)
- [ ] Dark/light toggle + PWA (manifest, SW)

## 4. Bridge & Data

- [ ] Update `ai_bridge.py` pour nouveaux JSON (account_stats.json, macro_bias.json)
