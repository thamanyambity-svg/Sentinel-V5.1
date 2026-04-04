"""
bot/quantum_hedge.py — Quantum-Bayesian Hedge Engine
=====================================================
Inspired by quantum superposition and Bayesian inference to model market
uncertainty and compute optimal hedge volume dynamically.

Concepts used (all classical statistics, quantum terminology used as metaphor):
- Market state |ψ⟩ = α|up⟩ + β|down⟩  (probability amplitudes from indicators)
- Bayesian reversal probability: P(reversal | observed_loss, signal)
- Volatility-scaled volume: V_hedge = V0 × (1 + k × |ΔP|) × (σ / σ_ref)
- Coupled stop-loss: SL_hedge limits combined max loss

Author: Ambity Project / Sentinel V5.3
"""

import math
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger("quantum_hedge")


class QuantumHedge:
    """
    Quantum-Bayesian hedge decision engine.

    Parameters
    ----------
    k : float
        Amplification factor for dynamic volume formula (default 2.0).
        Higher k = more aggressive hedge when signal is strong.
    bayes_threshold : float
        Minimum Bayesian reversal probability to trigger a hedge (default 0.65).
    atr_window : int
        Number of ATR readings kept to compute σ_ref (reference volatility).
    max_lot : float
        Hard cap on any hedge volume regardless of formula output.
    min_drawdown_trigger : float
        Minimum absolute floating loss (negative) before hedge is even evaluated.
        Safety gate — prevents triggering on noise.
    """

    def __init__(
        self,
        k: float = 2.0,
        bayes_threshold: float = 0.65,
        atr_window: int = 30,
        max_lot: float = 5.0,
        min_drawdown_trigger: float = -0.80,
        stop_factor: float = 2.0,        # SL couplé = atr × stop_factor
        max_combined_loss: float = 5.0,  # Perte combinée max acceptable ($)
    ):
        self.k = k
        self.bayes_threshold = bayes_threshold
        self.max_lot = max_lot
        self.min_drawdown_trigger = min_drawdown_trigger
        self.stop_factor = stop_factor
        self.max_combined_loss = max_combined_loss
        self._atr_history: deque = deque(maxlen=atr_window)

    # ------------------------------------------------------------------
    # 1. Market State: α (prob_up) and β (prob_down)
    # ------------------------------------------------------------------
    def compute_state(
        self,
        rsi: Optional[float],
        ai_score: float,      # 0.0 (strong sell) → 1.0 (strong buy)
        trend_momentum: float,  # % change recent (positive = up momentum)
        ai_signal: Optional[dict] = None,  # Optional: {'up': 0.6, 'down': 0.4} from IA
    ) -> tuple[float, float]:
        """
        Compute market probability amplitudes α (up) and β (down).

        Accepts either:
        - Scalar ai_score (0→1)
        - Dict ai_signal with 'up'/'down' keys (from IA signal output)
        - Dict ai_signal with 'score' key (-1→1 converted to 0→1)
        """
        # Resolve ai_score from dict if provided
        if ai_signal is not None:
            if 'score' in ai_signal:
                ai_score = (ai_signal['score'] + 1) / 2  # -1→1 → 0→1
            elif 'up' in ai_signal:
                ai_score = float(ai_signal['up'])

        # RSI normalization
        rsi_norm = ((rsi - 50) / 50 + 1) / 2 if rsi is not None else 0.5
        rsi_norm = max(0.0, min(1.0, rsi_norm))
        # Boost: RSI < 30 = oversold = bullish reversal likely
        if rsi is not None and rsi < 30:
            rsi_norm = min(1.0, rsi_norm + 0.15)
        elif rsi is not None and rsi > 70:
            rsi_norm = max(0.0, rsi_norm - 0.15)

        # Normalize momentum: tanh squashes to (-1, 1), then to (0, 1)
        momentum_norm = (math.tanh(trend_momentum * 10) + 1) / 2

        # Weighted composite probability of upward move
        prob_up = (
            0.50 * ai_score
            + 0.25 * rsi_norm
            + 0.25 * momentum_norm
        )
        prob_up = max(0.01, min(0.99, prob_up))  # Avoid extremes
        prob_down = 1.0 - prob_up

        # Normalize to unit sphere: |α|² + |β|² = 1
        norm = math.sqrt(prob_up ** 2 + prob_down ** 2)
        alpha = prob_up / norm
        beta = prob_down / norm

        return alpha, beta

    # ------------------------------------------------------------------
    # 2. Bayesian Reversal Probability
    # ------------------------------------------------------------------
    def bayes_update(
        self,
        floating_loss: float,    # Current P/L of losing position (negative)
        ai_score: float,         # AI confidence 0→1
        position_type: str,      # "BUY" or "SELL" (losing position)
    ) -> float:
        """
        Compute P(reversal | observed_loss, ai_signal).

        Using Bayes theorem:
            P(R|E) = P(E|R) × P(R) / P(E)

        Where:
        - P(R) = prior probability of reversal (from AI score)
        - P(E|R) = likelihood of this loss IF reversal is happening
                  (larger loss → more likely it's a sustained move, so
                   we use a sigmoid that peaks for moderate losses)
        - P(E|¬R) = likelihood of this loss if it's just noise
                   (small losses are common noise; very large ones are extremes)

        For a selling position (SELL losing = market went up):
          ai_score < 0.5 means AI sees downward pressure = reversal likely
        """
        loss = abs(floating_loss)

        # Prior: from AI signal
        # If BUY is losing (market going down), reversal means market going back up
        # High ai_score (AI bullish) → higher prior reversal probability
        if position_type == "BUY":
            prior = ai_score  # High AI bullish = likely reversal back up
        else:
            prior = 1.0 - ai_score  # High AI bearish = likely reversal back down

        prior = max(0.10, min(0.90, prior))

        # Likelihood P(E|R): sigmoid centered at -$1.50 loss
        # Peak likelihood at $1.50 loss (moderate drawdown = reversal zone)
        # Decreases for very large losses (might be a breakout, not reversal)
        peak_loss = 1.5
        likelihood_reversal = math.exp(-0.5 * ((loss - peak_loss) / 0.8) ** 2)

        # Likelihood P(E|¬R): exponential — noise loses are small, large ones rare
        likelihood_noise = math.exp(-loss / 0.5)  # Decays fast with loss size

        # Bayes: P(R|E) ∝ prior × likelihood
        numerator = prior * likelihood_reversal
        denominator = numerator + (1 - prior) * likelihood_noise

        if denominator == 0:
            return 0.0

        posterior = numerator / denominator
        return round(posterior, 4)

    # ------------------------------------------------------------------
    # 3. Hedge Decision Gate
    # ------------------------------------------------------------------
    def should_hedge(
        self,
        existing_profit: float,
        alpha: float,
        beta: float,
        position_type: str,
        ai_score: float,
    ) -> tuple[bool, float, str]:
        """
        Decide whether to open a hedge.

        Returns (should_hedge: bool, bayes_prob: float, reason: str)

        Gates (all must pass):
        1. Min drawdown: loss must exceed min_drawdown_trigger
        2. Direction alignment: β must be > α for BUY-losing (market going down)
        3. Bayesian threshold: P(reversal) > bayes_threshold
        """
        # Gate 1: Minimum loss requirement
        if existing_profit > self.min_drawdown_trigger:
            return False, 0.0, f"P/L {existing_profit:.2f} > trigger {self.min_drawdown_trigger}"

        # Gate 2: Signal alignment
        # If BUY is losing, we SELL. Need β (down) > α (up).
        if position_type == "BUY":
            signal_ok = beta > alpha
            delta_label = f"β={beta:.3f} > α={alpha:.3f}" if signal_ok else f"NOT aligned (α={alpha:.3f} dominant)"
        else:
            signal_ok = alpha > beta
            delta_label = f"α={alpha:.3f} > β={beta:.3f}" if signal_ok else f"NOT aligned (β={beta:.3f} dominant)"

        if not signal_ok:
            return False, 0.0, f"Signal not aligned for reversal: {delta_label}"

        # Gate 3: Bayesian probability
        p_reversal = self.bayes_update(existing_profit, ai_score, position_type)
        if p_reversal < self.bayes_threshold:
            return False, p_reversal, f"Bayes P={p_reversal:.3f} < threshold {self.bayes_threshold}"

        reason = f"QUANTUM_HEDGE ✅ | P={p_reversal:.3f} | {delta_label}"
        return True, p_reversal, reason

    # ------------------------------------------------------------------
    # 4. Dynamic Volume Formula
    # ------------------------------------------------------------------
    def compute_hedge_volume(
        self,
        existing_volume: float,
        alpha: float,
        beta: float,
        position_type: str,
        current_atr: float,
    ) -> tuple:
        """
        Returns (hedge_volume: float, stop_loss_points: float)

        V_hedge = V0 × (1 + k × |ΔP|) × (σ / σ_ref)
        SL_points = current_atr × stop_factor

        stop_loss_points: distance in price units from hedge entry to its SL.
        The EA uses this as: SL = entry ± stop_loss_points.
        """
        # Update ATR history
        if current_atr > 0:
            self._atr_history.append(current_atr)

        sigma_ref = (
            sum(self._atr_history) / len(self._atr_history)
            if self._atr_history
            else current_atr
        )
        sigma_ratio = current_atr / sigma_ref if sigma_ref > 0 else 1.0

        # Probability differential (|ΔP|)
        if position_type == "BUY":
            delta_p = abs(beta - alpha)
        else:
            delta_p = abs(alpha - beta)

        # Volume formula
        multiplier = (1 + self.k * delta_p) * sigma_ratio
        hedge_vol = existing_volume * multiplier

        # Hard cap
        hedge_vol = min(hedge_vol, self.max_lot)
        hedge_vol = max(hedge_vol, existing_volume)  # At minimum 1×
        hedge_vol = round(hedge_vol, 2)

        # Coupled SL: ATR × stop_factor
        stop_loss_points = round(current_atr * self.stop_factor, 5)

        return hedge_vol, stop_loss_points

    # ------------------------------------------------------------------
    # 4b. Combined Stop Risk Summary
    # ------------------------------------------------------------------
    def calculate_combined_stop(
        self,
        existing_profit: float,
        existing_volume: float,
        hedge_volume: float,
        current_atr: float,
    ) -> dict:
        """
        Estimates worst-case combined P&L if the hedge hits its SL.
        Symbol-agnostic approximation (no tick_value needed).

        Worst case: price moves stop_factor × ATR against the hedge.
        The existing position benefits from this move (it's opposing).
        """
        move = current_atr * self.stop_factor
        hedge_loss_at_sl = -(hedge_volume * move)   # hedge hits SL
        existing_gain = existing_volume * move        # original recovers partially
        combined = existing_profit + hedge_loss_at_sl + existing_gain
        return {
            "existing_profit_now": round(existing_profit, 2),
            "hedge_loss_at_sl": round(hedge_loss_at_sl, 4),
            "existing_recovery": round(existing_gain, 4),
            "combined_worst_case": round(combined, 2),
            "within_max_loss": abs(min(combined, 0)) <= self.max_combined_loss,
        }

    # ------------------------------------------------------------------
    # 5. Full pipeline: one call returns hedge order or None
    # ------------------------------------------------------------------
    def evaluate(
        self,
        existing_pos: dict,
        market_data: dict,
        ai_score: float,
    ) -> Optional[dict]:
        """
        Full quantum hedge evaluation pipeline.

        Parameters
        ----------
        existing_pos : dict
            {'type': 'BUY'|'SELL', 'volume': float, 'profit': float, 'symbol': str}
        market_data : dict
            {'rsi': float, 'trend_momentum': float, 'atr': float}
        ai_score : float
            0.0 (fully bearish) to 1.0 (fully bullish) from LearningBrain

        Returns
        -------
        dict or None
            If hedge recommended: {'hedge_volume': float, 'bayes_prob': float,
                                   'alpha': float, 'beta': float, 'reason': str}
            None if no hedge.
        """
        pos_type = existing_pos.get("type", "BUY")
        profit = float(existing_pos.get("profit", 0))
        volume = float(existing_pos.get("volume", 0.5))
        atr = float(market_data.get("atr", 1.0))
        rsi = market_data.get("rsi")
        momentum = float(market_data.get("trend_momentum", 0.0))

        # 1. Compute market state
        alpha, beta = self.compute_state(rsi, ai_score, momentum)

        # 2. Hedge gate
        do_hedge, p_rev, reason = self.should_hedge(profit, alpha, beta, pos_type, ai_score)

        logger.info(
            "QH Eval | %s P/L=%.2f | α=%.3f β=%.3f | P(rev)=%.3f | %s",
            pos_type, profit, alpha, beta, p_rev, reason
        )

        if not do_hedge:
            return None

        # 3. Compute volume + coupled SL
        hedge_vol, sl_points = self.compute_hedge_volume(volume, alpha, beta, pos_type, atr)

        # 4. Combined risk check
        risk_summary = self.calculate_combined_stop(profit, volume, hedge_vol, atr)
        logger.info("QH Risk: %s", risk_summary)

        return {
            "hedge_volume": hedge_vol,
            "stop_loss_points": sl_points,        # For EA command JSON
            "hedge_comment": "HEDGE_QUANTUM",     # Tag so EA can identify this position
            "bayes_prob": p_rev,
            "alpha": alpha,
            "beta": beta,
            "reason": reason,
            "multiplier": round(hedge_vol / volume, 2),
            "risk_summary": risk_summary,
        }
