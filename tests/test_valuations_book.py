from pathlib import Path

import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def book():
    return pd.read_csv(DATA_DIR / "trades.csv", parse_dates=["trade_date", "maturity_date"])


@pytest.fixture(scope="module")
def vals():
    return pd.read_csv(DATA_DIR / "valuations.csv", parse_dates=["date"])


def test_every_trade_is_valued(book, vals):
    assert set(vals["trade_id"]) == set(book["trade_id"])


def test_valuation_starts_on_the_trade_date(book, vals):
    first_dates = vals.groupby("trade_id")["date"].min()
    assert (first_dates == book.set_index("trade_id")["trade_date"]).all()


def test_no_missing_values(vals):
    assert not vals.isna().any().any()


def test_pnl_is_close_to_zero_on_the_trade_date(book, vals):
    # Small differences come from rounding and from the day-count convention
    first = vals.merge(book[["trade_id", "trade_date"]], on="trade_id")
    first = first[first["date"] == first["trade_date"]]
    assert (first["pnl"].abs() < 1_000).all()


def test_dv01_only_on_bonds(book, vals):
    merged = vals.merge(book[["trade_id", "instrument_type"]], on="trade_id")
    is_bond = merged["instrument_type"] == "BOND"
    assert (merged.loc[is_bond, "dv01"] != 0).all()
    assert (merged.loc[~is_bond, "dv01"] == 0).all()


def test_matured_fx_pnl_stays_frozen(vals):
    matured = vals[vals["status"] == "MATURED"]
    assert len(matured) > 0
    assert (matured.groupby("trade_id")["pnl"].nunique() == 1).all()
