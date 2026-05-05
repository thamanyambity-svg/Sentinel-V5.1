"""
╔══════════════════════════════════════════════════════════════════════╗
║  ALADDIN PRO V6 — Module 4: Filtre Calendrier Economique            ║
║                                                                      ║
║  Bloque le trading autour des news haute importance                  ║
║  NFP · FOMC · CPI · GDP · ECB · BOE · BOJ                           ║
║  Fenetre: -30min avant / +60min apres (x2 pour Tier1)               ║
║                                                                      ║
║  Sources: ForexFactory API → fallback calendrier statique            ║
║  Output:  news_block.json (lu par MQL5) + alertes Python             ║
╚══════════════════════════════════════════════════════════════════════╝

Intégration dans engine.py:
    from news_filter import NewsFilter
    self.news_filter = NewsFilter(mt5_path=str(self.cfg.MT5_FILES_PATH))
    self.news_filter.start()
    # Dans la boucle de scan:
    if self.news_filter.is_trading_blocked(sym):
        continue
"""

import json
import time
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum


# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════

class NewsConfig:
    BLOCK_BEFORE_MINUTES  = 30    # Bloquer N minutes AVANT la news
    BLOCK_AFTER_MINUTES   = 60    # Bloquer N minutes APRES la news
    TIER1_MULTIPLIER      = 2     # Fenetre x2 pour NFP, FOMC, etc.
    REFRESH_INTERVAL_SEC  = 7200  # Re-fetch ForexFactory toutes les 2h (anti rate-limit)
    MIN_IMPACT_TO_BLOCK   = "HIGH"  # HIGH | MEDIUM
    FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    HTTP_TIMEOUT          = 10    # secondes
    MT5_NEWS_FILE         = "news_block.json"   # Lu par le bot MQL5
    CACHE_FILE            = "news_cache.json"
    MT5_COMMON_FILES_PATH = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"


# ══════════════════════════════════════════════════════════════════
#  STRUCTURES
# ══════════════════════════════════════════════════════════════════

class Impact(Enum):
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3

@dataclass
class NewsEvent:
    eid:      str
    title:    str
    currency: str
    impact:   Impact
    dt:       datetime
    actual:   Optional[str] = None

    @property
    def minutes_until(self) -> float:
        return (self.dt - datetime.utcnow()).total_seconds() / 60

    @property
    def is_published(self) -> bool:
        return self.actual is not None and self.actual.strip() != ""

    def in_window(self, before_mins: float, after_mins: float) -> bool:
        m = self.minutes_until
        return -after_mins <= m <= before_mins


# ══════════════════════════════════════════════════════════════════
#  MAPPING DEVISE → INSTRUMENTS AFFECTES
# ══════════════════════════════════════════════════════════════════

CURRENCY_MAP: Dict[str, List[str]] = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF",
            "AUDUSD", "NZDUSD", "XAUUSD", "US30Cash", "Nasdaq", "US500", "SPX500"],
    "EUR": ["EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD"],
    "GBP": ["GBPUSD", "EURGBP", "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY"],
    "CAD": ["USDCAD", "EURCAD", "GBPCAD", "CADJPY", "AUDCAD"],
    "CHF": ["USDCHF", "EURCHF", "GBPCHF", "CHFJPY"],
    "AUD": ["AUDUSD", "EURAUD", "GBPAUD", "AUDJPY", "AUDCAD", "AUDNZD"],
    "NZD": ["NZDUSD", "NZDJPY", "AUDNZD", "GBPNZD"],
    "CNY": ["USDCNH", "CNHJPY"],
}

# Événements critiques — fenêtre de protection doublée
TIER1_KEYWORDS: Set[str] = {
    "Non-Farm Payrolls", "NFP", "FOMC", "Federal Funds Rate",
    "Fed Interest Rate Decision", "Fed Rate", "CPI", "Consumer Price Index",
    "GDP", "Gross Domestic Product", "ECB Rate Decision", "ECB Deposit Rate",
    "BOE Interest Rate Decision", "Bank Rate", "BOJ Policy Rate",
    "Unemployment Rate", "PCE", "Core PCE", "Core Inflation",
    "Powell", "Lagarde", "Bailey", "Jackson Hole", "Beige Book",
    "Retail Sales", "ISM Manufacturing", "ISM Services",
}


