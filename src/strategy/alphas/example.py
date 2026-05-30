from __future__ import annotations

from collections import deque
import numpy as np

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
    
class AlwaysShort(Strategy):
    """
    Example strategy that always generates short signals for all instruments.
    """

    def __init__(self, symbol: str, weight: float = -1.0) -> None:
        self._symbol = symbol
        self._weight = float(weight)

    def on_data(
        self,
        ctx: Context,
    ) -> StrategyOutput:
        """
        Generate short signals for the specified symbol.
        """
        if not ctx.has_symbol(self._symbol):
            return StrategyOutput(weights={})
        
        return StrategyOutput({self._symbol: self._weight})
    

class DollarCostAveraging(Strategy):
    """
    Example strategy that implements Dollar-Cost Averaging (DCA).
    Invests a fixed amount at regular intervals.
    """

    def __init__(
        self, 
        symbol: str, 
        *,
        interval_ticks: int = 20,
        weight: float = 0.1, 
        max_weight: float = 1.0,
    ) -> None:
        self._symbol = symbol
        self._weight = float(weight)
        self._interval_ticks = interval_ticks
        self._max_weight = float(max_weight)
        self._current_year_month = None

        self._current_tick = 0
        self._ctr = 0

    def on_data(
        self,
        ctx: Context,
    ) -> StrategyOutput:
        """
        Generate DCA signals for the specified symbol.
        """
        if not ctx.has_symbol(self._symbol):
            return StrategyOutput(weights={})
                
        if self._weight * self._ctr >= self._max_weight:
            return StrategyOutput(weights={self._symbol: self._max_weight})
        
        if self._ctr * self._weight < self._max_weight:
            if self._current_tick % self._interval_ticks == 0:
                self._ctr += 1

        self._current_tick += 1

        return StrategyOutput(weights={self._symbol: self._weight * self._ctr})
    

class MeanReversion(Strategy):
    """
    Example strategy that implements a very basic mean reversion stratgegy 
    based on simple moving average. 
    """

    def __init__(
        self, 
        symbol: str, 
        *,
        avg_window: int = 14,
        long_threshold: float = 0.02,
        short_threshold: float = -0.02,
        side_constraint: int = 0, # -1/1 = short|long only, 0 long & short
        weight: float = 1.0
    ) -> StrategyOutput:
        self._symbol = symbol
        self._weight = float(weight)
        self._avg_window = avg_window
        self._long_threshold = long_threshold
        self._short_threshold = short_threshold
        self._side_constraint = side_constraint

        self._current_tick = 0
        self._past_prices = deque(maxlen=avg_window)

        self._curr_side = 0 # 0 = no expo, -1 = short, 1 = long

    def on_data(
        self,
        ctx: Context,
    ) -> StrategyOutput:
        self._current_tick += 1

        if not ctx.has_symbol(self._symbol):
            return StrategyOutput(weights={})
        
        curr_px = ctx.get_price(self._symbol)
        self._past_prices.append(curr_px)

        if self._current_tick < 14:
            return StrategyOutput(weights={})
        
        # compute avg of X past prices and current diff to average in %
        avg = np.mean(self._past_prices)
        diff_w_avg = curr_px / avg - 1.0

        # if diff to avg is >= our long threshold then become short or neutral
        # based on the side_constraint input
        if diff_w_avg >= self._long_threshold:
            if not self._side_constraint == 1:
                self._curr_side = -1
                return StrategyOutput(
                    weights={self._symbol: -self._weight}
                )
            self._curr_side = 0
            return StrategyOutput(weights={})

        # if diff to avg is <= our long threshold then become long or neutral
        # based on the side_constraint input
        if diff_w_avg <= self._short_threshold:
            if not self._side_constraint == -1:
                self._curr_side = 1
                return StrategyOutput(
                    weights={self._symbol: self._weight}
                )
            self._curr_side = 0
            return StrategyOutput(weights={})
    
        # else, just keep the current positions
        strat_output = {
            -1: StrategyOutput(weights={self._symbol: -self._weight}),
            0: StrategyOutput(weights={}),
            1: StrategyOutput(weights={self._symbol: self._weight}),
        }

        return strat_output[self._curr_side]


class Momentum(Strategy):
    """
    Example strategy that implements a very basic momentum stratgegy 
    based on simple moving average. (same as the above mean reverting strat
    but instead of reverting to the mean here we follow the recent trend)
    """

    def __init__(
        self, 
        symbol: str, 
        *,
        avg_window: int = 14,
        long_threshold: float = 0.02,
        short_threshold: float = -0.02,
        side_constraint: int = 0, # -1/1 = short|long only, 0 long & short
        weight: float = 1.0
    ) -> StrategyOutput:
        self._symbol = symbol
        self._weight = float(weight)
        self._avg_window = avg_window
        self._long_threshold = long_threshold
        self._short_threshold = short_threshold
        self._side_constraint = side_constraint

        self._current_tick = 0
        self._past_prices = deque(maxlen=avg_window)

        self._curr_side = 0 # 0 = no expo, -1 = short, 1 = long

    def on_data(
        self,
        ctx: Context,
    ) -> StrategyOutput:
        self._current_tick += 1

        if not ctx.has_symbol(self._symbol):
            return StrategyOutput(weights={})
        
        curr_px = ctx.get_price(self._symbol)
        self._past_prices.append(curr_px)

        if self._current_tick < 14:
            return StrategyOutput(weights={})
        
        # compute avg of X past prices and current diff to average in %
        avg = np.mean(self._past_prices)
        diff_w_avg = curr_px / avg - 1.0

        # if diff to avg is >= our long threshold then become short or neutral
        # based on the side_constraint input
        if diff_w_avg >= self._long_threshold:
            if not self._side_constraint == -1:
                self._curr_side = 1
                return StrategyOutput(
                    weights={self._symbol: self._weight}
                )
            self._curr_side = 0
            return StrategyOutput(weights={})

        # if diff to avg is <= our long threshold then become long or neutral
        # based on the side_constraint input
        if diff_w_avg <= self._short_threshold:
            if not self._side_constraint == 1:
                self._curr_side = -1
                return StrategyOutput(
                    weights={self._symbol: -self._weight}
                )
            self._curr_side = 0
            return StrategyOutput(weights={})
    
        # else, just keep the current positions
        strat_output = {
            -1: StrategyOutput(weights={self._symbol: -self._weight}),
            0: StrategyOutput(weights={}),
            1: StrategyOutput(weights={self._symbol: self._weight}),
        }

        return strat_output[self._curr_side]


        

    