from __future__ import annotations

from ...backtesting.context import Context, StrategyOutput
from ..base import Strategy


class AlwaysLong(Strategy):
    """
    Example strategy that always generates long signals for all instruments.
    """

    def __init__(self, symbol: str, weight: float = 1.0) -> None:
        self._symbol = symbol
        self._weight = float(weight)

    def on_data(
        self,
        ctx: Context,
    ) -> StrategyOutput:
        """
        Generate long signals for the specified symbol.
        """
        if not ctx.has_symbol(self._symbol):
            return StrategyOutput(weights={})
        
        return StrategyOutput({self._symbol: self._weight})