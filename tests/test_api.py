"""API tests: status codes, filters, validation, and values reconciled with the dbt marts.

They need a loaded database with the dbt marts built: run src/load_db.py, then dbt build.
"""
import os

import pytest
from fastapi.testclient import TestClient
from lxml import etree
from sqlalchemy import create_engine, text

from api import app
from export_xml import load_schema
from load_db import DATABASE_URL


def marts_problem():
    """Return None if the dbt marts are ready, otherwise the reason they aren't."""
    try:
        with create_engine(DATABASE_URL).connect() as conn:
            ready = conn.execute(text("SELECT to_regclass('analytics_marts.fct_market_prices')")).scalar()
    except Exception:
        return "PostgreSQL is not available"
    return None if ready else "dbt marts are missing: run load_db.py, then dbt build"


@pytest.fixture(scope="module")
def client():
    problem = marts_problem()
    if problem:
        if os.environ.get("CI"):
            pytest.fail(problem)
        pytest.skip(problem)
    return TestClient(app)


# ---------- Health and trades ----------

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_all_trades(client):
    assert len(client.get("/trades").json()) == 60


def test_trades_filtered_by_desk(client):
    trades = client.get("/trades", params={"desk": "FX"}).json()
    assert len(trades) == 20
    assert all(t["desk"] == "FX" for t in trades)


def test_desk_filter_is_case_insensitive(client):
    assert len(client.get("/trades", params={"desk": "fx"}).json()) == 20


def test_unknown_desk_returns_400(client):
    assert client.get("/trades", params={"desk": "XYZ"}).status_code == 400


# ---------- P&L (from fct_daily_pnl_by_desk) ----------

def test_latest_pnl_reconciles_with_the_marts(client):
    body = client.get("/pnl").json()
    assert body["date"] == "2025-12-18"
    pnl = {d["desk"]: float(d["pnl"]) for d in body["desks"]}
    assert pnl["EQUITY"] == pytest.approx(-3_032_792, abs=1)
    assert pnl["FX"] == pytest.approx(-4_449_993, abs=1)
    assert pnl["RATES"] == pytest.approx(654_261, abs=1)
    assert body["total_pnl"] == pytest.approx(-6_828_524, abs=1)


def test_pnl_on_a_weekend_returns_404(client):
    assert client.get("/pnl", params={"date": "2025-06-07"}).status_code == 404   # a Saturday


def test_pnl_with_an_invalid_date_returns_422(client):
    assert client.get("/pnl", params={"date": "not-a-date"}).status_code == 422


# ---------- Risk (from fct_daily_rates_risk) ----------

def test_risk_totals_match_the_portfolio(client):
    body = client.get("/risk").json()
    assert len(body["bonds"]) == 5
    assert body["total_dv01_usd"] == pytest.approx(40_695.51, abs=1)
    assert body["pnl_if_rates_up_10bp_usd"] == pytest.approx(-10 * body["total_dv01_usd"], rel=1e-3)


def test_risk_on_a_weekend_returns_404(client):
    assert client.get("/risk", params={"date": "2025-06-07"}).status_code == 404


# ---------- Market prices (from fct_market_prices) ----------

def test_market_prices_full_history(client):
    prices = client.get("/market-prices", params={"series": "EURUSD"}).json()["prices"]
    assert len(prices) == 252
    assert prices[0]["daily_return"] is None          # first day: no previous price
    assert prices[1]["daily_return"] is not None


def test_market_prices_date_filter(client):
    params = {"series": "EURUSD", "start": "2025-01-01", "end": "2025-01-06"}
    dates = [p["price_date"] for p in client.get("/market-prices", params=params).json()["prices"]]
    assert dates == ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"]   # weekend skipped


def test_unknown_series_returns_400(client):
    assert client.get("/market-prices", params={"series": "XYZ"}).status_code == 400


# ---------- XML trade messages ----------

def test_trade_xml_is_valid_against_the_xsd(client):
    response = client.get("/trades/T00001/xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    message = etree.fromstring(response.content)
    assert load_schema().validate(message)
    assert message.findtext("trade/tradeId") == "T00001"


def test_unknown_trade_returns_404(client):
    assert client.get("/trades/T99999/xml").status_code == 404


def test_malformed_trade_id_returns_422(client):
    assert client.get("/trades/BAD/xml").status_code == 422


# ---------- Bond pricer ----------

def test_par_bond_prices_at_100(client):
    body = client.get("/bond-price", params={"coupon_rate": 0.05, "years": 5, "ytm": 0.05}).json()
    assert body["price"] == pytest.approx(100)


def test_bond_price_matches_the_pricing_module(client):
    body = client.get("/bond-price", params={"coupon_rate": 0.05, "years": 5, "ytm": 0.06}).json()
    assert body["price"] == pytest.approx(95.7876, abs=1e-4)


def test_zero_years_returns_422(client):
    params = {"coupon_rate": 0.05, "years": 0, "ytm": 0.05}
    assert client.get("/bond-price", params=params).status_code == 422


def test_missing_parameters_return_422(client):
    assert client.get("/bond-price").status_code == 422
