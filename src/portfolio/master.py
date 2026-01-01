"""
Global portfolio owning capital and positions.

Later on, I'll introduce portfolio.py whihch will represent subportfolios allowing
us to split exposure/PnLs/risk metrics... between subportfolios.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..backtesting.context import Context
from ..execution.order import Order, OrderType, TimeInForce
from ..execution.fill import Fill


class MasterPorfolio:

    __slots__ = (
        "_cash",
        "_positions",
        "_instrument_rules",
        "_default_order_type",
        "_default_tif",
    )

    def __init__(
        self,
        *,
        initial_cash: float = 1_000_000.0,
        instrument_rules: Optional[Dict[str, Dict[str, float | bool]]] = None,
        default_order_type: OrderType = OrderType.MARKET,
        default_time_in_force: TimeInForce = TimeInForce.DAY
    ):
        self._cash = float(initial_cash)
        self._positions: Dict[str, float] = {}
        self._instrument_rules: Dict[str, Dict[str, float | bool]] = instrument_rules
        self._default_order_type: OrderType = default_order_type
        self._default_tif: TimeInForce = default_time_in_force

    # -----------------------------
    # Getter & Setter
    # -----------------------------

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> Dict[str, float]:
        return dict(self._positions)
    
    def equity(self, ctx: Context) -> float:
        """
        Equity = cash + sum(positions * closing_price)
        """

        eq = self._cash
        for sym, qty in self._positions.items():
            if ctx.has_symbol(sym):
                eq += qty * ctx.get_price(sym, "close")

        return eq
    
    # -----------------------------
    # Sizing helpers
    # -----------------------------
    
    def _compute_unit_size(self, sym: str, qty: float) -> float:

        rules = self._instrument_rules.get(sym, {})
        in_lots = rules.get("in_lots", False)
        lot_size = float(rules.get("lot_size", 1.0))

        if not in_lots:
            return qty
        
        if lot_size <= 0.0:
            raise ValueError(f"Invalid lot_size for symbol '{sym}': {lot_size}")
        
        return float((round(qty) / lot_size) * lot_size)

    # -----------------------------
    # Oder generation
    # -----------------------------

    def build_orders(
        self,
        allocation: Dict[str, float],
        ctx: Context,
        *,
        order_type: Optional[OrderType] = None,
        time_in_force: Optional[TimeInForce] = None,
        price_time: str = "close",
        
    ) -> List[Order]:
        """
        Convert target weights into delta Orders.

        Parameters
        ----------
        allocation:
            dict[symbol: target_weight]
        order_type / time_in_force:
            Overrides for generated orders (defaults set in __init__).
        Returns
        -------
        List[Order]
        """
        if not allocation:
            return []

        ot = order_type or self._default_order_type
        tif = time_in_force or self._default_tif

        eq = self.equity(ctx)
        if eq <= 0.0:
            return []

        # 1) Compute target position per symbol (in units)
        target_pos: Dict[str, float] = {}

        for sym, weight in allocation.items():
            if not ctx.has_symbol(sym):
                continue

            px = ctx.get_price(sym, price_time)
            if px <= 0.0:
                continue

            # Raw units implied by target weight
            target_value = float(weight) * eq
            raw_units = target_value / px

            # Apply instrument conversion rule
            target_units = self._compute_unit_size(sym, raw_units)

            # Drop tiny values to reduce churn
            if abs(target_units) < 1e-12:
                target_units = 0.0

            target_pos[sym] = target_units

        # 2) Compute delta vs current positions
        orders: List[Order] = []
        for sym in (set(self._positions) | set(target_pos)):
            cur = self._positions.get(sym, 0.0)
            tgt = target_pos.get(sym, 0.0)
            delta = tgt - cur

            if abs(delta) <= 1e-12:
                continue

            orders.append(
                Order(
                    symbol=sym,
                    quantity=delta,
                    order_type=ot,
                    time_in_force=tif,
                    limit_price=None,
                    stop_price=None,
                    order_id=None,
                )
            )

        return orders

    # -----------------------------
    # Fill application
    # -----------------------------

    def apply_fills(self, fills: List[Fill]) -> None:
        """
        Apply fills to cash and positions.
        """
        for fill in fills:
            if fill.quantity == 0.0:
                continue

            self._cash -= fill.quantity * fill.price
            self._cash -= fill.fee

            self._positions[fill.symbol] = self._positions.get(fill.symbol, 0.0) + fill.quantity

            if abs(self._positions[fill.symbol]) < 1e-12:
                del self._positions[fill.symbol]


if __name__ == "__main__":
    import pandas as pd
    from ..backtesting.context import Context, Bar
    from ..execution.broker import Broker
    from ..portfolio.allocation import AllocationEngine
    from ..backtesting.context import StrategyOutput

    print("=" * 80)
    print("MASTER PORTFOLIO - COMPREHENSIVE MOCK TEST")
    print("=" * 80)
    print()

    # =====================================================================
    # Step 1: Initialize Portfolio
    # =====================================================================
    print("1. INITIALIZE PORTFOLIO")
    print("-" * 80)
    
    portfolio = MasterPorfolio(
        initial_cash=1_000_000.0,
        instrument_rules={
            "AAPL": {"in_lots": False},
            "MSFT": {"in_lots": False},
            "TSLA": {"in_lots": True, "lot_size": 100},  # Must buy in 100-share lots
        },
        default_order_type=OrderType.MARKET,
        default_time_in_force=TimeInForce.DAY
    )

    print(f"Initial Cash:          ${portfolio.cash:,.2f}")
    print(f"Initial Positions:     {portfolio.positions}")
    print()

    # =====================================================================
    # Step 2: Setup Market Context (Tick 1)
    # =====================================================================
    print("2. SETUP MARKET CONTEXT - TICK 1")
    print("-" * 80)
    
    ctx = Context(universe=["AAPL", "MSFT", "TSLA"], strict=True)
    tick1 = pd.Timestamp("2024-01-01 09:30")
    
    market_snapshot = {
        "AAPL": Bar(open=180.0, high=181.0, low=179.5, close=180.5, volume=50_000_000),
        "MSFT": Bar(open=370.0, high=371.5, low=369.0, close=370.75, volume=30_000_000),
        "TSLA": Bar(open=240.0, high=242.0, low=238.0, close=241.0, volume=100_000_000),
    }

    ctx.reset_step(tick1)
    ctx.update_market(market_snapshot)
    
    print(f"Timestamp:             {ctx.now}")
    print(f"Market Snapshot:")
    for sym, bar in ctx.market.items():
        print(f"  {sym:6s}: close=${bar.close:8.2f}  volume={bar.volume:>12,.0f}")
    print()

    # =====================================================================
    # Step 3: Strategy Signals → Allocation
    # =====================================================================
    print("3. STRATEGY OUTPUTS & ALLOCATION")
    print("-" * 80)
    
    # Simulate two strategies generating signals
    strategy_outputs = {
        "momentum_strategy": StrategyOutput(
            weights={"AAPL": 0.4, "MSFT": 0.3, "TSLA": -0.1}
        ),
        "mean_reversion_strategy": StrategyOutput(
            weights={"AAPL": 0.1, "MSFT": 0.2, "TSLA": 0.3}
        ),
    }
    
    print("Strategy Signals:")
    for strat_id, output in strategy_outputs.items():
        print(f"  {strat_id}:")
        for sym, weight in output.weights.items():
            print(f"    {sym}: {weight:+.2f}")
    print()

    # Aggregate signals via AllocationEngine
    alloc_engine = AllocationEngine(max_gross=1.0, normalize=True, mode="quantity_based")
    target_allocation = alloc_engine.allocate(strategy_outputs, ctx)
    
    print("Aggregated Allocation (after normalization):")
    for sym, weight in target_allocation.items():
        print(f"  {sym}: {weight:+.4f}")
    gross_exposure = sum(abs(w) for w in target_allocation.values())
    print(f"Gross Exposure: {gross_exposure:.4f}")
    print()

    # =====================================================================
    # Step 4: Build Orders (Initial Portfolio)
    # =====================================================================
    print("4. BUILD ORDERS - INITIAL ALLOCATION")
    print("-" * 80)
    
    equity = portfolio.equity(ctx)
    print(f"Portfolio Equity:      ${equity:,.2f}")
    print()

    orders = portfolio.build_orders(target_allocation, ctx)
    
    print(f"Generated {len(orders)} orders:")
    for i, order in enumerate(orders, 1):
        side = "BUY " if order.quantity > 0 else "SELL"
        price = ctx.get_price(order.symbol, "close")
        notional = abs(order.quantity * price)
        print(f"  Order {i}: {side} {abs(order.quantity):>8.0f} shares of {order.symbol:6s} @ ${price:8.2f}  (${notional:>12,.2f})")
    print()

    # =====================================================================
    # Step 5: Execute Orders via Broker
    # =====================================================================
    print("5. EXECUTE ORDERS - BROKER SIMULATION")
    print("-" * 80)
    
    broker = Broker(fee_rate=0.001, min_fee=0.0)  # 0.1% commission
    fills = broker.execute_orders(orders, ctx)
    
    print(f"Broker executed {len(fills)} fills (fee_rate={broker._fee_rate*100:.1f}%):")
    total_fees = 0.0
    for i, fill in enumerate(fills, 1):
        side = "BUY " if fill.quantity > 0 else "SELL"
        notional = abs(fill.quantity * fill.price)
        print(f"  Fill {i}: {side} {abs(fill.quantity):>8.0f} shares of {fill.symbol:6s} @ ${fill.price:8.2f}  Fee: ${fill.fee:>10,.2f}")
        total_fees += fill.fee
    
    print(f"Total Fees: ${total_fees:,.2f}")
    print()

    # =====================================================================
    # Step 6: Apply Fills to Portfolio
    # =====================================================================
    print("6. APPLY FILLS TO PORTFOLIO")
    print("-" * 80)
    
    portfolio.apply_fills(fills)
    
    print(f"After Fills:")
    print(f"  Cash:          ${portfolio.cash:,.2f}")
    print(f"  Positions:")
    for sym, qty in sorted(portfolio.positions.items()):
        price = ctx.get_price(sym, "close")
        position_value = qty * price
        print(f"    {sym}: {qty:>10,.0f} shares @ ${price:>8.2f} = ${position_value:>12,.2f}")
    
    new_equity = portfolio.equity(ctx)
    cash_deployed = 1_000_000.0 - portfolio.cash
    print(f"  Total Equity:  ${new_equity:,.2f}")
    print(f"  Cash Deployed: ${cash_deployed:,.2f}")
    print()

    # =====================================================================
    # Step 7: Simulate Tick 2 (Price Changes)
    # =====================================================================
    print("7. TICK 2 - PRICE CHANGES & REBALANCING")
    print("-" * 80)
    
    tick2 = pd.Timestamp("2024-01-02 09:30")
    
    # Prices move
    market_snapshot_tick2 = {
        "AAPL": Bar(open=181.0, high=182.0, low=180.0, close=181.5, volume=45_000_000),
        "MSFT": Bar(open=371.0, high=373.0, low=370.0, close=372.0, volume=35_000_000),
        "TSLA": Bar(open=242.0, high=244.0, low=240.0, close=243.0, volume=110_000_000),
    }
    
    ctx.reset_step(tick2)
    ctx.update_market(market_snapshot_tick2)
    
    print(f"Timestamp:             {ctx.now}")
    print(f"Price Changes:")
    for sym in ["AAPL", "MSFT", "TSLA"]:
        old_val = market_snapshot[sym].close
        new_price = ctx.get_price(sym, "close")
        change = ((new_price - old_val) / old_val) * 100
        print(f"  {sym}: ${old_val:>8.2f} → ${new_price:>8.2f} ({change:+.2f}%)")
    print()

    # Calculate current equity
    equity_tick2 = portfolio.equity(ctx)
    pnl = equity_tick2 - new_equity
    pnl_pct = (pnl / new_equity) * 100 if new_equity > 0 else 0
    
    print(f"Portfolio Update:")
    print(f"  Previous Equity: ${new_equity:,.2f}")
    print(f"  Current Equity:  ${equity_tick2:,.2f}")
    print(f"  Unrealized PnL:  ${pnl:,.2f} ({pnl_pct:+.2f}%)")
    print()

    # Generate new allocation
    new_strategy_outputs = {
        "momentum_strategy": StrategyOutput(
            weights={"AAPL": 0.3, "MSFT": 0.4, "TSLA": 0.0}
        ),
        "mean_reversion_strategy": StrategyOutput(
            weights={"AAPL": 0.2, "MSFT": 0.1, "TSLA": 0.2}
        ),
    }
    
    new_allocation = alloc_engine.allocate(new_strategy_outputs, ctx)
    new_orders = portfolio.build_orders(new_allocation, ctx)
    
    print(f"Generated {len(new_orders)} rebalancing orders:")
    for i, order in enumerate(new_orders, 1):
        side = "BUY " if order.quantity > 0 else "SELL"
        price = ctx.get_price(order.symbol, "close")
        notional = abs(order.quantity * price)
        print(f"  Order {i}: {side} {abs(order.quantity):>8.0f} shares of {order.symbol:6s} @ ${price:8.2f}  (${notional:>12,.2f})")
    print()

    # Execute rebalancing
    new_fills = broker.execute_orders(new_orders, ctx)
    portfolio.apply_fills(new_fills)
    
    print(f"After Rebalancing:")
    print(f"  Cash:          ${portfolio.cash:,.2f}")
    print(f"  Positions:")
    for sym, qty in sorted(portfolio.positions.items()):
        price = ctx.get_price(sym, "close")
        position_value = qty * price
        print(f"    {sym}: {qty:>10,.0f} shares @ ${price:>8.2f} = ${position_value:>12,.2f}")
    
    final_equity = portfolio.equity(ctx)
    print(f"  Total Equity:  ${final_equity:,.2f}")
    print()

    # =====================================================================
    # Summary
    # =====================================================================
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Initial Capital:       ${1_000_000:,.2f}")
    print(f"Final Equity:          ${final_equity:,.2f}")
    print(f"Total Return:          ${final_equity - 1_000_000:,.2f} ({((final_equity - 1_000_000) / 1_000_000) * 100:+.2f}%)")
    print(f"Final Positions:       {sum(1 for _ in portfolio.positions)}")
    print(f"Remaining Cash:        ${portfolio.cash:,.2f}")
    print()
    print("✅ MasterPortfolio smoke test completed successfully!")
    print("=" * 80)