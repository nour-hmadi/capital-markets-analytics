import pytest

from pricing import (bond_price, cross_rate, dv01, fx_forward,
                     macaulay_duration, modified_duration)


# ---------- Bond price ----------

def test_par_bond_prices_at_face_value():
    assert bond_price(1000, 0.05, 5, 0.05) == pytest.approx(1000)


def test_known_price_of_discount_bond():
    assert bond_price(1000, 0.05, 5, 0.06) == pytest.approx(957.88, abs=0.01)


def test_one_year_bond_matches_day1_formula():
    assert bond_price(1000, 0.05, 1, 0.06) == pytest.approx(1050 / 1.06)


def test_premium_and_discount():
    assert bond_price(1000, 0.05, 5, 0.04) > 1000   # yield < coupon -> premium
    assert bond_price(1000, 0.05, 5, 0.06) < 1000   # yield > coupon -> discount


def test_price_falls_when_yield_rises():
    assert bond_price(1000, 0.05, 10, 0.06) < bond_price(1000, 0.05, 10, 0.05)


def test_invalid_maturity_raises_error():
    with pytest.raises(ValueError):
        bond_price(1000, 0.05, 0, 0.05)


# ---------- Duration and DV01 ----------

@pytest.mark.parametrize("years", [1, 5, 10, 30])
def test_zero_coupon_duration_equals_maturity(years):
    assert macaulay_duration(1000, 0.0, years, 0.05) == pytest.approx(years)


@pytest.mark.parametrize("years", [2, 5, 10, 30])
def test_coupon_bond_duration_is_shorter_than_maturity(years):
    assert macaulay_duration(1000, 0.05, years, 0.05) < years


def test_dv01_is_positive_and_grows_with_maturity():
    values = [dv01(1000, 0.05, years, 0.05) for years in [2, 5, 10, 30]]
    assert all(v > 0 for v in values)
    assert values == sorted(values)


@pytest.mark.parametrize("years", [2, 5, 10, 30])
def test_dv01_matches_modified_duration(years):
    price = bond_price(1000, 0.05, years, 0.05)
    expected = price * modified_duration(1000, 0.05, years, 0.05) * 0.0001
    assert dv01(1000, 0.05, years, 0.05) == pytest.approx(expected, rel=1e-2)


# ---------- FX ----------

def test_cross_rate_is_consistent():
    eur_gbp = cross_rate(1.10, 1.28)
    assert eur_gbp * 1.28 == pytest.approx(1.10)


def test_forward_equals_spot_when_rates_are_equal():
    assert fx_forward(1.10, r_base=0.03, r_quote=0.03, years=1) == pytest.approx(1.10)


def test_forward_known_value():
    assert fx_forward(1.10, r_base=0.02, r_quote=0.04, years=1) == pytest.approx(1.10 * 1.04 / 1.02)
