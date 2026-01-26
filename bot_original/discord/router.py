from bot.discord.commands import (
    status_command,
    propose_command,
    confirm_command,
    reject_command
)

def route_command(message: str) -> str | None:
    """
    Routeur simple des commandes Discord
    """
    if message == "/status":
        return status_command()

    if message == "/propose":
        return propose_command()

    if message == "/confirm":
        return confirm_command()

    if message == "/reject":
        return reject_command()

    return None
