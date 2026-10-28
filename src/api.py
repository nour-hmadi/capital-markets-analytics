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

from desk_api import router as desk_router
from export_xml import load_schema, trade_to_xml
from load_db import DATABASE_URL
from pricing import bond_price, dv01, macaulay_duration

app = FastAPI(title="Capital Markets Analytics API", version="2.2")
app.include_router(desk_router)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)   # reconnects if the cloud DB went idle
MARTS = "analytics_marts"
VALID_DESKS = {"EQUITY", "RATES", "FX"}
VALID_ASSET_CLASSES = {"EQUITY", "RATES", "FX"}
SCHEMA = load_schema()


def latest_date(conn, table):
    return conn.execute(text(f"SELECT MAX(valuation_date) FROM {MARTS}.{table}")).scalar()


def check_desk(desk):
    """None stays None; a known desk is returned in capitals; anything else is a 400."""
    if desk is None:
        return None
    if desk.upper() not in VALID_DESKS:
        raise HTTPException(status_code=400,
                            detail=f"Unknown desk '{desk}'. Use one of {sorted(VALID_DESKS)}")
    return desk.upper()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/trades")
def list_trades(desk: Optional[str] = None):
    desk = check_desk(desk)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT trade_id, trade_date, desk, instrument_type, underlying, direction,
                   quantity, trade_price, counterparty
            FROM dim_trade
            WHERE CAST(:desk AS text) IS NULL OR desk = :desk
            ORDER BY trade_id
        """), {"desk": desk}).mappings().all()
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


@app.get("/pnl/history")
def pnl_history(desk: Optional[str] = None):
    desk = check_desk(desk)
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT valuation_date, desk, pnl_usd AS pnl
            FROM {MARTS}.fct_daily_pnl_by_desk
            WHERE CAST(:desk AS text) IS NULL OR desk = :desk
            ORDER BY valuation_date, desk
        """), {"desk": desk}).mappings().all()
    return [dict(row) for row in rows]


@app.get("/positions")
def positions(date: Optional[Date] = None, desk: Optional[str] = None):
    desk = check_desk(desk)
    with engine.connect() as conn:
        date = date or latest_date(conn, "fct_positions")
        rows = conn.execute(text(f"""
            SELECT trade_id, desk, instrument_type, underlying, direction, counterparty,
                   market_value_usd, pnl_usd, dv01_usd, trade_status
            FROM {MARTS}.fct_positions
            WHERE valuation_date = :date
              AND (CAST(:desk AS text) IS NULL OR desk = :desk)
            ORDER BY pnl_usd
        """), {"date": date, "desk": desk}).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No positions on {date}")
    return {"date": date, "positions": [dict(row) for row in rows]}


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
def market_prices(series: Optional[str] = None, asset_class: Optional[str] = None,
                  start: Optional[Date] = None, end: Optional[Date] = None):
    if series is None and asset_class is None:
        raise HTTPException(status_code=400,
                            detail="Give a series (e.g. EURUSD) or an asset_class (EQUITY, RATES, FX)")
    if asset_class is not None:
        asset_class = asset_class.upper()
        if asset_class not in VALID_ASSET_CLASSES:
            raise HTTPException(status_code=400,
                                detail=f"Unknown asset class. Use one of {sorted(VALID_ASSET_CLASSES)}")
    with engine.connect() as conn:
        if series is not None:
            known = set(conn.execute(text(f"SELECT DISTINCT series FROM {MARTS}.fct_market_prices")).scalars())
            if series not in known:
                raise HTTPException(status_code=400,
                                    detail=f"Unknown series '{series}'. Use one of {sorted(known)}")
        rows = conn.execute(text(f"""
            SELECT price_date, asset_class, series, value, daily_change, daily_change_bp, daily_return
            FROM {MARTS}.fct_market_prices
            WHERE (CAST(:series AS text) IS NULL OR series = :series)
              AND (CAST(:asset_class AS text) IS NULL OR asset_class = :asset_class)
              AND (CAST(:start AS date) IS NULL OR price_date >= :start)
              AND (CAST(:end AS date) IS NULL OR price_date <= :end)
            ORDER BY series, price_date
        """), {"series": series, "asset_class": asset_class, "start": start, "end": end}).mappings().all()
    return {"series": series, "asset_class": asset_class, "prices": [dict(row) for row in rows]}


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


@app.get("/pipeline/last-run")
def last_pipeline_run():
    """When the data was last loaded, and by whom: a person, or the scheduled GitHub Actions job."""
    with engine.connect() as conn:
        if conn.execute(text("SELECT to_regclass('public.pipeline_runs')")).scalar() is None:
            raise HTTPException(status_code=404, detail="No pipeline runs recorded yet")
        run = conn.execute(text("""
            SELECT loaded_at, triggered_by, valuations_loaded
            FROM pipeline_runs
            ORDER BY run_id DESC
            LIMIT 1
        """)).mappings().first()
    if run is None:
        raise HTTPException(status_code=404, detail="No pipeline runs recorded yet")
    return dict(run)


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
