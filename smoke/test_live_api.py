"""Smoke tests for the live system: run after a cloud refresh, against the real API on Render.

They are kept out of normal test runs (pytest.ini only collects tests/). Run on purpose:
    python -m pytest smoke -v
"""
import os
from datetime import datetime, timedelta, timezone

import requests

API_URL = os.environ.get("API_URL", "https://capital-markets-api.onrender.com")


def get(path):
    response = requests.get(f"{API_URL}{path}", timeout=120)     # long enough for a cold start
    response.raise_for_status()
    return response.json()


def test_api_is_up():
    assert get("/health") == {"status": "ok"}


def test_data_was_just_refreshed():
    run = get("/pipeline/last-run")
    loaded_at = datetime.fromisoformat(run["loaded_at"])
    assert datetime.now(timezone.utc) - loaded_at < timedelta(hours=1)
    assert run["valuations_loaded"] == 7403


def test_trade_book_is_complete():
    assert len(get("/trades")) == 60


def test_positions_reconcile_with_desk_pnl():
    positions = get("/positions")["positions"]
    total = get("/pnl")["total_pnl"]
    assert abs(sum(p["pnl_usd"] for p in positions) - total) < 1


def test_trade_desk_is_online():
    assert isinstance(get("/desk/trades"), list)
