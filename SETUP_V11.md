# SENTINEL V11 — Mise à Jour Complète de l'Interface de Trading

## 📋 Vue d'ensemble

Nous avons modernisé et refactorisé complètement votre plateforme de trading avec les améliorations suivantes:

### ✨ Nouveautés Majeures

1. **Architecture OOP** — `dashboard_manager.py`
   - Gestionnaire centralisé avec caching intelligent
   - Système de plugins extensible
   - Gestion d'erreurs robuste

2. **API REST moderne** — `api_server.py`
   - 7 endpoints JSON pour accès données en temps réel
   - Support CORS pour intégrations multi-domaines
   - Health checks et monitoring

3. **Configuration centralisée** — `config_sentinel.py`
   - Un seul fichier pour toutes les configurations
   - Thresholds tradables
   - Intégrations Discord/Telegram/Email

4. **Améliorations de Performance**
   - Cache multi-niveaux (5-10s)
   - Lectures fichiers optimisées
   - Validations de données strictes

5. **Sécurité Renforcée**
   - Validation de tous les inputs
   - Logging structuré
   - Gestion d'erreurs complète

---

## 🚀 Démarrage Rapide

### 1. Installation des Dépendances

```bash
\# Naviguer au dossier du projet
cd /Users/macbookpro/Downloads/bot_project

\# Activer l'environnement virtuel
source .venv/bin/activate

\# Installer les packages supplémentaires
pip install flask flask-cors
```

### 2. Lancer le Serveur API

```bash
\# Terminal 1 — Serveur API REST
python api_server.py

\# La sortie devrait montrer:
# ════════════════════════════════════════════════════════════════════
#  SENTINEL V11 - REST API SERVER 
# ════════════════════════════════════════════════════════════════════
# ✓ Starting Flask API on http://localhost:5000
```

### 3. Tester les Endpoints API

```bash
\# Dans une autre console, testez les endpoints:

\# ✓ Health check
curl http://localhost:5000/api/v1/health

\# ✓ Données du compte
curl http://localhost:5000/api/v1/account

\# ✓ Positions ouvertes
curl http://localhost:5000/api/v1/positions

\# ✓ Prix en temps réel
curl http://localhost:5000/api/v1/ticks

\# ✓ Signaux ML
curl http://localhost:5000/api/v1/ml

\# ✓ Résultats backtest
curl http://localhost:5000/api/v1/backtest

\# ✓ État complet du dashboard
curl http://localhost:5000/api/v1/dashboard
```

### 4. Accéder au Dashboard Web

Ouvrez votre navigateur à:
```
http://localhost:5000/
```

---

## 📊 Architecture Technique

### Frontend (dashboard.html)
```
┌─────────────────────────────────────────┐
│          HTML5 + TailwindCSS            │
│   (Responsive Design, Dark Theme)       │
├─────────────────────────────────────────┤
│  JavaScript (Fetch API + WebSocket)     │
│   (Live updates, Real-time charts)      │
└─────┬───────────────────────────────┬───┘
      │                               │
      │ REST API (JSON)               │ WebSocket
      │                               │ (Live)
  ┌───▼───────────────────────────────▼───┐
  │      Flask API Server (5000)           │
  │    (api_server.py + handler)           │
  └───┬───────────────────────────────┬───┘
      │                               │
      │                               │
  ┌───▼───────────────────────────────▼───┐
  │    Dashboard Manager (Core Logic)     │
  │  (dashboard_manager.py - OOP)         │
  │  • Cache System                       │
  │  • Data Loaders                       │
  │  • Validation                         │
  └───┬───────────────────────────────────┘
      │
  ┌───▼────────────────────────────────────┐
  │        Data Sources (JSON/CSV)         │
  │   status.json, ticks_v3.json, etc      │
  │   (From MT5 + Bot)                     │
  └────────────────────────────────────────┘
```

### Composants Python

#### `dashboard_manager.py`
- **CacheManager** — Caching multi-niveaux avec TTL
- **DataLoader** — Interface abstraite pour chargeurs
- **JSONFileLoader** — Charge JSON avec validation
- **CSVFileLoader** — Charge CSV optimisé
- **DashboardManager** — Orchestrateur principal

#### `api_server.py`
- **Endpoints REST** — 7 routes pour accès données
- **Décorateurs** — `@json_response`, `@cache_response`
- **Formatters** — Formate les données pour le frontend
- **Error Handlers** — Gestion 404/500

#### `config_sentinel.py`
- **DASHBOARD_CONFIG** — UI/UX settings
- **API_CONFIG** — Server configuration
- **DATA_FILES** — Chemins centralisés
- **TRADING_THRESHOLDS** — Alertes tradables
- **INTEGRATIONS** — Discord, Telegram, Email

---

## 📡 Endpoints API Disponibles

