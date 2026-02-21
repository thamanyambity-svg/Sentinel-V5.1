"""
Market Intelligence Module
==========================
The "Cortex" of the trading bot.
Aggregates data from OHLC.Dev (News, Calendar, Prices) to form a coherent market view.
Replaces the legacy 'MarketStructure' and 'SignalQuality' checks with institutional-grade data.
"""
import asyncio
import logging
import os
from typing import Dict, Optional, List, Any
# V5.1: Direct MT5 broker feed (real-time prices)
from bot.data.mt5_data_client import MT5DataClient

logger = logging.getLogger(__name__)

class MarketIntelligence:
    """
    Advanced centralized market analysis.
    """
    
    def __init__(self):
        # V5.1: Switched to MT5 Direct Feed for live trading
        self.client = MT5DataClient()
        logger.info("🧠 MarketIntelligence: MT5 Broker Feed Active")
        self.last_analysis: Dict[str, Any] = {}
        
    async def initialize(self):
        """
        Verify that the MT5 data feed is active.
        """
        logger.info("🎬 Initializing Market Intelligence...")
        # Check if the ticks file exists (at least once)
        if hasattr(self.client, 'ticks_file') and os.path.exists(self.client.ticks_file):
            logger.info("✅ Direct MT5 Data Feed (ticks.json) detected.")
        else:
            logger.info("ℹ️ Market Intelligence ready. Waiting for MT5 EA to generate ticks.json...")
    async def analyze_market_conditions(self) -> Dict[str, str]:
        """
        Broad risk analysis based on Calendar and Sentiment.
        Returns: { 'risk_level': 'LOW'|'MEDIUM'|'HIGH', 'narrative': ... }
        """
        try:
            # Parallel fetch
            headlines, calendar = await asyncio.gather(
                self.client.get_headlines(),
                self.client.get_calendar(),
                return_exceptions=True
            )
            
            # 1. Calendar Analysis (Risk of Volatility)
            risk_level = "LOW"
            risk_reasons = []
            
            if isinstance(calendar, list):
                # Simple logic: check for 'High' importance events today
                # Note: Real implementation needs date filtering
                high_impact = [e for e in calendar if e.get('importance', 0) >= 3]
                if high_impact:
                    risk_level = "HIGH"
                    risk_reasons.append(f"{len(high_impact)} High Impact Events")
            
            # 2. Sentiment Analysis (Narrative)
            sentiment_score = 0
            if isinstance(headlines, list):
                # Basic keyword sentiment
                # TODO: Connect to LLM for real sentiment analysis
                bullish_words = ['rise', 'jump', 'gain', 'up', 'bull', 'record']
                bearish_words = ['fall', 'drop', 'loss', 'down', 'bear', 'crash']
                
                for news in headlines[:10]: # Check top 10
                    title = news.get('title', '').lower()
                    if any(w in title for w in bullish_words): sentiment_score += 1
                    if any(w in title for w in bearish_words): sentiment_score -= 1
            
            global_sentiment = "NEUTRAL"
            if sentiment_score > 2: global_sentiment = "BULLISH"
            elif sentiment_score < -2: global_sentiment = "BEARISH"
            
            return {
                "risk_level": risk_level,
                "global_sentiment": global_sentiment,
                "reasons": risk_reasons,
                "sentiment_score": sentiment_score
            }
            
        except Exception as e:
            logger.error(f"Market Analysis Failed: {e}")
            return {"error": str(e), "risk_level": "HIGH"} # Default to High risk on error

    async def get_symbol_analysis(self, symbol: str) -> Dict[str, Any]:
        """
        Specific analysis for a symbol (Trend, Volatility).
        """
        try:
            candles = await self.client.get_candles(symbol, period="1D")
            
            if "error" in candles or "data" not in candles:
                return {"status": "UNKNOWN", "error": "No data"}
                
            data = candles["data"]
            # 1. Price Normalization (Stocks "price", Forex "exchange_rate")
            price = float(data.get("price", data.get("exchange_rate", 0)))
            
            # 2. Change % Normalization (Calculate if missing)
            change_pct = float(data.get("change_percent", 0))
            if change_pct == 0.0 and "previous_close" in data:
                prev = float(data["previous_close"])
                if prev > 0:
                    change_pct = ((price - prev) / prev) * 100
            
            # Volatility indices: seuils très bas (0.005% / 0.05%); Forex/stocks: 0.2% / 1%
            is_vol = "Volatility" in symbol or ("Index" in symbol and "Volatility" in str(symbol))
            th_weak = 0.005 if is_vol else 0.2
            th_strong = 0.05 if is_vol else 1.0
            trend = "RANGE"
            if change_pct > th_strong: trend = "STRONG_UP"
            elif change_pct > th_weak: trend = "WEAK_UP"
            elif change_pct < -th_strong: trend = "STRONG_DOWN"
            elif change_pct < -th_weak: trend = "WEAK_DOWN"
            
            return {
                "symbol": symbol,
                "price": price,
                "change_percent": change_pct,
                "trend": trend,
                "spread": data.get("spread", 0),
                "valid": True
            }
            
        except Exception as e:
            logger.error(f"Symbol Analysis Failed for {symbol}: {e}")
            return {"valid": False, "error": str(e)}

    async def close(self):
        await self.client.close()

# 🧪 Test Harness
async def test_intelligence():
    print("🧠 Starting Market Intelligence...")
    brain = MarketIntelligence()
    
    try:
        print("\n🌍 Analyzing Global Conditions...")
        conditions = await brain.analyze_market_conditions()
        print(f"   Risk Level: {conditions.get('risk_level')}")
        print(f"   Sentiment: {conditions.get('global_sentiment')} (Score: {conditions.get('sentiment_score')})")
        
        print("\n📈 Analyzing AAPL...")
        aapl = await brain.get_symbol_analysis("AAPL")
        print(f"   Trend: {aapl.get('trend')}")
        print(f"   Price: {aapl.get('price')}")
        
    finally:
        await brain.close()

if __name__ == "__main__":
    asyncio.run(test_intelligence())
