from __future__ import annotations
from abc import ABC, abstractmethod

from ..backtesting.context import Context, StrategyOutput


class Strategy(ABC):
    @abstractmethod
    def on_data(
        self,
        ctx: Context,
    ) -> StrategyOutput:
        """
        Generate trading signals based on market data and strategy logic.

        Parameters
        ----------
        ctx (Context): 
            The current backtesting context containing market data and state.
        Returns
        ----------
        StrategyOutput: 
            The generated trading signals and related information.
        """
        raise NotImplementedError
