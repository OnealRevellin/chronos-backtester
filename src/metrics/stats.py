from typing import Optional, List
import numpy as np
import pandas as pd


def log_return(
    df: pd.DataFrame,
    price_col: str,
    groupby: Optional[str | List[str]] = None
) -> pd.Series:
    """
    Compute log returns, optionally grouped.

    Parameters
    ----------
    df : pd.DataFrame
    price_col : str
        Column containing prices
    groupby : str or list[str], optional
        Grouping key(s)
    sort_index : bool
        Whether to sort by index before computing returns
    ascending : bool
        Sort order

    Returns
    -------
    pd.Series
        Log returns aligned with df index
    """
    if len(df) <= 1:
        return pd.Series(dtype="float64", index=df.index)

    s = df[price_col]

    log_price = np.log(s)

    if groupby is not None:
        return log_price - log_price.groupby(df[groupby]).shift(-1)

    return log_price - log_price.shift(-1)


if __name__ == "__main__":
    df = pd.read_csv("data/csv/random/random.csv")
    df.set_index("date", inplace=True)
    df.sort_index(ascending=False, inplace=True)
    log_ret = log_return(df, "close", groupby="ticker")
    print(df.head)