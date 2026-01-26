import threading
from bot.scheduler.loop import start_scheduler
import discord
from bot.discord.router import route_command

TOKEN = "MTQ1MDgwMDk1NTM5NzI0NzE0OQ.GyFK9R.wNE6_onM3RzzzBmxLIW_4yOqItQIDSv3vK9duc"

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)



@client.event
async def on_ready():
    print(f"Bot connecté : {client.user}")

    import threading
    from bot.scheduler.loop import start_scheduler

    scheduler_thread = threading.Thread(
        target=start_scheduler,
        kwargs={"interval": 3},
        daemon=True
    )
    scheduler_thread.start()

@client.event
async def on_message(message):
    if message.author.bot:
        return

    response = route_command(message.content)
    if response:
        await message.channel.send(response)


client.run(TOKEN)
