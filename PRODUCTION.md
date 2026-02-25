# PRODUCTION DEPLOYMENT GUIDE

## 📋 Prérequis
- **Docker** & **Docker Compose** installed (v20.10+ recommended)
- **Git** installed
- Server with **4GB RAM** minimum
- Domain with SSL (optional but recommended for Admin API)

## ⚙️ Configuration
1. **Environment Variables**:
   Copy `.env.example` to `.env.prod` and populate secrets:
   ```bash
   cp .env.example .env.prod
   nano .env.prod
   ```
   *Required variables:*
   - `PROD_POSTGRES_PASSWORD`
   - `PROD_REDIS_PASSWORD`
   - `ENCRYPTION_KEY`
   - `WHITELIST_IPS` (comma separated)

2. **Network**:
   Ensure ports `8080` (Admin API) and `8000` (Metrics) are accessible or proxied via Nginx.

## 🚀 Déploiement (Blue-Green)
Use the included script for zero-downtime updates:
```bash
./deploy.sh
```

## 📊 Monitoring
- **Admin API**: `http://<your-server>:8080/docs`
- **Prometheus Metrics**: `http://<your-server>:8000`
- **Health Check**:
  ```bash
  docker inspect --format='{{json .State.Health}}' sentinel-bot-prod
  ```
- **Logs**:
  ```bash
  docker-compose -f docker-compose.prod.yml logs -f sentinel-bot
  ```

## 🚨 Procédures d'Urgence

### 🛑 Arrêt Complet
```bash
docker-compose -f docker-compose.prod.yml down
```

### 🔄 Redémarrage Forcé
```bash
docker-compose -f docker-compose.prod.yml restart
```

### 💾 Backup Base de Données
```bash
docker exec -t sentinel-db-prod pg_dumpall -c -U sentinel_prod > dump_`date +%d-%m-%Y"_"%H_%M_%S`.sql
```

## 🛡️ Sécurité
- **IP Whitelisting**: Managed by `ProductionSecurityManager` (see `.env.prod`).
- **Encryption**: Sensitive data signed with HMAC-SHA256.
- **Audit**: Security events logged to `PROD_SECURITY` logger.
