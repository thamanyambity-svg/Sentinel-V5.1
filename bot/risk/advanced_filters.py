"""
Advanced Trading Filters
Implements RSI Extreme Gate, Trade Frequency Governor, Post-Rejection Cooldown, and Market Fatigue Detector
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("ADVANCED_FILTERS")

class RSIExtremeGate:
    """
    RSI Extreme Gate - Only allow mean reversion trades at extreme RSI levels
    Prevents over-trading in wide ranges
    """
    
    RSI_OVERBOUGHT = 65  # RSI > 65 → aggressive short
    RSI_OVERSOLD = 35    # RSI < 35 → aggressive long
    
    @staticmethod
    def is_allowed(rsi: float, signal_side: str, regime: str) -> tuple[bool, str]:
        """
        Check if RSI is extreme enough for mean reversion trade
        
        Args:
            rsi: Current RSI value
            signal_side: "CALL" or "PUT"
            regime: Current market regime
            
        Returns:
            (allowed: bool, reason: str)
        """
        # Only apply in RANGE_CALM
        if regime != "RANGE_CALM":
            return True, "Not in RANGE_CALM"
        
        # Long (CALL or BUY) only when oversold
        if signal_side in ("CALL", "BUY"):
            if rsi < RSIExtremeGate.RSI_OVERSOLD:
                return True, f"RSI oversold ({rsi:.1f} < {RSIExtremeGate.RSI_OVERSOLD})"
            else:
                return False, f"RSI not oversold enough ({rsi:.1f} >= {RSIExtremeGate.RSI_OVERSOLD})"
        
        # Short (PUT or SELL) only when overbought
        elif signal_side in ("PUT", "SELL"):
            if rsi > RSIExtremeGate.RSI_OVERBOUGHT:
                return True, f"RSI overbought ({rsi:.1f} > {RSIExtremeGate.RSI_OVERBOUGHT})"
            else:
                return False, f"RSI not overbought enough ({rsi:.1f} <= {RSIExtremeGate.RSI_OVERBOUGHT})"
        
        return False, f"Unknown signal side: {signal_side}"


class TradeFrequencyGovernor:
    """
    Trade Frequency Governor - Limit trades per session per symbol
    Prevents over-trading and chasing on single asset
    """
    
    MAX_TRADES_PER_SESSION_PER_SYMBOL = 10
    SESSION_DURATION_HOURS = 8  # Reset every 8 hours
    
    def __init__(self):
        self.session_trades: Dict[str, List[datetime]] = {}
        self.session_start = datetime.now(timezone.utc)
    
    def is_allowed(self, symbol: str) -> tuple[bool, str]:
        """
        Check if symbol has reached trade limit for current session
        
        Args:
            symbol: Trading symbol (e.g., "R_100")
            
        Returns:
            (allowed: bool, reason: str)
        """
        now = datetime.now(timezone.utc)
        
        # Reset session if expired
        if now - self.session_start > timedelta(hours=self.SESSION_DURATION_HOURS):
            self.session_trades = {}
            self.session_start = now
            logger.info("🔄 Trade frequency session reset")
        
        # Get trades for this symbol in current session
        symbol_trades = self.session_trades.get(symbol, [])
        
        # Check limit
        if len(symbol_trades) >= self.MAX_TRADES_PER_SESSION_PER_SYMBOL:
            return False, f"Session limit reached ({len(symbol_trades)}/{self.MAX_TRADES_PER_SESSION_PER_SYMBOL} trades on {symbol})"
        
        return True, f"Within limit ({len(symbol_trades)}/{self.MAX_TRADES_PER_SESSION_PER_SYMBOL})"
    
    def record_trade(self, symbol: str):
        """Record a trade for this symbol"""
        now = datetime.now(timezone.utc)
        if symbol not in self.session_trades:
            self.session_trades[symbol] = []
        self.session_trades[symbol].append(now)
        logger.info(f"📊 Trade recorded for {symbol}: {len(self.session_trades[symbol])}/{self.MAX_TRADES_PER_SESSION_PER_SYMBOL}")


class PostRejectionCooldown:
    """
    Post-Rejection Cooldown - Wait N bars after signal rejection
    Prevents immediate re-scanning when market is unstable
    """
    
    COOLDOWN_BARS = 1  # Wait only 1 bar
    
    def __init__(self):
        self.rejection_times: Dict[str, datetime] = {}
    
    def is_allowed(self, symbol: str) -> tuple[bool, str]:
        """
        Check if cooldown period has passed since last rejection
        
        Args:
            symbol: Trading symbol
            
        Returns:
            (allowed: bool, reason: str)
        """
        if symbol not in self.rejection_times:
            return True, "No recent rejection"
        
        last_rejection = self.rejection_times[symbol]
        now = datetime.now(timezone.utc)
        elapsed_minutes = (now - last_rejection).total_seconds() / 60
        
        if elapsed_minutes < self.COOLDOWN_BARS:
            remaining = self.COOLDOWN_BARS - int(elapsed_minutes)
            return False, f"Cooldown active ({remaining} bars remaining)"
        
        # Cooldown expired, remove from tracking
        del self.rejection_times[symbol]
        return True, "Cooldown expired"
    
    def record_rejection(self, symbol: str):
        """Record a signal rejection"""
        self.rejection_times[symbol] = datetime.now(timezone.utc)
        logger.info(f"⏸️ Cooldown started for {symbol} ({self.COOLDOWN_BARS} bars)")


class MarketFatigueDetector:
    """
    Market Fatigue Detector - Block trend following after multiple false breakouts
    Detects when market is producing fake signals
    """
    
    MAX_FALSE_BREAKOUTS = 5
    LOOKBACK_HOURS = 2       # Within last 2 hours
    BLOCK_DURATION_HOURS = 1 # Block for 1 hour
    
    def __init__(self):
        self.false_breakouts: Dict[str, List[datetime]] = {}
        self.blocked_until: Dict[str, datetime] = {}
    
    def is_allowed(self, symbol: str, regime: str) -> tuple[bool, str]:
        """
        Check if trend following is allowed (not fatigued)
        
        Args:
            symbol: Trading symbol
            regime: Current regime
            
        Returns:
            (allowed: bool, reason: str)
        """
        # Only applies to TREND_STABLE regime
        if regime != "TREND_STABLE":
            return True, "Not in TREND_STABLE"
        
        now = datetime.now(timezone.utc)
        
        # Check if currently blocked
        if symbol in self.blocked_until:
            if now < self.blocked_until[symbol]:
                remaining = (self.blocked_until[symbol] - now).total_seconds() / 60
                return False, f"Market fatigue block active ({int(remaining)} min remaining)"
            else:
                # Block expired
                del self.blocked_until[symbol]
                self.false_breakouts[symbol] = []
                logger.info(f"✅ Market fatigue block expired for {symbol}")
        
        # Count recent false breakouts
        if symbol in self.false_breakouts:
            # Remove old breakouts outside lookback window
            cutoff = now - timedelta(hours=self.LOOKBACK_HOURS)
            self.false_breakouts[symbol] = [
                ts for ts in self.false_breakouts[symbol] if ts > cutoff
            ]
            
            recent_count = len(self.false_breakouts[symbol])
            if recent_count >= self.MAX_FALSE_BREAKOUTS:
                # Trigger block
                self.blocked_until[symbol] = now + timedelta(hours=self.BLOCK_DURATION_HOURS)
                logger.warning(f"🚫 Market fatigue detected for {symbol}: {recent_count} false breakouts → blocking for {self.BLOCK_DURATION_HOURS}h")
                return False, f"Market fatigue ({recent_count} false breakouts)"
        
        return True, "No fatigue detected"
    
    def record_false_breakout(self, symbol: str):
        """Record a false breakout (trade that hit SL quickly)"""
        now = datetime.now(timezone.utc)
        if symbol not in self.false_breakouts:
            self.false_breakouts[symbol] = []
        self.false_breakouts[symbol].append(now)
        logger.warning(f"⚠️ False breakout recorded for {symbol} ({len(self.false_breakouts[symbol])} recent)")


class AdvancedFilterManager:
    """
    Central manager for all advanced filters
    Coordinates RSI Gate, Frequency Governor, Cooldown, and Fatigue Detector
    """
    
    def __init__(self):
        self.rsi_gate = RSIExtremeGate()
        self.frequency_governor = TradeFrequencyGovernor()
        self.cooldown = PostRejectionCooldown()
        self.fatigue_detector = MarketFatigueDetector()
    
    def validate_signal(
        self,
        symbol: str,
        signal_side: str,
        rsi: float,
        regime: str,
        signal_type: str
    ) -> tuple[bool, str]:
        """
        Run all advanced filters on a signal
        
        Args:
            symbol: Trading symbol
            signal_side: "CALL" or "PUT"
            rsi: Current RSI
            regime: Current regime
            signal_type: "MEAN_REVERSION" or "TREND_FOLLOWING"
            
        Returns:
            (approved: bool, rejection_reason: str)
        """
        # 1. RSI Extreme Gate (for mean reversion in RANGE_CALM)
        if signal_type == "MEAN_REVERSION":
            allowed, reason = self.rsi_gate.is_allowed(rsi, signal_side, regime)
            if not allowed:
                logger.info(f"🛡️ [RSI GATE] {symbol} rejected: {reason}")
                self.cooldown.record_rejection(symbol)
                return False, f"RSI Gate: {reason}"
        
        # 2. Trade Frequency Governor
        allowed, reason = self.frequency_governor.is_allowed(symbol)
        if not allowed:
            logger.warning(f"🛡️ [FREQUENCY] {symbol} rejected: {reason}")
            self.cooldown.record_rejection(symbol)
            return False, f"Frequency: {reason}"
        
        # 3. Post-Rejection Cooldown
        allowed, reason = self.cooldown.is_allowed(symbol)
        if not allowed:
            logger.info(f"🛡️ [COOLDOWN] {symbol} rejected: {reason}")
            return False, f"Cooldown: {reason}"
        
        # 4. Market Fatigue Detector (for trend following)
        if signal_type == "TREND_FOLLOWING":
            allowed, reason = self.fatigue_detector.is_allowed(symbol, regime)
            if not allowed:
                logger.warning(f"🛡️ [FATIGUE] {symbol} rejected: {reason}")
                self.cooldown.record_rejection(symbol)
                return False, f"Fatigue: {reason}"
        
        # All filters passed
        return True, "All advanced filters passed"
    
    def record_trade_executed(self, symbol: str):
        """Record that a trade was executed"""
        self.frequency_governor.record_trade(symbol)
    
    def record_trade_stopped_out(self, symbol: str, duration_minutes: float):
        """Record that a trade was stopped out (potential false breakout)"""
        # If stopped out within 15 minutes, consider it a false breakout
        if duration_minutes < 15:
            self.fatigue_detector.record_false_breakout(symbol)
