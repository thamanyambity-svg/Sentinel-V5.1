import os
from bot.config.settings import DISCORD_WEBHOOK


def get_webhook():
    return os.getenv("DISCORD_WEBHOOK", DISCORD_WEBHOOK)
