"""
Backtest Engine
===============
Event-driven backtesting framework for trading strategies.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Side(Enum):
    BUY = 1
    SELL = -1


@dataclass
class Order:
    """Represents a trading order."""
    symbol: str
    side: Side
    quantity: float
    order_type: str = 'MARKET'  # MARKET, LIMIT
    limit_price: Optional[float] = None
    timestamp: Optional[datetime] = None
    filled: bool = False
    fill_price: Optional[float] = None
    fill_timestamp: Optional[datetime] = None


@dataclass
class Position:
    """Represents a position in a symbol."""
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    entry_time: datetime = None  # When position was opened


@dataclass
class Trade:
    """Represents a completed trade (round trip)."""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    side: Side
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    return_pct: float


@dataclass
class BacktestConfig:
    """Configuration for backtest."""
    initial_capital: float = 100000.0
    commission: float = 0.001  # 0.1% per trade
    slippage: float = 0.0005  # 0.05% slippage
    margin_requirement: float = 1.0  # 1.0 = no margin
    max_position_size: float = 0.1  # Max 10% of capital per position
    allow_shorting: bool = True


@dataclass
class BacktestState:
    """Current state of the backtest."""
    timestamp: datetime = None
    cash: float = 0.0
    positions: dict = field(default_factory=dict)
    orders: list = field(default_factory=list)
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    

class BacktestEngine:
    """
    Event-driven backtesting engine.
    
    Usage:
        engine = BacktestEngine(config)
        engine.load_data(df)  # OHLCV data
        engine.set_strategy(my_strategy_fn)
        results = engine.run()
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.data: Optional[pd.DataFrame] = None
        self.strategy: Optional[Callable] = None
        self.state = BacktestState()
        self._reset()
    
    def _reset(self):
        """Reset backtest state."""
        self.state = BacktestState(
            cash=self.config.initial_capital,
            positions={},
            orders=[],
            trades=[],
            equity_curve=[]
        )
    
    def load_data(self, data: pd.DataFrame):
        """
        Load OHLCV data for backtesting.
        
        Expected columns: timestamp, open, high, low, close, volume, symbol
        """
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing = [c for c in required if c not in data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        self.data = data.sort_values('timestamp').reset_index(drop=True)
        logger.info(f"Loaded {len(self.data)} bars")
    
    def set_strategy(self, strategy_fn: Callable):
        """
        Set the strategy function.
        
        Strategy function signature:
            def strategy(engine, bar_idx, bar_data) -> list[Order]
        
        Args:
            engine: Reference to BacktestEngine (access state, positions, etc.)
            bar_idx: Current bar index
            bar_data: Current bar as dict (open, high, low, close, volume, timestamp)
        
        Returns:
            List of Order objects to execute
        """
        self.strategy = strategy_fn
    
    def get_position(self, symbol: str) -> Position:
        """Get current position for a symbol."""
        if symbol not in self.state.positions:
            self.state.positions[symbol] = Position(symbol=symbol)
        return self.state.positions[symbol]
    
    def get_equity(self) -> float:
        """Calculate current total equity."""
        equity = self.state.cash
        for pos in self.state.positions.values():
            equity += pos.quantity * pos.avg_price + pos.unrealized_pnl
        return equity
    
    def get_history(self, lookback: int, bar_idx: int) -> pd.DataFrame:
        """Get historical bars up to current bar."""
        start_idx = max(0, bar_idx - lookback + 1)
        return self.data.iloc[start_idx:bar_idx + 1].copy()
    
    def _execute_order(self, order: Order, bar: dict) -> bool:
        """Execute an order at current bar prices."""
        symbol = order.symbol
        
        # Determine fill price with slippage
        if order.order_type == 'MARKET':
            base_price = bar['close']
        else:
            base_price = order.limit_price
            # Check if limit order can be filled
            if order.side == Side.BUY and bar['low'] > order.limit_price:
                return False
            if order.side == Side.SELL and bar['high'] < order.limit_price:
                return False
        
        # Apply slippage
        slippage_factor = 1 + self.config.slippage if order.side == Side.BUY else 1 - self.config.slippage
        fill_price = base_price * slippage_factor
        
        # Calculate transaction value and commission
        transaction_value = order.quantity * fill_price
        commission = transaction_value * self.config.commission
        
        # Check if we have enough cash for buy
        if order.side == Side.BUY:
            required = transaction_value + commission
            if required > self.state.cash:
                logger.warning(f"Insufficient cash for order: need {required}, have {self.state.cash}")
                return False
            self.state.cash -= required
        else:
            # Check if we have position to sell (or allow shorting)
            pos = self.get_position(symbol)
            if not self.config.allow_shorting and pos.quantity < order.quantity:
                logger.warning(f"Cannot short {symbol}")
                return False
            self.state.cash += transaction_value - commission
        
        # Update position
        pos = self.get_position(symbol)
        old_qty = pos.quantity
        old_avg = pos.avg_price
        
        if order.side == Side.BUY:
            new_qty = old_qty + order.quantity
            if new_qty != 0:
                pos.avg_price = (old_qty * old_avg + order.quantity * fill_price) / new_qty
            # Track entry time when opening a new position
            if old_qty == 0:
                pos.entry_time = bar['timestamp']
            pos.quantity = new_qty
        else:
            # Selling - realize P&L
            if old_qty > 0:
                sell_qty = min(order.quantity, old_qty)
                pnl = sell_qty * (fill_price - old_avg)
                pos.realized_pnl += pnl
                
                # Record trade with actual entry time
                trade = Trade(
                    symbol=symbol,
                    entry_time=pos.entry_time or bar['timestamp'],  # Use position's entry time
                    exit_time=bar['timestamp'],
                    side=Side.BUY,  # Original side was buy
                    quantity=sell_qty,
                    entry_price=old_avg,
                    exit_price=fill_price,
                    pnl=pnl,
                    return_pct=pnl / (sell_qty * old_avg) if old_avg > 0 else 0
                )
                self.state.trades.append(trade)
            
            pos.quantity = old_qty - order.quantity
            if pos.quantity == 0:
                pos.avg_price = 0
                pos.entry_time = None  # Reset entry time when position closed
        
        # Mark order as filled
        order.filled = True
        order.fill_price = fill_price
        order.fill_timestamp = bar['timestamp']
        
        logger.debug(f"Filled {order.side.name} {order.quantity} {symbol} @ {fill_price:.2f}")
        return True
    
    def _update_positions(self, bar: dict):
        """Update unrealized P&L for all positions."""
        for pos in self.state.positions.values():
            if pos.quantity != 0:
                current_price = bar['close']
                pos.unrealized_pnl = pos.quantity * (current_price - pos.avg_price)
    
    def run(self) -> dict:
        """
        Run the backtest.
        
        Returns:
            Dictionary with results: equity_curve, trades, metrics
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        if self.strategy is None:
            raise ValueError("No strategy set. Call set_strategy() first.")
        
        self._reset()
        logger.info(f"Starting backtest with {len(self.data)} bars")
        
        for idx in range(len(self.data)):
            bar = self.data.iloc[idx].to_dict()
            self.state.timestamp = bar['timestamp']
            
            # Update positions with current prices
            self._update_positions(bar)
            
            # Get strategy signals
            orders = self.strategy(self, idx, bar)
            
            # Execute orders
            if orders:
                for order in orders:
                    order.timestamp = bar['timestamp']
                    if self._execute_order(order, bar):
                        self.state.orders.append(order)
            
            # Record equity
            equity = self.get_equity()
            self.state.equity_curve.append({
                'timestamp': bar['timestamp'],
                'equity': equity,
                'cash': self.state.cash
            })
        
        # Compile results
        equity_df = pd.DataFrame(self.state.equity_curve)
        trades_df = pd.DataFrame([
            {
                'symbol': t.symbol,
                'entry_time': t.entry_time,
                'exit_time': t.exit_time,
                'side': t.side.name,
                'quantity': t.quantity,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'pnl': t.pnl,
                'return_pct': t.return_pct
            }
            for t in self.state.trades
        ]) if self.state.trades else pd.DataFrame()
        
        # Calculate metrics
        metrics = self._calculate_metrics(equity_df, trades_df)
        
        return {
            'equity_curve': equity_df,
            'trades': trades_df,
            'metrics': metrics,
            'final_equity': equity_df['equity'].iloc[-1] if len(equity_df) > 0 else self.config.initial_capital
        }
    
    def _calculate_metrics(self, equity_df: pd.DataFrame, trades_df: pd.DataFrame) -> dict:
        """Calculate performance metrics."""
        if len(equity_df) < 2:
            return {}
        
        equity = equity_df['equity'].values
        returns = np.diff(equity) / equity[:-1]
        
        total_return = (equity[-1] / equity[0]) - 1
        
        # Annualized metrics (assuming daily data)
        n_periods = len(returns)
        annualized_return = (1 + total_return) ** (252 / n_periods) - 1 if n_periods > 0 else 0
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0
        sharpe = annualized_return / volatility if volatility > 0 else 0
        
        # Drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_drawdown = np.max(drawdown)
        
        # Trade statistics
        num_trades = len(trades_df)
        if num_trades > 0:
            winning_trades = trades_df[trades_df['pnl'] > 0]
            win_rate = len(winning_trades) / num_trades
            avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
            avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if len(trades_df[trades_df['pnl'] < 0]) > 0 else 0
            profit_factor = abs(winning_trades['pnl'].sum() / trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if trades_df[trades_df['pnl'] < 0]['pnl'].sum() != 0 else float('inf')
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'final_equity': equity[-1],
            'initial_capital': self.config.initial_capital
        }
