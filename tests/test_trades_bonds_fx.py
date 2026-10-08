import numpy as np
import pytest

from pricing import bond_price, fx_forward
from trades import DEPOSIT_RATES, generate_bond_trades, generate_fx_forward_trades, load_market


@pytest.fixture
def curves():
    return load_market("yield_curves.csv")


@pytest.fixture
def bond_trades(curves):
    return generate_bond_trades(np.random.default_rng(0), curves, n_trades=50)


@pytest.fixture
def fx_trades():
    return generate_fx_forward_trades(np.random.default_rng(0), load_market("fx_rates.csv"), n_trades=50)


# ---------- Bonds ----------

def test_coupon_is_a_multiple_of_a_quarter_percent(bond_trades):
    steps = bond_trades["coupon_rate"] * 400
    assert np.allclose(steps, steps.round())


def test_bond_price_is_recomputable_from_the_curve(curves, bond_trades):
    for _, t in bond_trades.iterrows():
        market_yield = curves.loc[t["trade_date"], f"{t['maturity_years']}Y"] / 100
        expected = bond_price(100, t["coupon_rate"], t["maturity_years"], market_yield)
        assert t["trade_price"] == pytest.approx(expected, abs=1e-4)


def test_premium_when_coupon_above_yield_discount_when_below(curves, bond_trades):
    for _, t in bond_trades.iterrows():
        market_yield = curves.loc[t["trade_date"], f"{t['maturity_years']}Y"] / 100
        if t["coupon_rate"] > market_yield:
            assert t["trade_price"] > 100
        elif t["coupon_rate"] < market_yield:
            assert t["trade_price"] < 100


# ---------- FX forwards ----------

def test_maturity_is_after_trade_date(fx_trades):
    assert (fx_trades["maturity_date"] > fx_trades["trade_date"]).all()


def test_forward_matches_interest_rate_parity(fx_trades):
    for _, t in fx_trades.iterrows():
        base, quote = t["underlying"][:3], t["underlying"][3:]
        months = round((t["maturity_date"] - t["trade_date"]).days / 30.4)
        expected = fx_forward(t["spot_at_trade"], DEPOSIT_RATES[base], DEPOSIT_RATES[quote], months / 12)
        assert t["trade_price"] == pytest.approx(expected, rel=1e-5)


def test_higher_rate_currency_is_cheaper_forward(fx_trades):
    for _, t in fx_trades.iterrows():
        base, quote = t["underlying"][:3], t["underlying"][3:]
        if DEPOSIT_RATES[quote] > DEPOSIT_RATES[base]:
            assert t["trade_price"] > t["spot_at_trade"]
        else:
            assert t["trade_price"] < t["spot_at_trade"]
