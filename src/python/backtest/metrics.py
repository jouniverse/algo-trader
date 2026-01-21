"""
Backtest Metrics
================
Performance metrics calculations for backtesting results.
"""

import numpy as np
import pandas as pd
from typing import Optional
from dataclasses import dataclass


@dataclass
class BacktestMetrics:
    """Container for backtest performance metrics."""
    
    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    cagr: float = 0.0
    
    # Risk
    volatility: float = 0.0
    downside_deviation: float = 0.0
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    drawdown_duration: int = 0  # Max duration in periods
    
    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Trade statistics
    num_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Exposure
    exposure_time: float = 0.0  # Percentage of time in market
    
    @classmethod
    def from_equity_curve(
        cls,
        equity: pd.Series,
        trades: Optional[pd.DataFrame] = None,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252
    ) -> 'BacktestMetrics':
        """
        Calculate metrics from an equity curve.
        
        Args:
            equity: Series of equity values indexed by timestamp
            trades: DataFrame of trades with 'pnl' column
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year (252 for daily)
        """
        metrics = cls()
        
        if len(equity) < 2:
            return metrics
        
        # Convert to numpy for calculations
        eq = equity.values
        returns = np.diff(eq) / eq[:-1]
        
        # Basic returns
        metrics.total_return = (eq[-1] / eq[0]) - 1
        n_periods = len(returns)
        years = n_periods / periods_per_year
        
        if years > 0:
            metrics.cagr = (eq[-1] / eq[0]) ** (1 / years) - 1
            metrics.annualized_return = metrics.cagr
        
        # Volatility
        metrics.volatility = np.std(returns) * np.sqrt(periods_per_year)
        
        # Downside deviation (for Sortino)
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            metrics.downside_deviation = np.std(negative_returns) * np.sqrt(periods_per_year)
        
        # Drawdown analysis
        peak = np.maximum.accumulate(eq)
        drawdown = (peak - eq) / peak
        metrics.max_drawdown = np.max(drawdown)
        metrics.avg_drawdown = np.mean(drawdown[drawdown > 0]) if np.any(drawdown > 0) else 0
        
        # Max drawdown duration
        in_drawdown = drawdown > 0
        if np.any(in_drawdown):
            runs = np.diff(np.where(np.concatenate(([in_drawdown[0]], 
                                                     in_drawdown[:-1] != in_drawdown[1:], 
                                                     [True])))[0])
            dd_runs = runs[::2] if in_drawdown[0] else runs[1::2]
            metrics.drawdown_duration = int(np.max(dd_runs)) if len(dd_runs) > 0 else 0
        
        # Risk-adjusted metrics
        rf_per_period = risk_free_rate / periods_per_year
        excess_returns = returns - rf_per_period
        
        if metrics.volatility > 0:
            metrics.sharpe_ratio = (np.mean(excess_returns) * periods_per_year) / metrics.volatility
        
        if metrics.downside_deviation > 0:
            metrics.sortino_ratio = (np.mean(excess_returns) * periods_per_year) / metrics.downside_deviation
        
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = metrics.annualized_return / metrics.max_drawdown
        
        # Trade statistics
        if trades is not None and len(trades) > 0:
            pnl = trades['pnl'].values
            metrics.num_trades = len(pnl)
            
            wins = pnl[pnl > 0]
            losses = pnl[pnl < 0]
            
            metrics.win_rate = len(wins) / len(pnl) if len(pnl) > 0 else 0
            metrics.avg_trade = np.mean(pnl)
            metrics.avg_win = np.mean(wins) if len(wins) > 0 else 0
            metrics.avg_loss = np.mean(losses) if len(losses) > 0 else 0
            metrics.largest_win = np.max(wins) if len(wins) > 0 else 0
            metrics.largest_loss = np.min(losses) if len(losses) > 0 else 0
            
            total_wins = np.sum(wins) if len(wins) > 0 else 0
            total_losses = abs(np.sum(losses)) if len(losses) > 0 else 0
            metrics.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
            
            # Consecutive wins/losses
            is_win = pnl > 0
            metrics.max_consecutive_wins = _max_consecutive(is_win)
            metrics.max_consecutive_losses = _max_consecutive(~is_win)
        
        return metrics
    
    def to_dict(self) -> dict:
        """Convert metrics to dictionary."""
        return {
            'total_return': f"{self.total_return:.2%}",
            'annualized_return': f"{self.annualized_return:.2%}",
            'volatility': f"{self.volatility:.2%}",
            'max_drawdown': f"{self.max_drawdown:.2%}",
            'sharpe_ratio': f"{self.sharpe_ratio:.2f}",
            'sortino_ratio': f"{self.sortino_ratio:.2f}",
            'calmar_ratio': f"{self.calmar_ratio:.2f}",
            'num_trades': self.num_trades,
            'win_rate': f"{self.win_rate:.1%}",
            'profit_factor': f"{self.profit_factor:.2f}",
            'avg_win': f"{self.avg_win:.2f}",
            'avg_loss': f"{self.avg_loss:.2f}",
        }
    
    def __repr__(self) -> str:
        return f"""BacktestMetrics:
  Total Return: {self.total_return:.2%}
  Annualized Return: {self.annualized_return:.2%}
  Volatility: {self.volatility:.2%}
  Sharpe Ratio: {self.sharpe_ratio:.2f}
  Max Drawdown: {self.max_drawdown:.2%}
  Trades: {self.num_trades} (Win Rate: {self.win_rate:.1%})
  Profit Factor: {self.profit_factor:.2f}"""


def _max_consecutive(arr: np.ndarray) -> int:
    """Calculate maximum consecutive True values."""
    if len(arr) == 0:
        return 0
    
    max_count = 0
    current_count = 0
    
    for val in arr:
        if val:
            current_count += 1
            max_count = max(max_count, current_count)
        else:
            current_count = 0
    
    return max_count
