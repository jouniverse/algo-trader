"""
FRED (Federal Reserve Economic Data) Feed Handler
==================================================
Fetches economic indicators from the FRED API.

Usage:
    feed = FREDFeed(api_key='your_key')
    gdp = feed.get_series('GDP')
    vix = feed.get_series('VIXCLS')
    
Common Series IDs:
    - GDP: Gross Domestic Product
    - UNRATE: Unemployment Rate
    - CPIAUCSL: Consumer Price Index
    - FEDFUNDS: Federal Funds Rate
    - DGS10: 10-Year Treasury Rate
    - VIXCLS: VIX (Volatility Index)
    - UMCSENT: Consumer Sentiment
    - INDPRO: Industrial Production
    
API Documentation: https://fred.stlouisfed.org/docs/api/fred/
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# Common economic indicators
COMMON_INDICATORS = {
    # Growth
    'GDP': 'Gross Domestic Product',
    'GDPC1': 'Real GDP',
    'INDPRO': 'Industrial Production Index',
    
    # Employment
    'UNRATE': 'Unemployment Rate',
    'PAYEMS': 'Total Nonfarm Payrolls',
    'ICSA': 'Initial Jobless Claims',
    
    # Inflation
    'CPIAUCSL': 'Consumer Price Index (All Urban)',
    'CPILFESL': 'Core CPI (Less Food & Energy)',
    'PCEPI': 'PCE Price Index',
    
    # Interest Rates
    'FEDFUNDS': 'Federal Funds Rate',
    'DGS2': '2-Year Treasury Rate',
    'DGS10': '10-Year Treasury Rate',
    'DGS30': '30-Year Treasury Rate',
    'T10Y2Y': '10Y-2Y Treasury Spread',
    
    # Market Indicators
    'VIXCLS': 'VIX (CBOE Volatility Index)',
    'SP500': 'S&P 500 Index',
    'NASDAQCOM': 'NASDAQ Composite',
    
    # Sentiment
    'UMCSENT': 'Consumer Sentiment (U of Michigan)',
    
    # Housing
    'HOUST': 'Housing Starts',
    'CSUSHPISA': 'Case-Shiller Home Price Index',
}


class FREDFeed:
    """
    FRED data feed handler.
    
    Fetches economic time series data from the Federal Reserve
    Economic Data (FRED) API.
    """
    
    BASE_URL = 'https://api.stlouisfed.org/fred'
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FRED feed.
        
        Args:
            api_key: FRED API key. If not provided, looks for FRED_API_KEY env var.
        """
        self.api_key = api_key or os.getenv('FRED_API_KEY')
        if not self.api_key:
            logger.warning("No FRED API key provided. Set FRED_API_KEY environment variable.")
        
        self._cache = {}
    
    def _make_request(self, endpoint: str, params: dict) -> dict:
        """Make API request to FRED."""
        params['api_key'] = self.api_key
        params['file_type'] = 'json'
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"FRED API error: {e}")
            raise
    
    def _sanitize_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Ensure date is in YYYY-MM-DD format for FRED API.
        Handles various input formats including timestamps with timezone.
        """
        if not date_str:
            return None
        
        # If already in correct format, return as-is
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            return date_str
        
        # Try to parse and extract date
        try:
            # Handle ISO format with T separator
            if 'T' in date_str:
                return date_str.split('T')[0]
            # Handle datetime with space separator
            if ' ' in date_str:
                return date_str.split(' ')[0]
            # Try parsing with pandas
            dt = pd.to_datetime(date_str)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            # Return first 10 chars as fallback
            return date_str[:10] if len(date_str) >= 10 else date_str
    
    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch a FRED series.
        
        Args:
            series_id: FRED series ID (e.g., 'GDP', 'UNRATE', 'VIXCLS')
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            frequency: Data frequency ('d', 'w', 'm', 'q', 'a')
        
        Returns:
            DataFrame with 'date' and 'value' columns
        """
        params = {'series_id': series_id}
        
        # Sanitize date formats
        start_date = self._sanitize_date(start_date)
        end_date = self._sanitize_date(end_date)
        
        if start_date:
            params['observation_start'] = start_date
        if end_date:
            params['observation_end'] = end_date
        if frequency:
            params['frequency'] = frequency
        
        data = self._make_request('series/observations', params)
        
        if 'observations' not in data:
            logger.warning(f"No data returned for {series_id}")
            return pd.DataFrame()
        
        df = pd.DataFrame(data['observations'])
        
        if df.empty:
            return df
        
        # Convert types
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        
        # Remove missing values (FRED uses '.' for missing)
        df = df.dropna(subset=['value'])
        
        return df[['date', 'value']].rename(columns={'value': series_id.lower()})
    
    def get_series_info(self, series_id: str) -> dict:
        """Get metadata about a series."""
        params = {'series_id': series_id}
        data = self._make_request('series', params)
        
        if 'seriess' in data and len(data['seriess']) > 0:
            return data['seriess'][0]
        return {}
    
    def search_series(self, query: str, limit: int = 10) -> List[dict]:
        """
        Search for series by keyword.
        
        Returns list of matching series with id, title, frequency.
        """
        params = {
            'search_text': query,
            'limit': limit,
            'order_by': 'popularity',
            'sort_order': 'desc'
        }
        
        data = self._make_request('series/search', params)
        
        results = []
        for series in data.get('seriess', []):
            results.append({
                'id': series['id'],
                'title': series['title'],
                'frequency': series.get('frequency_short', 'Unknown'),
                'units': series.get('units_short', ''),
                'last_updated': series.get('last_updated', '')
            })
        
        return results
    
    def get_multiple_series(
        self,
        series_ids: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch multiple series and merge into single DataFrame.
        
        Returns DataFrame indexed by date with one column per series.
        """
        dfs = []
        
        for series_id in series_ids:
            try:
                df = self.get_series(series_id, start_date, end_date)
                if not df.empty:
                    df = df.set_index('date')
                    dfs.append(df)
            except Exception as e:
                logger.warning(f"Could not fetch {series_id}: {e}")
        
        if not dfs:
            return pd.DataFrame()
        
        # Merge all series
        result = dfs[0]
        for df in dfs[1:]:
            result = result.join(df, how='outer')
        
        return result.reset_index()
    
    def get_macro_snapshot(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get a snapshot of key macro indicators.
        
        Fetches: VIX, Fed Funds Rate, 10Y Treasury, Unemployment, CPI.
        """
        indicators = ['VIXCLS', 'FEDFUNDS', 'DGS10', 'UNRATE', 'CPIAUCSL']
        return self.get_multiple_series(indicators, start_date, end_date)
    
    @staticmethod
    def list_common_indicators() -> dict:
        """Return dictionary of common indicators and descriptions."""
        return COMMON_INDICATORS.copy()


# Convenience function
def get_fred_series(series_id: str, api_key: Optional[str] = None) -> pd.DataFrame:
    """Quick function to fetch a FRED series."""
    feed = FREDFeed(api_key)
    return feed.get_series(series_id)
