"""
execution.order

Order model.

The portfolio produces Orders. The broker interprets their semantics.

Order semantics:
- quantity: + buy, - sell (in instrument units: shares, coins, lots, etc.)
- order_type:
    - market: execute immediately at simulated price 
        (slippage may apply from slippage model)
    - limit: execute only if price crosses limit
    - stop: execute only if price crosses stop
    - stop_limit: stop triggers, then limit condition applies
- time_in_force:
    - day: valid for the current bar/session
    - gtc: good till cancel (for backtests, typically treated as day unless you persist orders)
    - ioc: immediate-or-cancel
    - fok: fill-or-kill
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class TimeInForce(str, Enum):
    DAY = "day"   # good for day/session (sim)
    GTC = "gtc"   # good till cancel
    IOC = "ioc"   # immediate or cancel
    FOK = "fok"   # fill or kill

@dataclass(frozen=True, slots=True)
class Order:
    symbol: str
    quantity: float
    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    order_id: Optional[str] = None

    def __post_init__(self):
        if not self.symbol:
            raise ValueError("Order.symbol must be a non-empty string.")
        if self.quantity == 0:
            raise ValueError("Order.quantity must be non-zero.")
        
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("Limit orders must have a limit_price.")
        if self.order_type == OrderType.STOP and self.stop_price is None:
            raise ValueError("Stop orders must have a stop_price.")
        if self.order_type == OrderType.STOP_LIMIT:
            if self.stop_price is None or self.limit_price is None:
                raise ValueError(
                    "Stop-limit orders must have both stop_price and limit_price."
                )
            

if __name__ == "__main__":
    order = Order(
        symbol="AAPL",
        quantity=100,
        order_type=OrderType.LIMIT,
        time_in_force=TimeInForce.GTC,
        limit_price=150.0,
        order_id="order_123"
    )
    print(order)

    assert order.symbol == "AAPL"
    assert order.quantity == 100
    assert order.order_type == OrderType.LIMIT
    assert order.time_in_force == TimeInForce.GTC
    assert order.limit_price == 150.0
    assert order.stop_price is None
    assert order.order_id == "order_123"

    print("Order model smoke test passed.")