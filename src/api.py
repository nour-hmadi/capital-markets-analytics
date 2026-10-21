"""REST API for the capital markets project.

Run locally:  uvicorn api:app --app-dir src --reload
Interactive docs: http://127.0.0.1:8000/docs
"""
from datetime import date as Date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine, text

from load_db import DATABASE_URL
from pricing import bond_price, dv01, macaulay_duration

app = FastAPI(title="Capital Markets Analytics API", version="1.0")
engine = create_engine(DATABASE_URL)
VALID_DESKS = {"EQUITY", "RATES", "FX"}


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
        query += " WHERE desk = :desk"          # parameter, never pasted into the SQL text
        params["desk"] = desk.upper()
    query += " ORDER BY trade_id"
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


@app.get("/pnl")
def pnl_by_desk(date: Optional[Date] = None):
    with engine.connect() as conn:
        if date is None:
            date = conn.execute(text("SELECT MAX(date) FROM fact_valuations")).scalar()
        rows = conn.execute(text("""
            SELECT t.desk, ROUND(SUM(v.pnl), 2) AS pnl, ROUND(SUM(v.dv01), 2) AS dv01
            FROM fact_valuations v JOIN dim_trade t USING (trade_id)
            WHERE v.date = :date
            GROUP BY t.desk ORDER BY t.desk
        """), {"date": date}).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No valuations on {date}")
    desks = [dict(row) for row in rows]
    return {"date": date, "desks": desks,
            "total_pnl": round(sum(float(d["pnl"]) for d in desks), 2)}


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
