#!/bin/bash
# SENTINEL V11 - Start API Server
# Usage: ./start_api.sh

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║        SENTINEL V11 - API SERVER LAUNCHER                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Vérifier que l'env virtuel existe
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Run this first:"
    echo "   python3 -m venv .venv"
    exit 1
fi

# Activer l'env virtuel
echo "✓ Activating Python virtual environment..."
source .venv/bin/activate

# Installer les dépendances si nécessaire
echo "✓ Checking dependencies..."
pip install -q -r requirements_v11.txt 2>/dev/null || {
    echo "⚠️  Installing missing packages..."
    pip install flask flask-cors
}

# Tester l'installation
echo "✓ Running installation tests..."
python test_install.py --api

# Démarrer l'API
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                 🚀 STARTING API SERVER                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "  🌐 API Server:  http://localhost:5000"
echo "  📊 Dashboard:   http://localhost:5000/"
echo "  📡 Health:      http://localhost:5000/api/v1/health"
echo ""
echo "  Press Ctrl+C to stop the server"
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo ""

python api_server.py
