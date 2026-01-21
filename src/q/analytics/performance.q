/ ============================================================================
/ Performance & Risk Metrics Library
/ ============================================================================
/ Portfolio and strategy performance analytics
/
/ Usage:
/   \l analytics/performance.q
/   .perf.returns[prices]           / Calculate returns
/   .perf.sharpe[returns;0.02]      / Sharpe ratio with 2% risk-free rate
/   .perf.maxDrawdown[equity]       / Maximum drawdown
/ ============================================================================

\d .perf

/ ----------------------------------------------------------------------------
/ Return Calculations
/ ----------------------------------------------------------------------------

/ Simple returns
/ @param x - price series
returns:{[x] (x%1 xprev x)-1}

/ Log returns
/ @param x - price series
logReturns:{[x] log x%1 xprev x}

/ Cumulative returns from simple returns
/ @param r - returns series
cumReturns:{[r] (prd 1+r)-1}

/ Annualized returns
/ @param r - returns series
/ @param periods - periods per year (252 for daily, 12 for monthly)
annualizedReturn:{[r;periods]
    n:count r;
    totalReturn:prd 1+r;
    (totalReturn xexp periods%n)-1
  }

/ ----------------------------------------------------------------------------
/ Risk Metrics
/ ----------------------------------------------------------------------------

/ Sharpe Ratio
/ @param r - returns series
/ @param rf - risk-free rate (annualized, e.g., 0.02 for 2%)
/ @param periods - periods per year (252 for daily)
sharpe:{[r;rf;periods]
    if[null periods; periods:252];
    excessReturn:(avg r)-(rf%periods);
    annualizedExcess:excessReturn*periods;
    annualizedVol:(dev r)*sqrt periods;
    annualizedExcess%annualizedVol
  }

/ Sortino Ratio (uses downside deviation)
/ @param r - returns series
/ @param rf - risk-free rate
/ @param periods - periods per year
sortino:{[r;rf;periods]
    if[null periods; periods:252];
    excessReturn:(avg r)-(rf%periods);
    annualizedExcess:excessReturn*periods;
    / Downside deviation (only negative returns)
    downside:r where r<0;
    downsideVol:(dev downside)*sqrt periods;
    annualizedExcess%downsideVol
  }

/ Maximum Drawdown
/ @param equity - equity curve (cumulative values)
maxDrawdown:{[equity]
    peak:maxs equity;
    dd:(peak-equity)%peak;
    max dd
  }

/ Drawdown series
/ @param equity - equity curve
drawdowns:{[equity]
    peak:maxs equity;
    (peak-equity)%peak
  }

/ Calmar Ratio (annualized return / max drawdown)
/ @param r - returns series
/ @param periods - periods per year
calmar:{[r;periods]
    if[null periods; periods:252];
    equity:prds 1+r;
    ar:annualizedReturn[r;periods];
    mdd:maxDrawdown[equity];
    ar%mdd
  }

/ Value at Risk (VaR) - Historical method
/ @param r - returns series
/ @param confidence - confidence level (e.g., 0.95 for 95%)
var:{[r;confidence]
    sorted:asc r;
    idx:`int$(1-confidence)*count r;
    sorted idx
  }

/ Conditional VaR (Expected Shortfall)
/ @param r - returns series
/ @param confidence - confidence level
cvar:{[r;confidence]
    varLevel:var[r;confidence];
    avg r where r<=varLevel
  }

/ Volatility (annualized standard deviation)
/ @param r - returns series
/ @param periods - periods per year
volatility:{[r;periods]
    if[null periods; periods:252];
    (dev r)*sqrt periods
  }

/ Beta (relative to benchmark)
/ @param r - portfolio returns
/ @param rb - benchmark returns
beta:{[r;rb]
    cov[r;rb]%var rb
  }

/ Alpha (Jensen's alpha)
/ @param r - portfolio returns
/ @param rb - benchmark returns
/ @param rf - risk-free rate (per period)
alpha:{[r;rb;rf]
    b:beta[r;rb];
    avg[r]-rf-b*(avg[rb]-rf)
  }

/ Information Ratio
/ @param r - portfolio returns
/ @param rb - benchmark returns
/ @param periods - periods per year
informationRatio:{[r;rb;periods]
    if[null periods; periods:252];
    activeReturn:r-rb;
    annualizedActive:(avg activeReturn)*periods;
    trackingError:(dev activeReturn)*sqrt periods;
    annualizedActive%trackingError
  }

/ ----------------------------------------------------------------------------
/ Trade Statistics
/ ----------------------------------------------------------------------------

/ Win rate (percentage of winning trades)
/ @param trades - list of trade P&L values
winRate:{[trades]
    winners:trades where trades>0;
    (count winners)%count trades
  }

/ Profit factor (gross profit / gross loss)
/ @param trades - list of trade P&L values
profitFactor:{[trades]
    wins:sum trades where trades>0;
    losses:abs sum trades where trades<0;
    wins%losses
  }

/ Average win / average loss ratio
/ @param trades - list of trade P&L values
avgWinLossRatio:{[trades]
    avgWin:avg trades where trades>0;
    avgLoss:abs avg trades where trades<0;
    avgWin%avgLoss
  }

/ Expectancy (expected value per trade)
/ @param trades - list of trade P&L values
expectancy:{[trades]
    wr:winRate[trades];
    avgWin:avg trades where trades>0;
    avgLoss:abs avg trades where trades<0;
    (wr*avgWin)-(1-wr)*avgLoss
  }

/ Maximum consecutive wins
/ @param trades - list of trade P&L values
maxConsecWins:{[trades]
    wins:trades>0;
    runs:differ wins;
    groups:(sums runs);
    winGroups:groups where wins;
    if[0=count winGroups; :0];
    max count each group winGroups
  }

/ Maximum consecutive losses
/ @param trades - list of trade P&L values
maxConsecLosses:{[trades]
    losses:trades<0;
    runs:differ losses;
    groups:(sums runs);
    lossGroups:groups where losses;
    if[0=count lossGroups; :0];
    max count each group lossGroups
  }

/ ----------------------------------------------------------------------------
/ Summary Report
/ ----------------------------------------------------------------------------

/ Generate comprehensive performance summary
/ @param r - returns series
/ @param rf - risk-free rate (annualized)
/ @param periods - periods per year
summary:{[r;rf;periods]
    if[null rf; rf:0.0];
    if[null periods; periods:252];
    
    equity:prds 1+r;
    
    `totalReturn`annualizedReturn`volatility`sharpe`sortino`maxDrawdown`calmar`var95`cvar95!(
        cumReturns[r];
        annualizedReturn[r;periods];
        volatility[r;periods];
        sharpe[r;rf;periods];
        sortino[r;rf;periods];
        maxDrawdown[equity];
        calmar[r;periods];
        var[r;0.95];
        cvar[r;0.95]
    )
  }

/ Trade statistics summary
/ @param trades - list of trade P&L values
tradeSummary:{[trades]
    `numTrades`winRate`profitFactor`avgWinLoss`expectancy`maxConsecWins`maxConsecLosses`totalPnL`avgTrade!(
        count trades;
        winRate[trades];
        profitFactor[trades];
        avgWinLossRatio[trades];
        expectancy[trades];
        maxConsecWins[trades];
        maxConsecLosses[trades];
        sum trades;
        avg trades
    )
  }

\d .

/ Quick access
sharpe:.perf.sharpe
maxDrawdown:.perf.maxDrawdown
