"""XML trade messages: schema validation, rejection of broken messages, round trip, business rules."""
import copy
from pathlib import Path

import pandas as pd
import pytest
from lxml import etree

from export_xml import OUTPUT, book_to_xml, load_schema, xml_to_book

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DESK_FOR_PRODUCT = {"equity": "EQUITY", "bond": "RATES", "fxForward": "FX"}


@pytest.fixture(scope="module")
def schema():
    return load_schema()


@pytest.fixture(scope="module")
def book():
    return pd.read_csv(DATA_DIR / "trades.csv", parse_dates=["trade_date", "maturity_date"])


@pytest.fixture
def root(book):
    return book_to_xml(book)        # a fresh copy for every test, so tests can break it safely


def business_rule_errors(root):
    """Rules the XSD cannot express: each desk books only its own product type."""
    errors = []
    for trade in root.findall("trade"):
        product = trade[7].tag
        if trade.findtext("desk") != DESK_FOR_PRODUCT[product]:
            errors.append(f"{trade.findtext('tradeId')}: desk {trade.findtext('desk')} cannot book {product}")
    return errors


# ---------- 1. Positive tests ----------

def test_generated_xml_is_valid(schema, root):
    assert schema.validate(root), schema.error_log


def test_saved_file_is_valid_and_up_to_date(schema, root):
    saved = etree.parse(str(OUTPUT))
    assert schema.validate(saved), schema.error_log
    pd.testing.assert_frame_equal(xml_to_book(saved.getroot()), xml_to_book(root))


# ---------- 2. Negative tests: broken messages must be rejected ----------

def set_text(path, value):
    def mutate(root):
        root.find(path).text = value
    return mutate


def remove(path):
    def mutate(root):
        element = root.find(path)
        element.getparent().remove(element)
    return mutate


def add_second_product_block(root):
    trade = root.find("trade")
    trade.append(copy.deepcopy(trade[7]))


def duplicate_first_trade(root):
    root.append(copy.deepcopy(root[0]))


BROKEN_MESSAGES = {
    "direction is HOLD": set_text("trade/direction", "HOLD"),
    "negative quantity": set_text("trade/quantity", "-100"),
    "zero price": set_text("trade/tradePrice", "0"),
    "badly formatted trade id": set_text("trade/tradeId", "TRADE-1"),
    "unknown desk": set_text("trade/desk", "CRYPTO"),
    "impossible date": set_text("trade/tradeDate", "2025-13-01"),
    "missing counterparty": remove("trade/counterparty"),
    "empty counterparty": set_text("trade/counterparty", ""),
    "two product blocks": add_second_product_block,
    "duplicate trade id": duplicate_first_trade,
}


@pytest.mark.parametrize("name", list(BROKEN_MESSAGES))
def test_broken_message_is_rejected(schema, root, name):
    BROKEN_MESSAGES[name](root)
    assert not schema.validate(root)


# ---------- 3. Round trip ----------

def test_round_trip_csv_to_xml_and_back(book, root):
    back = xml_to_book(root)[book.columns]
    pd.testing.assert_frame_equal(back, book, check_dtype=False)


# ---------- 4. What the XSD cannot catch ----------

def test_generated_trades_follow_business_rules(root):
    assert business_rule_errors(root) == []


def test_xsd_cannot_catch_a_desk_product_mismatch(schema, root):
    root.find("trade/desk").text = "FX"          # the first trade is an equity
    assert schema.validate(root)                 # the XSD still says valid...
    assert business_rule_errors(root)            # ...but the business rule check catches it
