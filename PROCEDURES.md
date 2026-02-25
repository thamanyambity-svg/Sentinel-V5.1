# Procédures d'Urgence et Opérations

Ce document détaille les procédures standard pour assurer la continuité de service du bot Sentinel V5.2.

## 🚨 1. Redémarrage d'Urgence
Si le bot ne répond plus ou se comporte de manière erratique :
```bash
python3 smart_restart.py
```
*Ce script vérifie si le bot tourne, l'arrête proprement si nécessaire, et le relance.*

## 🛑 2. Arrêt Complet
Pour stopper toute activité de trading et éteindre le processus :
```bash
./stop_bot.sh
# OU
python3 -c "from smart_restart import BotManager; BotManager().stop_bot()"
```

## 🏥 3. Vérification de Santé (Health Check)
Pour obtenir un diagnostic rapide de l'état du système :
```bash
python3 monitor_dashboard.py
```
*Affiche l'utilisation CPU/RAM, l'uptime et le statut du processus.*

Pour un diagnostic approfondi (connexions, broker, compte) :
```bash
python3 health_check.py
```

## 📂 4. Logs et Debugging
Les logs sont situés dans `~/bot/logs/`.
- **Bot Principal** : `tail -f ~/bot/logs/bot.log`
- **Opérations/Restart** : `tail -f monitor_restarts.log`
- **Erreurs** : `bot_error.log`

## 🛠️ 5. Maintenance
- **Sauvegarde** : Le code est sur GitHub. L'état des trades est dans `bot_state.json` (sauvegarde atomique).
- **Mise à jour** : Faire un `git pull`, puis redémarrer avec `smart_restart.py`.
