# Trading Strategies Documentation

This document describes the trading strategies available in Algo-Trader, their underlying logic, parameters, and guidance on when to use them.

---

## Table of Contents

1. [Buy & Hold (Baseline)](#1-buy--hold-baseline)
2. [Momentum (MA Crossover)](#2-momentum-ma-crossover)
3. [MACD Crossover](#3-macd-crossover)
4. [RSI Strategy](#4-rsi-strategy)
5. [Trend Following](#5-trend-following)
6. [Bollinger Bands](#6-bollinger-bands)
7. [Mean Reversion (Z-Score)](#7-mean-reversion-z-score)
8. [Pairs Trading](#8-pairs-trading)
9. [Strategy Selection Guide](#strategy-selection-guide)
10. [Parameter Optimization Tips](#parameter-optimization-tips)

---

## 1. Buy & Hold (Baseline)

### Description
The simplest possible strategy: buy at the start of the period and hold until the end. This serves as a **benchmark** to compare active strategies against.

### Logic
```
Day 1: Buy with full position size
Days 2-N: Hold (no action)
```

### Parameters
None — this is a passive strategy.

### When to Use
- As a baseline comparison for other strategies
- During strong bull markets (active strategies often underperform)
- When transaction costs would erode active trading profits

### Interpretation
If an active strategy can't beat Buy & Hold after accounting for trading costs, the active strategy may not add value. In efficient markets, passive strategies often outperform.

---

## 2. Momentum (MA Crossover)

### Description
A trend-following strategy based on **moving average crossovers**. When the fast MA crosses above the slow MA, it signals upward momentum (buy). When it crosses below, it signals downward momentum (sell).

### Logic
```
BUY:  Fast MA crosses ABOVE Slow MA (golden cross)
SELL: Fast MA crosses BELOW Slow MA (death cross)
```

### Parameters
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `fast_period` | 10 | 2-50 | Period for fast moving average |
| `slow_period` | 30 | 10-200 | Period for slow moving average |
| `ma_type` | "sma" | sma/ema | Type of moving average |

### Parameter Tuning
- **Shorter periods** (5/20): More signals, more responsive, more false signals
- **Longer periods** (20/50 or 50/200): Fewer signals, more reliable, slower to react
- **EMA vs SMA**: EMA reacts faster to recent price changes

### Best Market Conditions
- Trending markets with sustained moves
- Not recommended for choppy, range-bound markets

---

## 3. MACD Crossover

### Description
The **Moving Average Convergence Divergence (MACD)** measures the relationship between two EMAs. The strategy trades when the MACD line crosses the signal line.

### Logic
```
MACD Line = EMA(fast) - EMA(slow)
Signal Line = EMA(signal) of MACD Line
Histogram = MACD Line - Signal Line

BUY:  MACD Line crosses ABOVE Signal Line
SELL: MACD Line crosses BELOW Signal Line
```

### Parameters
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `fast_period` | 12 | 5-20 | Fast EMA period |
| `slow_period` | 26 | 15-40 | Slow EMA period |
| `signal_period` | 9 | 5-15 | Signal line EMA period |

### Parameter Tuning
- **Standard (12/26/9)**: Classic settings, works for most assets
- **Faster (5/13/8)**: More sensitive, better for short-term trading
- **Slower (19/39/9)**: Fewer false signals, better for position trading

### Best Market Conditions
- Trending markets
- Can identify trend changes earlier than simple MA crossovers

---

## 4. RSI Strategy

### Description
The **Relative Strength Index (RSI)** measures momentum on a 0-100 scale. This strategy trades mean reversion: buy when RSI indicates oversold (expecting bounce), sell when overbought (expecting pullback).

### Logic
```
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss over N periods

BUY:  RSI crosses UP through oversold level (e.g., 30)
SELL: RSI crosses DOWN through overbought level (e.g., 70)
```

### Parameters
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `period` | 14 | 5-30 | RSI calculation period |
| `oversold` | 30 | 10-40 | Buy when RSI rises above this level |
| `overbought` | 70 | 60-90 | Sell when RSI falls below this level |

### Parameter Tuning
- **Tighter bands (20/80)**: Fewer but more extreme signals
- **Wider bands (40/60)**: More signals, more false positives
- **Shorter period**: More volatile RSI, more signals
- **Longer period**: Smoother RSI, fewer but more reliable signals

### Best Market Conditions
- Range-bound, sideways markets
- Not recommended during strong trends (RSI can stay overbought/oversold for extended periods)

---

## 5. Trend Following

### Description
A multi-timeframe strategy using **three moving averages** to filter trades. Only takes trades in the direction of the major trend.

### Logic
```
Short MA  (10):  Entry timing
Medium MA (50):  Trend direction
Long MA   (200): Major trend filter

BUY:  Price > Long MA AND Short MA crosses ABOVE Medium MA
SELL: Price < Long MA AND Short MA crosses BELOW Medium MA
```

### Parameters
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `short_period` | 10 | 5-20 | Short-term MA for entry signals |
| `medium_period` | 50 | 20-100 | Medium-term MA for trend direction |
| `long_period` | 200 | 100-300 | Long-term MA for trend filter |

### Parameter Tuning
- **10/50/200**: Standard, good for daily timeframe
- **5/20/50**: More active, suitable for shorter timeframes
- **20/100/200**: More conservative, fewer trades

### Best Market Conditions
- Strong trending markets
- Reduces whipsaws by requiring alignment across multiple timeframes

---

## 6. Bollinger Bands

### Description
Bollinger Bands consist of a middle band (SMA) with upper and lower bands at N standard deviations. This strategy trades **mean reversion** when price touches the bands.

### Logic
```
Middle Band = SMA(period)
Upper Band = Middle + (std_dev × Standard Deviation)
Lower Band = Middle - (std_dev × Standard Deviation)

BUY:  Price crosses BELOW Lower Band (oversold)
SELL: Price crosses ABOVE Upper Band (overbought)
```

### Parameters
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `period` | 20 | 10-50 | SMA period for middle band |
| `std_dev` | 2.0 | 1.0-3.0 | Number of standard deviations |

### Parameter Tuning
- **Wider bands (2.5-3.0)**: Fewer signals, captures extreme moves
- **Narrower bands (1.5-2.0)**: More signals, more false positives
- **Longer period**: Smoother bands, less responsive
- **Shorter period**: More volatile bands, more responsive

### Best Market Conditions
- Range-bound markets with clear support/resistance
- Less effective during strong trends (price can "walk the band")

---

## 7. Mean Reversion (Z-Score)

### Description
A statistical approach to mean reversion using **z-scores**. Measures how many standard deviations the current price is from its rolling mean.

### Logic
```
Z-Score = (Price - Rolling Mean) / Rolling Std Dev

BUY:  Z-Score < -entry_threshold (price is very low)
SELL: Z-Score > +entry_threshold (price is very high)
EXIT: |Z-Score| < exit_threshold (price returned to mean)
```

### Parameters
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `lookback` | 20 | 10-60 | Rolling window for mean/std calculation |
| `z_threshold` | 2.0 | 1.0-3.0 | Entry z-score threshold |
| `exit_threshold` | 0.5 | 0.0-1.5 | Exit z-score threshold |

### Parameter Tuning
- **Higher z_threshold (2.5+)**: Fewer trades, more extreme entries
- **Lower z_threshold (1.5)**: More trades, risk of trading noise
- **Longer lookback**: More stable mean estimate, slower to adapt
- **Shorter lookback**: More responsive, potentially noisy

### Best Market Conditions
- Mean-reverting assets (some commodities, pairs)
- Range-bound markets
- Avoid during regime changes or trending markets

---

## 8. Pairs Trading

### Description
A **statistical arbitrage** strategy that trades the spread between an asset and its expected value. This simplified version uses a single asset and trades deviations from its own rolling mean (proxy for a pairs spread).

### Logic
```
Spread = Log(Price) - Rolling Mean of Log(Price)
Z-Score of Spread = Spread / Rolling Std Dev

BUY:  Spread Z-Score < -entry_z (undervalued)
SELL: Spread Z-Score > +entry_z (overvalued)
EXIT: Z-Score reverts toward exit_z
```

### Parameters
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `lookback` | 60 | 20-120 | Rolling window for spread calculation |
| `entry_z` | 2.0 | 1.0-3.0 | Entry z-score threshold |
| `exit_z` | 0.5 | 0.0-1.5 | Exit z-score threshold |

### Parameter Tuning
- **Longer lookback (60-90)**: More stable spread estimate
- **Shorter lookback (20-30)**: More responsive to recent behavior
- **Half-life optimization**: Ideally, set lookback near the asset's mean reversion half-life

### True Pairs Trading
For actual pairs trading with two correlated assets:
1. Find cointegrated pairs (Engle-Granger test)
2. Calculate spread: `Spread = Price_A - β × Price_B`
3. Trade the spread's z-score

### Best Market Conditions
- Highly correlated or cointegrated pairs
- Market-neutral (hedges out market risk)
- Works in both trending and range-bound markets

---

## Strategy Selection Guide

### By Market Condition

| Market Condition | Recommended Strategies |
|------------------|----------------------|
| **Strong Uptrend** | Buy & Hold, Trend Following, Momentum |
| **Strong Downtrend** | Trend Following (short), Mean Reversion (carefully) |
| **Range-bound/Sideways** | RSI, Bollinger Bands, Mean Reversion, Pairs Trading |
| **High Volatility** | Wider Bollinger Bands, higher z-thresholds |
| **Low Volatility** | Narrower bands, lower thresholds, or avoid trading |

### By Trading Style

| Style | Recommended Strategies |
|-------|----------------------|
| **Long-term (weeks-months)** | Buy & Hold, Trend Following (50/200) |
| **Medium-term (days-weeks)** | Momentum, MACD, RSI |
| **Short-term (hours-days)** | Fast Momentum, Bollinger Bands |

### By Risk Tolerance

| Risk Level | Approach |
|------------|----------|
| **Conservative** | Longer periods, higher thresholds, fewer trades |
| **Moderate** | Default parameters, balanced approach |
| **Aggressive** | Shorter periods, lower thresholds, more trades |

---

## Parameter Optimization Tips

### General Guidelines

1. **Avoid overfitting**: Don't optimize on the exact data you'll test on
2. **Use walk-forward analysis**: Optimize on past data, test on unseen future data
3. **Consider transaction costs**: More trades = more costs
4. **Test across multiple assets**: Parameters should generalize

### Optimization Process

1. **Define objective**: Sharpe ratio? Total return? Max drawdown?
2. **Set parameter ranges**: Use reasonable bounds (see tables above)
3. **Grid search or random search**: Test parameter combinations
4. **Out-of-sample validation**: Reserve 20-30% of data for final test
5. **Monte Carlo validation**: Randomize trade order to test robustness

### Red Flags

- ⚠️ Parameters that work on one asset but fail on similar assets
- ⚠️ Extremely high Sharpe ratios (>3) often indicate overfitting
- ⚠️ Few trades (<20) make statistics unreliable
- ⚠️ Results highly sensitive to small parameter changes

---

## References

- **Moving Averages**: Murphy, J. (1999). *Technical Analysis of the Financial Markets*
- **RSI**: Wilder, J.W. (1978). *New Concepts in Technical Trading Systems*
- **Bollinger Bands**: Bollinger, J. (2001). *Bollinger on Bollinger Bands*
- **Pairs Trading**: Vidyamurthy, G. (2004). *Pairs Trading: Quantitative Methods and Analysis*
- **Mean Reversion**: Pole, A. (2007). *Statistical Arbitrage*
