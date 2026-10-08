import numpy as np
import pandas as pd
import pytest

from trades import generate_equity_trades, load_market


@pytest.fixture
def equities():
    return load_market("equities.csv")


@pytest.fixture
def equity_trades(equities):
    return generate_equity_trades(np.random.default_rng(0), equities, n_trades=50)


def test_number_of_trades(equity_trades):
    assert len(equity_trades) == 50


def test_direction_is_buy_or_sell(equity_trades):
    assert set(equity_trades["direction"]) <= {"BUY", "SELL"}


def test_quantity_is_a_positive_multiple_of_100(equity_trades):
    assert (equity_trades["quantity"] > 0).all()
    assert (equity_trades["quantity"] % 100 == 0).all()


def test_trade_price_matches_market_on_trade_date(equities, equity_trades):
    for _, trade in equity_trades.iterrows():
        assert trade["trade_price"] == equities.loc[trade["trade_date"], trade["underlying"]]


def test_same_seed_gives_same_trades(equities):
    first = generate_equity_trades(np.random.default_rng(1), equities)
    second = generate_equity_trades(np.random.default_rng(1), equities)
    pd.testing.assert_frame_equal(first, second)
