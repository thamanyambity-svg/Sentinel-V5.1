"""
MT5 Direct Data Client
======================
Uses the existing MT5 Bridge to fetch REAL-TIME broker prices from XM.
This replaces Yahoo Finance to eliminate slippage and delays.

Data Source: ticks.json (updated by Sentinel EA every second)
"""
import json
import os
import logging
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime, time

logger = logging.getLogger(__name__)

class MT5DataClient:
    """
    Production-grade data client using direct MT5 broker feed.
    """
    
    # Maximum allowed spreads (units: Pips for Forex, Dollars/Cents for Commodities/Stocks)
    MAX_SPREAD = {
        "EURUSD": 3.0,    # 3.0 pips
        "GBPUSD": 4.0,    # 4.0 pips
        "USDJPY": 3.0,    # 3.0 pips
        "GOLD": 60.0,     # 60 points/cents ($0.60)
        "XAUUSD": 60.0,
        "Nvidia": 3.0,    # $3.00 spread
        "Apple": 2.0,     # $2.00 spread
        "BTCUSD": 500.0,  # $5.00 spread (adjusted for points)
        "ETHUSD": 100.0,  # $1.00 spread
    }
    
    # Market hours (UTC) - US Stocks: 14:30 - 21:00 UTC
    MARKET_HOURS = {
        "EURUSD": {"always": True},
        "GOLD": {"always": True},
        "Nvidia": {"open": time(14, 30), "close": time(21, 0)},
        "Apple": {"open": time(14, 30), "close": time(21, 0)},
        "BTCUSD": {"always": True},
        "ETHUSD": {"always": True},
    }
    
    def __init__(self, ticks_file=None):
        self.ticks_file = ticks_file or os.path.join(
            os.getenv("MT5_FILES_PATH", "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"),
            "ticks_v3.json"
        )
        logger.info(f"🔌 MT5DataClient: Connected to {self.ticks_file}")
        
        # MEMORY FOR VELOCITY CALCULATION
        self.price_memory = {}
        
    async def get_headlines(self) -> list:
        """Minimal interface compatibility"""
        return []
    
    async def get_calendar(self) -> list:
        """Minimal interface compatibility"""
        return []
    
    async def get_candles(self, symbol: str, period: str = "1D") -> Dict[str, Any]:
        """
        Get real-time tick data from MT5 broker.
        Returns format compatible with MarketIntelligence.
        """
        try:
            # Map readable names to MT5 symbols
            mt5_symbol = self._map_to_mt5(symbol)
            
            # Check market hours FIRST
            if not await self._is_market_open(symbol):
                logger.warning(f"⏸️ Market closed for {symbol}")
                return {"error": "Market Closed"}
            
            # Read status.json for live prices
            tick_data = await self._read_broker_status(mt5_symbol)
            
            if not tick_data:
                logger.warning(f"⚠️ No tick data for {mt5_symbol}")
                return {"error": "No Data"}
            
            bid = tick_data.get("bid", 0)
            ask = tick_data.get("ask", 0)
            spread_points = tick_data.get("spread", 999)
            
            # Convert spread to pips/dollars
            spread_value = self._calculate_spread(mt5_symbol, spread_points)
            
            # CRITICAL: Reject if spread too high
            max_allowed = self.MAX_SPREAD.get(symbol, self.MAX_SPREAD.get(mt5_symbol, 100.0))
            if spread_value > max_allowed:
                logger.warning(f"⛔ Spread too high for {symbol}: {spread_value:.2f} > {max_allowed}")
                return {"error": f"Spread too high: {spread_value:.2f}"}
            
            # Use Bid as "price" (conservative for BUY signals)
            current_price = bid
            
            # Calculate change from previous close (if available)
            prev_close = tick_data.get("previous_close", bid)
            change_pct = 0.0
            if prev_close > 0:
                change_pct = ((current_price - prev_close) / prev_close) * 100
            
            return {
                "data": {
                    "price": current_price,
                    "exchange_rate": current_price,
                    "change_percent": change_pct,
                    "bid": bid,
                    "ask": ask,
                    "spread": spread_value,
                    "valid": True,
                    "source": "MT5_BROKER"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ MT5 Data Error ({symbol}): {e}")
            return {"error": str(e)}
    
    # Noms alternatifs pour retrouver le symbole dans ticks (broker peut utiliser R_100, Volatility 100 Index, etc.)
    SYMBOL_ALIASES = {
        "Volatility 100 Index": ["Volatility 100 Index", "R_100", "Volatility 100 (1s) Index", "1HZ100V"],
        "Volatility 75 Index": ["Volatility 75 Index", "R_75", "Volatility 75 (1s) Index", "1HZ75V"],
        "GOLD": ["GOLD", "XAUUSD", "XAUUSDm", "XAUUSD.a"],
        "XAUUSD": ["XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.a"],
    }

    def _map_to_mt5(self, symbol: str) -> str:
        """Map user-friendly names to MT5 broker symbols (BROKER-SPECIFIC)"""
        MAPPING = {
            "GOLD": "GOLD",      # Your broker uses "GOLD" literally
            "Nvidia": "Nvidia",  # Exact name from Market Watch
            "Apple": "Apple",    # Exact name from Market Watch
        }
        return MAPPING.get(symbol, symbol)
    
    async def _read_broker_status(self, symbol: str) -> Optional[Dict]:
        """Read real-time tick data from ticks_v3.json with race condition protection"""
        try:
            if not os.path.exists(self.ticks_file):
                logger.debug(f"Ticks file not found: {self.ticks_file}")
                return None
            
            # Run file I/O in thread pool
            loop = asyncio.get_running_loop()
            
            def read():
                try:
                    with open(self.ticks_file, 'r') as f:
                        return json.load(f)
                except json.JSONDecodeError:
                    # Race condition: MQL5 is writing, file is temporarily corrupt
                    # Return None and retry next cycle (10s later)
                    logger.debug("Race condition detected: JSON read collision, skipping cycle")
                    return None
            
            ticks = await loop.run_in_executor(None, read)
            
            if not ticks:
                return None

            # Support two formats:
            # Old Sentinel format:  {"t":..., "ticks": {"Volatility 100 Index": 1122.02, ...}}
            # New AladdinPro V7.19: [{"sym":"XAUUSD","bid":...,"ask":...,"spread":...,"imbalance":...,"t":...}, ...]
            price = None
            bid = None
            ask = None
            spread_val = 0
            resolved_symbol = symbol

            if isinstance(ticks, list):
                # AladdinPro V7.19 array format
                aliases = [symbol] + list(self.SYMBOL_ALIASES.get(symbol, []))
                for entry in ticks:
                    if entry.get("sym") in aliases:
                        bid = float(entry.get("bid", 0) or 0)
                        ask = float(entry.get("ask", bid) or bid)
                        spread_val = float(entry.get("spread", 0) or 0)
                        price = bid if bid else ask
                        resolved_symbol = entry.get("sym", symbol)
                        break
            else:
                # Old Sentinel dict format
                tick_values = ticks.get("ticks", {})
                if symbol in tick_values:
                    price = tick_values[symbol]
                elif symbol in self.SYMBOL_ALIASES:
                    for alias in self.SYMBOL_ALIASES[symbol]:
                        if alias in tick_values:
                            price = tick_values[alias]
                            resolved_symbol = alias
                            break
                bid = price
                ask = price

            if price is None:
                logger.debug(f"Symbol {symbol} not found in ticks_v3.json")
                return None

            # VELOCITY CALCULATION (Since Sentinel doesn't give previous close)
            # We use the LAST SEEN price in memory as the "previous" reference
            # If not in memory, we use current price (0% change initially)
            prev_price = self.price_memory.get(symbol, price)
            self.price_memory[symbol] = price

            return {
                "bid": bid if bid else price,
                "ask": ask if ask else price,
                "spread": spread_val,
                "previous_close": prev_price  # Now we have REAL previous price!
            }
            
        except Exception as e:
            logger.error(f"Error reading ticks_v3.json: {e}")
            return None
    
    def _calculate_spread(self, symbol: str, spread_points: float) -> float:
        """
        Convert spread points to human-readable units.
        - Forex: Points to Pips (usually 10 points = 1 pip)
        - Others: Points to Decimal/Dollar value
        """
        # Forex 6-char pairs (EURUSD, USDJPY, etc)
        if len(symbol) == 6 and not symbol.isdigit():
            return spread_points / 10.0 # Standard for 5-decimal brokers (XM)
            
        # GOLD (XAUUSD) - 1 point is usually 0.01 USD
        if "GOLD" in symbol or "XAU" in symbol:
            return spread_points # Return in cents (e.g. 45 pts = 45 cents)
            
        # Stocks & Crypto - 1 point is usually 0.01 USD if Digits=2
        return spread_points / 100.0 # Return in dollars/units
    
    async def _is_market_open(self, symbol: str) -> bool:
        """Check if market is currently open for trading"""
        hours = self.MARKET_HOURS.get(symbol, {"always": True})
        
        if hours.get("always"):
            return True
        
        # Check current UTC time
        now = datetime.utcnow().time()
        market_open = hours.get("open")
        market_close = hours.get("close")
        
        if market_open and market_close:
            return market_open <= now <= market_close
        
        return True  # Default: allow
    
    async def close(self):
        """Cleanup (nothing to close for file-based client)"""
        pass
