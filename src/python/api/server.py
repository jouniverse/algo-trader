"""
API Server
==========
FastAPI server for the algo-trader application.
Provides REST endpoints and WebSocket for real-time data.
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from pathlib import Path
import asyncio
import json
import logging
import os
import math

# Import our modules
from ..feedhandlers import YFinanceFeed, FREDFeed
from ..backtest import BacktestEngine, BacktestConfig


def load_api_keys(config_path: str = None) -> dict:
    """
    Load API keys from config/API_KEYS.txt file.

    Format: KEY=VALUE (one per line, # for comments)
    Falls back to environment variables if file not found.
    """
    keys = {}

    if config_path is None:
        # Find the config file relative to the project root
        # server.py is in src/python/api/, so go up 3 levels to project root
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "config" / "API_KEYS.txt"

    config_path = Path(config_path)

    if config_path.exists():
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    keys[key.strip()] = value.strip()

    return keys


# Load API keys from config file
_api_keys = load_api_keys()

# Get FRED API key (config file takes precedence, then env var)
FRED_API_KEY = _api_keys.get("FRED_API_KEY") or os.getenv("FRED_API_KEY")
from ..strategies import (
    BuyAndHoldStrategy,
    MomentumStrategy,
    RSIStrategy,
    MACDStrategy,
    TrendFollowingStrategy,
    BollingerBandsStrategy,
    MeanReversionStrategy,
    PairsTradingStrategy,
)

logger = logging.getLogger(__name__)

# Initialize feed
feed = YFinanceFeed()


def sanitize_float(value, field_name: str = None):
    """Convert inf/nan to JSON-safe values."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isinf(value):
            # Use None for infinity - UI will display appropriately
            return None
        if math.isnan(value):
            return None
    return value


def sanitize_dict(d: dict) -> dict:
    """Recursively sanitize a dictionary for JSON serialization."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = sanitize_dict(v)
        elif isinstance(v, list):
            result[k] = [
                sanitize_dict(x) if isinstance(x, dict) else sanitize_float(x)
                for x in v
            ]
        else:
            result[k] = sanitize_float(v)
    return result


# ============================================================================
# Pydantic Models
# ============================================================================


class QuoteRequest(BaseModel):
    symbol: str


class OHLCVRequest(BaseModel):
    symbol: str
    period: str = "1y"
    interval: str = "1d"


class BacktestRequest(BaseModel):
    symbol: str
    strategy: str
    period: str = "1y"
    initial_capital: float = 100000
    params: Optional[dict] = None


class SymbolSearchRequest(BaseModel):
    query: str


# ============================================================================
# App Factory
# ============================================================================


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="Algo-Trader API",
        description="Algorithmic Trading Analytics Platform",
        version="0.1.0",
    )

    # CORS for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ========================================================================
    # Routes
    # ========================================================================

    @app.get("/")
    async def root():
        return {"message": "Algo-Trader API", "version": "0.1.0"}

    @app.get("/health")
    async def health():
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}

    # ------------------------------------------------------------------------
    # Market Data Endpoints
    # ------------------------------------------------------------------------

    @app.get("/api/quote/{symbol}")
    async def get_quote(symbol: str):
        """Get current quote for a symbol."""
        try:
            quote = feed.get_quote(symbol.upper())
            return quote
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/ohlcv/{symbol}")
    async def get_ohlcv(symbol: str, period: str = "1y", interval: str = "1d"):
        """Get OHLCV data for a symbol."""
        try:
            from ..feedhandlers.yfinance_feed import fetch_ohlcv

            df = fetch_ohlcv(symbol.upper(), period, interval)

            if df.empty:
                raise HTTPException(status_code=404, detail=f"No data for {symbol}")

            # Convert to JSON-serializable format
            df["timestamp"] = df["timestamp"].astype(str)
            return df.to_dict(orient="records")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/quotes")
    async def get_multiple_quotes(symbols: List[str]):
        """Get quotes for multiple symbols."""
        try:
            df = feed.get_multiple_quotes(symbols)
            df["timestamp"] = df["timestamp"].astype(str)
            return df.to_dict(orient="records")
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ------------------------------------------------------------------------
    # Economic Data (FRED) Endpoints
    # ------------------------------------------------------------------------

    @app.get("/api/macro/{start_date}/{end_date}")
    async def get_macro_context(start_date: str, end_date: str):
        """
        Get macro economic indicators for a date range.

        Returns VIX, Fed Funds Rate, 10Y Treasury, and S&P 500 data.
        """
        try:
            fred = FREDFeed(api_key=FRED_API_KEY)

            # Fetch key indicators
            indicators = {}
            indicator_ids = {
                "vix": "VIXCLS",
                "fed_funds": "FEDFUNDS",
                "treasury_10y": "DGS10",
                "sp500": "SP500",
            }

            for name, series_id in indicator_ids.items():
                try:
                    df = fred.get_series(series_id, start_date, end_date)
                    if not df.empty:
                        df["date"] = df["date"].astype(str)
                        col_name = df.columns[1]  # The value column
                        # Get summary stats
                        values = df[col_name].dropna()
                        indicators[name] = {
                            "data": df.to_dict(orient="records"),
                            "latest": (
                                float(values.iloc[-1]) if len(values) > 0 else None
                            ),
                            "avg": float(values.mean()) if len(values) > 0 else None,
                            "min": float(values.min()) if len(values) > 0 else None,
                            "max": float(values.max()) if len(values) > 0 else None,
                        }
                except Exception as e:
                    logger.warning(f"Could not fetch {series_id}: {e}")
                    indicators[name] = None

            return {
                "period": {"start": start_date, "end": end_date},
                "indicators": indicators,
            }

        except Exception as e:
            logger.exception("FRED API error")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/fred/series/{series_id}")
    async def get_fred_series(
        series_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ):
        """Get a specific FRED series."""
        try:
            fred = FREDFeed(api_key=FRED_API_KEY)
            df = fred.get_series(series_id, start_date, end_date)

            if df.empty:
                raise HTTPException(status_code=404, detail=f"No data for {series_id}")

            df["date"] = df["date"].astype(str)
            return df.to_dict(orient="records")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ------------------------------------------------------------------------
    # Strategy Endpoints
    # ------------------------------------------------------------------------

    @app.get("/api/strategies")
    async def list_strategies():
        """List available trading strategies."""
        return {
            "strategies": [
                {
                    "id": "buy_hold",
                    "name": "Buy & Hold (Baseline)",
                    "description": "Buy at start, hold until end - benchmark strategy",
                    "params": {},
                },
                {
                    "id": "momentum",
                    "name": "Momentum (MA Crossover)",
                    "description": "Dual moving average crossover strategy",
                    "params": {
                        "fast_period": {
                            "type": "int",
                            "default": 10,
                            "min": 2,
                            "max": 50,
                        },
                        "slow_period": {
                            "type": "int",
                            "default": 30,
                            "min": 10,
                            "max": 200,
                        },
                        "ma_type": {
                            "type": "choice",
                            "options": ["sma", "ema"],
                            "default": "sma",
                        },
                    },
                },
                {
                    "id": "macd",
                    "name": "MACD Crossover",
                    "description": "MACD line crossing signal line",
                    "params": {
                        "fast_period": {
                            "type": "int",
                            "default": 12,
                            "min": 5,
                            "max": 20,
                        },
                        "slow_period": {
                            "type": "int",
                            "default": 26,
                            "min": 15,
                            "max": 40,
                        },
                        "signal_period": {
                            "type": "int",
                            "default": 9,
                            "min": 5,
                            "max": 15,
                        },
                    },
                },
                {
                    "id": "rsi",
                    "name": "RSI Strategy",
                    "description": "Relative Strength Index overbought/oversold",
                    "params": {
                        "period": {"type": "int", "default": 14, "min": 5, "max": 30},
                        "oversold": {
                            "type": "float",
                            "default": 30,
                            "min": 10,
                            "max": 40,
                        },
                        "overbought": {
                            "type": "float",
                            "default": 70,
                            "min": 60,
                            "max": 90,
                        },
                    },
                },
                {
                    "id": "trend_following",
                    "name": "Trend Following",
                    "description": "Multi-timeframe trend strategy with MA filters",
                    "params": {
                        "short_period": {
                            "type": "int",
                            "default": 10,
                            "min": 5,
                            "max": 20,
                        },
                        "medium_period": {
                            "type": "int",
                            "default": 50,
                            "min": 20,
                            "max": 100,
                        },
                        "long_period": {
                            "type": "int",
                            "default": 200,
                            "min": 100,
                            "max": 300,
                        },
                    },
                },
                {
                    "id": "bollinger",
                    "name": "Bollinger Bands",
                    "description": "Mean reversion on Bollinger Band touches",
                    "params": {
                        "period": {"type": "int", "default": 20, "min": 10, "max": 50},
                        "std_dev": {
                            "type": "float",
                            "default": 2.0,
                            "min": 1.0,
                            "max": 3.0,
                        },
                    },
                },
                {
                    "id": "mean_reversion",
                    "name": "Mean Reversion (Z-Score)",
                    "description": "Trade reversion to mean using z-score",
                    "params": {
                        "lookback": {
                            "type": "int",
                            "default": 20,
                            "min": 10,
                            "max": 60,
                        },
                        "z_threshold": {
                            "type": "float",
                            "default": 2.0,
                            "min": 1.0,
                            "max": 3.0,
                        },
                        "exit_threshold": {
                            "type": "float",
                            "default": 0.5,
                            "min": 0.0,
                            "max": 1.5,
                        },
                    },
                },
                {
                    "id": "pairs_trading",
                    "name": "Pairs Trading",
                    "description": "Statistical arbitrage based on spread z-score",
                    "params": {
                        "lookback": {
                            "type": "int",
                            "default": 60,
                            "min": 20,
                            "max": 120,
                        },
                        "entry_z": {
                            "type": "float",
                            "default": 2.0,
                            "min": 1.0,
                            "max": 3.0,
                        },
                        "exit_z": {
                            "type": "float",
                            "default": 0.5,
                            "min": 0.0,
                            "max": 1.5,
                        },
                    },
                },
            ]
        }

    # ------------------------------------------------------------------------
    # Backtest Endpoints
    # ------------------------------------------------------------------------

    @app.post("/api/backtest")
    async def run_backtest(request: BacktestRequest):
        """Run a backtest with specified strategy."""
        try:
            # Get data
            from ..feedhandlers.yfinance_feed import fetch_ohlcv

            df = fetch_ohlcv(request.symbol.upper(), request.period, "1d")

            if df.empty:
                raise HTTPException(
                    status_code=404, detail=f"No data for {request.symbol}"
                )

            # Add symbol column if missing
            if "symbol" not in df.columns:
                df["symbol"] = request.symbol.upper()

            # Create strategy
            params = request.params or {}

            if request.strategy == "buy_hold":
                strategy = BuyAndHoldStrategy()

            elif request.strategy == "momentum":
                strategy = MomentumStrategy(
                    fast_period=params.get("fast_period", 10),
                    slow_period=params.get("slow_period", 30),
                    ma_type=params.get("ma_type", "sma"),
                )

            elif request.strategy == "macd":
                strategy = MACDStrategy(
                    fast_period=params.get("fast_period", 12),
                    slow_period=params.get("slow_period", 26),
                    signal_period=params.get("signal_period", 9),
                )

            elif request.strategy == "rsi":
                strategy = RSIStrategy(
                    period=params.get("period", 14),
                    oversold=params.get("oversold", 30),
                    overbought=params.get("overbought", 70),
                )

            elif request.strategy == "trend_following":
                strategy = TrendFollowingStrategy(
                    short_period=params.get("short_period", 10),
                    medium_period=params.get("medium_period", 50),
                    long_period=params.get("long_period", 200),
                )

            elif request.strategy == "bollinger":
                strategy = BollingerBandsStrategy(
                    period=params.get("period", 20), std_dev=params.get("std_dev", 2.0)
                )

            elif request.strategy == "mean_reversion":
                strategy = MeanReversionStrategy(
                    lookback=params.get("lookback", 20),
                    z_threshold=params.get("z_threshold", 2.0),
                    exit_threshold=params.get("exit_threshold", 0.5),
                )

            elif request.strategy == "pairs_trading":
                strategy = PairsTradingStrategy(
                    lookback=params.get("lookback", 60),
                    entry_z=params.get("entry_z", 2.0),
                    exit_z=params.get("exit_z", 0.5),
                )

            else:
                raise HTTPException(
                    status_code=400, detail=f"Unknown strategy: {request.strategy}"
                )

            # Run backtest
            config = BacktestConfig(initial_capital=request.initial_capital)
            engine = BacktestEngine(config)
            engine.load_data(df)
            engine.set_strategy(strategy)
            results = engine.run()

            # Format results
            equity_curve = results["equity_curve"].copy()
            equity_curve["timestamp"] = equity_curve["timestamp"].astype(str)

            trades = results["trades"]
            if not trades.empty:
                trades = trades.copy()
                trades["entry_time"] = trades["entry_time"].astype(str)
                trades["exit_time"] = trades["exit_time"].astype(str)

            # Sanitize metrics to handle inf/nan values
            metrics = sanitize_dict(results["metrics"])

            # Sanitize equity curve and trades
            equity_data = [
                sanitize_dict(row) for row in equity_curve.to_dict(orient="records")
            ]
            trades_data = (
                [sanitize_dict(row) for row in trades.to_dict(orient="records")]
                if not trades.empty
                else []
            )

            return {
                "symbol": request.symbol,
                "strategy": request.strategy,
                "params": params,
                "metrics": metrics,
                "equity_curve": equity_data,
                "trades": trades_data,
                "final_equity": sanitize_float(results["final_equity"]),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Backtest error")
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------------
    # WebSocket for Real-time Updates
    # ------------------------------------------------------------------------

    class ConnectionManager:
        def __init__(self):
            self.active_connections: List[WebSocket] = []

        async def connect(self, websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)

        def disconnect(self, websocket: WebSocket):
            self.active_connections.remove(websocket)

        async def broadcast(self, message: str):
            for connection in self.active_connections:
                await connection.send_text(message)

    manager = ConnectionManager()

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "subscribe":
                    symbol = message.get("symbol")
                    # For now, send mock updates
                    await websocket.send_text(
                        json.dumps({"type": "subscribed", "symbol": symbol})
                    )

        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


# For running with uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
