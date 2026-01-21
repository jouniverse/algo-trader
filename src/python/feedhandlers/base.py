"""
Base Feed Handler Interface
===========================
Abstract base class for all data feed handlers.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import pandas as pd


class BaseFeed(ABC):
    """
    Abstract base class for market data feed handlers.
    
    All feed handlers must implement these methods to ensure
    consistent data format across different data sources.
    """
    
    def __init__(self, name: str):
        self.name = name
        self._connected = False
    
    @abstractmethod
    def get_quote(self, symbol: str) -> dict:
        """
        Get current quote for a symbol.
        
        Returns:
            dict with keys: symbol, price, bid, ask, volume, timestamp
        """
        pass
    
    @abstractmethod
    def get_ohlcv(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        Get OHLCV (Open, High, Low, Close, Volume) data.
        
        Args:
            symbol: Ticker symbol
            start: Start date (None = earliest available)
            end: End date (None = today)
            interval: Data interval ('1m', '5m', '1h', '1d', '1wk', '1mo')
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        pass
    
    @abstractmethod
    def get_multiple_quotes(self, symbols: list[str]) -> pd.DataFrame:
        """
        Get quotes for multiple symbols at once.
        
        Returns:
            DataFrame with one row per symbol
        """
        pass
    
    @abstractmethod
    def search_symbols(self, query: str) -> list[dict]:
        """
        Search for symbols matching a query.
        
        Returns:
            List of dicts with keys: symbol, name, exchange, type
        """
        pass
    
    def is_connected(self) -> bool:
        """Check if feed is connected and ready."""
        return self._connected
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate if a symbol exists."""
        try:
            quote = self.get_quote(symbol)
            return quote is not None and 'price' in quote
        except Exception:
            return False
