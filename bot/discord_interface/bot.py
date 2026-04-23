import os
import ssl
import certifi
import discord
from discord.ext import commands
import logging
import asyncio
from discord.ui import Button, View
from bot.ai_agents.audit_logger import log_event

# Configuration SSL (Patch Mac) - Forcing SSL Bypass via Monkeypatch
import aiohttp
import ssl

def patch_aiohttp_ssl():
    import aiohttp
    orig_init = aiohttp.TCPConnector.__init__
    def new_init(self, *args, **kwargs):
        kwargs['ssl'] = False
        orig_init(self, *args, **kwargs)
    aiohttp.TCPConnector.__init__ = new_init

patch_aiohttp_ssl()

os.environ['SSL_CERT_FILE'] = '/etc/ssl/cert.pem'
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/cert.pem'

from bot.discord_interface.commands import (
    status_command,
    broker_command,
    deriv_command,
    force_command
)

logger = logging.getLogger("BOT")

class StakeSelect(discord.ui.Select):
    def __init__(self, current_stake):
        # Options : 0.35$, 1$, 2$, 3$ (Micro-Mises pour test réel)
        stakes = [0.35, 1, 2, 3]
        options = [
            discord.SelectOption(label=f"${s}", value=str(s), default=(str(s) == str(current_stake).replace("$", "")))
            for s in stakes
        ]
        super().__init__(placeholder="💰 Modifier la mise...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.stake = self.values[0]
        await interaction.response.defer()

class TradeView(View):
    def __init__(self, bot, broker, signal, asset, stake):
        super().__init__(timeout=None)
        self.bot = bot
        self.broker = broker
        self.signal = signal
        self.asset = asset
        self.stake = str(stake).replace("$", "")
        self.add_item(StakeSelect(self.stake))

    async def _get_current_balance(self):
        client = getattr(self.bot, "deriv_client", None)
        if not client:
            return 0.0

        try:
            balance_data = await client.get_balance()
            if isinstance(balance_data, dict):
                return float(balance_data.get("balance", 0.0) or 0.0)
        except Exception as e:
            logger.warning(f"⚠️ Discord manual balance fetch failed: {e}")

        return 0.0

    async def _apply_manual_security(self):
        self.signal.setdefault("type", "MEAN_REVERSION")
        self.signal.setdefault("indicators", {"rsi": 50})

        requested_amount = float(self.stake)
        balance = await self._get_current_balance()

        sl_dist = self.signal.get("risk_plan", {}).get("sl_dist")
        if not sl_dist:
            atr_value = float(self.signal.get("atr", 0.0) or 0.0)
            sl_dist = (atr_value * 2.0) if atr_value > 0.0 else 50.0

        atr_for_governance = float(self.signal.get("atr", 0.0) or (sl_dist / 2.0))

        manager = getattr(self.bot, "manager", None)
        if manager:
            context = {
                "asset": self.signal.get("asset", self.asset),
                "price": float(self.signal.get("current_price", 0.0) or 0.0),
                "indicators": self.signal.get("indicators", {"rsi": 50}),
                "balance": balance,
                "atr": atr_for_governance,
            }
            approved, reason = await manager.validate_signal(
                self.signal,
                [],
                {"global_drawdown": 0.0, "losing_streak": 0},
                context,
            )
            if not approved:
                raise RuntimeError(f"Signal bloqué par gouvernance: {reason}")

        risk_manager = getattr(self.bot, "risk_manager", None)
        if risk_manager and balance > 0.0:
            safe_amount = risk_manager.calculate_lot_size(balance, float(sl_dist), self.signal.get("asset", self.asset))
            if safe_amount > 0.0:
                requested_amount = min(requested_amount, safe_amount)

        self.signal["amount"] = round(requested_amount, 2)
        self.signal["stake"] = self.signal["amount"]
        self.signal["risk_plan"] = {**self.signal.get("risk_plan", {}), "sl_dist": float(sl_dist)}

    @discord.ui.button(label="✅ VALIDER", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        print("🖱️ [DISCORD] Button Clicked! Starting Callback...")
        await interaction.response.defer()
        for child in self.children: child.disabled = True
        await interaction.message.edit(view=self)
        try:
            print("🖱️ [DISCORD] Processing Signal...")
            # --- SCIENTIFIC DATA COLLECTION ---
            import time
            execution_time = time.time()
            signal_time = self.signal.get("generated_at", execution_time)
            latency = execution_time - signal_time
            
            await self._apply_manual_security()
            self.signal["human_delay"] = latency # Inject for Collector
            
            logger.info(f"🧬 [METRICS] Human Validation Delay: {latency:.2f}s")
            
            result = await self.broker.execute(self.signal)
            embed = interaction.message.embeds[0]
            embed.color = 0x00ff00
            embed.add_field(name="STATUT", value=f"🚀 **ORDRE LANCÉ ({self.signal['amount']}$)**", inline=False)
            embed.add_field(name="⏱️ Réflexe Humain", value=f"`{latency:.2f}s`", inline=True)
            
            await interaction.followup.send(f"✅ Ordre de {self.signal['amount']}$ exécuté sur {self.asset} ! (Délai: {latency:.1f}s)")
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}")

    @discord.ui.button(label="❌ REJETER", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        for child in self.children: child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.followup.send(f"Signal sur {self.asset} rejeté.")

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="status")
    async def status(self, ctx):
        await ctx.send(status_command())

    @commands.command(name="deriv")
    async def deriv_cmd(self, ctx, mode: str):
        await ctx.send(deriv_command(mode.lower()))

    @commands.command(name="broker")
    async def broker_cmd(self, ctx, name: str):
        await ctx.send(broker_command(name.lower()))

    @commands.command(name="force")
    async def force_cmd(self, ctx, mode: str):
        await ctx.send(force_command(mode.lower()))

    @commands.command(name="balance", aliases=["bal", "balace"])
    async def balance(self, ctx):
        from bot.discord_interface.commands import balance_command
        logger.info(f"🔍 Requête solde par {ctx.author}")
        try:
            res = await balance_command(self.bot)
            await ctx.send(res)
        except Exception as e:
            await ctx.send(f"❌ Erreur interne : {e}")

    @commands.command(name="daily")
    async def daily(self, ctx):
        from bot.discord_interface.commands import daily_command
        await ctx.send(daily_command())

    @commands.command(name="help")
    async def help_cmd(self, ctx):
        from bot.discord_interface.commands import help_command
        await ctx.send(help_command())

    @commands.command(name="report")
    async def report(self, ctx):
        from bot.discord_interface.commands import professor_command
        report = professor_command()
        for i in range(0, len(report), 2000): await ctx.send(report[i:i+2000])

    @commands.command(name="audit")
    async def audit_delay(self, ctx):
        await ctx.send("�� **Audit lancé.** Rapport dans **20 minutes**.")
        async def delayed_report():
            await asyncio.sleep(1200)
            from bot.discord_interface.commands import professor_command
            report = professor_command()
            await ctx.send("🎓 **RAPPORT D'AUDIT DIFFÉRÉ**")
            for i in range(0, len(report), 2000): await ctx.send(report[i:i+2000])
        asyncio.create_task(delayed_report())

class TradingBot(commands.Bot):
    def __init__(self, trading_loop_coro):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.trading_loop_coro = trading_loop_coro
        self.channel_id = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
        self.deriv_client = None

    async def setup_hook(self):
        await self.add_cog(AdminCommands(self))

    async def on_ready(self):
        print(f"🚀 BOT CONNECTÉ : {self.user}")
        self.loop.create_task(self.trading_loop_coro(self))
        self.loop.create_task(self.scheduled_report_task())
        
        # --- NOTIFICATION DE DÉMARRAGE FORCÉE ---
        try:
            channel = self.get_channel(self.channel_id)
            if channel:
                import datetime
                await channel.send(f"🟢 **SENTINEL V4.7 ONLINE**\n🕒 Démarrage: {datetime.datetime.now().strftime('%H:%M:%S')}\n📊 Prêt à trader !")
        except Exception as e:
            logger.error(f"Failed to send startup msg: {e}")

    async def scheduled_report_task(self):
        """
        Runs every day at 08:30 AM to send the Morning Briefing.
        """
        import datetime
        await self.wait_until_ready()
        
        while not self.is_closed():
            now = datetime.datetime.now()
            target_time = datetime.time(8, 30, 0) # 08:30 AM
            target_date = datetime.date.today()
            
            # Combine to get target datetime
            future = datetime.datetime.combine(target_date, target_time)
            
            # If target is in the past, schedule for tomorrow
            if future < now:
                future += datetime.timedelta(days=1)
                
            sleep_seconds = (future - now).total_seconds()
            logger.info(f"📅 Morning Report scheduled in {sleep_seconds/3600:.2f} hours (at {future})")
            
            await asyncio.sleep(sleep_seconds)
            
            # --- EXECUTE REPORT ---
            try:
                channel = self.get_channel(self.channel_id)
                if channel:
                    from bot.discord_interface.commands import professor_command
                    logger.info("🌅 Sending Morning Report...")
                    await channel.send("☕ **Bonjour ! Voici votre Rapport Matinal (08:30) :**")
                    
                    report = professor_command()
                    if report:
                        for i in range(0, len(report), 2000): 
                            await channel.send(report[i:i+2000])
                    else:
                        await channel.send("Rien à signaler ce matin.")
            except Exception as e:
                logger.error(f"Failed to send scheduled report: {e}")
            
            # Wait a bit to avoid double trigger (though calc handles it)
            await asyncio.sleep(60)

    async def on_message(self, message):
        if message.author == self.user: return
        
        # Log de diagnostic
        logger.info(f"📩 Message reçu de {message.author}: '{message.content}'")
        
        content = message.content.strip()
        if content.startswith("! "): content = "!" + content[2:].strip()
        message.content = content
        await self.process_commands(message)


    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            logger.warning(f"🤔 Commande inconnue : {ctx.message.content}")
        else:
            logger.error(f"💥 Erreur : {error}")
            await ctx.send(f"❌ Erreur : {error}")

    async def send_interactive_signal(self, data, broker, signal):
        from datetime import datetime
        channel = self.get_channel(self.channel_id)
        if not channel: return
        embed = discord.Embed(
            title=f"🚨 SIGNAL : {data['asset']}",
            color=0x00ff00 if signal['side'] == 'BUY' else 0xff0000,
            timestamp=datetime.now()
        )
        embed.add_field(name="🕒 Heure", value=datetime.now().strftime("%H:%M:%S"), inline=True)
        embed.add_field(name="⏳ Durée", value=data.get('duration', '1m'), inline=True)
        embed.add_field(name="🎯 Position", value=f"**{signal['side']}**", inline=True)
        embed.add_field(name="💰 Mise IA", value=f"**{data.get('stake_advice')}**", inline=True)
        embed.add_field(name="📈 Proba", value=f"`{data.get('probability')}`", inline=True)
        embed.add_field(name="📊 Score", value=f"`{data['score']}/100`", inline=True)
        embed.set_footer(text="Sentinelle Alpha V1.0")
        view = TradeView(self, broker, signal, data['asset'], data.get("stake_advice", "$10"))
        await channel.send(embed=embed, view=view)

    async def send_signal_embed(self, data):
        """
        Send a passive signal embed (No Buttons) for Auto-Pilot / Night Mode.
        """
        from datetime import datetime
        channel = self.get_channel(self.channel_id)
        if not channel: return
        
        # Default Color (Blue for Info/Auto)
        color = 0x3498db 
        
        embed = discord.Embed(
            title=f"🌙 AUTO-PILOT : {data['asset']}",
            color=color,
            timestamp=datetime.now()
        )
        embed.add_field(name="Action", value=f"**AUTO-EXECUTED**", inline=True)
        
        # Display Amount
        stake_val = data.get('amount') or data.get('stake_advice')
        if isinstance(stake_val, float): stake_val = f"${stake_val:.2f}"
        embed.add_field(name="💰 Montant", value=f"**{stake_val}**", inline=True)
        embed.add_field(name="Proba", value=f"`{data.get('probability')}`", inline=True)
        embed.add_field(name="Score", value=f"`{data['score']}/100`", inline=True)
        embed.set_footer(text="Sentinelle Alpha (Night Mode)")
        
        await channel.send(embed=embed)


    async def send_report(self, report_data):
        from datetime import datetime
        channel = self.get_channel(self.channel_id)
        if not channel: return
        
        pnl = report_data.get("pnl", 0.0)
        is_win = pnl > 0
        
        if report_data.get("trade_id") == "GROUP_EXIT":
            # CASH OUT NOTIFICATION
            embed = discord.Embed(
                title="💰 CASH OUT (GLOBAL EXIT)",
                color=0xFFD700, # Gold
                timestamp=datetime.now()
            )
            embed.description = f"**{report_data.get('asset', 'UNK')}** | Grid Sécurisé & Fermé."
            embed.add_field(name="💵 Net PnL", value=f"**{pnl:+.2f}$**", inline=True)
            embed.add_field(name="📦 Trades", value=f"{report_data.get('count', '?')}", inline=True)
            embed.add_field(name="🏦 Nouveau Solde", value=f"**{report_data.get('new_balance', 0):.2f}$**", inline=False)
            embed.set_footer(text="✅ SAFE GRID - Tous les ordres fermés.")
            embed.set_thumbnail(url="https://img.icons8.com/3d-fluency/94/money-bag.png")
            await channel.send(embed=embed)
            return

        embed = discord.Embed(
            title="💰 RÉSULTAT DU TRADE",
            color=0x00ff00 if is_win else 0xff0000,
            timestamp=datetime.now()
        )
        embed.add_field(name="🆔 ID", value=report_data.get("trade_id", "N/A"), inline=True)
        embed.add_field(name="💼 Marché", value=f"**{report_data.get('asset', 'UNK')}**", inline=True)
        embed.add_field(name="⏱️ Durée", value=f"{report_data.get('duration', 'N/A')}", inline=True)

        embed.add_field(name="💰 Mise", value=f"**{report_data.get('stake', 0.0):.2f}$**", inline=True)
        embed.add_field(name="📉 P/L", value=f"**{pnl:+.2f}$**", inline=True)
        embed.add_field(name="📊 Résultat", value=f"**{'WIN' if is_win else 'LOSS'}**", inline=True)

        embed.add_field(name="🏦 Solde Avant", value=f"{report_data.get('entry_balance', 0):.2f}$", inline=True)
        embed.add_field(name="🏦 Solde Après", value=f"**{report_data.get('new_balance', 0):.2f}$**", inline=True)
        
        if is_win:
            embed.set_thumbnail(url="https://img.icons8.com/color/96/check-circle--v1.png")
            embed.set_footer(text="✅ SUCCÈS - Stratégie Validée")
        else:
            embed.set_thumbnail(url="https://img.icons8.com/color/96/cancel--v1.png")
            embed.set_footer(text="❌ ÉCHEC - Stop Loss Touché")
            
        try:
            await channel.send(embed=embed)
            logger.info(f"✅ Report sent to Discord for {report_data.get('trade_id')}")
        except Exception as e:
            logger.error(f"❌ Failed to send Discord Report embed: {e}")
            await channel.send(f"⚠️ **Rapport Simplifié (Embed Error)**\nTrade: {report_data.get('asset')}\nPnL: {pnl}\nSolde: {report_data.get('new_balance')}")

    async def send_periodic_report(self, positions, balance, mt5_balance=None, pnl_day=0.0):
        """
        Sends a live summary of active trades and current balance.
        """
        from datetime import datetime
        channel = self.get_channel(self.channel_id)
        if not channel: return
        
        embed = discord.Embed(
            title="📈 DIRECT : Suivi Live (2min)",
            color=0x3498db,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="💳 Solde Options", value=f"**{balance:.2f}$**", inline=True)
        
        mt5_text = f"**{mt5_balance:.2f}$**" if mt5_balance else "⏳ Attente Sentinel..."
        embed.add_field(name="📉 Solde MT5", value=mt5_text, inline=True)
        
        embed.add_field(name="📅 PnL Jour", value=f"**{pnl_day:+.2f}$**", inline=True)
        
        if positions:
            active_list = ""
            for p in positions:
                symbol = p.get('symbol', 'UNK')
                profit = float(p.get('profit', 0.0))
                icon = "🟢" if profit >= 0 else "🔴"
                active_list += f"{icon} **{symbol}** : {profit:+.2f}$\n"
            
            embed.add_field(name=f"📦 Positions Ouvertes ({len(positions)})", value=active_list or "Aucune", inline=False)
        else:
            embed.add_field(name="📦 Positions", value="😴 Aucun trade actif", inline=False)
            
        embed.set_footer(text="Auto-Refresh toutes les 2 min")
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send Periodic Report: {e}")

    async def log_to_discord(self, message):
        """
        Send a generic message or log to the main channel.
        """
        try:
            channel = self.get_channel(self.channel_id)
            if channel:
                await channel.send(message)
            else:
                logger.warning("Could not find Discord Channel to log message.")
        except Exception as e:
            logger.error(f"Failed to log to Discord: {e}")


if __name__ == "__main__":
    import asyncio
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv(override=True)
    
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ CRITICAL: No DISCORD_BOT_TOKEN found in .env")
        exit(1)

    async def mock_trading_loop(bot):
        print("🔧 DEBUG MODEL: Mock trading loop started")
        while True:
            await asyncio.sleep(60)

    # Initialize Bot
    print("🚀 STARTING DISCORD BOT (STANDALONE)...")
    bot = TradingBot(mock_trading_loop)
    
    try:
        bot.run(token)
    except Exception as e:
        print(f"❌ BOT CRASHED: {e}")
