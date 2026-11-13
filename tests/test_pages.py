"""Page tests: open every page of the app like a visitor would, without a browser.

Streamlit's AppTest runs each page. The page's API calls go to the real API, in-process
(the `client` fixture), and the API reads the dbt marts. So a test fails if any link
of the chain breaks: page → API → database.
"""
from pathlib import Path

import pytest
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.testing.v1 import AppTest

import app_data
import assistant
import assistant_api
import desk_api
import notes
from desk_api import engine
from sqlalchemy import text

APP = Path(__file__).resolve().parent.parent / "app"
PNL_SQL = ("SELECT desk, pnl_usd FROM analytics_marts.fct_daily_pnl_by_desk WHERE valuation_date = "
           "(SELECT MAX(valuation_date) FROM analytics_marts.fct_daily_pnl_by_desk) ORDER BY pnl_usd")
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
        headers = {"X-App-Key": "page-test-key", **({"X-User-Email": user} if user else {})}
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
    monkeypatch.setattr(assistant, "build_agent", lambda api_key=None, database=None, desk=None:
                        original(model=fake_model("The FX desk lost $4.45 million.")))
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


def test_the_assistant_page_shows_the_sql_behind_an_answer(api_in_process, reader_url, monkeypatch,
                                                            fake_model, tool_call):
    """The whole chain: page -> agent -> tool -> API -> read-only database user -> rows -> answer."""
    monkeypatch.setattr(assistant_api, "READER_URL", reader_url)
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    model = fake_model(tool_call("run_sql", query=PNL_SQL), "The FX desk lost the most.")
    original = assistant.build_agent
    monkeypatch.setattr(assistant, "build_agent", lambda api_key=None, database=None, desk=None:
                        original(model=model, database=database))
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30).run()
    at.chat_input[0].set_value("Which desk lost the most money?").run()
    assert not at.exception, at.exception[0].value
    assert at.expander[0].label == "The SQL behind this answer"
    assert at.code[0].value == PNL_SQL
    rows = model.received[-1][-1].content                 # what the database sent back to the model
    assert rows.index("FX") < rows.index("EQUITY") < rows.index("RATES")     # biggest loss first


def test_the_assistant_page_shows_the_lessons_behind_an_answer(monkeypatch, fake_model, tool_call, fake_embed):
    """For a concept: page -> agent -> search_notes -> the closest Learn paragraphs -> answer, with its lessons."""
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    model = fake_model(tool_call("search_notes", question="What is DV01?"), "DV01 is the rate risk of a bond.")
    learn_notes = notes.Notes(notes.load_chunks(), fake_embed)
    original = assistant.build_agent
    monkeypatch.setattr(assistant, "build_agent", lambda api_key=None, database=None, desk=None:
                        original(model=model, database=database, notes=learn_notes))
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30).run()
    at.chat_input[0].set_value("What is DV01?").run()
    assert not at.exception, at.exception[0].value
    assert at.expander[0].label == "From the Learn notes"
    assert "Rate risk (DV01)" in at.expander[0].markdown[0].value


def guest_trades():
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM desk_trades WHERE owner = 'guest'")).scalar()


