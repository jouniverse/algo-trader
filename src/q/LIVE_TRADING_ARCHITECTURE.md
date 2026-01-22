# kdb+/q Live Trading Architecture

This document describes the kdb+/q components for real-time trading that are **not currently active** in the analytics app, but are ready for integration when building a live trading system.

---

## Current State

| Component | File | Status |
|-----------|------|--------|
| Technical Indicators | `analytics/indicators.q` | ✅ Ready (standalone) |
| Performance Metrics | `analytics/performance.q` | ✅ Ready (standalone) |
| Table Schemas | `tick/sym.q` | ✅ Ready |
| Ticker Plant | `tick/tick.q`  | 📦 Reference only |
| PyKX Bridge | `python/utils/pykx_bridge.py` | ✅ Ready |

---

## Architecture for Live Trading

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LIVE DATA FEEDS                                │
│     (Broker API, Market Data Provider, WebSocket feeds)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FEEDHANDLER (Python)                             │
│  - Connects to data sources (Alpaca, IBKR, etc.)                            │
│  - Normalizes data to standard format                                       │
│  - Publishes to Ticker Plant via IPC                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TICKER PLANT (kdb+/q - port 5010)                    │
│  tick/tick.q                                                                │
│  - Receives all market data                                                 │
│  - Logs to disk for recovery                                                │
│  - Publishes to subscribers (RDB, strategy processes)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                          │                           │
                          ▼                           ▼
┌─────────────────────────────────---┐   ┌────────────────────────────────────┐
│   RDB (Real-time DB - port 5011)   │   │  STRATEGY ENGINE (Python + PyKX)   │
│   tick/r.q                         │   │  - Subscribes to TP                │
│   - In-memory current day data     │   │  - Calculates indicators           │
│   - Fast queries for analytics     │   │  - Generates signals               │
│   - End-of-day saves to HDB        │   │  - Sends orders to execution       │
└─────────────────────────────────---┘   └────────────────────────────────────┘
              │                                          │
              ▼                                          ▼
┌─────────────────────────────────---┐   ┌─────────────────────────────────────┐
│   HDB (Historical DB - port 5012)  │   │  EXECUTION ENGINE                   │
│   - Partitioned by date            │   │  - Order management                 │
│   - Years of tick data             │   │  - Risk checks                      │
│   - Analytics queries              │   │  - Broker API integration           │
└─────────────────────────────────---┘   └─────────────────────────────────────┘
```

---

## Component Details

### 1. Ticker Plant (`tick/tick.q`)

The central hub for all market data:

```q
/ Start ticker plant
q tick.q sym data/tplogs -p 5010

/ Key functions:
.u.upd[`trade; data]    / Receive trade data
.u.upd[`quote; data]    / Receive quote data
.u.pub[table; data]     / Publish to subscribers
.u.endofday[]           / End-of-day processing
```

**Configuration:**
- Port: 5010
- Log directory: `data/tplogs/`
- Schema: Defined in `tick/sym.q`

### 2. Real-time Database (`tick/r.q`)

Subscribes to ticker plant and holds today's data in memory:

```q
/ Start RDB
q tick/r.q :5010 -p 5011

/ Key tables:
trade: ([] time; sym; price; size)
quote: ([] time; sym; bid; ask; bsize; asize)

/ Example queries:
select last price by sym from trade
select avg price, sum size by 5 xbar time.minute, sym from trade
```

### 3. Historical Database (HDB)

Stores historical data partitioned by date:

```
data/hdb/
├── 2024.01.02/
│   ├── trade/
│   │   ├── time
│   │   ├── sym
│   │   ├── price
│   │   └── size
│   └── quote/
│       └── ...
├── 2024.01.03/
│   └── ...
└── sym           # Symbol enumeration file
```

```q
/ Start HDB
q data/hdb -p 5012

/ Query historical data
select from trade where date=2024.01.02, sym=`AAPL
select avg price by date from trade where sym=`AAPL
```

### 4. PyKX Bridge (`python/utils/pykx_bridge.py`)

Connects Python to kdb+ processes:

```python
from src.python.utils.pykx_bridge import KDBConnection

