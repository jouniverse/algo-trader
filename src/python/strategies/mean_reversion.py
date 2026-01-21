"""
Mean Reversion Trading Strategies
=================================
Strategies based on the assumption that prices revert to a mean.
"""

import pandas as pd
import numpy as np
from .base import BaseStrategy, sma, ema, bollinger_bands


class MeanReversionStrategy(BaseStrategy):
    """
    Simple mean reversion strategy using z-score.
    
    Buy when price is below mean by z_threshold standard deviations.
    Sell when price is above mean by z_threshold standard deviations.
    
    Parameters:
        lookback: Period for mean and std calculation (default: 20)
        z_threshold: Z-score threshold for entry (default: 2.0)
        exit_threshold: Z-score for exit (default: 0.5)
    """
    
    def __init__(
        self,
        lookback: int = 20,
        z_threshold: float = 2.0,
        exit_threshold: float = 0.5
    ):
        super().__init__(
            name='MeanReversion',
            params={
                'lookback': lookback,
                'z_threshold': z_threshold,
                'exit_threshold': exit_threshold,
                'min_history': lookback + 5
            }
        )
        self._in_position = 0  # Track position state
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on z-score."""
        close = data['close']
        lookback = self.params['lookback']
        
        # Calculate z-score
        rolling_mean = close.rolling(window=lookback).mean()
        rolling_std = close.rolling(window=lookback).std()
        z_score = (close - rolling_mean) / rolling_std
        
        signals = pd.Series(0, index=data.index)
        
        z_thresh = self.params['z_threshold']
        exit_thresh = self.params['exit_threshold']
        
        # Buy: z-score below negative threshold (price is low)
        buy_signal = z_score < -z_thresh
        # Sell: z-score above positive threshold (price is high)
        sell_signal = z_score > z_thresh
        
        # Exit signals when returning to mean
        exit_long = z_score > exit_thresh
        exit_short = z_score < -exit_thresh
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals


class BollingerBandsStrategy(BaseStrategy):
    """
    Bollinger Bands mean reversion strategy.
    
    Buy when price touches/crosses below lower band.
    Sell when price touches/crosses above upper band.
    Exit when price returns to middle band.
    
    Parameters:
        period: Bollinger Bands period (default: 20)
        std_dev: Number of standard deviations (default: 2.0)
    """
    
    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0
    ):
        super().__init__(
            name='BollingerBands',
            params={
                'period': period,
                'std_dev': std_dev,
                'min_history': period + 5
            }
        )
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on Bollinger Bands."""
        close = data['close']
        
        upper, middle, lower = bollinger_bands(
            close,
            self.params['period'],
            self.params['std_dev']
        )
        
        signals = pd.Series(0, index=data.index)
        
        prev_close = close.shift(1)
        
        # Buy: price crosses below lower band
        buy_signal = (close < lower) & (prev_close >= lower.shift(1))
        # Sell: price crosses above upper band
        sell_signal = (close > upper) & (prev_close <= upper.shift(1))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals


class StatisticalArbitrageStrategy(BaseStrategy):
    """
    Statistical arbitrage / pairs trading strategy (single asset version).
    
    Uses cointegration-based spread trading.
    For a true pairs strategy, extend to handle two symbols.
    
    This simplified version trades based on deviation from a linear regression
    of the asset against its own lagged values.
    
    Parameters:
        lookback: Regression lookback period (default: 60)
        entry_threshold: Entry threshold in std devs (default: 2.0)
        exit_threshold: Exit threshold in std devs (default: 0.5)
    """
    
    def __init__(
        self,
        lookback: int = 60,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5
    ):
        super().__init__(
            name='StatArb',
            params={
                'lookback': lookback,
                'entry_threshold': entry_threshold,
                'exit_threshold': exit_threshold,
                'min_history': lookback + 5
            }
        )
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on regression residuals."""
        close = data['close']
        lookback = self.params['lookback']
        
        signals = pd.Series(0, index=data.index)
        
        # Calculate residuals from rolling regression
        def calc_residual(window):
            if len(window) < lookback:
                return np.nan
            x = np.arange(len(window))
            y = window.values
            try:
                slope, intercept = np.polyfit(x, y, 1)
                predicted = slope * x[-1] + intercept
                return y[-1] - predicted
            except:
                return np.nan
        
        residuals = close.rolling(window=lookback).apply(calc_residual, raw=False)
        
        # Normalize residuals
        residual_std = residuals.rolling(window=lookback).std()
        z_residual = residuals / residual_std
        
        entry = self.params['entry_threshold']
        exit_thresh = self.params['exit_threshold']
        
        # Buy: residual is very negative (price below trend)
        buy_signal = z_residual < -entry
        # Sell: residual is very positive (price above trend)
        sell_signal = z_residual > entry
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals


class OverboughtOversoldStrategy(BaseStrategy):
    """
    Combined overbought/oversold indicator strategy.
    
    Uses multiple indicators to confirm oversold/overbought conditions:
    - RSI
    - Bollinger %B
    - Stochastic
    
    Parameters:
        rsi_period: RSI period (default: 14)
        bb_period: Bollinger Bands period (default: 20)
        stoch_period: Stochastic period (default: 14)
        confirmation_count: Number of indicators needed (default: 2)
    """
    
    def __init__(
        self,
        rsi_period: int = 14,
        bb_period: int = 20,
        stoch_period: int = 14,
        confirmation_count: int = 2
    ):
        super().__init__(
            name='OverboughtOversold',
            params={
                'rsi_period': rsi_period,
                'bb_period': bb_period,
                'stoch_period': stoch_period,
                'confirmation_count': confirmation_count,
                'min_history': max(rsi_period, bb_period, stoch_period) + 5
            }
        )
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on multiple indicators."""
        close = data['close']
        high = data['high']
        low = data['low']
        
        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(self.params['rsi_period']).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.params['rsi_period']).mean()
        rs = gain / loss
        rsi_val = 100 - (100 / (1 + rs))
        
        # Bollinger %B
        upper, middle, lower = bollinger_bands(close, self.params['bb_period'])
        pct_b = (close - lower) / (upper - lower)
        
        # Stochastic
        low_min = low.rolling(self.params['stoch_period']).min()
        high_max = high.rolling(self.params['stoch_period']).max()
        stoch_k = 100 * (close - low_min) / (high_max - low_min)
        
        # Count oversold signals
        oversold_rsi = rsi_val < 30
        oversold_bb = pct_b < 0
        oversold_stoch = stoch_k < 20
        oversold_count = oversold_rsi.astype(int) + oversold_bb.astype(int) + oversold_stoch.astype(int)
        
        # Count overbought signals
        overbought_rsi = rsi_val > 70
        overbought_bb = pct_b > 1
        overbought_stoch = stoch_k > 80
        overbought_count = overbought_rsi.astype(int) + overbought_bb.astype(int) + overbought_stoch.astype(int)
        
        signals = pd.Series(0, index=data.index)
        min_confirm = self.params['confirmation_count']
        
        signals[oversold_count >= min_confirm] = 1
        signals[overbought_count >= min_confirm] = -1
        
        return signals