### GET /api/v1/health
**Santé du système**
```json
{
  "status": "healthy",
  "version": "v1.1.0",
  "uptime": 1234567890.123,
  "manager_metrics": {
    "renders": 50,
    "refreshes": 10,
    "errors": 0
  }
}
```

### GET /api/v1/account
**Données du compte MT5**
```json
{
  "balance": 50000.00,
  "equity": 48500.00,
  "drawdown": 3.0,
  "pnl_open": -1500.00,
  "positions_count": 3,
  "trading_enabled": true,
  "last_sync": 1234567890
}
```

### GET /api/v1/positions
**Positions ouvertes détaillées**
```json
[
  {
    "symbol": "EURUSD",
    "type": "BUY",
    "volume": 1.5,
    "entry_price": 1.0950,
    "pnl": 150.00,
    "pnl_percent": 2.5
  }
]
```

### GET /api/v1/ticks
**Prix en temps réel**
```json
{
  "EURUSD": 1.0952,
  "GBPUSD": 1.2650,
  "XAUUSD": 2050.50
}
```

### GET /api/v1/ml
**Signaux ML et training**
```json
{
  "sovereign": {
    "decision": "BUY",
    "asset": "EURUSD",
    "kelly_risk": 2.5,
    "nexus_prob": 0.75,
    "spm_score": 0.82
  },
  "training": {
    "sessions": 45,
    "last_auc": 0.72,
    "last_win_rate": 0.58
  }
}
```

### GET /api/v1/backtest
**Résultats backtest**
```json
{
  "profit_factor": 1.45,
  "win_rate": 0.55,
  "max_drawdown_pct": 15.2,
  "sharpe": 1.2,
  "trades_count": 250,
  "status": "GOOD"
}
```

### POST /api/v1/refresh
**Force le rafraîchissement de toutes les données**
```json
{
  "message": "Dashboard refreshed successfully"
}
```

---

## ⚙️ Configuration

### Fichier: `config_sentinel.py`

Modifiez cette section pour adapter à votre système:

```python
\# Chemins
BASE_DIR = Path(__file__).parent
MT5_DIR = Path("/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5...")

\# Dashboard
DASHBOARD_CONFIG = {
    "display": {
        "width": 72,
        "refresh_interval": 5,  # en secondes
        "theme": "dark"
    }
}

\# API
API_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": True,
    }
}
```

---

## 🔄 Cache Strategy

Le système utilise un **cache multi-niveaux** pour optimiser les performances:

| Component | TTL | Exemple |
|-----------|-----|---------|
| Account | 3s | Balance, Equity |
| Positions | 2s | Trades ouverts |
| Ticks | 2s | Prix actuels |
| ML | 5s | Signaux |
| Backtest | 10s | Résultats |
| Health | 1s | Status |

**Astuce**: Augmentez le TTL pour réduire les lectures disque si vous avez beaucoup de positions.

---

## 🛡️ Sécurité

### Validations Implémentées
✓ Validation JSON structure
✓ Vérification fichiers existence
✓ Encoding UTF-8 strict
✓ Handle des nombres float proprement
✓ Error handling complet

### À Améliorer en Production
- Activer les API Keys (dans `config_sentinel.py`)
- Restreindre les CORS origins
- Ajouter rate limiting
- Passer en HTTPS
- Logs audit complets

---

## 📈 Monitoring & Metrics

Accédez aux metrics du système:

```bash
curl http://localhost:5000/api/v1/health | jq '.manager_metrics'
```

Affiche:
- `renders` — Nombre de rendus complets
- `refreshes` — Nombre de rafraîchissements
- `errors` — Nombre d'erreurs
- `cache` — État du cache système

---

## 🚨 Debugging

### Activer Logs Debug
```python
\# Dans api_server.py
logging.basicConfig(level=logging.DEBUG)
```

### Tester un Endpoint Spécifique
```bash
curl -v http://localhost:5000/api/v1/account
```

### Vérifier le Cache
```bash
curl http://localhost:5000/api/v1/health | jq '.manager_metrics.cache'
```

---

## 📝 Prochaines Étapes

### Phase 2 (à faire)
1. ✓ Refactoriser Python backend — **DONE**
2. ✓ Créer API REST — **DONE**
3. ✓ Centraliser config — **DONE**
4. ⏳ **Moderniser dashboard.html avec WebSocket live**
5. ⏳ **Ajouter charts interactifs (Chart.js)**
6. ⏳ **Système d'alertes (notifications desktop)**
7. ⏳ **Export données (CSV/PDF)**

### Phase 3
- Tests unitaires complets
- Monitoring Datadog/Prometheus
- CI/CD pipeline
- Documentation API Swagger

---

## 📞 Support

Pour questions ou problèmes:
1. Vérifiez logs: `grep "ERROR" bot.log`
2. Testez API health: `curl http://localhost:5000/api/v1/health`
3. Vérifiez fichiers existant: `ls -la status.json ticks_v3.json`

---

## 📄 License

SENTINEL V11 — Institutional Trading Platform
© 2026 - Proprietary
