"""
PyKX Bridge
===========
Bridge between Python and kdb+/q using PyKX library.
"""

import os
from typing import Optional, Union, Any
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Try to import pykx
try:
    import pykx as kx
    PYKX_AVAILABLE = True
except ImportError:
    PYKX_AVAILABLE = False
    logger.warning("PyKX not installed. kdb+ integration will be limited.")


class KDBConnection:
    """
    Connection manager for kdb+/q database.
    
    Usage:
        # IPC mode (connect to running q process)
        conn = KDBConnection(host='localhost', port=5010)
        result = conn.query('select from trade where sym=`AAPL')
        
        # Embedded mode (run q locally)
        conn = KDBConnection(embedded=True)
        conn.execute('t:([] a:1 2 3; b:`x`y`z)')
        df = conn.query('select from t').pd()
    """
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5010,
        username: str = '',
        password: str = '',
        embedded: bool = False
    ):
        if not PYKX_AVAILABLE:
            raise RuntimeError("PyKX is not installed. Run: pip install pykx")
        
        self.host = host
        self.port = port
        self.embedded = embedded
        self._conn = None
        
        if embedded:
            self._init_embedded()
        else:
            self._connect(host, port, username, password)
    
    def _init_embedded(self):
        """Initialize embedded q interpreter."""
        try:
            self._conn = kx
            logger.info("Initialized embedded q interpreter")
        except Exception as e:
            logger.error(f"Failed to initialize embedded q: {e}")
            raise
    
    def _connect(self, host: str, port: int, username: str, password: str):
        """Connect to remote kdb+ server via IPC."""
        try:
            self._conn = kx.SyncQConnection(
                host=host,
                port=port,
                username=username,
                password=password
            )
            logger.info(f"Connected to kdb+ at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to kdb+ at {host}:{port}: {e}")
            raise
    
    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        if self.embedded:
            return self._conn is not None
        try:
            self._conn('1+1')
            return True
        except Exception:
            return False
    
    def query(self, q_expr: str) -> Any:
        """
        Execute a q expression and return the result.
        
        Args:
            q_expr: q expression to execute
            
        Returns:
            PyKX result object (can be converted with .py() or .pd())
        """
        try:
            if self.embedded:
                return self._conn.q(q_expr)
            return self._conn(q_expr)
        except Exception as e:
            logger.error(f"Query error: {e}")
            raise
    
    def execute(self, q_expr: str):
        """Execute a q expression without returning result."""
        self.query(q_expr)
    
    def query_df(self, q_expr: str) -> pd.DataFrame:
        """Execute query and return result as pandas DataFrame."""
        result = self.query(q_expr)
        return result.pd()
    
    def insert(self, table: str, data: Union[dict, pd.DataFrame]):
        """
        Insert data into a kdb+ table.
        
        Args:
            table: Table name
            data: Dictionary or DataFrame to insert
        """
        if isinstance(data, pd.DataFrame):
            data = data.to_dict('list')
        
        try:
            if self.embedded:
                self._conn.q(f'`{table} insert', data)
            else:
                self._conn(f'`{table} insert', data)
            logger.debug(f"Inserted data into {table}")
        except Exception as e:
            logger.error(f"Insert error: {e}")
            raise
    
    def upsert(self, table: str, data: Union[dict, pd.DataFrame]):
        """
        Upsert data into a kdb+ table.
        
        Args:
            table: Table name
            data: Dictionary or DataFrame to upsert
        """
        if isinstance(data, pd.DataFrame):
            data = data.to_dict('list')
        
        try:
            if self.embedded:
                self._conn.q(f'`{table} upsert', data)
            else:
                self._conn(f'`{table} upsert', data)
            logger.debug(f"Upserted data into {table}")
        except Exception as e:
            logger.error(f"Upsert error: {e}")
            raise
    
    def load_script(self, script_path: str):
        """Load and execute a q script file."""
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script not found: {script_path}")
        
        abs_path = os.path.abspath(script_path)
        self.execute(f'\\l {abs_path}')
        logger.info(f"Loaded script: {script_path}")
    
    def get_tables(self) -> list:
        """Get list of tables in the current namespace."""
        result = self.query('tables[]')
        return [str(t) for t in result.py()]
    
    def describe_table(self, table: str) -> pd.DataFrame:
        """Get schema information for a table."""
        return self.query_df(f'meta {table}')
    
    def close(self):
        """Close the connection."""
        if not self.embedded and self._conn:
            try:
                self._conn.close()
                logger.info("Connection closed")
            except Exception:
                pass
        self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Convenience functions for quick access
def connect(host: str = 'localhost', port: int = 5010) -> KDBConnection:
    """Create a connection to kdb+ server."""
    return KDBConnection(host=host, port=port)


def embedded() -> KDBConnection:
    """Create an embedded q session."""
    return KDBConnection(embedded=True)
