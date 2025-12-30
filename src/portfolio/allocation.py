from __future__ import annotations

from typing import Dict, Mapping

from ..backtesting.context import StrategyOutput


class AllocationEngine:
    """
    Aggregate and normalize strategy outputs.
    This allocator is a first version and may be extended in the future.

    Another module between StrategyOutput and AllocationEngine
    may be introduced to handle more complex allocation logic 
    like equal risk contribution.
    
    """

    __slots__ = ("_max_gross", "_normalize")

    def __init__(
        self,
        *,
        max_gross: float = 1.0, # can be set > 1.0 for leverage
        normalize: bool = True, # whether to normalize weights to max_gross
    ) -> None:
        if max_gross <= 0:
            raise ValueError("max_gross must be positive.")
        
        self._max_gross = float(max_gross)
        self._normalize = bool(normalize)

    def allocate(
        self,
        strategy_outputs: Mapping[str, StrategyOutput],
    ) -> Dict[str, float]:
        
        agg: Dict[str, float] = {}

        for out in strategy_outputs.values():
            for symbol, weight in out.weights.items():
                agg[symbol] = agg.get(symbol, 0.0) + weight

        if not agg:
            return {}
        
        if self._normalize:
            gross = sum(abs(w) for w in agg.values())
            if gross > self._max_gross:
                scale = self._max_gross / gross
                for symbol in agg:
                    agg[symbol] *= scale

        return agg
    

if __name__ == "__main__":
    from ..backtesting.context import StrategyOutput

    allocator = AllocationEngine(max_gross=1.0)

    outputs = {
        "s1": StrategyOutput(weights={"BTC": 1.0}),
        "s2": StrategyOutput(weights={"BTC": 0.5, "ETH": 0.5}),
    }

    alloc = allocator.allocate(outputs)
    print("Allocation:", alloc)