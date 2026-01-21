"""
Yahoo Finance Feed Handler
==========================
Data feed handler using yfinance library for historical and quote data.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import logging

from .base import BaseFeed

logger = logging.getLogger(__name__)


class YFinanceFeed(BaseFeed):
    """
    Yahoo Finance data feed handler.
    
    Provides access to:
    - Real-time quotes (delayed ~15 min for most markets)
    - Historical OHLCV data
    - Company information and metadata
    
    Note: Yahoo Finance has rate limits. For heavy usage,
    consider caching responses or using a paid API.
    """
    
    # Interval mapping for yfinance
    VALID_INTERVALS = {
        '1m': '1m', '2m': '2m', '5m': '5m', '15m': '15m', '30m': '30m',
        '60m': '60m', '90m': '90m', '1h': '1h',
        '1d': '1d', '5d': '5d', '1wk': '1wk', '1mo': '1mo', '3mo': '3mo'
    }
    
    # Maximum period for each interval (yfinance limitations)
    INTERVAL_MAX_PERIOD = {
        '1m': 7, '2m': 60, '5m': 60, '15m': 60, '30m': 60,
        '60m': 730, '90m': 60, '1h': 730,
        '1d': None, '5d': None, '1wk': None, '1mo': None, '3mo': None
    }
    
    def __init__(self):
        super().__init__('yfinance')
        self._connected = True  # yfinance doesn't require connection
        self._cache = {}
    
    def _get_ticker(self, symbol: str) -> yf.Ticker:
        """Get or create a cached Ticker object."""
        if symbol not in self._cache:
            self._cache[symbol] = yf.Ticker(symbol)
        return self._cache[symbol]
    
    def get_quote(self, symbol: str) -> dict:
        """
        Get current quote for a symbol.
        
        Returns dict with: symbol, price, bid, ask, open, high, low,
                          prev_close, volume, market_cap, timestamp
        """
        try:
            ticker = self._get_ticker(symbol)
            info = ticker.info
            
            return {
                'symbol': symbol.upper(),
                'name': info.get('longName') or info.get('shortName', ''),
                'price': info.get('regularMarketPrice') or info.get('currentPrice'),
                'bid': info.get('bid'),
                'ask': info.get('ask'),
                'open': info.get('regularMarketOpen'),
                'high': info.get('regularMarketDayHigh'),
                'low': info.get('regularMarketDayLow'),
                'prev_close': info.get('regularMarketPreviousClose'),
                'volume': info.get('regularMarketVolume'),
                'market_cap': info.get('marketCap'),
                'currency': info.get('currency', 'USD'),
                'exchange': info.get('exchange'),
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            raise ValueError(f"Could not fetch quote for {symbol}: {e}")
    
    def get_ohlcv(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        Get OHLCV data for a symbol.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'MSFT')
            start: Start date (default: 1 year ago for daily)
            end: End date (default: today)
            interval: Data interval (default: '1d')
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume, symbol
        """
        if interval not in self.VALID_INTERVALS:
            raise ValueError(f"Invalid interval: {interval}. Valid: {list(self.VALID_INTERVALS.keys())}")
        
        # Set defaults
        if end is None:
            end = datetime.now()
        
        if start is None:
            max_days = self.INTERVAL_MAX_PERIOD.get(interval)
            if max_days:
                start = end - timedelta(days=max_days)
            else:
                start = end - timedelta(days=365)
        
        try:
            ticker = self._get_ticker(symbol)
            df = ticker.history(
                start=start.strftime('%Y-%m-%d'),
                end=end.strftime('%Y-%m-%d'),
                interval=interval
            )
            
            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()
            
            # Standardize column names
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            
            # Rename 'date' or 'datetime' to 'timestamp'
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'timestamp'})
            elif 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'timestamp'})
            
            # Add symbol column
            df['symbol'] = symbol.upper()
            
            # Select and order columns
            cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol']
            available_cols = [c for c in cols if c in df.columns]
            df = df[available_cols]
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            raise ValueError(f"Could not fetch OHLCV for {symbol}: {e}")
    
    def get_multiple_quotes(self, symbols: list[str]) -> pd.DataFrame:
        """
        Get quotes for multiple symbols.
        
        Returns DataFrame with one row per symbol.
        """
        quotes = []
        for symbol in symbols:
            try:
                quote = self.get_quote(symbol)
                quotes.append(quote)
            except Exception as e:
                logger.warning(f"Could not fetch {symbol}: {e}")
                continue
        
        if not quotes:
            return pd.DataFrame()
        
        return pd.DataFrame(quotes)
    
    def get_multiple_ohlcv(
        self,
        symbols: list[str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        Get OHLCV data for multiple symbols (combined DataFrame).
        """
        all_data = []
        for symbol in symbols:
            try:
                df = self.get_ohlcv(symbol, start, end, interval)
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                logger.warning(f"Could not fetch {symbol}: {e}")
                continue
        
        if not all_data:
            return pd.DataFrame()
        
        return pd.concat(all_data, ignore_index=True)
    
    def search_symbols(self, query: str) -> list[dict]:
        """
        Search for symbols matching a query.
        
        Note: yfinance has limited search capability.
        For better search, use a dedicated symbols database.
        """
        # yfinance doesn't have great search, so we do a basic lookup
        try:
            ticker = yf.Ticker(query)
            info = ticker.info
            
            if info and 'symbol' in info:
                return [{
                    'symbol': info['symbol'],
                    'name': info.get('longName') or info.get('shortName', ''),
                    'exchange': info.get('exchange', ''),
                    'type': info.get('quoteType', '')
                }]
        except Exception:
            pass
        
        return []
    
    def get_info(self, symbol: str) -> dict:
        """
        Get detailed company information.
        
        Returns comprehensive info including financials,
        company description, sector, industry, etc.
        """
        try:
            ticker = self._get_ticker(symbol)
            return ticker.info
        except Exception as e:
            logger.error(f"Error fetching info for {symbol}: {e}")
            return {}


# Convenience function for quick data fetching
def fetch_ohlcv(
    symbol: str,
    period: str = '1y',
    interval: str = '1d',
    exclude_today: bool = True
) -> pd.DataFrame:
    """
    Quick function to fetch OHLCV data.
    
    Args:
        symbol: Ticker symbol
        period: Time period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')
        interval: Data interval ('1m', '5m', '1h', '1d', '1wk', '1mo')
        exclude_today: If True, excludes today's potentially incomplete bar (default: True)
                       This ensures deterministic backtests by only using settled data.
    
    Returns:
        DataFrame with OHLCV data
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    
    if df.empty:
        return pd.DataFrame()
    
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    
    if 'date' in df.columns:
        df = df.rename(columns={'date': 'timestamp'})
    
    # Exclude today's incomplete bar for daily data to ensure deterministic backtests
    # During market hours, today's bar is incomplete and will change
    if exclude_today and interval in ['1d', '1wk', '1mo']:
        today = pd.Timestamp.now().normalize()
        if 'timestamp' in df.columns:
            # Convert to date for comparison (remove timezone if present)
            df_dates = pd.to_datetime(df['timestamp']).dt.tz_localize(None).dt.normalize()
            df = df[df_dates < today]
    
    df['symbol'] = symbol.upper()
    
    if df.empty:
        return pd.DataFrame()
    
    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol']]
