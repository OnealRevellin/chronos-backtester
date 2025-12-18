import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Set the seed for reproducibility
np.random.seed(42)
random.seed(42)

# Define parameters for the assets
assets = [f"asset{i}" for i in range(1, 11)]  # asset1, asset2, ..., asset10
start_date = datetime(2013, 1, 1)
end_date = datetime(2023, 1, 1)
date_range = pd.date_range(start=start_date, end=end_date, freq='D')

# Function to generate random price movement (Geometric Brownian Motion)
def generate_price_series(start_price, drift, volatility, days):
    prices = [start_price]
    for _ in range(1, days):
        daily_return = np.random.normal(drift / 252, volatility / np.sqrt(252))
        new_price = prices[-1] * (1 + daily_return)
        prices.append(new_price)
    return np.array(prices)

# Simulate market crash by increasing volatility and forcing correlations
def simulate_market_crash(prices_dict, crash_period_start, crash_period_end):
    for asset in prices_dict:
        crash_factor = 0.3  # 30% drop
        for i in range(len(prices_dict[asset])):
            if crash_period_start <= date_range[i] <= crash_period_end:
                prices_dict[asset][i] *= (1 - crash_factor + np.random.normal(0, 0.02))  # Crash with some noise

    # During crash, force correlation between assets
    correlated_assets = [f"asset{i}" for i in range(1, 6)]  # Example of correlated assets (asset1, asset2, ..., asset5)
    for i in range(len(prices_dict['asset1'])):
        if crash_period_start <= date_range[i] <= crash_period_end:
            asset1_price = prices_dict['asset1'][i]
            for asset in correlated_assets:
                prices_dict[asset][i] = asset1_price * np.random.normal(1, 0.02)  # Keep prices closely correlated

    return prices_dict

# Function to generate random volume data
def generate_volume(days):
    return np.random.randint(1000, 10000, size=days)

# Generate price data for each asset
prices_dict = {}
for asset in assets:
    start_price = random.uniform(50, 200)  # Random initial price for each asset
    drift = random.uniform(0.05, 0.15)  # Random drift (return)
    volatility = random.uniform(0.3, 1.5)  # Random volatility
    prices_dict[asset] = generate_price_series(start_price, drift, volatility, len(date_range))

# Simulate two market crashes (let's say one in 2017 and another in 2020)
prices_dict = simulate_market_crash(prices_dict, datetime(2017, 1, 1), datetime(2017, 6, 1))
prices_dict = simulate_market_crash(prices_dict, datetime(2020, 3, 1), datetime(2020, 5, 1))

# Create the final dataframe
final_data = []
for i, date in enumerate(date_range):
    for asset in assets:
        open_price = prices_dict[asset][i] * np.random.uniform(0.98, 1.02)  # Random opening price within 2% of the close
        close_price = prices_dict[asset][i]
        high_price = max(open_price, close_price) * np.random.uniform(1.02, 1.05)  # High price is slightly higher
        low_price = min(open_price, close_price) * np.random.uniform(0.95, 0.98)  # Low price is slightly lower
        volume = generate_volume(len(date_range))[i]  # Random volume
        final_data.append([date, asset, open_price, close_price, high_price, low_price, volume])

# Convert to DataFrame
df = pd.DataFrame(final_data, columns=['date', 'ticker', 'open', 'close', 'high', 'low', 'volume'])

# Save to CSV
df.to_csv('synthetic_crypto_data_assets.csv', index=False)

print("CSV file generated and saved as 'synthetic_crypto_data_assets.csv'")
