"""Generate synthetic market data for equities, rates and FX.

The data is simulated, not real. A fixed random seed makes every run
produce exactly the same numbers, so results can be tested and reproduced.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START_DATE = "2025-01-01"
N_DAYS = 252  # about one year of trading days
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def business_days(start=START_DATE, n=N_DAYS):
    """Weekdays only, like real trading days (holidays ignored)."""
    return pd.bdate_range(start=start, periods=n)


def simulate_gbm(rng, start_price, annual_drift, annual_vol, n_days):
    """Geometric Brownian motion: random daily returns, prices stay positive."""
    dt = 1 / 252
    shocks = rng.standard_normal(n_days - 1)
    log_returns = (annual_drift - 0.5 * annual_vol**2) * dt + annual_vol * np.sqrt(dt) * shocks
    log_prices = np.log(start_price) + np.concatenate([[0.0], np.cumsum(log_returns)])
    return np.exp(log_prices)


def generate_equities(rng, dates):
    # name: (start level, yearly drift, yearly volatility)
    indices = {
        "INDEX_US": (5000, 0.07, 0.16),
        "INDEX_TECH": (17000, 0.10, 0.22),
        "INDEX_EU": (4900, 0.05, 0.18),
    }
    data = {name: simulate_gbm(rng, *params, len(dates)) for name, params in indices.items()}
    return pd.DataFrame(data, index=dates).round(2)


def generate_yield_curves(rng, dates):
    tenors = ["1Y", "2Y", "5Y", "10Y", "30Y"]
    start_curve = np.array([3.0, 3.3, 3.7, 4.1, 4.4])  # yields in %, normal curve

    # Daily moves in basis points: one shift for the whole curve + a small move per tenor
    parallel_bp = rng.normal(0, 4, len(dates) - 1)
    individual_bp = rng.normal(0, 1.5, (len(dates) - 1, len(tenors)))
    daily_moves_bp = parallel_bp[:, None] + individual_bp

    moves_pct = np.vstack([np.zeros(len(tenors)), daily_moves_bp]) / 100  # bp -> %
    curves = start_curve + np.cumsum(moves_pct, axis=0)
    return pd.DataFrame(curves, index=dates, columns=tenors).round(4)


def generate_fx(rng, dates):
    # pair: (start rate, yearly drift, yearly volatility)
    pairs = {
        "EURUSD": (1.10, 0.0, 0.07),
        "GBPUSD": (1.28, 0.0, 0.08),
        "USDJPY": (150.0, 0.0, 0.10),
    }
    data = {pair: simulate_gbm(rng, *params, len(dates)) for pair, params in pairs.items()}
    df = pd.DataFrame(data, index=dates)
    df["EURGBP"] = df["EURUSD"] / df["GBPUSD"]  # cross rate, as on Day 2
    return df.round({"EURUSD": 5, "GBPUSD": 5, "USDJPY": 3, "EURGBP": 5})


def main():
    rng = np.random.default_rng(SEED)
    dates = business_days()
    DATA_DIR.mkdir(exist_ok=True)

    outputs = {
        "equities.csv": generate_equities(rng, dates),
        "yield_curves.csv": generate_yield_curves(rng, dates),
        "fx_rates.csv": generate_fx(rng, dates),
    }
    for filename, df in outputs.items():
        df.index.name = "date"
        df.to_csv(DATA_DIR / filename)
        print(f"Saved {filename}: {df.shape[0]} rows x {df.shape[1]} columns")


if __name__ == "__main__":
    main()
