import pytest

from pricing import fx_forward
from valuation import value_fx_forward

EURUSD_BUY = {"direction": "BUY", "underlying": "EURUSD", "quantity": 1_000_000,
              "trade_price": fx_forward(1.10, 0.02, 0.04, 1.0),
              "trade_date": "2025-01-02", "maturity_date": "2026-01-02"}
EURUSD_SELL = {**EURUSD_BUY, "direction": "SELL"}


def test_pnl_is_zero_on_the_trade_date():
    result = value_fx_forward(EURUSD_BUY, 1.10, "2025-01-02")
    assert result["pnl"] == pytest.approx(0, abs=1e-6)


def test_long_gains_and_short_loses_when_base_currency_rises():
    assert value_fx_forward(EURUSD_BUY, 1.15, "2025-01-02")["pnl"] > 0
    assert value_fx_forward(EURUSD_SELL, 1.15, "2025-01-02")["pnl"] < 0


def test_market_value_equals_pnl():
    result = value_fx_forward(EURUSD_BUY, 1.12, "2025-06-02")
    assert result["market_value"] == result["pnl"]


def test_revision_question_short_usdjpy_loses_when_usd_rises():
    trade = {"direction": "SELL", "underlying": "USDJPY", "quantity": 5_000_000,
             "trade_price": 150.20, "maturity_date": "2026-01-02"}
    pnl = value_fx_forward(trade, 160.0, "2025-02-01")["pnl"]
    assert -200_000 < pnl < -100_000          # about -151k USD


def test_matured_trade_pnl_is_spot_minus_agreed_rate():
    trade = {**EURUSD_BUY, "trade_price": 1.12, "maturity_date": "2025-07-01"}
    result = value_fx_forward(trade, 1.15, "2025-08-01")
    assert result["status"] == "MATURED"
    assert result["pnl"] == pytest.approx(1_000_000 * (1.15 - 1.12))


def test_live_trade_status():
    assert value_fx_forward(EURUSD_BUY, 1.10, "2025-06-02")["status"] == "LIVE"


def test_pair_without_usd_raises_error():
    trade = {**EURUSD_BUY, "underlying": "EURGBP"}
    with pytest.raises(NotImplementedError):
        value_fx_forward(trade, 0.86, "2025-06-02")
