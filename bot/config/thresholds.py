"""
Institutional Thresholds Configuration
Calibrated for M1/M5 synthetic indices
Target: Max Drawdown ≤ 10%
"""

# ============================================================================
# 1. REGIME DETECTOR THRESHOLDS
# ============================================================================

REGIME_THRESHOLDS = {
    # ATR Percentile (rolling 500-1000 bars)
    "atr_percentile": {
        "low": 25,           # ≤ 25 = low volatility
        "normal": 50,        # 25-50 = normal
        "high": 75,          # 50-75 = elevated
        # > 75 = extreme
    },
    
    # ADX (directional structure)
    "adx": {
        "range_pure": 15,         # < 15 = pure range
        "range_unstable": 22,     # 15-22 = unstable range
        "trend_exploitable": 35,  # 22-35 = tradeable trend
        # > 35 = strong but risky
    },
    
    # Vol-of-Vol (normalized)
    # Formula: std(ATR / EMA(ATR, 20)) over 20-30 bars
    "vol_of_vol": {
        "stable": 0.20,       # < 0.20 = stable
        "transition": 0.35,   # 0.20-0.35 = transition
        "unstable": 0.50,     # 0.35-0.50 = unstable
        # ≥ 0.50 = CHAOS
    },
    
    # Hysteresis
    "hysteresis_bars": 5,  # Require 5 consecutive bars for regime change
    "chaos_override": True,  # CHAOS = immediate (1 bar)
}

# Regime Mapping Logic
REGIME_RULES = {
    "RANGE_CALM": {
        "atr_percentile": {"max": 25},
        "adx": {"max": 20},
        "vol_of_vol": {"max": 0.20}
    },
    "TREND_STABLE": {
        "adx": {"min": 22, "max": 35},
        "vol_of_vol": {"max": 0.30}
    },
    "TRANSITION": {
        "vol_of_vol": {"min": 0.20, "max": 0.35},
        # OR conflicting indicators
    },
    "CHAOS": {
        "vol_of_vol": {"min": 0.50},
        # OR atr_percentile > 75
    }
}

# ============================================================================
# 2. AGENT 1 - REGIME AUDITOR (VETO)
# ============================================================================

AGENT_REGIME_AUDITOR = {
    "veto_thresholds": {
        "vol_of_vol_chaos": 0.45,  # VoV ≥ 0.45 → CHAOS vote
        "adx_high": 30,             # ADX > 30 + ATR > 60 → TRANSITION
        "atr_high": 60,
    },
    "confidence_thresholds": {
        "strong_signal": 0.80,  # ≥ 0.80 = high confidence
        "caution": 0.60,        # < 0.60 = favor blocking
    }
}

# ============================================================================
# 3. AGENT 4 - VOLATILITY STRUCTURE ANALYST
# ============================================================================

AGENT_VOLATILITY_STRUCTURE = {
    "atr_periods": {
        "short": 14,
        "medium": 50,
        "long": 100
    },
    "acceleration_threshold": 0.30,  # ΔATR > +30% in < 5 bars = explosive
    "acceleration_window": 5,
    
    "state_mapping": {
        "compressed": {"risk_bias": "neutral"},
        "expanding": {"risk_bias": "reduce"},
        "explosive": {"risk_bias": "block"}  # VETO
    }
}

# ============================================================================
# 4. AGENT 5 - SIGNAL QUALITY ASSESSOR
# ============================================================================

AGENT_SIGNAL_QUALITY = {
    # Risk/Reward scoring
    "rr_scores": {
        "below_1_2": 0,
        "1_2_to_1_5": 20,
        "1_5_to_2_0": 35,
        "above_2_0": 50
    },
    
    # Context bonuses/penalties
    "context_modifiers": {
        "regime_aligned": +20,
        "transition": -15,
        "chaos": -50,
        "low_win_rate": -20  # < 40% win rate
    },
    
    # Decision thresholds
    "score_thresholds": {
        "reject": 60,        # < 60 = REJECT
        "reduce_size": 75,   # 60-75 = accept with reduced size
        # > 75 = normal size
    },
    
    "win_rate_threshold": 0.40,  # 40% minimum
    "rolling_window": 20  # Last 20 similar signals
}

# ============================================================================
# 5. AGENT 2 - RISK BEHAVIOR ANALYST
# ============================================================================

AGENT_RISK_BEHAVIOR = {
    "loss_clustering": {
        "warning_threshold": 2,  # 2 consecutive SL same regime → WARNING
        "halt_threshold": 3,     # 3 consecutive SL same regime → HALT
        "global_halt": 4         # 4 consecutive SL overall → HALT
    },
    
    "cooldown_periods": {
        "warning": {"hours": 0, "risk_multiplier": 0.5},
        "halt": {"hours": 12, "risk_multiplier": 0.0}
    },
    
    "overtrading_detection": {
        "enabled": True,
        "time_between_trades_threshold": 0.5  # Decreasing time after SL = WARNING
    }
}

# ============================================================================
# 6. AGENT 6 - STRATEGY DRIFT MONITOR
# ============================================================================

AGENT_STRATEGY_DRIFT = {
    "drift_metrics": {
        "win_rate_degradation": 0.30,  # -30% vs backtest
        "skew_threshold": 0.20,         # Negative skew > 20%
        "dd_multiplier": 1.5            # Local DD > 1.5x expected
    },
    
    "severity_mapping": {
        "low": 1,      # 1 metric triggered
        "medium": 2,   # 2 metrics triggered
        "high": 3      # 3 metrics triggered → disable strategy
    }
}

# ============================================================================
# 7. AGENT 3 - EXECUTION SENTINEL
# ============================================================================

AGENT_EXECUTION_SENTINEL = {
    "spread_threshold": 1.8,      # > 1.8x median spread → block
    "slippage_threshold": 1.0,    # > 1 ATR tick → block
    "tick_rate_threshold": 2.5,   # > 2.5x normal → block
    "latency_threshold": 2.0,     # > 2x average latency → block
    
    "rolling_window": 100  # For median/average calculations
}

# ============================================================================
# 8. RISK ENGINE - FINAL GATE
# ============================================================================

RISK_ENGINE = {
    # Base risk per trade
    "base_risk_percent": 0.20,  # 0.20% of equity
    
    # Risk multipliers
    "risk_multipliers": {
        "transition_regime": 0.5,
        "warning_behavior": 0.5,
        "max_cumulative": 0.25  # Maximum cumulative reduction
    },
    
    # Kill-Switch thresholds
    "kill_switch": {
        "dd_24h_percent": 2.0,      # > 2% → halt 24h
        "dd_session_percent": 3.0,  # > 3% → halt session
        "dd_global_reduce": 8.0,    # > 8% → risk × 0.5
        "dd_global_hard_stop": 9.5  # ≥ 9.5% → HARD STOP
    },
    
    # Position sizing
    "position_cap_percent": 1.5,  # Max 1.5% of equity per position
}

# ============================================================================
# 9. DEFENSIVE PHILOSOPHY
# ============================================================================

PHILOSOPHY = {
    "rejection_rate_target": 0.30,  # Aggressive: Take more trades
    "asymmetry": "aggressive",       # Trade early
    "tail_risk": "synthetic_aware", # Calibrated for fat tails
    "auditability": "full",         # Every decision traceable
    "magic_numbers": False          # All thresholds justified
}
