"""The assistant's data access: the AI may write any SQL, and the database only lets it read the marts."""
import time

import psycopg2
import pytest
from sqlalchemy import text

import assistant_api
import desk_api
from desk_api import engine

KEY = "assistant-test-key"
PNL_BY_DESK = """
    SELECT desk, pnl_usd FROM analytics_marts.fct_daily_pnl_by_desk
    WHERE valuation_date = (SELECT MAX(valuation_date) FROM analytics_marts.fct_daily_pnl_by_desk)
    ORDER BY desk
"""


@pytest.fixture
def ask(client, reader_url, monkeypatch):
    """Send SQL to the API the way the app does: with the app's key."""
    monkeypatch.setattr(assistant_api, "READER_URL", reader_url)
    monkeypatch.setattr(desk_api, "APP_KEY", KEY)
    return lambda sql: client.post("/assistant/query", json={"sql": sql}, headers={"X-App-Key": KEY})


def test_only_the_app_can_use_the_assistant_endpoints(client, monkeypatch):
    monkeypatch.setattr(desk_api, "APP_KEY", KEY)
    for headers in (None, {"X-App-Key": "wrong-key"}):
        assert client.get("/assistant/tables", headers=headers).status_code == 401
        assert client.post("/assistant/query", json={"sql": "SELECT 1"}, headers=headers).status_code == 401


def test_the_assistant_sees_only_the_marts(ask, client):
    response = client.get("/assistant/tables", headers={"X-App-Key": KEY})
    tables = {table["table"]: table for table in response.json()}
    assert "analytics_marts.fct_positions" in tables
    assert all(name.startswith("analytics_marts.") for name in tables)      # no desk_trades, so no emails
    pnl = tables["analytics_marts.fct_daily_pnl_by_desk"]
    assert pnl["description"].startswith("Daily P&L")                       # the dbt docs, saved in the database
    assert "pnl_usd (numeric)" in pnl["columns"]


def test_a_query_returns_the_rows(ask):
    response = ask(PNL_BY_DESK)
    assert response.status_code == 200
    body = response.json()
    assert body["columns"] == ["desk", "pnl_usd"]
    assert [row[0] for row in body["rows"]] == ["EQUITY", "FX", "RATES"]
    assert body["truncated"] is False


def test_the_sql_runs_exactly_as_written(ask):
    """Percent signs, colons and casts reach the database unchanged, and a final semicolon is fine."""
    body = ask("SELECT desk FROM analytics_marts.fct_positions "
               "WHERE desk LIKE 'F%' AND '10:30'::text = '10:30' LIMIT 1;").json()
    assert body["rows"] == [["FX"]]


def test_at_most_50_rows_come_back(ask):
    body = ask("SELECT n FROM generate_series(1, 120) AS n").json()
    assert len(body["rows"]) == 50 and body["truncated"] is True


@pytest.mark.parametrize("sql", [
    "DELETE FROM analytics_marts.fct_positions",
    "UPDATE analytics_marts.fct_positions SET pnl_usd = 0",
    "DROP TABLE analytics_marts.fct_positions",
    "WITH gone AS (DELETE FROM analytics_marts.fct_positions RETURNING *) SELECT COUNT(*) FROM gone",
    "SELECT 1; DROP TABLE analytics_marts.fct_positions",
], ids=["delete", "update", "drop", "delete hidden in a select", "two statements"])
def test_the_assistant_cannot_change_anything(ask, sql):
    with engine.connect() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM analytics_marts.fct_positions")).scalar()
    assert ask(sql).status_code == 400
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM analytics_marts.fct_positions")).scalar() == before


def test_visitors_trades_and_emails_are_out_of_reach(ask):
    response = ask("SELECT owner FROM desk_trades")
    assert response.status_code == 400
    assert "permission denied for table desk_trades" in response.json()["detail"]


def test_a_slow_query_is_stopped(ask, monkeypatch):
    monkeypatch.setattr(assistant_api, "TIMEOUT", "1s")
    started = time.monotonic()
    response = ask("SELECT pg_sleep(5)")
    assert response.status_code == 400
    assert "statement timeout" in response.json()["detail"]
    assert time.monotonic() - started < 4


def test_errors_help_the_ai_fix_its_query(ask):
    response = ask("SELECT pnl FROM analytics_marts.fct_positions")
    assert response.status_code == 400
    assert 'column "pnl" does not exist' in response.json()["detail"]


def test_the_database_itself_refuses_to_change_data(reader_url):
    """Outside the API, in a read-write transaction: the user's rights alone still say no."""
    conn = psycopg2.connect(reader_url.replace("postgresql+psycopg2://", "postgresql://", 1))
    conn.set_session(readonly=False)                    # switch off the read-only safety net
    try:
        for sql, refusal in [("DELETE FROM analytics_marts.fct_positions", "permission denied"),
                             ("DROP TABLE analytics_marts.fct_positions", "must be owner")]:
            with pytest.raises(psycopg2.Error, match=refusal):
                with conn.cursor() as cur:
                    cur.execute(sql)
            conn.rollback()
    finally:
        conn.close()


def test_without_its_database_user_the_assistant_says_so(client, monkeypatch):
    monkeypatch.setattr(assistant_api, "READER_URL", "")
    monkeypatch.setattr(desk_api, "APP_KEY", KEY)
    response = client.post("/assistant/query", json={"sql": "SELECT 1"}, headers={"X-App-Key": KEY})
    assert response.status_code == 503
