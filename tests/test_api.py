"""API tests: status codes, filters, validation, and values reconciled with T3."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from api import app
from load_db import DATABASE_URL, load_all


@pytest.fixture(scope="module")
def client():
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect():
            pass
    except Exception:
        if os.environ.get("CI"):
            pytest.fail("PostgreSQL is required in CI")
        pytest.skip("PostgreSQL is not available")
    load_all(engine)
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


# ---------- P&L ----------

def test_latest_pnl_matches_the_reconciled_numbers(client):
    body = client.get("/pnl").json()
    assert body["date"] == "2025-12-18"
    pnl = {d["desk"]: d["pnl"] for d in body["desks"]}
    assert pnl["EQUITY"] == pytest.approx(-3_032_792, abs=1)
    assert pnl["FX"] == pytest.approx(-4_449_993, abs=1)
    assert pnl["RATES"] == pytest.approx(654_261, abs=1)
    assert body["total_pnl"] == pytest.approx(-6_828_524, abs=1)


def test_pnl_on_a_weekend_returns_404(client):
    assert client.get("/pnl", params={"date": "2025-06-07"}).status_code == 404   # a Saturday


def test_pnl_with_an_invalid_date_returns_422(client):
    assert client.get("/pnl", params={"date": "not-a-date"}).status_code == 422


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
