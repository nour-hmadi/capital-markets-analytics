"""Page tests: open every page of the app like a visitor would, without a browser.

Streamlit's AppTest runs each page. The page's API calls go to the real API, in-process
(the `client` fixture), and the API reads the dbt marts. So a test fails if any link
of the chain breaks: page → API → database.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app_data
from desk_api import engine
from sqlalchemy import text

APP = Path(__file__).resolve().parent.parent / "app"
PAGES = ["Home.py", "pages/1_Market.py", "pages/2_Portfolio.py", "pages/3_Pricing.py",
         "pages/4_Trade_desk.py"]


@pytest.fixture
def api_in_process(client, monkeypatch):
    """Send the app's API calls to the in-process API instead of the internet."""
    def call(path, params=None, as_text=False):
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.text if as_text else response.json()

    monkeypatch.setattr(app_data, "api", call)
    monkeypatch.setattr(app_data, "_fetch", call)

    def send(method, path, body=None, as_text=False):
        response = client.request(method, path, json=body)
        if response.status_code >= 400:
            return False, str(response.json().get("detail"))
        if as_text:
            return True, response.text
        return True, response.json() if response.content else None

    monkeypatch.setattr(app_data, "send", send)
    monkeypatch.setattr(app_data, "wake_backend", lambda: None)   # tests never call the internet


@pytest.mark.parametrize("page", PAGES)
def test_page_opens_without_errors(api_in_process, page):
    at = AppTest.from_file(str(APP / page), default_timeout=30).run()
    assert not at.exception, at.exception[0].value
    assert not at.error, at.error[0].value


def test_book_change_and_delete_a_trade_from_the_page(api_in_process):
    """The whole chain from the page: form -> API -> database -> back to the table."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM desk_trades WHERE owner = 'guest'"))
    at = AppTest.from_file(str(APP / "pages/4_Trade_desk.py"), default_timeout=30).run()
    assert any("No trades yet" in info.value for info in at.info)

    next(b for b in at.button if b.label == "Book trade").click().run()
    assert any("Booked T9" in message.value for message in at.success)
    assert len(at.dataframe) == 1

    next(b for b in at.button if b.label == "Delete").click().run()
    assert any("Deleted T9" in message.value for message in at.success)
    assert any("No trades yet" in info.value for info in at.info)
