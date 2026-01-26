
import logging
import asyncio
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

class YFinanceClient:
    """
    Unlimited Data Feed via Yahoo Finance.
    Drop-in replacement for OHLCClient during API outages.
    """
    
    def __init__(self):
        self.logger = logger

    async def get_headlines(self) -> list:
        # Minimal implementation to satisfy interface
        return []

    async def get_calendar(self) -> list:
        return []

    async def get_candles(self, symbol: str, period: str = "1D") -> dict:
        """
        Fetch real-time data from Yahoo Finance.
        Maps Sentinel symbols to YF Tickers.
        """
        yf_symbol = self._map_symbol(symbol)
        
        try:
            # Run blocking I/O in thread pool to keep bot async
            loop = asyncio.get_running_loop()
            
            def fetch():
                ticker = yf.Ticker(yf_symbol)
                # 1m interval for the last day
                return ticker.history(period="1d", interval="1m")
            
            hist = await loop.run_in_executor(None, fetch)
            
            if hist.empty:
                self.logger.warning(f"⚠️ YFinance: No data for {symbol} ({yf_symbol})")
                return {"error": "Empty Data"}
                
            # Extract latest data
            last_close = float(hist["Close"].iloc[-1])
            open_price = float(hist["Open"].iloc[0]) # Open of the '1d' period (Market Open)
            
            if len(hist) > 1:
                # Better change calculation: (Last - PrevClose) / PrevClose
                # But 'Open' of day is good for 'DoD Change'
                pass
                
            change_pct = 0.0
            if open_price > 0:
                change_pct = ((last_close - open_price) / open_price) * 100
            
            return {
                "data": {
                    "price": last_close,
                    "exchange_rate": last_close, # Dual key for compatibility
                    "change_percent": change_pct,
                    "trend": "CALCULATED",
                    "valid": True
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ YFinance Error ({symbol}): {e}")
            return {"error": str(e)}

    def _map_symbol(self, s: str) -> str:
        """Map generic symbols to Yahoo Tickers"""
        s = s.upper()
        
        # 1. SPECIFIC MAPPINGS (Priority)
        MAPPING = {
            "GOLD": "GC=F",
            "XAUUSD": "GC=F",
            "NVIDIA": "NVDA",
            "APPLE": "AAPL",
            "USDCNH": "CNH=X",
            "USDSEK": "SEK=X",
            "EURUSD": "EURUSD=X",
        }
        if s in MAPPING:
            return MAPPING[s]

        # 2. GENERIC FOREX (If 6 chars, uppercase, and not in mapping)
        if len(s) == 6 and s.isalpha():
             return f"{s}=X"
             
        # 3. DEFAULT (Return as is)
        return s

    async def close(self):
        pass # Nothing to close
