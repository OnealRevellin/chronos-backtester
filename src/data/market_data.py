from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence

import pandas as pd

from ..backtesting.context import Bar

    
@dataclass(frozen=True)
class DataHandlerConfig:
    """
    Configuration for the DataHandler.

    Exactly one of `combined_path` or `folder_path` must be provided.
     - `combined_path`: Path to a single file containing all market data.
     - `folder_path`: Path to a folder containing multiple files, 
        each representing market data for a different instrument.

    """
    combined_path: Optional[Path] = None
    folder_path: Optional[Path] = None

    file_extension: str = ".parquet"
    timestamp_col: str = "timestamp"
    ohlcv_cols: Sequence[str] = ("open", "high", "low", "close", "volume")

    tz: Optional[str] = None


class DataHandler:
    """
    Minimal DataHandler: preloads market data and serves per-tick snapshots.

    Public API:
        update(now: pd.Timestamp) -> dict[str, Bar]
    """

    __slots__ = ("_snapshots_by_timestamp", "_empty_snapshot")


if __name__ == "__main__":
    pass