@pytest.mark.parametrize("click, booked, status", [("book", 1, "Booked T9"), ("cancel", 0, "Cancelled")])
def test_a_drafted_trade_is_booked_only_by_the_visitors_click(api_in_process, monkeypatch, fake_model,
                                                              tool_call, click, booked, status):
    """Human in the loop: the AI drafts, nothing is saved until the visitor clicks Book, and Cancel saves nothing."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM desk_trades WHERE owner = 'guest'"))
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    draft = {"instrument_type": "EQUITY_INDEX", "underlying": "INDEX_US", "direction": "BUY", "quantity": 100,
             "counterparty": "Alpha Bank"}
    model = fake_model(tool_call("draft_trade", **draft), "Here is the trade: book it with the button.")
    original = assistant.build_agent
    monkeypatch.setattr(assistant, "build_agent", lambda api_key=None, database=None, desk=None:
                        original(model=model, database=database, desk=desk))
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30).run()
    at.chat_input[0].set_value("Buy 100 INDEX_US with Alpha Bank").run()
    assert any("Trade to confirm" in info.value for info in at.info)
    assert guest_trades() == 0                                     # drafted, not booked
    at.button(key=f"{click}-1").click().run()
    assert not at.exception, at.exception[0].value
    assert guest_trades() == booked
    assert any(message.value.startswith(status) for message in at.markdown)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM desk_trades WHERE owner = 'guest'"))


def test_the_trade_tools_act_for_the_signed_in_visitor(monkeypatch, fake_model, tool_call):
    """The agent runs its tools in another thread, where st.user is empty: the page must pass the email itself."""
    def signed_in_email():                                    # like st.user: known only in Streamlit's thread
        return "nour@example.com" if get_script_run_ctx() is not None else None

    calls = []

    def send(method, path, body=None, as_text=False, user=None):
        calls.append((method, path, user))
        return True, []

    monkeypatch.setattr(app_data, "signed_in_email", signed_in_email)
    monkeypatch.setattr(app_data, "send", send)
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    model = fake_model(tool_call("my_trades"), "Here are your trades.")
    original = assistant.build_agent
    monkeypatch.setattr(assistant, "build_agent", lambda api_key=None, database=None, desk=None:
                        original(model=model, desk=desk))
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30).run()
    at.chat_input[0].set_value("What did I book?").run()
    assert not at.exception, at.exception[0].value
    assert calls == [("GET", "/desk/trades", "nour@example.com")]


def test_a_guest_is_told_to_sign_in(monkeypatch, fake_model, tool_call):
    """A guest's trades come with a note, so the AI can suggest signing in with Google to keep their own."""
    monkeypatch.setattr(app_data, "signed_in_email", lambda: None)
    monkeypatch.setattr(app_data, "send", lambda method, path, body=None, as_text=False, user=None: (True, []))
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    model = fake_model(tool_call("my_trades"), "You aren't signed in: sign in with Google to keep your trades.")
    original = assistant.build_agent
    monkeypatch.setattr(assistant, "build_agent", lambda api_key=None, database=None, desk=None:
                        original(model=model, desk=desk))
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30).run()
    at.chat_input[0].set_value("What did I book?").run()
    assert not at.exception, at.exception[0].value
    assert "sign in with Google" in model.received[-1][-1].content     # what my_trades told the model


def test_the_ai_never_sees_the_visitors_email(api_in_process, monkeypatch, fake_model, tool_call):
    """Privacy: a signed-in visitor's trades go to Gemini, but their email never does."""
    email = "privacy-test@example.com"
    ok, trade = app_data.send("POST", "/desk/trades", {
        "instrument_type": "EQUITY_INDEX", "underlying": "INDEX_US", "direction": "BUY", "quantity": 100,
        "trade_date": "2025-03-03", "counterparty": "Alpha Bank"}, user=email)
    monkeypatch.setattr(app_data, "signed_in_email", lambda: email)
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    model = fake_model(tool_call("my_trades"), "You have one trade.")
    original = assistant.build_agent
    monkeypatch.setattr(assistant, "build_agent", lambda api_key=None, database=None, desk=None:
                        original(model=model, desk=desk))
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30).run()
    at.chat_input[0].set_value("What did I book?").run()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM desk_trades WHERE owner = :owner"), {"owner": email})
    assert ok and trade["trade_id"] in model.received[-1][-1].content     # the trade reached the model...
    assert email not in str(model.received)                               # ...but the email never did


def test_a_visitor_rates_an_answer(api_in_process, monkeypatch, fake_model):
    """Thumbs up under an answer saves the question, the answer and the rating: no name or email."""
    monkeypatch.setattr(app_data, "secret", lambda name: "test-key" if name == "GOOGLE_API_KEY" else None)
    original = assistant.build_agent
    monkeypatch.setattr(assistant, "build_agent", lambda api_key=None, database=None, desk=None:
                        original(model=fake_model("The FX desk lost the most.")))
    at = AppTest.from_file(str(APP / "pages/6_Assistant.py"), default_timeout=30).run()
    at.chat_input[0].set_value("Which desk lost the most money?").run()
    at.feedback[0].set_value(1).run()                                  # thumbs up
    assert not at.exception, at.exception[0].value
    assert any("rating was saved" in caption.value for caption in at.caption)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT helpful, question, answer FROM assistant_feedback "
                                "ORDER BY feedback_id DESC LIMIT 1")).one()
        conn.execute(text("DELETE FROM assistant_feedback WHERE question = 'Which desk lost the most money?'"))
    assert tuple(row) == (True, "Which desk lost the most money?", "The FX desk lost the most.")
