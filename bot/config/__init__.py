import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

from bot.config.flags import (
    REAL_TRADING_ENABLED,
    enable_real_trading,
    disable_real_trading,
)
