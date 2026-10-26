"""REST API for the capital markets project.

Numbers come from the tested dbt marts; trade reference data comes from the trade table.
Run locally:  uvicorn api:app --app-dir src --reload
Interactive docs: http://127.0.0.1:8000/docs
"""
from datetime import date as Date
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import Response
from lxml import etree
from sqlalchemy import create_engine, text

from export_xml import load_schema, trade_to_xml
from load_db import DATABASE_URL
from pricing import bond_price, dv01, macaulay_duration

app = FastAPI(title="Capital Markets Analytics API", version="2.0")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)   # reconnects if the cloud DB went idle
MARTS = "analytics_marts"
VALID_DESKS = {"EQUITY", "RATES", "FX"}
SCHEMA = load_schema()


def latest_date(conn, table):
    return conn.execute(text(f"SELECT MAX(valuation_date) FROM {MARTS}.{table}")).scalar()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/trades")
def list_trades(desk: Optional[str] = None):
    if desk is not None and desk.upper() not in VALID_DESKS:
        raise HTTPException(status_code=400,
                            detail=f"Unknown desk '{desk}'. Use one of {sorted(VALID_DESKS)}")
    query = ("SELECT trade_id, trade_date, desk, instrument_type, underlying, direction, "
             "quantity, trade_price, counterparty FROM dim_trade")
    params = {}
    if desk:
        query += " WHERE desk = :desk"
        params["desk"] = desk.upper()
    query += " ORDER BY trade_id"
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


@app.get("/pnl")
def pnl_by_desk(date: Optional[Date] = None):
    with engine.connect() as conn:
        date = date or latest_date(conn, "fct_daily_pnl_by_desk")
        rows = conn.execute(text(f"""
            SELECT desk, pnl_usd AS pnl, dv01_usd AS dv01, trade_count
            FROM {MARTS}.fct_daily_pnl_by_desk
            WHERE valuation_date = :date
            ORDER BY desk
        """), {"date": date}).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No valuations on {date}")
    desks = [dict(row) for row in rows]
    return {"date": date, "desks": desks,
            "total_pnl": round(sum(float(d["pnl"]) for d in desks), 2)}


@app.get("/risk")
def rates_risk(date: Optional[Date] = None):
    with engine.connect() as conn:
        date = date or latest_date(conn, "fct_daily_rates_risk")
        rows = conn.execute(text(f"""
            SELECT security, position_count, dv01_usd, pnl_if_rates_up_10bp_usd
            FROM {MARTS}.fct_daily_rates_risk
            WHERE valuation_date = :date
            ORDER BY security
        """), {"date": date}).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No risk figures on {date}")
    bonds = [dict(row) for row in rows]
    return {
        "date": date,
        "bonds": bonds,
        "total_dv01_usd": round(sum(float(b["dv01_usd"]) for b in bonds), 2),
        "pnl_if_rates_up_10bp_usd": round(sum(float(b["pnl_if_rates_up_10bp_usd"]) for b in bonds), 2),
    }


@app.get("/market-prices")
def market_prices(series: str, start: Optional[Date] = None, end: Optional[Date] = None):
    with engine.connect() as conn:
        known = set(conn.execute(text(f"SELECT DISTINCT series FROM {MARTS}.fct_market_prices")).scalars())
        if series not in known:
            raise HTTPException(status_code=400,
                                detail=f"Unknown series '{series}'. Use one of {sorted(known)}")
        rows = conn.execute(text(f"""
            SELECT price_date, value, daily_change, daily_change_bp, daily_return
            FROM {MARTS}.fct_market_prices
            WHERE series = :series
              AND (CAST(:start AS date) IS NULL OR price_date >= :start)
              AND (CAST(:end AS date) IS NULL OR price_date <= :end)
            ORDER BY price_date
        """), {"series": series, "start": start, "end": end}).mappings().all()
    return {"series": series, "prices": [dict(row) for row in rows]}


@app.get("/trades/{trade_id}/xml")
def trade_xml(trade_id: str = Path(pattern=r"^T\d{5}$")):
    with engine.connect() as conn:
        book = pd.read_sql(text("SELECT * FROM dim_trade WHERE trade_id = :id"), conn,
                           params={"id": trade_id}, parse_dates=["trade_date", "maturity_date"])
    if book.empty:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    root = etree.Element("trades")
    trade_to_xml(root, book.iloc[0])
    if not SCHEMA.validate(root):                       # never send an invalid message
        raise HTTPException(status_code=500, detail="Generated message failed XSD validation")
    return Response(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"),
                    media_type="application/xml")


@app.get("/bond-price")
def price_bond(coupon_rate: float = Query(..., ge=0, le=1),
               years: int = Query(..., ge=1, le=100),
               ytm: float = Query(..., gt=-1, le=1),
               face_value: float = Query(100, gt=0)):
    return {
        "price": round(bond_price(face_value, coupon_rate, years, ytm), 4),
        "dv01": round(dv01(face_value, coupon_rate, years, ytm), 6),
        "macaulay_duration": round(macaulay_duration(face_value, coupon_rate, years, ytm), 4),
    }
