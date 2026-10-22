"""Convert the trade book (CSV) into XML trade messages, validated against schemas/trade.xsd."""
from pathlib import Path

import pandas as pd
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCHEMA_FILE = ROOT / "schemas" / "trade.xsd"
OUTPUT = DATA_DIR / "trades.xml"
PRODUCT_TYPES = {"equity": "EQUITY_INDEX", "bond": "BOND", "fxForward": "FX_FORWARD"}


def load_schema():
    return etree.XMLSchema(etree.parse(str(SCHEMA_FILE)))


def number(value):
    """Whole numbers without '.0' (9000000, not 9000000.0); other numbers exactly as stored."""
    value = float(value)
    return str(int(value)) if value.is_integer() else repr(value)


def add(parent, tag, text):
    child = etree.SubElement(parent, tag)
    child.text = str(text)
    return child


# ---------- CSV row -> XML ----------

def trade_to_xml(parent, trade):
    element = etree.SubElement(parent, "trade")
    add(element, "tradeId", trade["trade_id"])
    add(element, "tradeDate", trade["trade_date"].date().isoformat())
    add(element, "desk", trade["desk"])
    add(element, "counterparty", trade["counterparty"])
    add(element, "direction", trade["direction"])
    add(element, "quantity", int(trade["quantity"]))
    add(element, "tradePrice", number(trade["trade_price"]))

    kind = trade["instrument_type"]
    if kind == "EQUITY_INDEX":
        product = etree.SubElement(element, "equity")
        add(product, "index", trade["underlying"])
    elif kind == "BOND":
        product = etree.SubElement(element, "bond")
        add(product, "security", trade["underlying"])
        add(product, "couponRate", number(trade["coupon_rate"]))
        add(product, "maturityYears", int(trade["maturity_years"]))
    elif kind == "FX_FORWARD":
        product = etree.SubElement(element, "fxForward")
        add(product, "currencyPair", trade["underlying"])
        add(product, "spotAtTrade", number(trade["spot_at_trade"]))
        add(product, "maturityDate", trade["maturity_date"].date().isoformat())
    else:
        raise ValueError(f"Unknown instrument type: {kind}")


def book_to_xml(book):
    root = etree.Element("trades")
    for _, trade in book.iterrows():
        trade_to_xml(root, trade)
    return root


# ---------- XML -> table (used by the round-trip test) ----------

def optional_float(element, tag):
    text = element.findtext(tag)
    return float(text) if text is not None else float("nan")


def xml_to_book(root):
    rows = []
    for trade in root.findall("trade"):
        product = trade[7]                      # the product block follows the 7 common fields
        maturity_date = product.findtext("maturityDate")
        rows.append({
            "trade_id": trade.findtext("tradeId"),
            "trade_date": pd.Timestamp(trade.findtext("tradeDate")),
            "desk": trade.findtext("desk"),
            "instrument_type": PRODUCT_TYPES[product.tag],
            "underlying": product[0].text,      # index, security or currencyPair
            "direction": trade.findtext("direction"),
            "quantity": int(trade.findtext("quantity")),
            "trade_price": float(trade.findtext("tradePrice")),
            "counterparty": trade.findtext("counterparty"),
            "coupon_rate": optional_float(product, "couponRate"),
            "maturity_years": optional_float(product, "maturityYears"),
            "spot_at_trade": optional_float(product, "spotAtTrade"),
            "maturity_date": pd.Timestamp(maturity_date) if maturity_date else pd.NaT,
        })
    return pd.DataFrame(rows)


def main():
    book = pd.read_csv(DATA_DIR / "trades.csv", parse_dates=["trade_date", "maturity_date"])
    root = book_to_xml(book)
    schema = load_schema()
    if not schema.validate(root):                # validate BEFORE saving
        for error in schema.error_log:
            print(f"line {error.line}: {error.message}")
        raise SystemExit("Generated XML does not match the schema. Nothing was saved.")
    etree.ElementTree(root).write(str(OUTPUT), pretty_print=True,
                                  xml_declaration=True, encoding="UTF-8")
    print(f"Saved {OUTPUT.name}: {len(book)} trades, valid against {SCHEMA_FILE.name}")


if __name__ == "__main__":
    main()
