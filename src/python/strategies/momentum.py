"""
Momentum Trading Strategies
===========================
Strategies based on price momentum and trend following.
"""

import pandas as pd
import numpy as np
from .base import BaseStrategy, sma, ema, rsi, macd


class MomentumStrategy(BaseStrategy):
    """
    Simple dual moving average crossover strategy.
    
    Buy when fast MA crosses above slow MA.
    Sell when fast MA crosses below slow MA.
    
    Parameters:
        fast_period: Fast moving average period (default: 10)
        slow_period: Slow moving average period (default: 30)
        ma_type: 'sma' or 'ema' (default: 'sma')
    """
    
    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 30,
        ma_type: str = 'sma'
    ):
        super().__init__(
            name='Momentum',
            params={
                'fast_period': fast_period,
                'slow_period': slow_period,
                'ma_type': ma_type,
                'min_history': slow_period + 5
            }
        )
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on MA crossover."""
        close = data['close']
        fast = self.params['fast_period']
        slow = self.params['slow_period']
        
        # Calculate MAs
        if self.params['ma_type'] == 'ema':
            fast_ma = ema(close, fast)
            slow_ma = ema(close, slow)
        else:
            fast_ma = sma(close, fast)
            slow_ma = sma(close, slow)
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Crossover detection
        prev_fast = fast_ma.shift(1)
        prev_slow = slow_ma.shift(1)
        
        # Buy: fast crosses above slow
        buy_signal = (fast_ma > slow_ma) & (prev_fast <= prev_slow)
        # Sell: fast crosses below slow
        sell_signal = (fast_ma < slow_ma) & (prev_fast >= prev_slow)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals


class RSIStrategy(BaseStrategy):
    """
    RSI (Relative Strength Index) mean reversion strategy.
    
    Buy when RSI crosses below oversold threshold.
    Sell when RSI crosses above overbought threshold.
    
    Parameters:
        period: RSI calculation period (default: 14)
        oversold: Oversold threshold (default: 30)
        overbought: Overbought threshold (default: 70)
    """
    
    def __init__(
        self,
        period: int = 14,
        oversold: float = 30,
        overbought: float = 70
    ):
        super().__init__(
            name='RSI',
            params={
                'period': period,
                'oversold': oversold,
                'overbought': overbought,
                'min_history': period + 5
            }
        )
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on RSI levels."""
        close = data['close']
        rsi_values = rsi(close, self.params['period'])
        
        signals = pd.Series(0, index=data.index)
        
        oversold = self.params['oversold']
        overbought = self.params['overbought']
        
        prev_rsi = rsi_values.shift(1)
        
        # Buy: RSI crosses above oversold from below
        buy_signal = (rsi_values > oversold) & (prev_rsi <= oversold)
        # Sell: RSI crosses below overbought from above
        sell_signal = (rsi_values < overbought) & (prev_rsi >= overbought)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals


class MACDStrategy(BaseStrategy):
    """
    MACD crossover strategy.
    
    Buy when MACD crosses above signal line.
    Sell when MACD crosses below signal line.
    
    Parameters:
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line period (default: 9)
    """
    
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ):
        super().__init__(
            name='MACD',
            params={
                'fast_period': fast_period,
                'slow_period': slow_period,
                'signal_period': signal_period,
                'min_history': slow_period + signal_period + 5
            }
        )
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on MACD crossover."""
        close = data['close']
        
        macd_line, signal_line, histogram = macd(
            close,
            self.params['fast_period'],
            self.params['slow_period'],
            self.params['signal_period']
        )
        
        signals = pd.Series(0, index=data.index)
        
        prev_macd = macd_line.shift(1)
        prev_signal = signal_line.shift(1)
        
        # Buy: MACD crosses above signal
        buy_signal = (macd_line > signal_line) & (prev_macd <= prev_signal)
        # Sell: MACD crosses below signal
        sell_signal = (macd_line < signal_line) & (prev_macd >= prev_signal)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals


class TrendFollowingStrategy(BaseStrategy):
    """
    Multi-timeframe trend following strategy.
    
    Uses multiple MAs to confirm trend direction:
    - Short-term MA for entry timing
    - Medium-term MA for trend direction
    - Long-term MA for major trend filter
    
    Only takes trades in the direction of the major trend.
    
    Parameters:
        short_period: Short MA period (default: 10)
        medium_period: Medium MA period (default: 50)
        long_period: Long MA period (default: 200)
    """
    
    def __init__(
        self,
        short_period: int = 10,
        medium_period: int = 50,
        long_period: int = 200
    ):
        super().__init__(
            name='TrendFollowing',
            params={
                'short_period': short_period,
                'medium_period': medium_period,
                'long_period': long_period,
                'min_history': long_period + 5
            }
        )
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on multi-timeframe trend."""
        close = data['close']
        
        short_ma = sma(close, self.params['short_period'])
        medium_ma = sma(close, self.params['medium_period'])
        long_ma = sma(close, self.params['long_period'])
        
        signals = pd.Series(0, index=data.index)
        
        # Uptrend: price above long MA
        uptrend = close > long_ma
        # Downtrend: price below long MA
        downtrend = close < long_ma
        
        prev_short = short_ma.shift(1)
        prev_medium = medium_ma.shift(1)
        
        # Buy: uptrend AND short crosses above medium
        buy_signal = uptrend & (short_ma > medium_ma) & (prev_short <= prev_medium)
        # Sell: downtrend AND short crosses below medium
        sell_signal = downtrend & (short_ma < medium_ma) & (prev_short >= prev_medium)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
