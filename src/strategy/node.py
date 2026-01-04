from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..backtesting.context import Context, StrategyOutput
from .base import Strategy


@dataclass(slots=True)
class StrategyNode:
    """
    Wraps a strategy with an ID and optional enabled flag.
    """

    id: str
    strategy: Strategy
    enabled: bool = True


    def on_data(
        self,
        ctx: Context,
    ) -> StrategyOutput:
        """
        Execute the strategy on current tick and return strategy output.
        """
        if not self.enabled:
            return StrategyOutput.empty()
        
        out = self.strategy.on_data(ctx)

        if not isinstance(out, StrategyOutput):
            raise TypeError(
                f"StrategyNode.on_data() must return StrategyOutput, got {type(out)}"
            )
        
        return out
    
if __name__ == "__main__":
    import pandas as pd
    from ..backtesting.context import Context, Bar
    from .alphas.example import AlwaysLong

    ctx = Context(universe=["ES"], strict=True)
    ctx.reset_step(pd.Timestamp("2022-01-03"))
    ctx.update_market({"ES": Bar(open=1, high=1, low=1, close=1)})

    node = StrategyNode(id="always_long", strategy=AlwaysLong("ES", 1.0))
    out = node.on_data(ctx)
    assert out.weights["ES"] == 1.0
    print("StrategyNode smoke test passed.")
    print(out)