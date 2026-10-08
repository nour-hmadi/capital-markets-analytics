from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analytics import correlation_matrix, daily_returns, drawdown, max_drawdown

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load(name):
    return pd.read_csv(DATA_DIR / name, index_col="date", parse_dates=True)


def test_drawdown_known_values():
    prices = pd.DataFrame({"A": [100.0, 120.0, 90.0, 130.0]})
    assert drawdown(prices)["A"].tolist() == pytest.approx([0.0, 0.0, -0.25, 0.0])
    assert max_drawdown(prices)["A"] == pytest.approx(-0.25)


def test_rising_prices_have_no_drawdown():
    prices = pd.DataFrame({"A": [100.0, 101.0, 105.0, 110.0]})
    assert max_drawdown(prices)["A"] == pytest.approx(0.0)


def test_drawdown_is_never_positive():
    assert (drawdown(load("equities.csv")) <= 0).all().all()


def test_correlation_matrix_shape_and_values():
    corr = correlation_matrix(daily_returns(load("equities.csv")))
    assert np.allclose(np.diag(corr), 1.0)          # each index vs itself = 1
    assert np.allclose(corr, corr.T)                # A vs B = B vs A
    assert ((corr >= -1) & (corr <= 1)).all().all()


def test_independent_simulations_are_nearly_uncorrelated():
    corr = correlation_matrix(daily_returns(load("equities.csv")))
    off_diagonal = corr.values[~np.eye(len(corr), dtype=bool)]
    assert (np.abs(off_diagonal) < 0.2).all()
