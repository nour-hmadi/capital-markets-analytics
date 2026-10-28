"""Trade desk endpoints: visitors create, read, update and delete their own trades.

Desk trades live in desk_trades (IDs from T90001). The official book (dim_trade) is read-only.
"""
from datetime import date as Date
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response
from lxml import etree
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

import desk
from export_xml import load_schema, trade_to_xml
from load_db import DATABASE_URL

router = APIRouter(prefix="/desk/trades", tags=["trade desk"])
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SCHEMA = load_schema()
OWNER = "guest"                      # Sign in with Google will replace this with the user's email
MAX_TRADES = 20
COLUMNS = ("trade_id, trade_date, desk, instrument_type, underlying, direction, quantity, trade_price, "
           "coupon_rate, maturity_years, spot_at_trade, maturity_date, counterparty")
TradeId = Path(pattern=r"^T\d{5}$")


class NewTrade(BaseModel):
    instrument_type: Literal["EQUITY_INDEX", "BOND", "FX_FORWARD"]
    underlying: str
    direction: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0, le=desk.MAX_QUANTITY)
    trade_date: Date
    counterparty: str
    tenor_months: Optional[int] = None


class TradeChange(BaseModel):
    direction: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0, le=desk.MAX_QUANTITY)


def market_data():
    """Market prices from the database, as the wide tables the pricing code expects."""
    with engine.connect() as conn:
        prices = pd.read_sql(text("SELECT date, asset_class, series, value FROM fact_market_prices"),
                             conn, parse_dates=["date"])
    return {name: prices[prices["asset_class"] == asset_class]
            .pivot(index="date", columns="series", values="value").astype(float)
            for name, asset_class in [("equities", "EQUITY"), ("curves", "RATES"), ("fx", "FX")]}


def as_trade(row):
    """A database row with Python types the pricing and XML code can use."""
    trade = dict(row)
    for key in ("quantity", "maturity_years"):
        trade[key] = None if trade[key] is None else int(trade[key])
    for key in ("trade_price", "coupon_rate", "spot_at_trade"):
        trade[key] = None if trade[key] is None else float(trade[key])
    for key in ("trade_date", "maturity_date"):
        trade[key] = None if trade[key] is None else pd.Timestamp(trade[key])
    return trade


def with_valuation(row, market):
    trade = as_trade(row)
    shown = {**trade, "trade_date": trade["trade_date"].date(),
             "maturity_date": trade["maturity_date"].date() if trade["maturity_date"] is not None else None}
    return {**shown, **desk.value_today(trade, market)}


def check_editable(trade_id):
    if trade_id < "T90001":
        raise HTTPException(status_code=403, detail="The official book is read-only: only desk trades "
                                                    "(T90001 and above) can be changed")


@router.get("")
def list_trades():
    market = market_data()
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT {COLUMNS} FROM desk_trades WHERE owner = :owner ORDER BY trade_id"),
                            {"owner": OWNER}).mappings().all()
    return [with_valuation(row, market) for row in rows]


@router.post("", status_code=201)
def create_trade(new: NewTrade):
    market = market_data()
    try:
        trade = desk.book_trade(market=market, **new.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    values = {**trade, "owner": OWNER, "trade_date": trade["trade_date"].date(),
              "maturity_date": trade["maturity_date"].date() if trade["maturity_date"] is not None else None}
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM desk_trades WHERE owner = :owner"),
                             {"owner": OWNER}).scalar()
        if count >= MAX_TRADES:
            raise HTTPException(status_code=409, detail=f"Limit of {MAX_TRADES} trades reached: delete one first")
        row = conn.execute(text(f"""
            INSERT INTO desk_trades (owner, trade_date, desk, instrument_type, underlying, direction, quantity,
                                     trade_price, coupon_rate, maturity_years, spot_at_trade, maturity_date,
                                     counterparty)
            VALUES (:owner, :trade_date, :desk, :instrument_type, :underlying, :direction, :quantity,
                    :trade_price, :coupon_rate, :maturity_years, :spot_at_trade, :maturity_date, :counterparty)
            RETURNING {COLUMNS}
        """), values).mappings().one()
    return with_valuation(row, market)


@router.put("/{trade_id}")
def change_trade(change: TradeChange, trade_id: str = TradeId):
    check_editable(trade_id)
    with engine.begin() as conn:
        row = conn.execute(text(f"""
            UPDATE desk_trades SET direction = :direction, quantity = :quantity
            WHERE trade_id = :trade_id AND owner = :owner
            RETURNING {COLUMNS}
        """), {**change.model_dump(), "trade_id": trade_id, "owner": OWNER}).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Desk trade {trade_id} not found")
    return with_valuation(row, market_data())


@router.delete("/{trade_id}", status_code=204)
def delete_trade(trade_id: str = TradeId):
    check_editable(trade_id)
    with engine.begin() as conn:
        deleted = conn.execute(text("DELETE FROM desk_trades WHERE trade_id = :trade_id AND owner = :owner"),
                               {"trade_id": trade_id, "owner": OWNER}).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Desk trade {trade_id} not found")
    return Response(status_code=204)


@router.get("/{trade_id}/xml")
def trade_xml(trade_id: str = TradeId):
    with engine.connect() as conn:
        row = conn.execute(text(f"SELECT {COLUMNS} FROM desk_trades WHERE trade_id = :trade_id AND owner = :owner"),
                           {"trade_id": trade_id, "owner": OWNER}).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Desk trade {trade_id} not found")
    root = etree.Element("trades")
    trade_to_xml(root, as_trade(row))
    if not SCHEMA.validate(root):                       # never send an invalid message
        raise HTTPException(status_code=500, detail="Generated message failed XSD validation")
    return Response(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"),
                    media_type="application/xml")
