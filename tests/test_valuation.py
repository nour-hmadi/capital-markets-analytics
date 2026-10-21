import pytest

from valuation import direction_sign, value_bond, value_equity

EQUITY_BUY = {"direction": "BUY", "quantity": 100, "trade_price": 5000.0}
EQUITY_SELL = {"direction": "SELL", "quantity": 100, "trade_price": 5000.0}
BOND_BUY = {"direction": "BUY", "quantity": 1_000_000, "trade_price": 100.0,
            "coupon_rate": 0.05, "maturity_years": 5}
BOND_SELL = {**BOND_BUY, "direction": "SELL"}


# ---------- Direction ----------

def test_direction_sign():
    assert direction_sign("BUY") == 1
    assert direction_sign("SELL") == -1


def test_unknown_direction_raises_error():
    with pytest.raises(ValueError):
        direction_sign("HOLD")


# ---------- Equities ----------

def test_long_equity_gains_when_price_rises():
    result = value_equity(EQUITY_BUY, 5100.0)
    assert result["market_value"] == pytest.approx(510_000)
    assert result["pnl"] == pytest.approx(10_000)


def test_short_equity_loses_when_price_rises():
    assert value_equity(EQUITY_SELL, 5100.0)["pnl"] == pytest.approx(-10_000)


def test_equity_pnl_is_zero_at_trade_price():
    assert value_equity(EQUITY_BUY, 5000.0)["pnl"] == pytest.approx(0)


# ---------- Bonds ----------

def test_bond_pnl_is_zero_at_the_trade_yield():
    # A 5% coupon bond bought at 100 was bought at a 5% yield
    assert value_bond(BOND_BUY, 5.0)["pnl"] == pytest.approx(0, abs=1e-6)


def test_long_bond_loses_and_short_bond_gains_when_yields_rise():
    assert value_bond(BOND_BUY, 5.5)["pnl"] < 0
    assert value_bond(BOND_SELL, 5.5)["pnl"] > 0


def test_bond_dv01_known_value():
    # 5-year 5% bond: DV01 is about 0.433 per 100 of face, so about 433 for 1,000,000 face
    assert value_bond(BOND_BUY, 5.0)["dv01"] == pytest.approx(432.9, abs=1)


def test_one_bp_rise_loses_about_one_dv01():
    dv01_now = value_bond(BOND_BUY, 5.0)["dv01"]
    pnl_after_1bp = value_bond(BOND_BUY, 5.01)["pnl"]
    assert pnl_after_1bp == pytest.approx(-dv01_now, rel=1e-2)
