"""
backtesting.engine

Purpose
-------
Main orchestration loop for the backtesting system.

This engine is designed for:
- Multi-strategy execution (N strategies evaluated per tick)
- Centralized capital ownership (MasterPortfolio is the single source of truth)
- Cross-strategy capital allocation (AllocationEngine)
- Risk overlays (strategy-level and global)
- Execution simulation (Broker + Slippage)
- Accounting updates (PnL, costs, exposure)
- Deterministic, reproducible runs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Protocol, Optional, Mapping

import pandas as pd

from .context import Context, StrategyOutput
from ..data.market_data import DataHandler, DataHandlerConfig
from ..portfolio.allocation import AllocationEngine
from ..portfolio.master import MasterPortfolio
from ..portfolio.portfolio_recorder import PortfolioRecorder
from ..execution.broker import Broker
from ..backtesting.clock import Clock, ClockConfig
from ..strategy.alphas.example import (
    AlwaysLong, DollarCostAveraging, MeanReversion, Momentum
)
from ..analytics.performance import PerformanceAnalyzer


class StrategyLike(Protocol):
    def on_data(self, ctx: Context) -> StrategyOutput:
        ...


@dataclass(slots=True)
class EngineConfig:
    universe: List[str]

    close_positions_at_end: Optional[bool] = True

    # orders parameters
    min_size: Optional[float] = 1e-12

    # context parameters
    strict: Optional[bool] = True

    # -----------------------------
    # logging (optional)
    # -----------------------------
    verbose: bool = False
    log_allocation: bool = False
    log_orders: bool = False
    log_fills: bool = False
    log_equity: bool = False
    log_every_n: int = 1  # print every N ticks (1 = every tick)


class BacktestingEngine:
    """
    Main backtesting engine.

    Responsibilities:
    - orchestrate the backtesting loop
    - manage strategies, portfolio, broker, clock, recorder
    """

    __slots__ = (
        "_cfg",
        "_ctx",
        "_data_handler",
        "_strategies",
        "_portfolio",
        "_broker",
        "_recorder",
        "_allocation_engine",
        "_tick",
        "_initial_equity",
        "_cum_fees",
    )

    def __init__(
        self,
        cfg: EngineConfig,
        *,
        data_handler: DataHandler,
        strategies: List[StrategyLike],
        portfolio: MasterPortfolio,
        broker: Broker,
        recorder: PortfolioRecorder,
        allocation_engine: AllocationEngine,
    ) -> None:
        self._cfg = cfg

        self._ctx: Context = Context(
            universe=cfg.universe,
            strict=cfg.strict,
        )

        self._data_handler = data_handler
        self._strategies = strategies
        self._portfolio = portfolio
        self._broker = broker
        self._recorder = recorder
        self._allocation_engine = allocation_engine

        # logging state
        self._tick = 0
        self._initial_equity: Optional[float] = None
        self._cum_fees: float = 0.0

    # -----------------------------
    # Logging helper
    # -----------------------------

    def _log(self, msg: str) -> None:
        if self._cfg.verbose:
            print(msg)

    def run(self, clock: Clock) -> PortfolioRecorder:
        if self._cfg.verbose:
            print("=" * 80)
            print("BACKTEST START")
            print("=" * 80)

        while clock.next():
            ts = clock.now
            self._tick += 1

            # Update context market data
            market_snapshot = self._data_handler.update(ts)
            if not market_snapshot:
                continue

            self._ctx.reset_step(ts)
            self._ctx.update_market(market_snapshot)

            # Initial equity
            if self._initial_equity is None:
                self._initial_equity = self._portfolio.equity(self._ctx)
                self._log(f"[{ts}] Initial equity: {self._initial_equity:,.2f}")

            # Generate strategy signals
            for strat in self._strategies:
                out = strat.on_data(self._ctx)
                self._ctx.submit_signals(strat.__class__.__name__, out)
            strategy_outputs = self._ctx.collect_signals()

            # Allocation -> Orders -> Execution -> Apply -> Record
            alloc = self._allocation_engine.allocate(
                strategy_outputs,
                self._ctx,
            )
            print(alloc)

            do_log_this_tick = (
                (self._cfg.log_every_n > 0) 
                and (self._tick % self._cfg.log_every_n == 0)
            )

            if clock.has_next() or not self._cfg.close_positions_at_end:
                orders = self._portfolio.build_orders(
                    alloc,
                    self._ctx,
                    min_size=self._cfg.min_size
                )
            else:
                orders = self._portfolio.build_closing_orders(self._ctx)

            if self._cfg.log_orders and orders:
                self._log(f"\n[{ts}] ORDERS | count={len(orders)}")
                for o in orders:
                    px = (
                        self._ctx.get_price(o.symbol, "close") 
                        if self._ctx.has_symbol(o.symbol) 
                        else float("nan")
                    )

                    notional = (
                        abs(o.quantity * px) if px == px else float("nan")
                    )

                    side = "BUY" if o.quantity > 0 else "SELL"
                    
                    self._log(
                        f"  {side:4s} {abs(o.quantity):>12.6f} {o.symbol:12s} "
                        f"@ {px:>12.6f} | notional={notional:>14,.2f} "
                        f"| type={getattr(o, 'order_type', None)} | tif={getattr(o, 'time_in_force', None)}"
                    )

                if self._cfg.log_allocation:
                    gross = sum(abs(w) for w in alloc.values()) if alloc else 0.0
                    net = sum(alloc.values()) if alloc else 0.0
                    self._log(
                        f"\n[{ts}] ALLOCATION | n={len(alloc)} | gross={gross:.6f} | net={net:.6f}"
                    )
                    for sym, w in sorted(alloc.items()):
                        self._log(f"  {sym:12s} {w:+.6f}")

            fills = self._broker.execute_orders(orders, self._ctx)

            if fills:
                tick_fees = 0.0
                if self._cfg.log_fills:
                    self._log(f"\n[{ts}] FILLS | count={len(fills)}")
                for f in fills:
                    side = "BUY" if f.quantity > 0 else "SELL"
                    notional = abs(f.quantity * f.price)
                    fee = float(getattr(f, "fee", 0.0))
                    tick_fees += fee
                    if self._cfg.log_fills:
                        self._log(
                            f"  {side:4s} {abs(f.quantity):>12.6f} {f.symbol:12s} "
                            f"@ {f.price:>12.6f} | notional={notional:>14,.2f} | fee={fee:>10.2f}"
                        )
                self._cum_fees += tick_fees
                if self._cfg.log_fills:
                    self._log(
                        f"  Fees this tick: {tick_fees:,.2f} | Cumulative fees: {self._cum_fees:,.2f}"
                        )

                self._portfolio.apply_fills(fills)

            if self._cfg.log_equity and do_log_this_tick or not clock.has_next():
                eq = self._portfolio.equity(self._ctx)
                self._log((
                    f"[{ts}] EQUITY: {eq:,.2f} "
                    f"| cash={self._portfolio.cash:,.2f} "
                    f"| positions={len(self._portfolio.positions)}"
                ))

            # Record portfolio state
            self._recorder.record(ts, self._portfolio, self._ctx)

        # Final summary
        if self._cfg.verbose and self._initial_equity is not None:
            final_eq = self._portfolio.equity(self._ctx)
            pnl = final_eq - self._initial_equity
            pnl_pct = (
                (pnl / self._initial_equity) * 100 
                if self._initial_equity > 0 
                else 0.0
            )

            print("\n" + "=" * 80)
            print("BACKTEST SUMMARY")
            print("=" * 80)
            print(f"Initial equity: {self._initial_equity:,.2f}")
            print(f"Final equity:   {final_eq:,.2f}")
            print(f"PnL:            {pnl:,.2f} ({pnl_pct:+.2f}%)")
            print(f"Cumulative fees:{self._cum_fees:,.2f}")
            print(f"Final cash:     {self._portfolio.cash:,.2f}")
            print(f"Final positions:{self._portfolio.positions}")

            # ----------------------------- 
            # Print performance metrics
            # -----------------------------
            print("\n" + "=" * 80)
            print("PERFORMANCE METRICS")
            print("=" * 80)
            perf_data = self._recorder.export_performance_data()
            perf_analyzer = PerformanceAnalyzer(perf_data)
            print(f"CAGR:           {perf_analyzer.compute_cagr():.2%}")
            print(f"Max Drawdown:   {perf_analyzer.compute_max_drawdown():.2%}")
            print(
                f"Sharpe Ratio:   "
                f"{perf_analyzer.compute_sharpe_ratio(risk_free_rate=0.04):.4f} (risk-free rate fixed to 4%)"
            )

        return self._recorder


if __name__ == "__main__":
    import time
    perf_timer = {}

    tmp = "data_storage/parquet/MSCI_WORLD_NET_USD.parquet"
    # tmp = "data_storage/parquet/MSCI_WORLD.parquet"
    # tmp = "data_storage/parquet/EURUSD_hourly.parquet"

    # # Setup clock
    # clock_config = ClockConfig(
    #     start=pd.Timestamp("2012-09-07 17:00"),
    #     end=pd.Timestamp("2026-01-07 17:00"),
    #     freq="1d",
    #     keep_weekends=False,
    # )
    start_time = time.perf_counter()
    clock_config = ClockConfig(
        start=pd.Timestamp("2012-12-25 17:30"),
        end=pd.Timestamp("2026-04-27 17:30"),
        freq="1d",
        keep_weekends=False,
    )

    clock = Clock(clock_config)

    timestamps = []
    while clock.next():
        timestamps.append(clock.now)

    clock.reset()
    end_time = time.perf_counter()
    perf_timer["clock_init"] = (end_time - start_time) * 1000

    start_time = time.perf_counter()
    dh = DataHandler(
        clock=timestamps,
        universe=["MSCI_WORLD", "EURUSD", "MSCI_WORLD_NET_USD"],
        config=DataHandlerConfig(file_path=tmp, ohlcv_cols=("open", "close", "high", "low")),
    )
    end_time = time.perf_counter()
    perf_timer["datahandler_init"] = (end_time - start_time) * 1000

    # strategies: List[StrategyLike] = [
    #     AlwaysLong(symbol="EURUSD", weight=1.0)
    # ]

    # strategies: List[StrategyLike] = [
    #     AlwaysLong(symbol="MSCI_WORLD", weight=1.0)
    # ]

    strategies: List[StrategyLike] = [
        # DollarCostAveraging(symbol="MSCI_WORLD", weight=0.04, interval_ticks=40),
        # AlwaysLong(symbol="MSCI_WORLD_NET_USD", weight=1.0),
        # MeanReversion(
        #     symbol="MSCI_WORLD_NET_USD", 
        #     avg_window=14,
        #     long_threshold=0.03,
        #     short_threshold=-0.03,
        #     side_constraint=0,
        #     weight=1.0
        # ),
        Momentum(
            symbol="MSCI_WORLD_NET_USD", 
            avg_window=14,
            long_threshold=0.03,
            short_threshold=-0.03,
            side_constraint=1,
            keep_expo_in_range=True,
            weight=1.0
        )
    ]

    start_time = time.perf_counter()
    portfolio = MasterPortfolio(
        initial_cash=1_000_000.0,
        instrument_rules={
            "EURUSD": {"in_lots": False, "integer": False},
            "MSCI_WORLD": {"in_lots": False, "integer": True},
            "MSCI_WORLD_NET_USD": {"in_lots": False, "integer": True},
        },
    )
    end_time = time.perf_counter()
    perf_timer["portfolio_init"] = (end_time - start_time) * 1000

    start_time = time.perf_counter()
    broker = Broker(fee_rate=0.002, min_fee=0.0)

    alloc_engine = AllocationEngine(
        max_gross=1.0,
        normalize=True,
        mode="capital_based"
    )

    end_time = time.perf_counter()
    perf_timer["alloc_engine_init"] = (end_time - start_time) * 1000

    portfolio_recorder = PortfolioRecorder()

    start_time = time.perf_counter()
    engine = BacktestingEngine(
        cfg=EngineConfig(
            universe=["MSCI_WORLD", "EURUSD", "MSCI_WORLD_NET_USD"],
            min_size=1.0,
            verbose=True,
            log_allocation=False,
            log_orders=True,
            log_fills=True,
            log_equity=False,
            log_every_n=1,
        ),
        data_handler=dh,
        strategies=strategies,
        portfolio=portfolio,
        broker=broker,
        recorder=portfolio_recorder,
        allocation_engine=alloc_engine,
    )

    end_time = time.perf_counter()
    perf_timer["engine_init"] = (end_time - start_time) * 1000

    start_time = time.perf_counter()
    recorder = engine.run(clock)
    end_time = time.perf_counter()
    perf_timer["engine_run"] = (end_time - start_time) * 1000
    
    recorder.plot_equity_line()

    recorder.metrics_df().to_clipboard()
    # print(recorder.positions_df())


    print("\n" + "-" * 80)
    print("EXEC PERF TIMERS")
    print("-" * 80)
    for k, v in perf_timer.items():
        print(f"{k} = {v} ms")
