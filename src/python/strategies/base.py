"""
Base Strategy Interface
=======================
Abstract base class for all trading strategies.
"""

from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd
import numpy as np


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    
    All strategies must implement:
    - generate_signals(): Returns buy/sell signals for given data
    - __call__(): Makes strategy callable for backtest engine
    """
    
    def __init__(self, name: str, params: Optional[dict] = None):
        self.name = name
        self.params = params or {}
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals from OHLCV data.
        
        Args:
            data: DataFrame with columns: timestamp, open, high, low, close, volume
        
        Returns:
            Series with values: 1 (buy), -1 (sell), 0 (hold)
        """
        pass
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators needed for the strategy.
        Override in subclass to add custom indicators.
        
        Returns DataFrame with original data plus indicator columns.
        """
        return data.copy()
    
    def __call__(self, engine, bar_idx: int, bar: dict) -> list:
        """
        Called by backtest engine on each bar.
        
        This default implementation uses vectorized signals.
        Override for more complex order logic.
        """
        from ..backtest.engine import Order, Side
        
        # Need enough history for indicators
        min_history = self.params.get('min_history', 50)
        if bar_idx < min_history:
            return []
        
        # Get historical data up to current bar
        history = engine.get_history(min_history + 1, bar_idx)
        
        # Generate signals
        signals = self.generate_signals(history)
        current_signal = signals.iloc[-1] if len(signals) > 0 else 0
        
        if current_signal == 0:
            return []
        
        # Get current position
        symbol = bar.get('symbol', 'UNKNOWN')
        position = engine.get_position(symbol)
        
        orders = []
        position_size = self._calculate_position_size(engine, bar)
        
        if current_signal == 1 and position.quantity <= 0:
            # Buy signal and not already long
            if position.quantity < 0:
                # Close short first
                orders.append(Order(
                    symbol=symbol,
                    side=Side.BUY,
                    quantity=abs(position.quantity)
                ))
            # Open long
            orders.append(Order(
                symbol=symbol,
                side=Side.BUY,
                quantity=position_size
            ))
        
        elif current_signal == -1 and position.quantity >= 0:
            # Sell signal and not already short
            if position.quantity > 0:
                # Close long
                orders.append(Order(
                    symbol=symbol,
                    side=Side.SELL,
                    quantity=position.quantity
                ))
            # Open short (if allowed)
            if engine.config.allow_shorting:
                orders.append(Order(
                    symbol=symbol,
                    side=Side.SELL,
                    quantity=position_size
                ))
        
        return orders
    
    def _calculate_position_size(self, engine, bar: dict) -> float:
        """
        Calculate position size based on available capital.
        Override for custom position sizing.
        """
        equity = engine.get_equity()
        max_position_value = equity * engine.config.max_position_size
        price = bar['close']
        return int(max_position_value / price)
    
    def __repr__(self) -> str:
        return f"{self.name}({self.params})"


# Helper functions for indicators
def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple:
    """
    Bollinger Bands.
    Returns: (upper, middle, lower)
    """
    middle = sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    return upper, middle, lower


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """
    MACD (Moving Average Convergence Divergence).
    Returns: (macd_line, signal_line, histogram)
    """
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


class BuyAndHoldStrategy(BaseStrategy):
    """
    Buy and Hold Strategy (Baseline).
    
    Simply buys at the start and holds until the end.
    Used as a benchmark to compare active strategies against.
    
    Parameters:
        None - this is a passive strategy
    """
    
    def __init__(self):
        super().__init__(
            name='BuyAndHold',
            params={'min_history': 1}
        )
        self._bought = False
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Buy on first bar, hold forever."""
        signals = pd.Series(0, index=data.index)
        # Buy signal only on first bar
        signals.iloc[0] = 1
        return signals
    
    def __call__(self, engine, bar_idx: int, bar: dict) -> list:
        """Buy once at the start, then hold."""
        from ..backtest.engine import Order, Side
        
        symbol = bar.get('symbol', 'UNKNOWN')
        position = engine.get_position(symbol)
        
        # Only buy if we don't have a position yet
        if bar_idx == 1 and position.quantity == 0:
            position_size = self._calculate_position_size(engine, bar)
            return [Order(
                symbol=symbol,
                side=Side.BUY,
                quantity=position_size
            )]
        
        return []
