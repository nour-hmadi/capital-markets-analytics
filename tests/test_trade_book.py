from pathlib import Path

import pandas as pd
import pytest

from trades import generate_trade_book

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REQUIRED = ["trade_id", "trade_date", "desk", "instrument_type", "underlying",
            "direction", "quantity", "trade_price", "counterparty"]


@pytest.fixture(scope="module")
def book():
    return pd.read_csv(DATA_DIR / "trades.csv", parse_dates=["trade_date", "maturity_date"])


def test_sixty_trades_twenty_per_type(book):
    assert len(book) == 60
    assert (book["instrument_type"].value_counts() == 20).all()


def test_trade_ids_are_unique(book):
    assert book["trade_id"].is_unique


def test_trades_are_sorted_by_date(book):
    assert book["trade_date"].is_monotonic_increasing


def test_required_fields_are_never_empty(book):
    assert not book[REQUIRED].isna().any().any()


def test_desk_matches_instrument_type(book):
    expected_desk = {"EQUITY_INDEX": "EQUITY", "BOND": "RATES", "FX_FORWARD": "FX"}
    assert (book["instrument_type"].map(expected_desk) == book["desk"]).all()


def test_bond_fields_only_on_bonds(book):
    is_bond = book["instrument_type"] == "BOND"
    cols = ["coupon_rate", "maturity_years"]
    assert book.loc[is_bond, cols].notna().all().all()
    assert book.loc[~is_bond, cols].isna().all().all()


def test_fx_fields_only_on_fx_forwards(book):
    is_fx = book["instrument_type"] == "FX_FORWARD"
    cols = ["spot_at_trade", "maturity_date"]
    assert book.loc[is_fx, cols].notna().all().all()
    assert book.loc[~is_fx, cols].isna().all().all()


def test_saved_file_matches_the_generator(book):
    fresh = generate_trade_book()
    assert fresh["trade_id"].tolist() == book["trade_id"].tolist()
    assert fresh["trade_price"].tolist() == pytest.approx(book["trade_price"].tolist())
