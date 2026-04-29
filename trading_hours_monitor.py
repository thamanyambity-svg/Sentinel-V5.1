import json
import asyncio
import os
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from bot.discord_interface.discord_api_notifier import DiscordAPINotifier
from dotenv import load_dotenv

# Load bot/.env first
load_dotenv(dotenv_path=Path("bot/.env"))

class TradingHoursMonitor:
    def __init__(self):
        with open("config_trading_hours.json", "r") as f:
            self.config = json.load(f)["markets"]
        self.notifier = DiscordAPINotifier()
        self.tz = ZoneInfo("GMT")
        self.kinshasa_tz = ZoneInfo("Africa/Lagos")  # GMT+1 Kinshasa

    def is_market_open(self, market, session):
        """Check if current GMT time is within session open-close."""
        now = datetime.now(self.tz).time()
        open_t = time.fromisoformat(session["open"])
        close_t = time.fromisoformat(session["close"])
        
        if open_t <= close_t:  # Same day session
            return open_t <= now <= close_t
        else:  # Overnight session
            return now >= open_t or now <= close_t

    def format_time_kinshasa(self, gmt_time_str):
        """Convert GMT time string to Kinshasa (GMT+1)."""
        gmt_time = time.fromisoformat(gmt_time_str)
        gmt_dt = datetime.combine(datetime.today(), gmt_time, self.tz)
        kin_dt = gmt_dt.astimezone(self.kinshasa_tz)
        return kin_dt.strftime("%H:%M")

    def calculate_events(self):
        """Calcule tous les événements open/close pour les 36h prochaines."""
        events = []
        now = datetime.now(self.tz)
        today = now.date()
        tomorrow = today + timedelta(days=1)
        
        for market, data in self.config.items():
            for session in data["sessions"]:
                # Today (future events only)
                open_dt = datetime.combine(today, time.fromisoformat(session["open"]), self.tz)
                close_dt = datetime.combine(today, time.fromisoformat(session["close"]), self.tz)
                if open_dt > now:
                    events.append({'market': market, 'time': open_dt, 'type': 'open', 'session': session['name']})
                if close_dt > now:
                    events.append({'market': market, 'time': close_dt, 'type': 'close', 'session': session['name']})
                
                # Tomorrow (full coverage)
                open_dt_tom = datetime.combine(tomorrow, time.fromisoformat(session["open"]), self.tz)
                close_dt_tom = datetime.combine(tomorrow, time.fromisoformat(session["close"]), self.tz)
                events.append({'market': market, 'time': open_dt_tom, 'type': 'open', 'session': session['name']})
                events.append({'market': market, 'time': close_dt_tom, 'type': 'close', 'session': session['name']})
        
        events = [e for e in events if e['time'] > now]
        events.sort(key=lambda x: x['time'])
        return events

    def get_market_status(self, market):
        """Return True if ANY session active."""
        sessions = self.config[market]["sessions"]
        return any(self.is_market_open(market, s) for s in sessions)

    async def run_continuous_scheduler(self):
        """Scheduler précis: sleep jusqu'au prochain événement exact."""
        print("🚀 Trading Hours Monitor EXACT - Démarrage...")
        
        while True:
            events = self.calculate_events()
            if not events:
                print("❌ Aucun événement trouvé, attente 1h...")
                await asyncio.sleep(3600)
                continue
            
            next_event = events[0]
            wait_seconds = (next_event['time'] - datetime.now(self.tz)).total_seconds()
            
            if wait_seconds > 0:
                hours = int(wait_seconds // 3600)
                minutes = int((wait_seconds % 3600) // 60)
                print(f"⏳ Attente {hours}h{minutes:02d}m jusqu'à {next_event['market']} "
                      f"{next_event['type']} ({next_event['session']}) à {next_event['time'].strftime('%H:%M GMT')}")
                await asyncio.sleep(wait_seconds)
            
            # Envoyer notification exacte
            market_name = self.config[next_event['market']]['name']
            status_open = next_event['type'] == 'open'
            print(f"🔔 ÉVÉNEMENT EXACT: {market_name} {next_event['type']} à {datetime.now(self.tz).strftime('%H:%M:%S GMT')}")
            
            await self.send_status_change(next_event['market'], status_open)

    def is_exact_time(self, target_time_str):
        """Check if current time matches EXACTLY the target time (minutes)."""
        now = datetime.now(self.tz).time()
        target = time.fromisoformat(target_time_str)
        # Match heure + minutes exactes

    async def send_status_change(self, market, new_status):
        """Send Discord notification on status change."""
        status_emoji = "🟢 OUVERT" if new_status else "🔴 FERMÉ"
        sessions = self.config[market]["sessions"]
        
        # Format sessions with Kinshasa time
        session_lines = []
        for s in sessions:
            kin_open = self.format_time_kinshasa(s["open"])
            kin_close = self.format_time_kinshasa(s["close"])
            session_lines.append(f"• {s['name']}: {s['open']}-{s['close']} GMT (Kinshasa: {kin_open}-{kin_close})")
        
        content = (
            f"🕐 **{self.config[market]['name']} {status_emoji}**\n"
            f"{'🟢 Trading AUTORISÉ' if new_status else '🔴 Trading BLOQUÉ'}\n\n"
            f"**Sessions :**\n" + "\n".join(session_lines)
        )
        
        await self.notifier.send_message(
            content=content,
            title=f"📈 {self.config[market]['name']} - État Trading",
            color=0x00ff00 if new_status else 0xff0000
        )
        print(f"✅ Discord envoyé : {market} {new_status}")

async def main():
    monitor = TradingHoursMonitor()
    try:
        await monitor.run_continuous_scheduler()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par utilisateur")
    except Exception as e:
        print(f"❌ Erreur critique: {e}")

if __name__ == "__main__":
    asyncio.run(main())
