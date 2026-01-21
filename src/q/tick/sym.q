/ sym.q - Schema definitions for ticker plant
/ ============================================
/ Defines the table schemas for trade and quote data
/
/ Usage: Load before starting ticker plant
/   q sym.q

/ Trade table schema
/ - time: timestamp of the trade
/ - sym: symbol (stock ticker)
/ - price: trade price
/ - size: number of shares
trade:([]
    time:`timestamp$();
    sym:`symbol$();
    price:`float$();
    size:`long$()
  )

/ Quote table schema  
/ - time: timestamp of the quote
/ - sym: symbol (stock ticker)
/ - bid: best bid price
/ - ask: best ask price
/ - bsize: bid size (shares at bid)
/ - asize: ask size (shares at ask)
quote:([]
    time:`timestamp$();
    sym:`symbol$();
    bid:`float$();
    ask:`float$();
    bsize:`long$();
    asize:`long$()
  )

/ OHLCV bar table (for aggregated data)
/ - time: bar timestamp
/ - sym: symbol
/ - open/high/low/close: OHLC prices
/ - volume: total volume in bar
bar:([]
    time:`timestamp$();
    sym:`symbol$();
    open:`float$();
    high:`float$();
    low:`float$();
    close:`float$();
    volume:`long$()
  )

/ Order table (for execution tracking)
/ - time: order timestamp
/ - sym: symbol
/ - side: `B for buy, `S for sell
/ - qty: order quantity
/ - price: order price
/ - status: order status
order:([]
    time:`timestamp$();
    sym:`symbol$();
    side:`symbol$();
    qty:`long$();
    price:`float$();
    status:`symbol$()
  )

/ Position table (for portfolio tracking)
/ - sym: symbol
/ - qty: quantity held
/ - avgCost: average cost basis
/ - lastPrice: last traded price
/ - unrealizedPnL: unrealized P&L
position:([]
    sym:`symbol$();
    qty:`long$();
    avgCost:`float$();
    lastPrice:`float$();
    unrealizedPnL:`float$()
  )

/ Apply grouped attribute to sym columns for faster queries
`sym xasc `trade;
`sym xasc `quote;

/ Helper functions for data insertion
/ Insert trade with automatic timestamp
insertTrade:{[s;p;sz]
    `trade insert (.z.P; s; p; sz)
  }

/ Insert quote with automatic timestamp
insertQuote:{[s;b;a;bs;as]
    `quote insert (.z.P; s; b; a; bs; as)
  }

/ Generate OHLCV bars from trades
/ @param t - table of trades
/ @param period - bar period (e.g., `minute, `hour)
generateBars:{[t;period]
    select 
        open:first price, 
        high:max price, 
        low:min price, 
        close:last price, 
        volume:sum size 
    by time:period xbar time, sym from t
  }
