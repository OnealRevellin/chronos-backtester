from dataclasses import dataclass

import pandas as pd
from typing import Optional


class MarketData:
    def __init__(self):
        pass

    def get_data(
        self, 
        datasource: str,

        folder_name: Optional[str] = "random",
        file_name: Optional[str] = "random"
    ) -> pd.DataFrame:
        data = pd.DataFrame()
        
        if datasource == "csv":
            data = self.get_data_from_csv(folder_name, file_name)

        return data

    def get_data_from_csv(
        self, 
        folder_name, 
        file_name
    ) -> pd.DataFrame:
        path = f"data/csv/{folder_name}/{file_name}.csv"
        return pd.read_csv(path)
    


if __name__ == "__main__":
    df = MarketData().get_data(datasource="csv")
    print(df)