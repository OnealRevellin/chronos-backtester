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
    symbol_col: str = "symbol"
    ohlcv_cols: Sequence[str] = ("open", "high", "low", "close", "volume")

    required_cols: Sequence[str] = tuple(
        [timestamp_col, symbol_col] 
        + list(ohlcv_cols)
    )

    tz: Optional[str] = None


class DataHandler:
    """
    Minimal DataHandler: preloads market data and serves per-tick snapshots.

    Public API:
        update(now: pd.Timestamp) -> dict[str, Bar]
    """

    __slots__ = ("_snapshots_by_timestamp", "_empty_snapshot")

    def __init__(
        self,
        *,
        config: DataHandlerConfig,
        universe: Iterable[str],
        clock: Sequence[pd.Timestamp]
    ):
        if not clock:
            raise ValueError("Clock must not be empty")
        
        self._check_universe_valid(universe)
        self._empty_snapshot: Dict[str, Bar] = {}

        u = tuple(universe)
        df = self._load_data(config=config, universe=u)

        clock_index = pd.DatetimeIndex(clock)
        if config.tz is not None:
            clock_index = (
                clock_index.tz_localize(config.tz) 
                if clock_index.tz is None 
                else clock_index.tz_convert(config.tz)
            )
        
        self._snapshots_by_timestamp: Mapping[pd.Timestamp, Dict[str, Bar]] = (
            self._build_snapshots(df, clock, config)
        )

    def update(self, now: pd.Timestamp) -> Dict[str, Bar]:
        """Get the market snapshot for the given timestamp."""
        return self._snapshots_by_timestamp.get(now, self._empty_snapshot)

    def _check_universe_valid(self, universe: Iterable[str]) -> None:
        """Check that the universe is valid."""
        u = set(universe)
        if not u:
            raise ValueError("Universe must not be empty")
        
        if len(u) != len(list(universe)):
            raise ValueError("Universe contains duplicate instruments")

    def _load_data(
        self,
        *,
        config: DataHandlerConfig,
        universe: Sequence[str]
    ) -> pd.DataFrame:
        """Load market data from disk."""
        if ((config.combined_path is None) == (config.folder_path is None)):
            raise ValueError(
                "Exactly one of `combined_path` or `folder_path` must be provided"
            )
        
        def _load_data_from_path(path: Path) -> pd.DataFrame:
            if path.suffix.lower() == ".parquet":
                return pd.read_parquet(path)
            elif path.suffix.lower() == ".csv":
                return pd.read_csv(path)
            elif path.suffix.lower() == ".feather":
                return pd.read_feather(path)
            else:
                raise ValueError(f"Unsupported file extension: {path.suffix}")
        
        if config.combined_path is not None:
            path = Path(config.combined_path)
            if not path.exists():
                raise FileNotFoundError(f"Combined data file not found: {path}")
            
            df = _load_data_from_path(path)

            # filter by universe
            df = df[df[config.symbol_col].isin(universe)]
        else:
            folder_path = Path(config.folder_path)
            if not folder_path.exists() or not folder_path.is_dir():
                raise FileNotFoundError(f"Data folder not found: {folder_path}")
            
            symb_dfs = []

            for symbol in universe:
                fp = folder_path / f"{symbol}{config.file_extension}"
                if not fp.exists():
                    raise FileNotFoundError(
                        f"Data file for symbol '{symbol}' not found: {fp}"
                    )
                
                tmp = _load_data_from_path(fp)
                tmp[config.symbol_col] = symbol
                symb_dfs.append(tmp)

            if not symb_dfs:
                raise ValueError("No data files found for the given universe")
            
            df = pd.concat(symb_dfs, ignore_index=True)

        # Ensure timestamp column is datetime
        df[config.timestamp_col] = pd.to_datetime(df[config.timestamp_col])
        if config.tz is not None:
            # If df timestamps are naive, localize; else convert
            if df[config.timestamp_col].dt.tz is None:
                df[config.timestamp_col] = (
                    df[config.timestamp_col].dt.tz_localize(config.tz)
                )
            else:
                df[config.timestamp_col] = (
                    df[config.timestamp_col].dt.tz_convert(config.tz)
                )

        # Keep required cols only
        for col in config.required_cols:
            if col not in df.columns:
                raise ValueError(f"Required column '{col}' not found in data")
        
        df = df[list(config.required_cols)]

        df = df.sort_values(
            [config.timestamp_col, config.symbol_col], 
            kind="mergesort"
        ).reset_index(drop=True)

        return df

    def _build_snapshots(
        self,
        df: pd.DataFrame,
        clock_index: Sequence[pd.Timestamp],
        config: DataHandlerConfig
    ) -> Mapping[pd.Timestamp, Dict[str, Bar]]:
        """Build per-timestamp snapshots from the loaded data."""
        snapshots: Dict[pd.Timestamp, Dict[str, Bar]] = {}

        grouped = df.groupby(config.timestamp_col, sort=False)
        has_vol_col = "volume" in df.columns

        for ts, g in grouped:
            snap: Dict[str, Bar] = {}
            for row in g.itertuples(index=False):
                    sym = getattr(row, config.symbol_col)
                    vol = float(row.volume) if has_vol_col else 0.0
                    snap[sym] = Bar(
                        open=float(row.open),
                        high=float(row.high),
                        low=float(row.low),
                        close=float(row.close),
                        volume=vol,
                    )
            snapshots[ts] = snap

        clock_set = set(clock_index)
        snapshots = {ts: snap for ts, snap in snapshots.items() if ts in clock_set}

        return snapshots


            
if __name__ == "__main__":
    # Minimal smoke test with an in-memory dataframe (no files needed)
    from src.backtesting.clock import Clock, ClockConfig  # adjust import to your actual clock module

    cfg_clock = ClockConfig(
        start=pd.Timestamp("2025-01-03"),
        end=pd.Timestamp("2025-01-05"),
        freq="1D",
        tz=None,
    )
    clock = Clock(cfg_clock)
    timestamps = []
    while clock.next():
        timestamps.append(clock.now)

    # Create toy combined data
    df = pd.DataFrame(
        {
            "timestamp": [timestamps[0], timestamps[0], timestamps[1], timestamps[1]],
            "symbol": ["ES", "NQ", "ES", "NQ"],
            "open": [1, 10, 2, 11],
            "high": [1, 10, 2, 11],
            "low": [1, 10, 2, 11],
            "close": [1.5, 10.5, 2.5, 11.5],
            "volume": [100, 200, 110, 210],
        }
    )
    # Write temp parquet to test config path loading
    tmp = Path("tmp_combined.parquet")
    df.to_parquet(tmp)

    dh = DataHandler(
        clock=timestamps,
        universe=["ES", "NQ"],
        config=DataHandlerConfig(combined_path=tmp),
    )

    snap0 = dh.update(timestamps[0])
    assert snap0["ES"].close == 1.5
    assert snap0["NQ"].close == 10.5

    snap1 = dh.update(timestamps[1])
    assert snap1["ES"].close == 2.5
    assert snap1["NQ"].close == 11.5

    snap_missing = dh.update(pd.Timestamp("1999-01-01"))
    assert snap_missing == {}

    tmp.unlink(missing_ok=True)
    print("DataHandler smoke test passed.")
