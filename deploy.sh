#!/bin/bash
set -e

# Configuration
PROD_COMPOSE="docker-compose.prod.yml"
STAGING_COMPOSE="docker-compose.staging.yml" # We might reuse prod config with different ports/names for true staging
# For simplicity in this script, we'll simulate check on a "Staging" environment that is just a parallel instance

echo "🚀 Starting Blue-Green Deployment Sequence..."

# 1. Pull latest code/images
echo "📥 Pulling updates..."
# git pull origin main
# docker pull ...

# 2. Build New Images
echo "🛠️ Building Production Images..."
docker-compose -f $PROD_COMPOSE build

# 3. Start Staging / Pre-Flight Check
# We'll spin up the new containers alongside the old ones? 
# In a single-host docker-compose setup, "Blue-Green" usually implies swapping ports or services.
# Simplified approach: Up -d --build (Compose handles rolling updates if configured, but let's follow the script logic requested)

echo "🚦 Starting Validation Container (Staging Mode)..."
# We spin up a temporary instance to check health
docker-compose -f $PROD_COMPOSE run --rm --entrypoint python3 sentinel-bot health_check.py

if [ $? -eq 0 ]; then
    echo "✅ Health Check PASSED: New image is healthy."
else
    echo "❌ Health Check FAILED: Aborting deployment."
    exit 1
fi

# 4. Deploy to Production
echo "🔄 Rolling out to Production..."
docker-compose -f $PROD_COMPOSE up -d

# 5. Post-Deployment Check
echo "🔍 Verifying Production status..."
sleep 10
if docker-compose -f $PROD_COMPOSE ps | grep -q "Up"; then
    echo "✅ Production is UP and Running."
else
    echo "⚠️ Warning: Production service might be unstable. Check logs."
    docker-compose -f $PROD_COMPOSE logs --tail=20
    exit 1
fi

echo "✨ Deployment Completed Successfully!"