# ══════════════════════════════════════════════════════════════════
#  CALENDRIER STATIQUE — Fallback si ForexFactory inaccessible
# ══════════════════════════════════════════════════════════════════

def build_static_calendar() -> List[NewsEvent]:
    """
    Génère les récurrences hebdomadaires fixes.
    Utilisé uniquement si l'API externe est indisponible.
    """
    now  = datetime.utcnow()
    mon  = now - timedelta(days=now.weekday())  # Lundi UTC courant

    # (jour 0=lun, heure_UTC, min, titre, devise)
    SCHEDULE = [
        # USA — Tier1
        (4, 13, 30, "Non-Farm Payrolls",         "USD"),
        (4, 13, 30, "Unemployment Rate",          "USD"),
        (1, 13, 30, "CPI m/m",                    "USD"),
        (3, 14,  0, "Fed Interest Rate Decision", "USD"),
        (3, 18,  0, "FOMC Statement",             "USD"),
        (3, 18, 30, "Fed Press Conference",       "USD"),
        (4, 12, 30, "Core PCE Price Index",       "USD"),
        (4, 13, 30, "GDP q/q",                    "USD"),
        # USA — High
        (2, 14,  0, "ADP Non-Farm Employment",   "USD"),
        (3, 14,  0, "ISM Manufacturing PMI",     "USD"),
        (3, 13, 30, "Retail Sales m/m",          "USD"),
        (4, 14,  0, "ISM Services PMI",          "USD"),
        # Zone Euro
        (3, 12, 15, "ECB Rate Decision",         "EUR"),
        (3, 12, 45, "ECB Press Conference",      "EUR"),
        (0,  9,  0, "German CPI m/m",            "EUR"),
        (0, 10,  0, "Euro Zone CPI Flash",       "EUR"),
        # Royaume-Uni
        (3, 12,  0, "BOE Interest Rate Decision","GBP"),
        (1,  7,  0, "CPI y/y UK",               "GBP"),
        (1,  7,  0, "Retail Sales m/m UK",      "GBP"),
        # Japon
        (4,  3,  0, "BOJ Policy Rate",           "JPY"),
        (4,  5, 30, "BOJ Press Conference",      "JPY"),
        # Canada
        (3, 14, 45, "BOC Rate Decision",         "CAD"),
        (4, 13, 30, "Canada Employment Change",  "CAD"),
    ]

    events = []
    for day, h, m, title, currency in SCHEDULE:
        dt      = mon + timedelta(days=day, hours=h, minutes=m)
        is_t1   = any(kw.lower() in title.lower() for kw in TIER1_KEYWORDS)
        impact  = Impact.HIGH if is_t1 else Impact.MEDIUM
        safe_id = title[:20].replace(" ", "_").replace("/", "")
        events.append(NewsEvent(
            eid=f"static_{safe_id}_{day}",
            title=title, currency=currency,
            impact=impact, dt=dt,
        ))
    return events


# ══════════════════════════════════════════════════════════════════
#  PARSEUR FOREXFACTORY
# ══════════════════════════════════════════════════════════════════

