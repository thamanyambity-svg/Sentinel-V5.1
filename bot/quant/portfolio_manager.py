import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class Position:
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    weight: float = 0.0

class PortfolioManager:
    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.history = []
    
    def add_position(self, symbol: str, direction: str, size: float, entry_price: float, current_price: float):
        """Ajoute une position au portefeuille"""
        cost = size * entry_price
        # Check margin/cash (simplified)
        # In real world, leverage is considered
        
        unrealized_pnl = (current_price - entry_price) * size if direction == 'LONG' else (entry_price - current_price) * size
        
        position = Position(
            symbol=symbol,
            direction=direction,
            size=size,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl
        )
        
        self.positions[symbol] = position
        self._update_weights()
        print(f"✅ Position Opened: {symbol} {direction} {size} @ {entry_price}")
    
    def update_prices(self, price_updates: Dict[str, float]):
        """Met à jour les prix des positions"""
        for symbol, current_price in price_updates.items():
            if symbol in self.positions:
                position = self.positions[symbol]
                position.current_price = current_price
                
                # Recalculer le P&L
                if position.direction == 'LONG':
                    position.unrealized_pnl = (current_price - position.entry_price) * position.size
                else:
                    position.unrealized_pnl = (position.entry_price - current_price) * position.size
        
        self._update_weights()
    
    def _update_weights(self):
        """Met à jour les poids des positions"""
        total_value = self.calculate_total_value()
        for position in self.positions.values():
            position_value = position.size * position.current_price
            position.weight = position_value / total_value if total_value > 0 else 0.0
    
    def calculate_total_value(self) -> float:
        """Calcule la valeur totale (Cash + Unrealized PnL of positions + Initial Cost basis - but simpler: Equity)"""
        # Equity = Cash + Position Value (Longs) - Position Liabilities (Shorts) ??
        # Simpler model: Equity = Initial Capital + Realized PnL + Unrealized PnL
        # Or: Equity = Current Cash + Market Value of Positions
        
        # Track realized pnl in self.cash? 
        # Let's assume self.cash is "Available Balance".
        # When opening, we deduct cost? Or is it margin trading?
        # User prompt implies simpler tracking.
        # Let's use: Total Value = Initial Capital + Sum(Realized PnL) + Sum(Unrealized PnL)
        
        realized_pnl_so_far = sum(h['pnl'] for h in self.history)
        unrealized_total = sum(p.unrealized_pnl for p in self.positions.values())
        
        return self.initial_capital + realized_pnl_so_far + unrealized_total
    
    def get_portfolio_metrics(self) -> Dict:
        """Retourne les métriques du portefeuille"""
        total_value = self.calculate_total_value()
        total_pnl = total_value - self.initial_capital
        
        long_exposure = sum(pos.size * pos.current_price for pos in self.positions.values() if pos.direction == 'LONG')
        # Short exposure is absolute value of notional
        short_exposure = sum(pos.size * pos.current_price for pos in self.positions.values() if pos.direction == 'SHORT')
        net_exposure = long_exposure - short_exposure
        
        return {
            'total_value': round(total_value, 2),
            'total_pnl': round(total_pnl, 2),
            'total_return_%': round((total_value / self.initial_capital - 1) * 100, 2),
            'positions_count': len(self.positions),
            'long_exposure': round(long_exposure, 2),
            'short_exposure': round(short_exposure, 2),
            'net_exposure': round(net_exposure, 2)
        }
    
    def close_position(self, symbol: str, exit_price: float):
        """Ferme une position"""
        if symbol in self.positions:
            position = self.positions[symbol]
            if position.direction == 'LONG':
                realized_pnl = (exit_price - position.entry_price) * position.size
            else:
                realized_pnl = (position.entry_price - exit_price) * position.size
            
            # self.cash += ... (Not updating cash strictly in this simplified view, just tracking PnL)
            
            del self.positions[symbol]
            
            self.history.append({
                'symbol': symbol,
                'entry_price': position.entry_price,
                'exit_price': exit_price,
                'size': position.size,
                'pnl': realized_pnl,
                'direction': position.direction
            })
            
            print(f"🔐 Closed {symbol}. P&L: {realized_pnl:.2f}")

if __name__ == "__main__":
    # Test
    pm = PortfolioManager(initial_capital=10000)
    pm.add_position('EURUSD', 'LONG', 10000, 1.0500, 1.0500)
    
    print("Metrics Initial:", pm.get_portfolio_metrics())
    
    # Price Moves Up
    pm.update_prices({'EURUSD': 1.0600})
    print("Metrics After Pump:", pm.get_portfolio_metrics())
    
    # Close
    pm.close_position('EURUSD', 1.0600)
    print("Metrics After Close:", pm.get_portfolio_metrics())
