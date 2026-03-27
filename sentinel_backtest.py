"""
sentinel_backtest.py — V9 Backtest Engine for Sentinel
======================================================
Structured backtesting with realistic trade simulation (ATR-based SL/TP),
walk-forward validation, and professional performance metrics.

Architecture:
    Historical Data → Strategy Signal → Trade Simulation → Metrics
                                                ↑
                                        Walk-Forward Split
"""

import json
import os
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger("SENTINEL_BACKTEST")


# ============================================================
# Professional Metrics (§5)
# ============================================================

def compute_metrics(trades: list) -> dict:
    """
    Compute professional trading metrics from a list of trade results.
    Each trade must have a 'pnl' key (float, in risk units).

    Returns dict with: winrate, sharpe, max_drawdown, profit_factor,
    total_trades, total_pnl, avg_pnl.
    """
    if not trades:
        return {
            "winrate": 0.0, "sharpe": 0.0, "max_drawdown": 0.0,
            "profit_factor": 0.0, "total_trades": 0, "total_pnl": 0.0,
            "avg_pnl": 0.0,
        }

    pnls = np.array([t["pnl"] for t in trades], dtype=np.float64)
    n = len(pnls)

    winrate = float(np.mean(pnls > 0))
    avg_pnl = float(pnls.mean())
    total_pnl = float(pnls.sum())

    # Sharpe ratio (annualized estimate if daily, else raw)
    std = float(pnls.std())
    sharpe = float(pnls.mean() / (std + 1e-9))

    # Max drawdown from cumulative PnL
    cumsum = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cumsum)
    drawdowns = running_max - cumsum
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    # Profit factor = gross_win / gross_loss
    gross_win = float(pnls[pnls > 0].sum()) if np.any(pnls > 0) else 0.0
    gross_loss = float(np.abs(pnls[pnls < 0].sum())) if np.any(pnls < 0) else 1e-9
    profit_factor = gross_win / gross_loss

    return {
        "winrate": round(winrate, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4),
        "profit_factor": round(profit_factor, 4),
        "total_trades": n,
        "total_pnl": round(total_pnl, 4),
        "avg_pnl": round(avg_pnl, 4),
    }


# ============================================================
# Validation Criteria (§7)
# ============================================================

def validate_system(metrics: dict) -> dict:
    """
    Check if system metrics pass institutional validation criteria.
    Returns dict with 'valid' bool and list of 'failures'.
    """
    failures = []
    if metrics.get("sharpe", 0) < 1.2:
        failures.append(f"Sharpe {metrics['sharpe']:.2f} < 1.2")
    if metrics.get("max_drawdown", 999) > 15.0:
        failures.append(f"MaxDD {metrics['max_drawdown']:.2f} > 15%")
    if metrics.get("profit_factor", 0) < 1.5:
        failures.append(f"PF {metrics['profit_factor']:.2f} < 1.5")
    if metrics.get("total_trades", 0) < 200:
        failures.append(f"Trades {metrics['total_trades']} < 200")

    return {"valid": len(failures) == 0, "failures": failures}


# ============================================================
# Trade Simulation (§4.2) — ATR-based SL/TP
# ============================================================

def simulate_trade(future_candles: list, signal: dict, atr: float,
                   sl_mult: float = 1.2, tp_mult: float = 2.5) -> dict:
    """
    Simulate a single trade against future candle data.

    Args:
        future_candles: list of dicts with 'high', 'low', 'close' keys
        signal: dict with 'action' ('BUY' or 'SELL') and 'entry' price
        atr: ATR value at entry
        sl_mult: SL distance = atr * sl_mult
        tp_mult: TP distance = atr * tp_mult

    Returns:
        dict with 'pnl' (in risk units: -1 for loss, +tp_mult/sl_mult for win),
        'tp_hit' (bool), 'sl_hit' (bool), 'bars_held' (int)
    """
    entry = signal["entry"]
    action = signal["action"]

    sl_dist = atr * sl_mult
    tp_dist = atr * tp_mult

    if action == "BUY":
        sl = entry - sl_dist
        tp = entry + tp_dist
    else:
        sl = entry + sl_dist
        tp = entry - tp_dist

    reward_ratio = tp_mult / sl_mult  # Risk:Reward in risk units

    for i, candle in enumerate(future_candles):
        h = candle.get("high", candle.get("close", entry))
        l = candle.get("low", candle.get("close", entry))

        if action == "BUY":
            if l <= sl:
                return {"pnl": -1.0, "tp_hit": False, "sl_hit": True, "bars_held": i + 1}
            if h >= tp:
                return {"pnl": reward_ratio, "tp_hit": True, "sl_hit": False, "bars_held": i + 1}
        else:
            if h >= sl:
                return {"pnl": -1.0, "tp_hit": False, "sl_hit": True, "bars_held": i + 1}
            if l <= tp:
                return {"pnl": reward_ratio, "tp_hit": True, "sl_hit": False, "bars_held": i + 1}

    # Neither SL nor TP hit — scratch/timeout
    return {"pnl": 0.0, "tp_hit": False, "sl_hit": False, "bars_held": len(future_candles)}


# ============================================================
# Backtest Engine (§4.1)
# ============================================================