class ForexFactoryParser:

    @staticmethod
    def fetch(url: str, timeout: int) -> Optional[list]:
        import ssl, time as _time
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        log = logging.getLogger("NewsFilter")
        
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
                )
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = 60 * (2 ** attempt)  # 1min, 2min, 4min
                    log.warning("ForexFactory rate-limited (429). Waiting %ds before retry %d/3", wait, attempt + 1)
                    _time.sleep(wait)
                else:
                    log.warning("ForexFactory unreachable: %s", e)
                    return None
            except Exception as e:
                log.warning("ForexFactory unreachable: %s", e)
                return None
        
        log.error("ForexFactory: all retries exhausted (rate-limited). Using cache/fallback.")
        return None

    @staticmethod
    def parse(raw: list) -> List[NewsEvent]:
        events = []
        for item in raw:
            try:
                impact_str = item.get("impact", "Low").strip().upper()
                if impact_str == "HIGH":   imp = Impact.HIGH
                elif impact_str == "MEDIUM": imp = Impact.MEDIUM
                else:                       imp = Impact.LOW

                date_str = item.get("date", "").strip()
                time_str = item.get("time", "").strip()
                
                dt = None
                from datetime import timezone
                
                if "T" in date_str:
                    try:
                        dt_aware = datetime.fromisoformat(date_str)
                        if dt_aware.tzinfo is not None:
                            dt = dt_aware.astimezone(timezone.utc).replace(tzinfo=None)
                        else:
                            dt = dt_aware
                    except ValueError:
                        pass
                
                if dt is None:
                    combined = (date_str + " " + time_str).strip()
                    for fmt in ["%Y-%m-%d %I:%M%p", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"]:
                        try:
                            dt = datetime.strptime(combined, fmt)
                            break
                        except ValueError:
                            continue
                            
                if dt is None:
                    continue

                title    = item.get("title", "").strip()
                currency = item.get("country", "USD").upper().strip()[:3]

                events.append(NewsEvent(
                    eid      = str(item.get("id", hash(title + str(dt)))),
                    title    = title,
                    currency = currency,
                    impact   = imp,
                    dt       = dt,
                    actual   = item.get("actual") or None,
                ))
            except Exception:
                continue
        return events


# ══════════════════════════════════════════════════════════════════
#  FILTRE PRINCIPAL
# ══════════════════════════════════════════════════════════════════

class NewsFilter:
    """
    Filtre calendrier économique thread-safe.
    S'intègre dans AladdinEngine comme guard avant toute entrée en trade.
    """

    def __init__(self, cfg: NewsConfig = None, mt5_path: str = "."):
        self.cfg       = cfg or NewsConfig()
        self.mt5_path  = mt5_path
        self.log       = logging.getLogger("NewsFilter")

        self._events:   List[NewsEvent]  = []
        self._lock      = threading.Lock()
        self._running   = False
        self._last_ref  = datetime.min

        self.blocks_triggered = 0
        self.last_blocked: Optional[NewsEvent] = None

    # ── Démarrage ─────────────────────────────────────────────────

    def start(self):
        self._running = True
        t = threading.Thread(target=self._refresh_loop, daemon=True, name="NewsFilter")
        t.start()
        self._refresh()
        self.log.info("NewsFilter OK — %d events loaded", len(self._events))

    def stop(self):
        self._running = False

    # ── Interface publique ─────────────────────────────────────────

    def is_trading_blocked(self, symbol: str) -> bool:
        """
        Retourne True si une news haute importance est dans la fenêtre
        de protection pour ce symbole. Appeler AVANT toute entrée en trade.
        """
        for event in self._get_affecting_events(symbol):
            if self._is_event_blocking(event):
                with self._lock:
                    self.blocks_triggered += 1
                    self.last_blocked = event
                return True
        return False

    def get_blocking_reason(self, symbol: str) -> Optional[str]:
        for event in self._get_affecting_events(symbol):
            if self._is_event_blocking(event):
                m = event.minutes_until
                if m > 0:
                    return f"NEWS dans {m:.0f}min: [{event.currency}] {event.title}"
                else:
                    return f"POST-NEWS {abs(m):.0f}min ecoules: [{event.currency}] {event.title}"
        return None

    def get_next_event(self, symbol: str) -> Optional[NewsEvent]:
        future = [e for e in self._get_affecting_events(symbol) if e.minutes_until > 0]
        return min(future, key=lambda e: e.minutes_until) if future else None

    def get_upcoming(self, hours_ahead: int = 12) -> List[NewsEvent]:
        cutoff = datetime.utcnow() + timedelta(hours=hours_ahead)
        with self._lock:
            return sorted(
                [e for e in self._events
                 if e.impact == Impact.HIGH
                 and datetime.utcnow() <= e.dt <= cutoff
                 and not e.is_published],
                key=lambda e: e.dt
            )

    # ── Logique interne ────────────────────────────────────────────

    def _get_affecting_events(self, symbol: str) -> List[NewsEvent]:
        sym = symbol.upper().strip()
        result = []
        with self._lock:
            for event in self._events:
                if event.impact == Impact.LOW:
                    continue
                instruments = CURRENCY_MAP.get(event.currency, [])
                if sym in instruments or event.currency in sym:
                    result.append(event)
        return result

    def _is_event_blocking(self, event: NewsEvent) -> bool:
        if event.impact == Impact.LOW:
            return False
        if event.impact == Impact.MEDIUM and self.cfg.MIN_IMPACT_TO_BLOCK == "HIGH":
            return False
        is_tier1 = any(kw.lower() in event.title.lower() for kw in TIER1_KEYWORDS)
        mul      = self.cfg.TIER1_MULTIPLIER if is_tier1 else 1
        before   = self.cfg.BLOCK_BEFORE_MINUTES * mul
        after    = self.cfg.BLOCK_AFTER_MINUTES  * mul
        return event.in_window(before, after)

    # ── Refresh ────────────────────────────────────────────────────

    def _refresh_loop(self):
        while self._running:
            time.sleep(60)
            elapsed = (datetime.utcnow() - self._last_ref).total_seconds()
            if elapsed >= self.cfg.REFRESH_INTERVAL_SEC:
                self._refresh()

    def _refresh(self):
        self.log.info("Refresh calendar...")
        raw = ForexFactoryParser.fetch(self.cfg.FF_URL, self.cfg.HTTP_TIMEOUT)
        if raw:
            events = ForexFactoryParser.parse(raw)
            self.log.info("ForexFactory OK: %d events parsed", len(events))
        else:
            # Try loading the local cache before falling back to static calendar
            events = self._load_cache_events()
            if events:
                self.log.warning("Fallback: loaded %d events from local cache", len(events))
            else:
                self.log.warning("Fallback: using static calendar (no cache available)")
                events = build_static_calendar()

        cutoff = datetime.utcnow() - timedelta(hours=2)
        with self._lock:
            self._events = [e for e in events if e.dt >= cutoff]
        self._last_ref = datetime.utcnow()
        self.log.info("Calendar loaded: %d upcoming events (past 2h filtered)", len(self._events))

        self._export_for_mt5()
        self._save_cache()

    # ── Export vers MT5 ────────────────────────────────────────────

    def _export_for_mt5(self):
        import os
        # Simplification format V7.18 : on gère un état global pour toutes les paires USD
        # Si ANY event est HIGH impact dans Mins < BlockTime, on bloque.
        # Si event dans < 120 mins, on active pre_news_secure.
        
        is_blocked = False
        pre_news_secure = False
        min_minutes_until = 9999
        
        # Obtenir les events impactants l'USD (qui couvre FOMC, NFP, CPI, etc.)
        affecting_events = self._get_affecting_events("USD")
        
        for event in affecting_events:
            if event.impact == Impact.HIGH:
                m = event.minutes_until
                if 0 <= m < min_minutes_until:
                    min_minutes_until = m
                    
                if self._is_event_blocking(event):
                    is_blocked = True
                    
                if 0 <= m <= 120:
                    pre_news_secure = True

        if min_minutes_until == 9999:
            min_minutes_until = 0
            
        data = {
            "blocked": is_blocked,
            "symbol": "ALL",
            "mins_until": int(min_minutes_until) if min_minutes_until > 0 else 0,
            "pre_news_secure": pre_news_secure
        }
        
        try:
            # Ecriture dans Terminal/Common/Files
            path = os.path.join(self.cfg.MT5_COMMON_FILES_PATH, self.cfg.MT5_NEWS_FILE)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.log.info("news_block.json exporté vers Common/Files : %s", data)
        except IOError as e:
            self.log.error("Export failed: %s", e)

    def _load_cache_events(self) -> list:
        """Load previously cached events from disk as a fallback."""
        try:
            if not os.path.exists(self.cfg.CACHE_FILE):
                return []
            with open(self.cfg.CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if not isinstance(cache, list) or not cache:
                return []
            events = []
            for item in cache:
                try:
                    impact = Impact[item.get("impact", "LOW")]
                    dt = datetime.fromisoformat(item["dt"])
                    events.append(NewsEvent(
                        eid=item["eid"], title=item["title"],
                        currency=item["currency"], impact=impact,
                        dt=dt, actual=item.get("actual")
                    ))
                except Exception:
                    continue
            return events
        except Exception:
            return []

    def _save_cache(self):
        try:
            with self._lock:
                cache = [
                    {"eid": e.eid, "title": e.title, "currency": e.currency,
                     "impact": e.impact.name, "dt": e.dt.isoformat(), "actual": e.actual}
                    for e in self._events
                ]
            with open(self.cfg.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
            self.log.info("Cache saved: %d events", len(cache))
        except IOError:
            pass

    # ── Rapport ────────────────────────────────────────────────────

    def schedule_text(self, hours: int = 24) -> str:
        events = self.get_upcoming(hours)
        if not events:
            return f"  Aucune news HIGH dans les {hours}h a venir"
        lines = [f"  Calendrier HIGH — {hours}h:"]
        for e in events:
            tier = " [T1]" if any(kw.lower() in e.title.lower() for kw in TIER1_KEYWORDS) else ""
            lines.append(
                f"  {e.dt.strftime('%d/%m %H:%M')} UTC"
                f"  [{e.currency}]"
                f"  {e.title[:40]:<40}"
                f"  dans {e.minutes_until:.0f}min{tier}"
            )
        return "\n".join(lines)

    def status_report(self) -> str:
        with self._lock:
            total = len(self._events)
            high  = sum(1 for e in self._events if e.impact == Impact.HIGH)
        return "\n".join([
            "  == NewsFilter Status ==",
            f"  Events charges:      {total}  ({high} HIGH / {total-high} MEDIUM+LOW)",
            f"  Bloquages total:     {self.blocks_triggered}",
            f"  Dernier bloquage:    {self.last_blocked.title if self.last_blocked else 'Aucun'}",
            f"  Dernier refresh:     {self._last_ref.strftime('%H:%M:%S UTC') if self._last_ref != datetime.min else 'N/A'}",
            self.schedule_text(24),
        ])


# ══════════════════════════════════════════════════════════════════
#  SNIPPET MQL5 — A copier dans Aladdin_Pro_V6.00.mq5
# ══════════════════════════════════════════════════════════════════
MQL5_SNIPPET = """
// Ajouter dans OnTick(), AVANT la boucle de scan des signaux:

bool IsNewsBlocked(string symbol)
{
   string path = "news_block.json";
   if(!FileIsExist(path)) return false;
   
   int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) return false;
   
   string content = "";
   while(!FileIsEnding(h)) content += FileReadString(h);
   FileClose(h);
   
   // Cherche le symbole dans le JSON "blocked"
   string search = "\\"" + symbol + "\\"";
   int pos = StringFind(content, search);
   if(pos < 0) return false;
   
   // Vérifie "blocked": true
   int bl_pos = StringFind(content, "\\"blocked\\":true", pos);
   return (bl_pos > pos && bl_pos < pos + 200);
}

// Dans OnTick(), avant ExecuteEntry():
if(BlockNewsWindow && IsNewsBlocked(symbols[i].symbol))
{
   if(EnableLogs)
      Print("[NEWS BLOCK] ", symbols[i].symbol, " — Trade suspendu (news imminente)");
   continue;
}
"""

# ══════════════════════════════════════════════════════════════════
#  TEST STANDALONE
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    print("\n" + "="*60)
    print("  ALADDIN PRO — NewsFilter Daemon Mode")
    print("="*60)

    nf = NewsFilter(mt5_path=NewsConfig.MT5_COMMON_FILES_PATH)
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Actualisation du calendrier...")
            nf._refresh()
            print(nf.status_report())
        except Exception as e:
            print(f"Erreur lors de l'actualisation : {e}")
        
        time.sleep(NewsConfig.REFRESH_INTERVAL_SEC)
