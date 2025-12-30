"""
execution.fill

Fill model.

A Fill updates the portfolio:
- cash
- positions

Optional:
- fee (commissions, taker fee, etc.)
"""


from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .order import OrderType, TimeInForce


@dataclass(frozen=True, slots=True)
class Fill:
    symbol: str
    quantity: float
    price: float
    fee: float = 0.0
    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY
    order_id: Optional[str] = None

if __name__ == "__main__":
    fill = Fill(
        symbol="AAPL",
        quantity=100,
        price=150.0,
        fee=1.0,
        order_type=OrderType.LIMIT,
        time_in_force=TimeInForce.GTC,
        order_id="order_123"
    )
    print(fill)
