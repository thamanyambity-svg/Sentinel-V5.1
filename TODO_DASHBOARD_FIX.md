# 🚀 Dashboard Performance Optimization [IN PROGRESS]

**Objectif:** Réduire temps de rafraîchissement de 5s → <2s avec cache

## ✅ Étapes Planifiées [0/5]

- [ ] **1. Créer TODO.md** ← EN COURS
- [ ] **2. Ajouter cache simple** dans dashboard.py (dict TTL 8s)
- [ ] **3. Limiter CSV reads** (max 10 lignes)
- [ ] **4. Augmenter intervalle** défaut à 10s 
- [ ] **5. Ajouter métriques perf** + test
- [ ] **6. Test & validation** (`time python dashboard.py --once`)

**Temps estimé:** 3-5 min par étape
**Critères succès:** Rafraîchissement <2s (vs 5s+ actuel)

**Fichiers impactés:**
- `dashboard.py` (principal)
- `dashboard_manager.py` (cache logic)
