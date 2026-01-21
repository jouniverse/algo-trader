#!/usr/bin/env python3
"""
Backtest Example
================
Demonstrates how to run a backtest with the algo-trader framework.

Usage:
    python examples/backtest_example.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from python.feedhandlers import YFinanceFeed
from python.backtest import BacktestEngine, BacktestConfig
from python.strategies import (
    MomentumStrategy, 
    RSIStrategy, 
    BollingerBandsStrategy
)


def run_single_backtest():
    """Run a single strategy backtest."""
    print("=" * 60)
    print("Single Strategy Backtest")
    print("=" * 60)
    
    # Initialize feed and fetch data
    feed = YFinanceFeed()
    symbol = 'AAPL'
    
    print(f"\nFetching data for {symbol}...")
    data = feed.get_ohlcv(symbol, interval='1d')
    print(f"Loaded {len(data)} bars from {data['timestamp'].iloc[0]} to {data['timestamp'].iloc[-1]}")
    
    # Add symbol column
    data['symbol'] = symbol
    
    # Configure backtest
    config = BacktestConfig(
        initial_capital=100000,
        commission=0.001,      # 0.1%
        slippage=0.0005,       # 0.05%
        max_position_size=0.2  # 20% max position
    )
    
    # Create strategy
    strategy = MomentumStrategy(fast_period=10, slow_period=30, ma_type='sma')
    print(f"\nStrategy: {strategy}")
    
    # Run backtest
    print("\nRunning backtest...")
    engine = BacktestEngine(config)
    engine.load_data(data)
    engine.set_strategy(strategy)
    results = engine.run()
    
    # Print results
    metrics = results['metrics']
    print("\n" + "=" * 40)
    print("RESULTS")
    print("=" * 40)
    print(f"Total Return:      {metrics['total_return']:.2%}")
    print(f"Annualized Return: {metrics['annualized_return']:.2%}")
    print(f"Volatility:        {metrics['volatility']:.2%}")
    print(f"Sharpe Ratio:      {metrics['sharpe_ratio']:.2f}")
    print(f"Max Drawdown:      {metrics['max_drawdown']:.2%}")
    print(f"Number of Trades:  {metrics['num_trades']}")
    print(f"Win Rate:          {metrics['win_rate']:.1%}")
    print(f"Profit Factor:     {metrics['profit_factor']:.2f}")
    print(f"Final Equity:      ${metrics['final_equity']:,.2f}")
    
    return results


def compare_strategies():
    """Compare multiple strategies on the same data."""
    print("\n" + "=" * 60)
    print("Strategy Comparison")
    print("=" * 60)
    
    # Fetch data once
    feed = YFinanceFeed()
    symbol = 'SPY'
    
    print(f"\nFetching data for {symbol}...")
    data = feed.get_ohlcv(symbol, interval='1d')
    data['symbol'] = symbol
    print(f"Loaded {len(data)} bars")
    
    # Define strategies to compare
    strategies = [
        MomentumStrategy(fast_period=10, slow_period=30),
        MomentumStrategy(fast_period=5, slow_period=20),
        RSIStrategy(period=14, oversold=30, overbought=70),
        BollingerBandsStrategy(period=20, std_dev=2.0),
    ]
    
    config = BacktestConfig(initial_capital=100000)
    results = []
    
    print("\nRunning backtests...")
    for strategy in strategies:
        engine = BacktestEngine(config)
        engine.load_data(data.copy())
        engine.set_strategy(strategy)
        result = engine.run()
        results.append({
            'strategy': str(strategy),
            'metrics': result['metrics']
        })
    
    # Print comparison table
    print("\n" + "-" * 100)
    print(f"{'Strategy':<40} {'Return':>10} {'Sharpe':>10} {'MaxDD':>10} {'Trades':>8} {'WinRate':>10}")
    print("-" * 100)
    
    for r in results:
        m = r['metrics']
        print(f"{r['strategy']:<40} {m['total_return']:>9.1%} {m['sharpe_ratio']:>10.2f} {m['max_drawdown']:>9.1%} {m['num_trades']:>8} {m['win_rate']:>9.1%}")
    
    print("-" * 100)


def multi_symbol_backtest():
    """Run backtest across multiple symbols."""
    print("\n" + "=" * 60)
    print("Multi-Symbol Backtest")
    print("=" * 60)
    
    feed = YFinanceFeed()
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    
    strategy = MomentumStrategy(fast_period=10, slow_period=30)
    config = BacktestConfig(initial_capital=100000)
    
    print(f"\nStrategy: {strategy}")
    print(f"Symbols: {', '.join(symbols)}")
    
    all_results = []
    
    print("\nRunning backtests...")
    for symbol in symbols:
        try:
            data = feed.get_ohlcv(symbol, interval='1d')
            if data.empty:
                print(f"  {symbol}: No data")
                continue
            
            data['symbol'] = symbol
            
            engine = BacktestEngine(config)
            engine.load_data(data)
            engine.set_strategy(strategy)
            result = engine.run()
            
            all_results.append({
                'symbol': symbol,
                'metrics': result['metrics']
            })
            print(f"  {symbol}: Return = {result['metrics']['total_return']:.1%}")
            
        except Exception as e:
            print(f"  {symbol}: Error - {e}")
    
    # Summary
    if all_results:
        avg_return = sum(r['metrics']['total_return'] for r in all_results) / len(all_results)
        avg_sharpe = sum(r['metrics']['sharpe_ratio'] for r in all_results) / len(all_results)
        
        print(f"\nPortfolio Summary:")
        print(f"  Average Return: {avg_return:.1%}")
        print(f"  Average Sharpe: {avg_sharpe:.2f}")


if __name__ == '__main__':
    print("\n" + "#" * 60)
    print("#  ALGO-TRADER BACKTEST EXAMPLES")
    print("#" * 60)
    
    # Run examples
    run_single_backtest()
    compare_strategies()
    multi_symbol_backtest()
    
    print("\n✓ All examples completed!")
