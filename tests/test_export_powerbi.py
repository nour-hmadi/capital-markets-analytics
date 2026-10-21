import pandas as pd
import pytest

from export_powerbi import OUTPUT, main

EXPECTED_ROWS = {"dim_date": 252, "dim_trade": 60, "fact_market_prices": 3024,
                 "fact_price_analytics": 7 * 252, "fact_curve": 252, "fact_valuations": 7403}


@pytest.fixture(scope="module")
def workbook():
    main()
    return pd.read_excel(OUTPUT, sheet_name=None)     # all sheets, as {name: table}


def test_all_sheets_present(workbook):
    assert set(workbook) == set(EXPECTED_ROWS)


@pytest.mark.parametrize("sheet, rows", EXPECTED_ROWS.items())
def test_row_counts(workbook, sheet, rows):
    assert len(workbook[sheet]) == rows


def test_valuation_dates_exist_in_dim_date(workbook):
    assert set(workbook["fact_valuations"]["date"]) <= set(workbook["dim_date"]["date"])


def test_valuation_trades_exist_in_dim_trade(workbook):
    assert set(workbook["fact_valuations"]["trade_id"]) <= set(workbook["dim_trade"]["trade_id"])
