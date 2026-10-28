"""Trade desk logic: booking at market prices, validation, valuation and XML. No database needed."""
import pandas as pd
import pytest
from lxml import etree

import desk
from export_xml import load_schema, trade_to_xml
from trades import load_market

MARKET = {"equities": load_market("equities.csv"), "curves": load_market("yield_curves.csv"),
          "fx": load_market("fx_rates.csv")}
DAY = "2025-03-03"                                   # a Monday, so a trading day


def book(**changes):
    args = dict(instrument_type="EQUITY_INDEX", underlying="INDEX_US", direction="BUY",
                quantity=100, trade_date=DAY, counterparty="Alpha Bank")
    return desk.book_trade(market=MARKET, **(args | changes))


def test_equity_is_booked_at_that_days_close():
    trade = book()
    assert trade["desk"] == "EQUITY"
    assert trade["trade_price"] == round(MARKET["equities"].loc[DAY, "INDEX_US"], 2)


def test_bond_gets_a_coupon_a_maturity_and_a_price_near_par():
    trade = book(instrument_type="BOND", underlying="GOV_10Y", quantity=1_000_000)
    assert trade["maturity_years"] == 10
    assert 95 < trade["trade_price"] < 105            # coupon is set near the market yield


def test_fx_forward_matures_after_its_tenor():
    trade = book(instrument_type="FX_FORWARD", underlying="EURUSD", quantity=1_000_000, tenor_months=6)
    assert trade["maturity_date"] == pd.Timestamp(DAY) + pd.DateOffset(months=6)


@pytest.mark.parametrize("changes, message", [
    ({"underlying": "GOV_10Y"}, "not a valid underlying"),
    ({"direction": "HOLD"}, "BUY or SELL"),
    ({"quantity": 0}, "whole number"),
    ({"trade_date": "2025-03-01"}, "not a trading day"),          # a Saturday
    ({"counterparty": "Unknown Bank"}, "Unknown counterparty"),
    ({"instrument_type": "FX_FORWARD", "underlying": "EURUSD"}, "tenor"),
])
def test_invalid_bookings_are_rejected(changes, message):
    with pytest.raises(ValueError, match=message):
        book(**changes)


def test_buy_and_sell_of_the_same_trade_offset_each_other():
    assert desk.value_today(book(), MARKET)["pnl"] == -desk.value_today(book(direction="SELL"), MARKET)["pnl"]


def test_pnl_follows_the_market_move():
    trade = book()
    last = MARKET["equities"]["INDEX_US"].iloc[-1]
    assert desk.value_today(trade, MARKET)["pnl"] == pytest.approx(100 * (last - trade["trade_price"]), abs=0.01)


def test_booked_trades_make_valid_xml_messages():
    root = etree.Element("trades")
    for number, changes in enumerate([{}, {"instrument_type": "BOND", "underlying": "GOV_5Y"},
                                      {"instrument_type": "FX_FORWARD", "underlying": "USDJPY",
                                       "tenor_months": 3}], start=90001):
        trade_to_xml(root, book(**changes) | {"trade_id": f"T{number}"})
    assert load_schema().validate(root)
