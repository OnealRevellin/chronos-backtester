# Trading Strategies Backtester (Chronos Backtester)

A modular quantitative trading backtesting framework written in Python (this first version is not leveraging HPC but more focused on accuracy and analytics).

The project is designed around:

* Multi-strategy execution
* Centralized portfolio management
* Capital allocation engines
* Deterministic backtesting
* In-sample / out-of-sample evaluation
* Execution simulation (fees/slippage)
* Risk overlays
* Portfolio analytics and performance tracking

---

# Example Output

## long only position (lumpsum) on MSCI World ETF (ACC).
```text
================================================================================
BACKTEST START
================================================================================
[2012-12-25 17:30:00] Initial equity: 1,000,000.00

[2012-12-25 17:30:00] ORDERS | count=1
  BUY    292.000000 MSCI_WORLD_NET_USD @  3419.360000 | notional=    998,453.12 | type=market | tif=day

[2012-12-25 17:30:00] FILLS | count=1
  BUY    292.000000 MSCI_WORLD_NET_USD @  3419.360000 | notional=    998,453.12 | fee=   1996.91
  Fees this tick: 1,996.91 | Cumulative fees: 1,996.91

[2026-04-27 17:30:00] ORDERS | count=1
  SELL   292.000000 MSCI_WORLD_NET_USD @ 14936.030000 | notional=  4,361,320.76 | type=market | tif=day

[2026-04-27 17:30:00] FILLS | count=1
  SELL   292.000000 MSCI_WORLD_NET_USD @ 14936.030000 | notional=  4,361,320.76 | fee=   8722.64
  Fees this tick: 8,722.64 | Cumulative fees: 10,719.55
[2026-04-27 17:30:00] EQUITY: 4,352,148.09 | cash=4,352,148.09 | positions=0

================================================================================
BACKTEST SUMMARY
================================================================================
Initial equity: 1,000,000.00
Final equity:   4,352,148.09
PnL:            3,352,148.09 (+335.21%)
Cumulative fees:10,719.55
Final cash:     4,352,148.09
Final positions:{}

================================================================================
PERFORMANCE METRICS
================================================================================
CAGR:           11.68%
Max Drawdown:   -34.04%
Sharpe Ratio:   0.5411 (risk-free rate fixed to 4%)
```

Equity line:
![alt text](<msci world long only eq line.png>)

---

## Mean reverting strategy (our params: price > 14d avg + 3% => Short position, 
## price < 14d avg - 3% => Long position) on MSCI World ETF (ACC).
```text
================================================================================
BACKTEST SUMMARY
================================================================================
Initial equity: 1,000,000.00
Final equity:   298,017.11
PnL:            -701,982.89 (-70.20%)
Cumulative fees:138,820.35
Final cash:     298,017.11
Final positions:{}

================================================================================
PERFORMANCE METRICS
================================================================================
CAGR:           -8.68%
Max Drawdown:   -76.82%
Sharpe Ratio:   -0.8404 (risk-free rate fixed to 4%)
```

Equity line:
![alt text](<msci world mean_reversion long_short eq line.png>)

---

## Momentum strategy (our params: price > 14d avg + 3% => Long position, 
## price < 14d avg - 3% => Short position) on MSCI World ETF (ACC).
```text
================================================================================
BACKTEST SUMMARY
================================================================================
Initial equity: 1,000,000.00
Final equity:   298,017.11
PnL:            -701,982.89 (-70.20%)
Cumulative fees:138,820.35
Final cash:     298,017.11
Final positions:{}

================================================================================
PERFORMANCE METRICS
================================================================================
CAGR:           -8.68%
Max Drawdown:   -76.82%
Sharpe Ratio:   -0.8404 (risk-free rate fixed to 4%)
```

Equity line:
![alt text](<msci world momentum long_short eq line.png>)

---


# Architecture Overview

The backtesting pipeline is:

```text
Clock
  -> DataHandler
      -> Strategy signals
          -> AllocationEngine
              -> Portfolio order generation
                  -> Broker execution simulation
                      -> Portfolio updates
                          -> Recorder / Analytics
```

Main modules:

```text
src/
├── accounting/
├── analytics/
├── backtesting/
├── data/
├── execution/
├── metrics/
├── portfolio/
├── risk/
└── strategy/
```

---

# Installation

## Clone repository

```bash
git clone https://github.com/OnealRevellin/chronos-backtester.git
cd chronos-backtester
```

## Create environment

```bash
python -m venv venv
source venv/bin/activate
```

Windows:

```powershell
venv\Scripts\activate
```

## Install dependencies

```bash
pip install -r requirements.txt
```

---

# Running a Backtest

The main example is located in:

```text
src/backtesting/engine.py
```

You can run it directly:

```bash
python -m src.backtesting.engine
```

---

# Example Backtest Configuration

## 1. Configure market data

```python
tmp = "data_storage/parquet/MSCI_WORLD_NET_USD.parquet"
```