# Connect to RDB for real-time data
rdb = KDBConnection(host='localhost', port=5011)
trades = rdb.query_df('select last price by sym from trade')

# Connect to HDB for historical data
hdb = KDBConnection(host='localhost', port=5012)
history = hdb.query_df('select from trade where date=2024.01.02')

# Use embedded q (no external process needed)
q = KDBConnection(embedded=True)
q.load_script('src/q/analytics/indicators.q')
result = q.query('sma[20; prices]')
```

---

## Table Schemas (`tick/sym.q`)

```q
/ Trade table
trade:([]
    time:`timestamp$();
    sym:`symbol$();
    price:`float$();
    size:`long$()
)

/ Quote table
quote:([]
    time:`timestamp$();
    sym:`symbol$();
    bid:`float$();
    ask:`float$();
    bsize:`long$();
    asize:`long$()
)

/ OHLCV bar table
bar:([]
    time:`timestamp$();
    sym:`symbol$();
    open:`float$();
    high:`float$();
    low:`float$();
    close:`float$();
    volume:`long$()
)
```

---

## Integration Steps (Future)

### Step 1: Start kdb+ Infrastructure

```bash
# Terminal 1: Ticker Plant
q src/q/tick/tick.q sym data/tplogs -p 5010

# Terminal 2: RDB
q src/q/tick/r.q :5010 -p 5011

# Terminal 3: HDB
q data/hdb -p 5012
```

### Step 2: Connect Python Feedhandler

```python
import pykx as kx

# Connect to ticker plant
tp = kx.SyncQConnection(host='localhost', port=5010)

# Publish trade data
def publish_trade(sym, price, size):
    tp('{[s;p;sz] .u.upd[`trade; (.z.P; s; p; sz)]}', sym, price, size)
```

### Step 3: Strategy Subscription

```python
# Subscribe to real-time updates
def on_trade(data):
    # Calculate indicator
    # Generate signal
    # Execute order
    pass

# Async subscription
tp.subscribe('trade', symbols=['AAPL', 'MSFT'], callback=on_trade)
```

---

## Performance Considerations

| Operation | Python | kdb+/q |
|-----------|--------|--------|
| Process 1M rows | ~1 second | ~10ms |
| Join 10M rows | ~5 seconds | ~50ms |
| Time-series aggregation | Pandas works | 10-100x faster |
| Real-time streaming | Adequate | Built for it |

**When to use kdb+:**
- High-frequency data (>100 updates/second)
- Large historical datasets (>1GB)
- Complex time-series joins
- Real-time analytics during trading

**When Python is fine:**
- Backtesting with daily data
- Strategy development/research
- Small to medium datasets
- API integrations

---

## Files Reference

```
src/q/
├── analytics/
│   ├── indicators.q     # Technical indicators (SMA, RSI, etc.)
│   └── performance.q    # Performance metrics (Sharpe, drawdown, etc.)
├── tick/
│   ├── sym.q            # Table schemas
|   └── tick.q           # Main ticker plant
└── LIVE_TRADING_ARCHITECTURE.md  # This document

freezer/ticker-plant/    # Reference ticker plant implementation
├── tick.q               # Main ticker plant
├── tick/
│   ├── u.q              # Pub/sub utilities
│   ├── r.q              # RDB script
│   ├── feed.q           # Sample feed script
│   └── sym.q            # Schema definitions
```

---

## Summary

The analytics app is **pure Python** for simplicity. When we move into live trading, we can leverage the kdb+/q components outlined here for high-performance data handling and real-time analytics:

1. **Copy** ticker plant files from `freezer/ticker-plant/` to `src/q/tick/`
2. **Start** kdb+ processes (TP, RDB, HDB)
3. **Connect** Python feedhandler to broker API
4. **Publish** market data to ticker plant
5. **Subscribe** strategy engine to receive updates
6. **Execute** orders through broker API

The analytics modules (`indicators.q`, `performance.q`) can be loaded into any q process for fast calculations.
