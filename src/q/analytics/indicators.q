/ ============================================================================
/ Technical Indicators Library
/ ============================================================================
/ Core technical analysis indicators for algorithmic trading
/ All functions operate on vectors (lists) for kdb+ efficiency
/
/ Usage:
/   \l analytics/indicators.q
/   sma[20; prices]           / 20-period SMA
/   ema[12; prices]           / 12-period EMA
/   rsi[14; prices]           / 14-period RSI
/   macd[prices]              / MACD with default 12,26,9 periods
/ ============================================================================

\d .ind

/ ----------------------------------------------------------------------------
/ Moving Averages
/ ----------------------------------------------------------------------------

/ Simple Moving Average
/ @param n - period
/ @param x - price series
sma:{[n;x] mavg[n;x]}

/ Exponential Moving Average
/ @param n - period
/ @param x - price series
ema:{[n;x]
    alpha:2.0%1+n;
    {[a;prev;curr] (a*curr)+(1-a)*prev}[alpha]\[first x;x]
  }

/ Weighted Moving Average
/ @param n - period
/ @param x - price series
wma:{[n;x]
    w:1+til n;
    {[w;x] (sum w*x)%sum w}[w] each {[n;i;x] (neg n)#(i+1)#x}[n;;x] each til count x
  }

/ Double Exponential Moving Average (DEMA)
/ @param n - period
/ @param x - price series
dema:{[n;x] (2*ema[n;x])-ema[n;ema[n;x]]}

/ Triple Exponential Moving Average (TEMA)
/ @param n - period
/ @param x - price series
tema:{[n;x]
    e1:ema[n;x];
    e2:ema[n;e1];
    e3:ema[n;e2];
    (3*e1)-(3*e2)+e3
  }

/ ----------------------------------------------------------------------------
/ Momentum Indicators
/ ----------------------------------------------------------------------------

/ Relative Strength Index (RSI)
/ @param n - period (typically 14)
/ @param x - price series
rsi:{[n;x]
    d:deltas x;
    gains:0|d;
    losses:0|neg d;
    avgGain:ema[n;gains];
    avgLoss:ema[n;losses];
    rs:avgGain%avgLoss;
    100-100%1+rs
  }

/ Stochastic Oscillator %K and %D
/ @param n - lookback period (typically 14)
/ @param k - %K smoothing (typically 3)
/ @param d - %D smoothing (typically 3)
/ @param h - high prices
/ @param l - low prices
/ @param c - close prices
/ Returns: table with k and d columns
stochastic:{[n;kSmooth;dSmooth;h;l;c]
    hh:n mmax h;         / highest high
    ll:n mmin l;         / lowest low
    rawK:100*(c-ll)%(hh-ll);
    k:sma[kSmooth;rawK]; / %K smoothed
    d:sma[dSmooth;k];    / %D (signal line)
    ([] k:k; d:d)
  }

/ Rate of Change (ROC)
/ @param n - period
/ @param x - price series
roc:{[n;x] 100*(x-n xprev x)%n xprev x}

/ Momentum
/ @param n - period
/ @param x - price series
momentum:{[n;x] x - n xprev x}

/ ----------------------------------------------------------------------------
/ Volatility Indicators
/ ----------------------------------------------------------------------------

/ Bollinger Bands
/ @param n - period (typically 20)
/ @param k - standard deviations (typically 2)
/ @param x - price series
/ Returns: table with upper, middle, lower bands
bollinger:{[n;k;x]
    mid:sma[n;x];
    sd:mdev[n;x];
    ([] upper:mid+k*sd; middle:mid; lower:mid-k*sd)
  }

/ Average True Range (ATR)
/ @param n - period (typically 14)
/ @param h - high prices
/ @param l - low prices
/ @param c - close prices
atr:{[n;h;l;c]
    pc:1 xprev c;                      / previous close
    tr:(h-l)|(abs h-pc)|(abs l-pc);    / true range
    ema[n;tr]
  }

/ Standard Deviation
/ @param n - period
/ @param x - price series
stdev:{[n;x] mdev[n;x]}

/ Historical Volatility (annualized)
/ @param n - period
/ @param x - price series
/ @param periods - trading periods per year (252 for daily)
hvol:{[n;periods;x]
    ret:log x%1 xprev x;    / log returns
    (sqrt periods)*mdev[n;ret]
  }

/ ----------------------------------------------------------------------------
/ Trend Indicators
/ ----------------------------------------------------------------------------

/ Moving Average Convergence Divergence (MACD)
/ @param x - price series
/ @param fast - fast EMA period (default 12)
/ @param slow - slow EMA period (default 26)
/ @param signal - signal line period (default 9)
/ Returns: table with macd, signal, histogram
macd:{[x;fast;slow;sig]
    if[null fast; fast:12];
    if[null slow; slow:26];
    if[null sig; sig:9];
    m:ema[fast;x]-ema[slow;x];
    s:ema[sig;m];
    ([] macd:m; signal:s; histogram:m-s)
  }

/ Average Directional Index (ADX)
/ @param n - period (typically 14)
/ @param h - high prices
/ @param l - low prices
/ @param c - close prices
/ Returns: table with pdi, mdi, adx (Plus DI, Minus DI, ADX)
adx:{[n;h;l;c]
    / True Range
    pc:1 xprev c;
    tr:(h-l)|(abs h-pc)|(abs l-pc);
    
    / Directional Movement
    upMove:h - 1 xprev h;
    downMove:(1 xprev l) - l;
    
    plusDM:(upMove>downMove) & upMove>0;
    plusDM:plusDM*upMove;
    
    minusDM:(downMove>upMove) & downMove>0;
    minusDM:minusDM*downMove;
    
    / Smoothed values
    atr:ema[n;tr];
    plusDI:100*ema[n;plusDM]%atr;
    minusDI:100*ema[n;minusDM]%atr;
    
    / ADX
    dx:100*abs[plusDI-minusDI]%plusDI+minusDI;
    adxVal:ema[n;dx];
    
    ([] pdi:plusDI; mdi:minusDI; adx:adxVal)
  }

/ Parabolic SAR (simplified version)
/ @param af - acceleration factor (typically 0.02)
/ @param maxAf - maximum acceleration (typically 0.2)
/ @param h - high prices
/ @param l - low prices
psar:{[af;maxAf;h;l]
    / Simplified implementation - returns SAR values
    / Full implementation would need state tracking
    n:count h;
    sar:n#0f;
    trend:1;  / 1 = up, -1 = down
    ep:h 0;   / extreme point
    currAf:af;
    sar[0]:l 0;
    
    / Iterate through prices
    i:1;
    while[i<n;
        if[trend=1;
            sar[i]:sar[i-1]+currAf*(ep-sar[i-1]);
            sar[i]:sar[i]&(l i-1)&l i;
            if[h[i]>ep; ep:h i; currAf:currAf+af; currAf:currAf&maxAf];
            if[l[i]<sar i; trend:-1; sar[i]:ep; ep:l i; currAf:af]
        ];
        if[trend=-1;
            sar[i]:sar[i-1]-currAf*(sar[i-1]-ep);
            sar[i]:sar[i]|(h i-1)|h i;
            if[l[i]<ep; ep:l i; currAf:currAf+af; currAf:currAf&maxAf];
            if[h[i]>sar i; trend:1; sar[i]:ep; ep:h i; currAf:af]
        ];
        i+:1
    ];
    sar
  }

/ ----------------------------------------------------------------------------
/ Volume Indicators
/ ----------------------------------------------------------------------------

/ On-Balance Volume (OBV)
/ @param c - close prices
/ @param v - volume
obv:{[c;v]
    d:signum deltas c;
    sums d*v
  }

/ Volume Weighted Average Price (VWAP)
/ @param h - high prices
/ @param l - low prices
/ @param c - close prices
/ @param v - volume
vwap:{[h;l;c;v]
    typical:(h+l+c)%3;
    sums[typical*v]%sums v
  }

/ Money Flow Index (MFI)
/ @param n - period (typically 14)
/ @param h - high prices
/ @param l - low prices
/ @param c - close prices
/ @param v - volume
mfi:{[n;h;l;c;v]
    typical:(h+l+c)%3;
    mf:typical*v;
    posMf:(typical>1 xprev typical)*mf;
    negMf:(typical<1 xprev typical)*mf;
    mfr:(n msum posMf)%n msum negMf;
    100-100%(1+mfr)
  }

/ ----------------------------------------------------------------------------
/ Support/Resistance
/ ----------------------------------------------------------------------------

/ Pivot Points (Standard)
/ @param h - high (single value or last)
/ @param l - low (single value or last)
/ @param c - close (single value or last)
/ Returns: dict with pp, r1, r2, r3, s1, s2, s3
pivots:{[h;l;c]
    pp:(h+l+c)%3;
    `pp`r1`r2`r3`s1`s2`s3!(
        pp;
        (2*pp)-l;      / R1
        pp+h-l;        / R2
        h+2*(pp-l);    / R3
        (2*pp)-h;      / S1
        pp-h-l;        / S2
        l-2*(h-pp)     / S3
    )
  }

/ Fibonacci Retracement Levels
/ @param high - swing high
/ @param low - swing low
/ Returns: dict with fib levels
fib:{[high;low]
    diff:high-low;
    `l0`l236`l382`l500`l618`l786`l1!(
        high;
        high-0.236*diff;
        high-0.382*diff;
        high-0.500*diff;
        high-0.618*diff;
        high-0.786*diff;
        low
    )
  }

/ ----------------------------------------------------------------------------
/ Signal Generation Helpers
/ ----------------------------------------------------------------------------

/ Crossover detection: 1 when x crosses above y
crossover:{[x;y] (x>y) & (1 xprev x)<1 xprev y}

/ Crossunder detection: 1 when x crosses below y
crossunder:{[x;y] (x<y) & (1 xprev x)>1 xprev y}

/ Generate signals based on condition
/ @param cond - boolean vector of conditions
/ Returns: 1 for buy, -1 for sell (first occurrence only)
signal:{[cond] 
    d:deltas cond;
    (d=1)-(d=-1)
  }

\d .

/ Quick access aliases
sma:.ind.sma
ema:.ind.ema
rsi:.ind.rsi
macd:.ind.macd
bollinger:.ind.bollinger
atr:.ind.atr
