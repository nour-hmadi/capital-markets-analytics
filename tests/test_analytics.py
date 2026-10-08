from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analytics import annualised_volatility, daily_returns, rolling_volatility

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load(name):
    return pd.read_csv(DATA_DIR / name, index_col="date", parse_dates=True)


def test_daily_returns_known_values():
    prices = pd.DataFrame({"A": [100.0, 110.0, 99.0]})
    assert daily_returns(prices)["A"].tolist() == pytest.approx([0.10, -0.10])


def test_first_day_has_no_return():
    prices = pd.DataFrame({"A": [100.0, 101.0, 102.0, 103.0]})
    assert len(daily_returns(prices)) == 3


def test_constant_prices_have_zero_volatility():
    prices = pd.DataFrame({"A": [100.0] * 30})
    assert annualised_volatility(daily_returns(prices))["A"] == pytest.approx(0.0)


def test_rolling_volatility_needs_a_full_window():
    returns = pd.DataFrame({"A": np.random.default_rng(0).normal(0, 0.01, 100)})
    assert rolling_volatility(returns, window=21)["A"].isna().sum() == 20


@pytest.mark.parametrize("column, model_vol",
                         [("INDEX_US", 0.16), ("INDEX_TECH", 0.22), ("INDEX_EU", 0.18)])
def test_equity_volatility_matches_the_generator(column, model_vol):
    vol = annualised_volatility(daily_returns(load("equities.csv")))
    assert vol[column] == pytest.approx(model_vol, abs=0.03)
