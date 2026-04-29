# 🚀 TODO - Notifications Trading Hours EXACTES (Plan Approuvé)

**Statut global:** ⏳ En cours  
**Objectif:** Notifications à l'HEURE EXACTE (pas ±5min)

## 📋 Étapes du Plan (à cocher)

### 1. **trading_hours_monitor.py** [4/4] ✅
- [x] Ajouter `calculate_events()` → tous open/close 24h+ 
- [x] Implémenter `run_continuous_scheduler()` → sleep précis
- [x] Supprimer polling `check_all_markets()` + `last_states`
- [x] Ajouter logs attente: "Waiting XhYm until EURUSD open"

### 2. **config_trading_hours.json** [1/1] ✅
- [x] Supprimer `"check_interval_minutes": 5`

### 3. **setup_cron_hours.sh** [2/2] ✅
- [x] Changer cron: `*/5` → `0 0 * * *` (minuit quotidien)
- [x] Logs: `trading_hours.log` + messages exact

### 4. **Tests & Validation** [0/3]
- [ ] Test local: `python3 trading_hours_monitor.py`
- [ ] Vérifier sleep précis jusqu'au prochain event  
- [ ] Deploy: `./setup_cron_hours.sh` + `crontab -l`

### 5. **Production** [0/2]
- [ ] Monitor logs + Discord notifs exactes
- [ ] Mettre à jour TODO_TRADING_HOURS.md → ✅ EXACT

---

**Commandes utiles:**
```bash
tail -f trading_hours_monitor.log  # Si log ajouté
crontab -l                         # Vérifier cron
python3 trading_hours_monitor.py   # Test manuel
```

**Critère succès:** Notifs Discord pile à 08:00:00, 13:00:00, 17:00:00...