class BacktestEngine:
    """
    Run a strategy over historical candle data and simulate trades.

    data format: list of dicts, each with:
        'open', 'high', 'low', 'close', 'atr', 'rsi', 'spread', 'imbalance'
    """

    def __init__(self, sl_mult: float = 1.2, tp_mult: float = 2.5,
                 lookback: int = 50, forward: int = 20):
        self.sl_mult = sl_mult
        self.tp_mult = tp_mult
        self.lookback = lookback
        self.forward = forward

    def run(self, data: list, strategy_fn) -> tuple:
        """
        Run backtest over data.

        Args:
            data: list of candle dicts (chronological)
            strategy_fn: callable(window) → dict with 'action' key ('BUY'/'SELL')
                         or None if no signal

        Returns:
            (trades_list, final_equity)
        """
        equity = 10000.0
        trades = []
        n = len(data)

        for i in range(self.lookback, n - self.forward):
            window = data[:i + 1]
            signal = strategy_fn(window)
            if signal is None:
                continue

            # Entry price is the close of the current bar
            signal["entry"] = data[i]["close"]
            atr = data[i].get("atr", 0.0)
            if atr <= 0:
                continue

            # Simulate against future candles
            future = data[i + 1: i + 1 + self.forward]
            result = simulate_trade(future, signal, atr,
                                    self.sl_mult, self.tp_mult)

            # Record trade
            result["bar_index"] = i
            result["action"] = signal["action"]
            result["entry"] = signal["entry"]
            trades.append(result)

            # Update equity (assuming 1% risk per trade)
            risk_amount = equity * 0.01
            equity += risk_amount * result["pnl"]

        return trades, round(equity, 2)


# ============================================================
# Walk-Forward Validation (§6)
# ============================================================

def walk_forward(data: list, train_fn, strategy_fn,
                 train_size: int = 200, test_size: int = 50,
                 sl_mult: float = 1.2, tp_mult: float = 2.5) -> list:
    """
    Walk-forward out-of-sample validation.

    Args:
        data: full historical candle data
        train_fn: callable(train_data) → trains the model in-place
        strategy_fn: callable(window) → signal dict or None
        train_size: number of bars for training window
        test_size: number of bars for test window

    Returns:
        list of dicts, each with 'fold', 'metrics', 'trades'
    """
    results = []
    n = len(data)
    fold = 0

    for start in range(train_size, n - test_size, test_size):
        train_data = data[start - train_size: start]
        test_data = data[start: start + test_size]

        # Train model on train window
        train_fn(train_data)

        # Backtest on test window
        engine = BacktestEngine(sl_mult=sl_mult, tp_mult=tp_mult,
                                lookback=min(50, len(test_data) // 3),
                                forward=min(20, len(test_data) // 4))
        trades, equity = engine.run(test_data, strategy_fn)

        metrics = compute_metrics(trades)
        results.append({
            "fold": fold,
            "start_bar": start,
            "metrics": metrics,
            "n_trades": len(trades),
            "equity": equity,
        })
        fold += 1

    return results


def aggregate_walk_forward(results: list) -> dict:
    """Aggregate walk-forward fold results into summary metrics."""
    if not results:
        return {"error": "no walk-forward results"}

    all_trades = sum(r["n_trades"] for r in results)
    avg_sharpe = float(np.mean([r["metrics"]["sharpe"] for r in results]))
    avg_winrate = float(np.mean([r["metrics"]["winrate"] for r in results]))
    avg_pf = float(np.mean([r["metrics"]["profit_factor"] for r in results]))
    max_dd = float(np.max([r["metrics"]["max_drawdown"] for r in results]))

    summary = {
        "folds": len(results),
        "total_trades": all_trades,
        "avg_sharpe": round(avg_sharpe, 4),
        "avg_winrate": round(avg_winrate, 4),
        "avg_profit_factor": round(avg_pf, 4),
        "worst_max_drawdown": round(max_dd, 4),
    }

    validation = validate_system({
        "sharpe": avg_sharpe,
        "max_drawdown": max_dd,
        "profit_factor": avg_pf,
        "total_trades": all_trades,
    })
    summary["validation"] = validation

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Demo: generate synthetic data and run backtest
    np.random.seed(42)
    n_bars = 500
    price = 2000.0
    data = []
    for i in range(n_bars):
        change = np.random.randn() * 2.0
        h = price + abs(np.random.randn() * 1.5)
        l = price - abs(np.random.randn() * 1.5)
        c = price + change
        data.append({
            "open": price, "high": h, "low": l, "close": c,
            "atr": 3.0 + np.random.randn() * 0.5,
            "rsi": 50 + np.random.randn() * 15,
            "spread": 0.5,
            "imbalance": np.random.randn() * 0.3,
        })
        price = c

    def demo_strategy(window):
        """Simple RSI strategy for demonstration."""
        last = window[-1]
        rsi = last.get("rsi", 50)
        if rsi < 35:
            return {"action": "BUY"}
        elif rsi > 65:
            return {"action": "SELL"}
        return None

    engine = BacktestEngine()
    trades, equity = engine.run(data, demo_strategy)
    metrics = compute_metrics(trades)
    validation = validate_system(metrics)

    print(f"[BACKTEST] Trades: {len(trades)} | Equity: {equity}")
    print(f"[BACKTEST] Metrics: {json.dumps(metrics, indent=2)}")
    print(f"[BACKTEST] Validation: {json.dumps(validation, indent=2)}")
