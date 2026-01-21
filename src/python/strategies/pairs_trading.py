"""
Pairs Trading Strategy
======================
Statistical arbitrage strategy that trades the spread between two correlated assets.

Note: This is a simplified single-asset version that simulates pairs trading
by using a synthetic spread against a benchmark or the asset's own mean.
For true pairs trading, you would need to load two symbols simultaneously.
"""

import pandas as pd
import numpy as np
from .base import BaseStrategy, sma


class PairsTradingStrategy(BaseStrategy):
    """
    Pairs Trading / Mean Reversion Strategy.
    
    This strategy identifies when an asset has deviated significantly
    from its historical relationship (spread) and trades the reversion.
    
    In this simplified single-asset version, we trade based on:
    - Z-score of price relative to a rolling mean (proxy for spread)
    - Entry when z-score exceeds threshold
    - Exit when z-score reverts toward zero
    
    For actual pairs trading with two assets, extend this class
    to compute the spread between two symbols.
    
    Parameters:
        lookback: Rolling window for mean/std calculation (default: 60)
        entry_z: Z-score threshold for entry (default: 2.0)
        exit_z: Z-score threshold for exit (default: 0.5)
        use_log_prices: Use log prices for spread calculation (default: True)
    """
    
    def __init__(
        self,
        lookback: int = 60,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        use_log_prices: bool = True
    ):
        super().__init__(
            name='PairsTrading',
            params={
                'lookback': lookback,
                'entry_z': entry_z,
                'exit_z': exit_z,
                'use_log_prices': use_log_prices,
                'min_history': lookback + 10
            }
        )
        self._position_side = 0  # 1 = long spread, -1 = short spread
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate signals based on z-score of the spread.
        
        Buy when spread is too low (expect reversion up).
        Sell when spread is too high (expect reversion down).
        """
        close = data['close']
        lookback = self.params['lookback']
        entry_z = self.params['entry_z']
        exit_z = self.params['exit_z']
        
        # Use log prices for better statistical properties
        if self.params['use_log_prices']:
            prices = np.log(close)
        else:
            prices = close
        
        # Calculate rolling statistics
        rolling_mean = prices.rolling(window=lookback).mean()
        rolling_std = prices.rolling(window=lookback).std()
        
        # Calculate z-score (spread from mean)
        z_score = (prices - rolling_mean) / rolling_std
        
        signals = pd.Series(0, index=data.index)
        
        # Entry signals
        # Buy (long spread): z-score very negative, expect price to rise
        buy_entry = z_score < -entry_z
        # Sell (short spread): z-score very positive, expect price to fall  
        sell_entry = z_score > entry_z
        
        # Exit signals (reversion toward mean)
        exit_long = z_score > -exit_z  # Z-score risen back toward 0
        exit_short = z_score < exit_z   # Z-score fallen back toward 0
        
        # Generate signals with state tracking
        position = 0
        for i in range(len(signals)):
            if position == 0:
                # No position - look for entry
                if buy_entry.iloc[i]:
                    signals.iloc[i] = 1
                    position = 1
                elif sell_entry.iloc[i]:
                    signals.iloc[i] = -1
                    position = -1
            elif position == 1:
                # Long position - look for exit
                if exit_long.iloc[i]:
                    signals.iloc[i] = -1  # Close long
                    position = 0
            elif position == -1:
                # Short position - look for exit
                if exit_short.iloc[i]:
                    signals.iloc[i] = 1  # Close short
                    position = 0
        
        return signals
    
    def calculate_half_life(self, spread: pd.Series) -> float:
        """
        Calculate the half-life of mean reversion using OLS.
        
        This helps determine optimal holding period and lookback.
        Returns the number of periods for the spread to revert halfway to the mean.
        """
        # Lag the spread
        spread_lag = spread.shift(1)
        spread_diff = spread - spread_lag
        
        # Remove NaN
        mask = ~(spread_lag.isna() | spread_diff.isna())
        y = spread_diff[mask].values
        x = spread_lag[mask].values
        
        if len(x) < 10:
            return float('nan')
        
        # OLS regression: spread_diff = alpha + beta * spread_lag
        x_with_const = np.column_stack([np.ones(len(x)), x])
        try:
            beta = np.linalg.lstsq(x_with_const, y, rcond=None)[0][1]
            if beta >= 0:
                return float('nan')  # Not mean reverting
            half_life = -np.log(2) / beta
            return half_life
        except:
            return float('nan')


class CointegrationStrategy(BaseStrategy):
    """
    Cointegration-based Pairs Trading Strategy.
    
    Uses the Augmented Dickey-Fuller test concept to identify
    mean-reverting behavior and trade accordingly.
    
    This is a more sophisticated version that adapts the lookback
    period based on the estimated half-life of mean reversion.
    
    Parameters:
        base_lookback: Base lookback for spread calculation (default: 60)
        entry_z: Z-score threshold for entry (default: 2.0)
        exit_z: Z-score threshold for exit (default: 0.5)
        adaptive_lookback: Adjust lookback based on half-life (default: True)
    """
    
    def __init__(
        self,
        base_lookback: int = 60,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        adaptive_lookback: bool = True
    ):
        super().__init__(
            name='Cointegration',
            params={
                'base_lookback': base_lookback,
                'entry_z': entry_z,
                'exit_z': exit_z,
                'adaptive_lookback': adaptive_lookback,
                'min_history': base_lookback + 20
            }
        )
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals based on cointegration spread."""
        close = data['close']
        base_lookback = self.params['base_lookback']
        entry_z = self.params['entry_z']
        exit_z = self.params['exit_z']
        
        # Log prices
        log_prices = np.log(close)
        
        # Calculate rolling regression residuals (spread)
        def calc_spread(window):
            if len(window) < base_lookback:
                return np.nan
            x = np.arange(len(window))
            y = window.values
            try:
                slope, intercept = np.polyfit(x, y, 1)
                predicted = slope * x[-1] + intercept
                return y[-1] - predicted
            except:
                return np.nan
        
        spread = log_prices.rolling(window=base_lookback).apply(calc_spread, raw=False)
        
        # Z-score of spread
        spread_mean = spread.rolling(window=base_lookback).mean()
        spread_std = spread.rolling(window=base_lookback).std()
        z_score = (spread - spread_mean) / spread_std
        
        signals = pd.Series(0, index=data.index)
        
        # Entry/exit logic
        position = 0
        for i in range(len(signals)):
            z = z_score.iloc[i]
            if pd.isna(z):
                continue
                
            if position == 0:
                if z < -entry_z:
                    signals.iloc[i] = 1
                    position = 1
                elif z > entry_z:
                    signals.iloc[i] = -1
                    position = -1
            elif position == 1:
                if z > -exit_z:
                    signals.iloc[i] = -1
                    position = 0
            elif position == -1:
                if z < exit_z:
                    signals.iloc[i] = 1
                    position = 0
        
        return signals
