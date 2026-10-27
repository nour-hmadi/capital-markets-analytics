"""API tests: status codes, filters, validation, and values reconciled with the dbt marts.

They need a loaded database with the dbt marts built: run src/load_db.py, then dbt build.
The `client` fixture is in conftest.py, shared with the page tests.
"""
import pytest
from lxml import etree

from export_xml import load_schema


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
# ---------- P&L history ----------

def test_pnl_history_reconciles_on_the_last_date(client):
    history = client.get("/pnl/history").json()
    last_date = max(row["valuation_date"] for row in history)
    last_total = sum(float(row["pnl"]) for row in history if row["valuation_date"] == last_date)
    assert last_date == "2025-12-18"
    assert last_total == pytest.approx(-6_828_524, abs=1)


def test_pnl_history_desk_filter(client):
    history = client.get("/pnl/history", params={"desk": "rates"}).json()
    assert history and all(row["desk"] == "RATES" for row in history)


def test_pnl_history_unknown_desk_returns_400(client):
    assert client.get("/pnl/history", params={"desk": "XYZ"}).status_code == 400


# ---------- Positions (from fct_positions) ----------

def test_latest_positions_reconcile_with_desk_pnl(client):
    positions = client.get("/positions").json()["positions"]
    assert len(positions) == 60
    assert sum(float(p["pnl_usd"]) for p in positions) == pytest.approx(-6_828_524, abs=1)


def test_positions_are_sorted_worst_first(client):
    worst = client.get("/positions").json()["positions"][0]
    assert worst["trade_id"] == "T00001"
    assert float(worst["pnl_usd"]) == pytest.approx(-2_483_054, abs=1)


def test_positions_desk_filter(client):
    positions = client.get("/positions", params={"desk": "FX"}).json()["positions"]
    assert len(positions) == 20
    assert all(p["desk"] == "FX" for p in positions)


def test_positions_on_a_weekend_returns_404(client):
    assert client.get("/positions", params={"date": "2025-06-07"}).status_code == 404


# ---------- Market prices by asset class ----------

def test_market_prices_by_asset_class(client):
    prices = client.get("/market-prices", params={"asset_class": "EQUITY"}).json()["prices"]
    assert len(prices) == 3 * 252
    assert {p["series"] for p in prices} == {"INDEX_US", "INDEX_TECH", "INDEX_EU"}


def test_market_prices_needs_a_filter(client):
    assert client.get("/market-prices").status_code == 400


def test_unknown_asset_class_returns_400(client):
    assert client.get("/market-prices", params={"asset_class": "CRYPTO"}).status_code == 400
