from __future__ import annotations

from typing import Dict, Mapping, Literal

from ..backtesting.context import Context, StrategyOutput

AllocationMethod = Literal["quantity_based", "capital_based"]

class AllocationEngine:
    """
    Aggregate and normalize strategy outputs.
    This allocator is a first version and may be extended in the future.

    Another module between StrategyOutput and AllocationEngine
    may be introduced to handle more complex allocation logic 
    like equal risk contribution.
    
    """

    __slots__ = ("_max_gross", "_normalize", "_mode")

    def __init__(
        self,
        *,
        max_gross: float = 1.0, # can be set > 1.0 for leverage
        normalize: bool = True, # whether to normalize weights to max_gross
        mode: AllocationMethod = "quantity_based",
    ) -> None:
        if max_gross <= 0:
            raise ValueError("max_gross must be positive.")
        
        self._max_gross = float(max_gross)
        self._normalize = bool(normalize)
        self._mode: AllocationMethod = mode

    def allocate(
        self,
        strategy_outputs: Mapping[str, StrategyOutput],
        ctx: Context,
    ) -> Dict[str, float]:
        
        agg: Dict[str, float] = {}

        for out in strategy_outputs.values():
            for symbol, weight in out.weights.items():
                agg[symbol] = agg.get(symbol, 0.0) + float(weight)

        if not agg:
            return {}
        
        # Convert qty-based to capital-based weights if needed
        if self._mode == "capital_based":
            notional: Dict[str, float] = {}
            for sym, qty in agg.items():
                if not ctx.has_symbol(sym):
                    continue

            price = ctx.get_price(sym, "close")

            if price <= 0:
                raise ValueError(f"Invalid price for symbol {sym}: {price}")
            
            notional[sym] = qty * price

            if not notional:
                return {}
            
            agg = notional

        # Normalize weights if needed
        if self._normalize:
            gross = sum(abs(w) for w in agg.values())
            if gross > self._max_gross:
                scale = self._max_gross / gross
                for symbol in agg:
                    agg[symbol] *= scale

        return agg
    

if __name__ == "__main__":
    import pandas as pd

    # -----------------------------
    # Dummy market context
    # -----------------------------
    from ..backtesting.context import Context, Bar

    ctx = Context(universe=["A", "B"], strict=True)
    ctx.reset_step(pd.Timestamp("2024-01-01"))

    # Prices are deliberately different
    ctx.update_market(
        {
            "A": Bar(open=100.0, high=100.0, low=100.0, close=100.0),
            "B": Bar(open=50.0, high=50.0, low=50.0, close=50.0),
        }
    )

    # -----------------------------
    # Fake strategy outputs
    # -----------------------------
    # Strategy wants "same quantity" on both legs
    # Long A / Short B
    outputs = {
        "pair_strategy": StrategyOutput(
            weights={
                "A": +0.5,
                "B": -0.5,
            }
        )
    }

    # -----------------------------
    # Mode = weights (capital-based)
    # -----------------------------
    alloc_weights = AllocationEngine(
        mode="weights",
        max_gross=1.0,
        normalize=True,
    )

    w_capital = alloc_weights.allocate(outputs, ctx)

    print("=== Allocation mode = 'weights' (capital-based) ===")
    for sym, w in w_capital.items():
        print(f"{sym}: weight = {w:.4f}")
    print(f"Gross exposure: {sum(abs(x) for x in w_capital.values()):.4f}")
    print()

    # Interpretation:
    # -> 50% capital in A, 50% capital in B
    # -> quantities will NOT be equal because prices differ

    # -----------------------------
    # Mode = qty (equal quantity)
    # -----------------------------
    alloc_qty = AllocationEngine(
        mode="qty",
        max_gross=1.0,
        normalize=True,
    )

    w_qty = alloc_qty.allocate(outputs, ctx)

    print("=== Allocation mode = 'qty' (equal quantity semantics) ===")
    for sym, w in w_qty.items():
        print(f"{sym}: weight = {w:.4f}")
    print(f"Gross exposure: {sum(abs(x) for x in w_qty.values()):.4f}")
    print()

    # -----------------------------
    # Sanity check: implied quantities
    # -----------------------------
    # Assume 1.0 equity for simplicity
    equity = 1.0

    qA = (w_qty["A"] * equity) / ctx.get_price("A", "close")
    qB = (w_qty["B"] * equity) / ctx.get_price("B", "close")

    print("=== Implied quantities (from weights) ===")
    print(f"A quantity ≈ {qA:.6f}")
    print(f"B quantity ≈ {qB:.6f}")
    print("(They should be equal in absolute value)")
