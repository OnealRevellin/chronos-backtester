import pandas as pd
from typing import Dict
from ..backtesting.context import Context
from ..portfolio.master import MasterPortfolio


class PortfolioRecorder:
    """
    Records portfolio value over time.
    """

    def __init__(self) -> None:
        self._positions: Dict[pd.Timestamp, Dict[str, float]] = {}
        self._metrics: Dict[pd.Timestamp, Dict[str, float]] = {}

    def record(
        self,
        ts: pd.Timestamp,
        portfolio: MasterPortfolio,
        ctx: Context
    ) -> None:
        self._positions[ts] = portfolio.positions.copy()
        self._metrics[ts] = {
            "cash": portfolio.cash,
            "total_equity": portfolio.equity(ctx),
        }

    def positions_df(self) -> pd.DataFrame:
        return pd.DataFrame.from_dict(self._positions, orient="index").fillna(0.0).sort_index()

    def metrics_df(self) -> pd.DataFrame:
        df = pd.DataFrame.from_dict(self._metrics, orient="index").sort_index()
        df["returns"] = df["total_equity"].pct_change().fillna(0.0)
        return df

    def to_parquet(self, path: str):
        self.positions_df().to_parquet(path + ".positions.parquet")
        self.metrics_df().to_parquet(path + ".metrics.parquet")