Other available datasets (you can add your own .parquet files using the available examples as a template):

```python
# data_storage/parquet/MSCI_WORLD.parquet
# data_storage/parquet/EURUSD_hourly.parquet
```

---

## 2. Configure the clock

```python
clock_config = ClockConfig(
    start=pd.Timestamp("2012-12-25 17:30"),
    end=pd.Timestamp("2026-04-27 17:30"),
    freq="1d",
    keep_weekends=False,
)
```

Parameters:

| Parameter     | Description                  |
| ------------- | ---------------------------- |
| start         | Backtest start timestamp     |
| end           | Backtest end timestamp       |
| freq          | Frequency (`1d`, `1h`, etc.) |
| keep_weekends | Include weekends or not      |

Initialize:

```python
clock = Clock(clock_config)
```

---

## 3. Create the DataHandler

```python
dh = DataHandler(
    clock=timestamps,
    universe=["MSCI_WORLD", "EURUSD", "MSCI_WORLD_NET_USD"],
    config=DataHandlerConfig(
        file_path=tmp,
        ohlcv_cols=("open", "close", "high", "low")
    ),
)
```

Responsibilities:

* Load parquet/csv market data
* Serve synchronized market snapshots
* Provide OHLCV data to strategies

---

# Strategies

Example strategy:

```python
Below we implement a lumpsum long only strategy on a MSCI world Acc ETF 
strategies = [
    AlwaysLong(symbol="MSCI_WORLD_NET_USD", weight=1.0),
]
```

Alternative example:

```python
Below we implement a dollar cost averaging strategy on a MSCI world Acc ETF
(4% of the total capital invested every 40 days)
strategies = [
    DollarCostAveraging(
        symbol="MSCI_WORLD",
        weight=0.04,
        interval_ticks=40,
    )
]
```

Each strategy must implement:

```python
on_data(self, ctx: Context) -> StrategyOutput
```

The strategy receives the current market context and returns signals.

---

# Portfolio Configuration

```python
portfolio = MasterPortfolio(
    initial_cash=1_000_000.0,
    instrument_rules={
        "EURUSD": {
            "in_lots": False,
            "integer": False,
        },
        "MSCI_WORLD": {
            "in_lots": False,
            "integer": True,
        },
    },
)
```

Parameters:

| Parameter     | Description                                                           |
| ------------- | --------------------------------------------------------------------- |
| in_lots       | True -> udl contract quotes in lots                                   |
| integer       | True -> udl qty is an int (eg: shares, lots) / False -> eg: FX, BTC   |

Responsibilities:

* Track positions
* Track cash
* Compute equity
* Generate orders
* Apply fills

---

# Broker and Execution

```python
broker = Broker(
    fee_rate=0.002,
    min_fee=0.0,
)
```

Responsibilities:

* Simulate executions
* Apply transaction fees
* Generate fills

---

# Allocation Engine

```python
alloc_engine = AllocationEngine(
    max_gross=1.0,
    normalize=True,
    mode="capital_based"
)
```

Responsibilities:

* Normalize strategy weights
* Enforce gross exposure limits
* Convert signals into target allocations

---

# Engine Initialization

```python
engine = BacktestingEngine(
    cfg=EngineConfig(
        universe=["MSCI_WORLD", "EURUSD", "MSCI_WORLD_NET_USD"],
        min_size=1.0,
        verbose=True,
        log_orders=True,
        log_fills=True,
    ),
    data_handler=dh,
    strategies=strategies,
    portfolio=portfolio,
    broker=broker,
    recorder=portfolio_recorder,
    allocation_engine=alloc_engine,
)
```

---

# Run the Backtest

```python
recorder = engine.run(clock)
```

This performs:

1. Clock iteration
2. Market data update
3. Strategy evaluation
4. Allocation computation
5. Order generation
6. Broker execution
7. Portfolio update
8. Metrics recording

---

# Results and Analytics

Plot equity curve:

```python
recorder.plot_equity_line()
```

Export metrics:

```python
print(recorder.metrics_df())
```

Export positions:

```python
print(recorder.positions_df())
```

The engine also computes:

* CAGR
* Max Drawdown
* Sharpe Ratio
* Final Equity
* PnL
* Fees

---

# Current Features

* Deterministic backtesting
* Multi-strategy orchestration
* Centralized portfolio accounting
* Fee simulation
* Allocation engine
* Portfolio recorder
* Performance analytics
* Equity curve plotting
* Parquet market data support

---

# Future Improvements

Potential future extensions:

* Event-driven execution
* Slippage models
* Multi-asset portfolio constraints
* Position sizing models
* Walk-forward testing
* Parallelized strategy execution
* Live trading adapters
* Advanced risk overlays
* Factor attribution
* Transaction cost analysis

---

# Notes

The project is currently structured as a research-oriented backtesting engine with a modular architecture suitable for extension toward production quantitative trading systems.
