"""Page tests: open every page of the app like a visitor would, without a browser.

Streamlit's AppTest runs each page. The page's API calls go to the real API, in-process
(the `client` fixture), and the API reads the dbt marts. So a test fails if any link
of the chain breaks: page → API → database.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app_data
import assistant
import desk_api
from desk_api import engine
from sqlalchemy import text

APP = Path(__file__).resolve().parent.parent / "app"
PAGES = ["Home.py", "pages/1_Market.py", "pages/2_Portfolio.py", "pages/3_Pricing.py",
         "pages/4_Trade_desk.py", "pages/5_Learn.py", "pages/6_Assistant.py", "pages/7_Privacy_and_terms.py"]


@pytest.fixture
def api_in_process(client, monkeypatch):
    """Send the app's API calls to the in-process API instead of the internet."""
    def call(path, params=None, as_text=False):
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.text if as_text else response.json()

    monkeypatch.setattr(app_data, "api", call)
    monkeypatch.setattr(app_data, "_fetch", call)

    def send(method, path, body=None, as_text=False, user=None):
        headers = {"X-User-Email": user, "X-App-Key": "page-test-key"} if user else None
        response = client.request(method, path, json=body, headers=headers)
        if response.status_code >= 400:
            return False, str(response.json().get("detail"))
        if as_text:
            return True, response.text
        return True, response.json() if response.content else None

    monkeypatch.setattr(app_data, "send", send)
    monkeypatch.setattr(desk_api, "APP_KEY", "page-test-key")
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
    assert any("Loaded live from the database" in caption.value for caption in at.caption)
    assert "saved_at" in at.dataframe[0].value.columns

    next(b for b in at.button if b.label == "Delete").click().run()
    assert any("Deleted T9" in message.value for message in at.success)
    assert any("No trades yet" in info.value for info in at.info)


def test_a_guest_sees_the_sign_in_button(api_in_process, monkeypatch):
    monkeypatch.setattr(app_data, "sign_in_ready", lambda: True)
    at = AppTest.from_file(str(APP / "pages/4_Trade_desk.py"), default_timeout=30).run()
    assert not at.exception, at.exception[0].value
    assert any(b.label == "Sign in with Google" for b in at.button)


def test_a_signed_in_user_books_under_their_email(api_in_process, monkeypatch):
    """Signed in with Google: the trade is saved under the user's email, and guests don't see it."""
    monkeypatch.setattr(app_data, "sign_in_ready", lambda: True)
    monkeypatch.setattr(app_data, "signed_in_email", lambda: "page-test@example.com")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM desk_trades WHERE owner = 'page-test@example.com'"))
    at = AppTest.from_file(str(APP / "pages/4_Trade_desk.py"), default_timeout=30).run()
    assert any("page-test@example.com" in m.value for m in at.markdown)
    assert any(b.label == "Log out" for b in at.button)

    next(b for b in at.button if b.label == "Book trade").click().run()
    trade_id = next(m.value for m in at.success if "Booked T9" in m.value).split()[1].rstrip(":")
    with engine.begin() as conn:
        owner = conn.execute(text("SELECT owner FROM desk_trades WHERE trade_id = :id"), {"id": trade_id}).scalar()
        conn.execute(text("DELETE FROM desk_trades WHERE owner = 'page-test@example.com'"))
    assert owner == "page-test@example.com"


def test_a_quiz_answer_gets_feedback():
    at = AppTest.from_file(str(APP / "pages/5_Learn.py"), default_timeout=30).run()
    at.radio[0].set_value("B").run()                     # Equities, question 1: the right answer
    assert any(message.value.startswith("Correct") for message in at.success)
    at.radio[1].set_value("A").run()                     # question 2: a wrong answer
    assert any(message.value.startswith("Not quite") for message in at.error)


def test_the_assistant_page_chats(monkeypatch, fake_model):
    """Ask on the page: the question and the answer appear, and dollar amounts stay as text."""
    original = assistant.build_agent
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    monkeypatch.setattr(assistant, "build_agent",
                        lambda api_key=None: original(model=fake_model("The FX desk lost $4.45 million.")))
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30).run()
    at.chat_input[0].set_value("Which desk lost the most?").run()
    assert not at.exception, at.exception[0].value
    assert any("don't type personal information" in caption.value for caption in at.caption)
    shown = [message.markdown[0].value for message in at.chat_message]
    assert shown == ["Which desk lost the most?", "The FX desk lost \\$4.45 million."]


@pytest.mark.parametrize("problem, message", [
    ("429 RESOURCE_EXHAUSTED: quota exceeded", "Too many questions right now"),
    ("503 UNAVAILABLE: This model is currently experiencing high demand", "busy right now"),
], ids=["free limit", "high demand"])
def test_the_assistant_page_explains_google_errors(monkeypatch, problem, message):
    """When Google can't answer, the visitor gets a clear message and can ask again later."""
    def failing(agent, conversation):
        raise RuntimeError(problem)
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    monkeypatch.setattr(assistant, "reply", failing)
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30).run()
    at.chat_input[0].set_value("What is a bond?").run()
    assert any(message in error.value for error in at.error)
    assert at.session_state["chat"] == []          # the question was dropped, so it can be asked again


def test_an_interrupted_question_is_dropped(monkeypatch, fake_model):
    """A question left unanswered (the visitor asked again while it was thinking) is removed."""
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30)
    at.session_state["chat"] = [{"role": "user", "content": "hello"}]
    at.session_state["agent"] = assistant.build_agent(model=fake_model("Yes, I'm good."))
    at.run()
    at.chat_input[0].set_value("Are you good?").run()
    assert [message["content"] for message in at.session_state["chat"]] == ["Are you good?", "Yes, I'm good."]
