
import os
import aiohttp
import logging
import asyncio
import json
import ssl
import certifi

# Fix SSL context for macOS
ssl_context = ssl.create_default_context(cafile=certifi.where())

logger = logging.getLogger("TELEGRAM")

class TelegramNotifier:
    """
    Simple async wrapper to send messages to Telegram.
    Running simultaneously with Discord.
    """
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self.silent_mode = False # DIRECTIVE: START IN ACTIVE MODE FOR PROJECT 100
        self.active_signals = {}

    async def send_message(self, text):
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials missing. Skipping notification.")
            return

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                async with session.post(self.base_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Telegram API Error: {await response.text()}")
                    else:
                        logger.info("📲 Notification sent to Telegram")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    async def send_signal(self, data, signal):
        """
        Formats a trading signal for Telegram with INTERACTIVE BUTTONS.
        """
        if not self.token: return
        
        # User requested silence for automatic signals
        if self.silent_mode:
            logger.info("🔕 Signal generated but suppressed (Silent Mode active)")
            return

        icon = "🟢" if signal['side'] == "BUY" else "🔴"
        stake = float(signal['amount'])
        
        msg_text = (
            f"{icon} *SIGNAL {signal['side']} - {data['asset']}*\n\n"
            f"💰 *Mise*: ${stake}\n"
            f"📈 *Proba*: {data.get('probability')}\n"
            f"⏳ *Durée*: {data.get('duration')}\n"
            f"🧠 *AI*: {data.get('market_details')[2] if len(data.get('market_details', [])) > 2 else 'N/A'}\n\n"
            f"_Sentinelle Alpha V1.0_"
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "➖ 10%", "callback_data": "stake_down"},
                    {"text": f"${stake}", "callback_data": "noop"},
                    {"text": "➕ 10%", "callback_data": "stake_up"}
                ],
                [
                    {"text": "✅ VALIDER", "callback_data": "confirm_trade"},
                    {"text": "❌ REJETER", "callback_data": "cancel_trade"}
                ]
            ]
        }

        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                payload = {
                    "chat_id": self.chat_id,
                    "text": msg_text,
                    "parse_mode": "Markdown",
                    "reply_markup": keyboard
                }
                async with session.post(self.base_url, json=payload) as response:
                    if response.status == 200:
                        res_json = await response.json()
                        msg_id = res_json['result']['message_id']
                        # Store context for interactivity
                        self.active_signals[str(msg_id)] = {
                            "signal": signal,
                            "data": data,
                            "stake": stake
                        }
                        logger.info(f"📲 Interactive Signal sent (Msg ID: {msg_id})")
        except Exception as e:
            logger.error(f"Failed to send interactive signal: {e}")

    async def send_report(self, report_data):
        """
        Formats a trade report (PnL) for Telegram.
        """
        pnl = report_data.get("pnl", 0.0)
        is_win = pnl > 0
        icon = "✅" if is_win else "❌"
        
        msg = (
            f"{icon} *RÉSULTAT DU TRADE*\n\n"
            f"💰 *P/L*: {pnl:+.2f}$\n"
            f"🏦 *Nouveau Solde*: {report_data.get('new_balance'):.2f}$\n"
            f"🆔 *ID*: {report_data.get('trade_id')}"
        )
        await self.send_message(msg)

    async def start_polling(self, bot_instance, broker=None):
        """
        Polls Telegram for new commands AND button clicks.
        """
        if not self.token: return
        
        offset = 0
        update_url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        
        logger.info("📡 Telegram Listener Started (Commands + Buttons + Chat)")
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            logger.info(f"DEBUG: Starting polling loop... URL={update_url}")
            while True:
                try:
                    payload = {"offset": offset, "timeout": 30}
                    async with session.post(update_url, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("ok"):
                                for result in data.get("result", []):
                                    offset = result["update_id"] + 1
                                    
                                    # 1. Handle Messages (Commands AND Chat)
                                    if "message" in result:
                                        message = result["message"]
                                        text = message.get("text", "").strip()
                                        chat_id = message.get("chat", {}).get("id")
                                        
                                        # Strict security: Process only user's chat_id
                                        if str(chat_id) != str(self.chat_id): 
                                            continue
                                            
                                        if text.startswith("/"):
                                            await self.handle_command(text, bot_instance)
                                        else:
                                            # Chat Mode!
                                            asyncio.create_task(self.handle_chat(text))

                                    # 2. Handle Callback Queries (Buttons)
                                    if "callback_query" in result:
                                        await self.handle_callback(result["callback_query"], broker, session)

                except Exception as e:
                    logger.error(f"Telegram Polling Error: {e}")
                    await asyncio.sleep(5)
                
                await asyncio.sleep(1)

    async def handle_callback(self, callback, broker, session):
        callback_id = callback["id"]
        msg_id = str(callback["message"]["message_id"])
        data = callback["data"]
        
        if msg_id not in self.active_signals:
            await self.answer_callback(session, callback_id, "⚠️ Signal expiré ou inconnu.")
            return

        ctx = self.active_signals[msg_id]
        current_stake = ctx["stake"]
        
        if data == "stake_up":
            ctx["stake"] = round(current_stake * 1.1, 2)
            await self.update_signal_message(session, msg_id, ctx)
            await self.answer_callback(session, callback_id, f"Mise augmentée: ${ctx['stake']}")
            
        elif data == "stake_down":
            ctx["stake"] = round(current_stake * 0.9, 2)
            await self.update_signal_message(session, msg_id, ctx)
            await self.answer_callback(session, callback_id, f"Mise réduite: ${ctx['stake']}")
            
        elif data == "confirm_trade":
            if broker:
                # Execute Trade Logic
                signal = ctx['signal']
                signal['amount'] = ctx['stake'] # Update stake
                
                try:
                    order = await broker.execute_trade(signal)
                    await self.edit_message_text(session, msg_id, f"✅ *TRADE EXÉCUTÉ*\nID: {order.get('contract_id')}\nMise: ${signal['amount']}")
                    del self.active_signals[msg_id]
                except Exception as e:
                    await self.answer_callback(session, callback_id, f"Erreur: {e}")
            else:
                await self.answer_callback(session, callback_id, "Erreur: Broker non connecté")

        elif data == "cancel_trade":
            await self.edit_message_text(session, msg_id, "❌ *TRADE ANNULÉ PAR L'UTILISATEUR*")
            del self.active_signals[msg_id]
        
        elif data == "noop":
            await self.answer_callback(session, callback_id, "Montant actuel")

    async def answer_callback(self, session, callback_id, text):
        url = f"https://api.telegram.org/bot{self.token}/answerCallbackQuery"
        await session.post(url, json={"callback_query_id": callback_id, "text": text})

    async def update_signal_message(self, session, msg_id, ctx):
        stake = ctx['stake']
        signal = ctx['signal']
        data = ctx['data']
        # Rebuild keyboard with new stake
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "➖ 10%", "callback_data": "stake_down"},
                    {"text": f"${stake}", "callback_data": "noop"},
                    {"text": "➕ 10%", "callback_data": "stake_up"}
                ],
                [
                    {"text": "✅ VALIDER", "callback_data": "confirm_trade"},
                    {"text": "❌ REJETER", "callback_data": "cancel_trade"}
                ]
            ]
        }
        # Rebuild text
        icon = "🟢" if signal['side'] == "BUY" else "🔴"
        text = (
            f"{icon} *SIGNAL {signal['side']} - {data['asset']}*\n\n"
            f"💰 *Mise ajustée*: ${stake}\n"
            f"📈 *Proba*: {data.get('probability')}\n"
            f"⏳ *Durée*: {data.get('duration')}\n"
            f"🧠 *AI*: {data.get('market_details')[2] if len(data.get('market_details', [])) > 2 else 'N/A'}\n\n"
            f"_Sentinelle Alpha V1.0_"
        )
        
        url = f"https://api.telegram.org/bot{self.token}/editMessageText"
        payload = {
            "chat_id": self.chat_id,
            "message_id": msg_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        }
        await session.post(url, json=payload)

    async def edit_message_text(self, session, msg_id, text):
        url = f"https://api.telegram.org/bot{self.token}/editMessageText"
        payload = {
            "chat_id": self.chat_id,
            "message_id": msg_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        await session.post(url, json=payload)

    # --- NEW: Chat & Logs Logic ---
    
    async def handle_chat(self, user_text):
        """
        Uses Groq directly to reply to user chat messages.
        Turns the bot into 'Jorvise'.
        """
        if not self.groq_key:
            return # Silent fail if no key

        system_prompt = (
            "Tu es Jorvise, un assistant de trading institutionnel avancé. "
            "Tu gères le bot de trading 'Alpha Sentinel' de l'utilisateur. "
            "Sois professionnel, concis et utile. Réponds toujours en Français. "
            "Si on te demande le statut, mentionne '/status'. "
            "Si on te demande les logs, mentionne '/logs'. "
            "Ne donne pas de conseils financiers risqués. Garde tes réponses courtes (moins de 200 car. si possible)."
        )

        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 300
                }
                headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
                
                async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        reply = data['choices'][0]['message']['content']
                        await self.send_message(f"🤵‍♂️ *Jorvise*: {reply}")
                    else:
                        logger.error(f"Groq Chat Error: {await response.text()}")
        except Exception as e:
            logger.error(f"Chat Exception: {e}")

    async def handle_command(self, text, bot_instance):
        from bot.discord_interface.commands import (
            status_command, balance_command, daily_command, 
            help_command, professor_command, broker_command, force_command
        )
        
        cmd = text.lower().split()[0]
        logger.info(f"📩 Telegram Command: {cmd}")
        
        response = ""
        
        try:
            if cmd == "/status":
                response = status_command()
            elif cmd == "/balance":
                response = await balance_command(bot_instance)
            elif cmd == "/daily":
                response = daily_command()
            elif cmd == "/help":
                response = help_command()
            elif cmd == "/report":
                # Forcing report from professor if possible or using general logic
                response = professor_command()
            elif cmd == "/logs":
                # NEW: Read last 5 lines from CSV
                try:
                    lines = []
                    filename = "training_data_v75.csv"
                    if os.path.exists(filename):
                        with open(filename, 'r') as f:
                            # Read all lines efficiently
                            # For small files, readlines is fine.
                            all_lines = f.readlines()
                            # Get header + last 5
                            if len(all_lines) > 5:
                                lines = [all_lines[0]] + all_lines[-5:]
                            else:
                                lines = all_lines
                        
                        # Format as code block
                        response = "📜 *Derniers Logs (Live)*:\n```csv\n" + "".join(lines) + "\n```"
                    else:
                        response = "⚠️ Aucun fichier de logs trouvé."
                except Exception as e:
                    response = f"❌ Erreur lecture logs: {e}"

            elif cmd == "/force":
                # simplistic parsing for /force buy r_100
                parts = text.split()
                if len(parts) >= 2:
                    mode = parts[1]
                    response = force_command(mode)
                else:
                    response = "Usage: /force [buy/sell]"
            else:
                response = "❓ Commande inconnue. Essayez /help."
                
            # Send (split if too long)
            logger.info(f"DEBUG: Response length: {len(response)}")
            if len(response) > 4000:
                for i in range(0, len(response), 4000):
                    await self.send_message(response[i:i+4000])
            else:
                await self.send_message(response)
                
        except Exception as e:
            await self.send_message(f"❌ Erreur: {e}")
