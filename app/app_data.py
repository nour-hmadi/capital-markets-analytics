"""Data access for every page: the app asks the API; it never reads files or the database.

Free hosting sleeps when idle, so the first request after a quiet period can take up to a minute.
"""
import os
import sys
import threading
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))      # the pricing tools still use pricing.py directly

API_URL = os.environ.get("API_URL", "https://capital-markets-api.onrender.com")
TIMEOUT_SECONDS = 90                        # long enough for a cold start

# Pivoting sorts series alphabetically: that would scramble the yield curve (10Y before 1Y)
# and make the EURGBP cross rate the default FX pair. Known series keep this order.
SERIES_ORDER = {
    "EQUITY": ["INDEX_US", "INDEX_TECH", "INDEX_EU"],
    "RATES": ["1Y", "2Y", "5Y", "10Y", "30Y"],
    "FX": ["EURUSD", "GBPUSD", "USDJPY", "EURGBP"],
}


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch(path, params=None, as_text=False):
    response = requests.get(f"{API_URL}{path}", params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text if as_text else response.json()


def api(path, params=None, as_text=False):
    """Call the API with a friendly message, and stop the page cleanly if it fails."""
    with st.spinner("Loading from the API… (the free backend can take up to a minute to wake up)"):
        try:
            return _fetch(path, params, as_text)
        except requests.RequestException as error:
            st.error(f"The API is not reachable right now ({error.__class__.__name__}). "
                     "Please refresh in a minute.")
            st.stop()


def load_market(asset_class):
    """One column per series, one row per date, from GET /market-prices?asset_class=..."""
    prices = pd.DataFrame(api("/market-prices", {"asset_class": asset_class})["prices"])
    prices["price_date"] = pd.to_datetime(prices["price_date"])
    wide = prices.pivot(index="price_date", columns="series", values="value")
    wide.index.name, wide.columns.name = "date", None
    known = [s for s in SERIES_ORDER.get(asset_class, []) if s in wide.columns]
    others = [s for s in wide.columns if s not in known]      # new series go last, never lost
    return wide[known + others]


def load_pnl_history():
    history = pd.DataFrame(api("/pnl/history"))
    history["valuation_date"] = pd.to_datetime(history["valuation_date"])
    return history.pivot(index="valuation_date", columns="desk", values="pnl")


def load_positions():
    body = api("/positions")
    return body["date"], pd.DataFrame(body["positions"])


def load_risk():
    return api("/risk")


def load_trade_xml(trade_id):
    return api(f"/trades/{trade_id}/xml", as_text=True)


def wake_backend():
    """Ping the API in the background, so it is awake by the time the visitor opens a page."""
    def ping():
        try:
            requests.get(f"{API_URL}/health", timeout=TIMEOUT_SECONDS)
        except requests.RequestException:
            pass                        # the pages show their own message if the API is down
    threading.Thread(target=ping, daemon=True).start()


def load_last_run():
    """When the data was last refreshed, or None. It's extra information, so it never stops the page."""
    try:
        return _fetch("/pipeline/last-run")
    except Exception:
        return None


def send(method, path, body=None, as_text=False):
    """Create, change or delete through the API, or read data that changes often. Never cached.

    Returns (True, result) or (False, a message to show the user).
    """
    try:
        response = requests.request(method, f"{API_URL}{path}", json=body, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as error:
        return False, f"The API is not reachable right now ({error.__class__.__name__}). Please try again."
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, list):                          # errors from the API's request model
            detail = "; ".join(item.get("msg", "") for item in detail)
        return False, detail or f"The API answered {response.status_code}."
    if as_text:
        return True, response.text
    return True, response.json() if response.content else None
