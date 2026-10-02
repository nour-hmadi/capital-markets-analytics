"""Data validation tests for the generated market data."""
from pathlib import Path

import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FILES = ["equities.csv", "yield_curves.csv", "fx_rates.csv"]


def load(name):
    return pd.read_csv(DATA_DIR / name, index_col="date", parse_dates=True)


@pytest.mark.parametrize("name", FILES)
def test_file_has_one_year_and_no_missing_values(name):
    df = load(name)
    assert len(df) == 252
    assert not df.isna().any().any()


@pytest.mark.parametrize("name", FILES)
def test_dates_are_weekdays_in_order(name):
    df = load(name)
    assert df.index.is_monotonic_increasing
    assert (df.index.dayofweek < 5).all()


def test_equity_and_fx_prices_are_positive():
    assert (load("equities.csv") > 0).all().all()
    assert (load("fx_rates.csv") > 0).all().all()


def test_eurgbp_matches_cross_rate():
    fx = load("fx_rates.csv")
    implied = fx["EURUSD"] / fx["GBPUSD"]
    assert ((fx["EURGBP"] - implied).abs() < 1e-4).all()
