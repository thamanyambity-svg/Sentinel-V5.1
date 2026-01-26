"""
OHLC.Dev Unified Client
=======================
Integrates multiple RapidAPI sources to provide comprehensive market intelligence:
1. Market Reaper (trading-api4): News, Calendar, Signals
2. Real-Time Finance (real-time-finance-data): OHLC v Candles, Prices

Unified interface for the bot to easy access all data.
"""
import os
import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class OHLCClient:
    """
    Unified client for OHLC.Dev ecosystem.
    """
    
    # Hosts
    HOST_INTELLIGENCE = "trading-api4.p.rapidapi.com"
    HOST_MARKET_DATA = "real-time-finance-data.p.rapidapi.com"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY")
        if not self.api_key:
            raise ValueError("RAPIDAPI_KEY is required. Set it in .env")
            
        self._client: Optional[httpx.AsyncClient] = None
        
    async def _ensure_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
            
    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get(self, host: str, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Generic GET request handling switching hosts."""
        await self._ensure_client()
        
        url = f"https://{host}/{endpoint}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": host
        }
        
        try:
            response = await self._client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            # Handle specific API errors gracefully
            error_msg = f"HTTP {e.response.status_code} from {host}: {e.response.text[:200]}"
            logger.error(error_msg)
            
            # Identify rate limits
            if e.response.status_code == 429:
                logger.warning("⚠️ RapidAPI Rate Limit Hit!")
                
            return {"error": error_msg, "status_code": e.response.status_code}
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return {"error": str(e)}

    # ========================================================
    # 🧠 MARKET INTELLIGENCE (News, Calendar, Sentiment)
    # Source: Market Reaper (trading-api4)
    # ========================================================

    async def get_headlines(self) -> List[Dict]:
        """Get latest market headlines."""
        data = await self._get(self.HOST_INTELLIGENCE, "headlines")
        if isinstance(data, list):
            return data
        return data.get('data', []) if 'data' in data else []

    async def get_calendar(self) -> List[Dict]:
        """Get economic calendar events."""
        data = await self._get(self.HOST_INTELLIGENCE, "calendar")
        # Ensure we return a list, some APIs return wrapped dicts
        if isinstance(data, list):
            return data
        return []

    # ========================================================
    # 🕯️ MARKET DATA (Prices, Candles)
    # Source: Real-Time Finance (real-time-finance-data)
    # ========================================================

    async def get_candles(self, symbol: str, period: str = "1D", language: str = "en") -> Dict[str, Any]:
        """
        Get OHLCV Candles.
        
        :param symbol: Ticker symbol (e.g., 'AAPL', 'EURUSD').
        :param period: Timeframe. Valid: 1D, 5D, 1M, 6M, YTD, 1Y, 5Y, MAX.
        :return: Dict with 'time_series' data.
        """
        # 1. SPECIAL COMMODITIES (Gold/Silver)
        if symbol in ["GOLD", "XAUUSD"]:
            params = {"from_symbol": "XAU", "to_symbol": "USD", "period": period, "language": language}
            return await self._get(self.HOST_MARKET_DATA, "currency-time-series", params)

        # 2. FOREX ROUTING (Majors + Minors + Exotics)
        # Check explicit list or standard 6-char length for currencies
        is_forex = symbol in ["USDCNH", "USDSEK"] # Explicit Exotics
        if not is_forex and len(symbol) == 6 and symbol.isupper() and not symbol.isalpha() == False:
             # Basic heuristic: 6 upper chars might be forex (risky for tickers like GOOGLE? No, GOOG is 4, GOOGL is 5. Tickers can be 6)
             # Better to stick to known pairs if possible, or assume 6-char is forex if not a known stock.
             # Safe approach: Expand the list greatly.
             pass
             
        known_forex = [
            "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
            "USDCNH", "USDSEK", "EURGBP", "EURJPY", "GBPJPY"
        ]
        
        if symbol in known_forex:
            from_sym = symbol[:3]
            to_sym = symbol[3:]
            params = {"from_symbol": from_sym, "to_symbol": to_sym, "period": period, "language": language}
            return await self._get(self.HOST_MARKET_DATA, "currency-time-series", params)
            
        # 3. STOCK ROUTING (Default)
        # NVDA, AAPL, etc.
        params = {
            "symbol": symbol,
            "period": period,
            "language": language
        }
        return await self._get(self.HOST_MARKET_DATA, "stock-time-series", params)

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get the latest price for a symbol."""
        data = await self.get_candles(symbol, period="1D")
        if "data" in data and "price" in data["data"]:
            return float(data["data"]["price"])
        return None

# ========================================================
# 🧪 TEST HARNESS
# ========================================================

async def test_unified():
    print("🚀 Initializing Unified OHLC Client...")
    client = OHLCClient()
    
    try:
        # 1. Intelligence
        print("\n📰 Fetching Headlines...")
        news = await client.get_headlines()
        print(f"   Success: Found {len(news)} articles.")
        if news: print(f"   Latest: {news[0].get('title', 'No Title')}")

        # 2. Market Data
        symbol = "AAPL"
        print(f"\n🕯️ Fetching Candles for {symbol}...")
        candles = await client.get_candles(symbol)
        
        if "data" in candles:
            price = candles["data"].get("price")
            print(f"   Success: Current Price = ${price}")
            ts = candles["data"].get("time_series", {})
            print(f"   Datapoints: {len(ts)}")
        else:
            print(f"   Failed: {candles}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.close()
        print("\n✅ Unified Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_unified())
