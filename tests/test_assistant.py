"""The AI assistant with fake models and fake tools: no internet, no API key, the same answers every time."""
from langchain_core.messages import SystemMessage, ToolMessage

from assistant import INSTRUCTIONS, build_agent, reply
from notes import Notes, load_chunks

SQL = "SELECT desk, SUM(pnl_usd) AS pnl_usd FROM analytics_marts.fct_daily_pnl_by_desk GROUP BY desk"
DRAFT = {"instrument_type": "EQUITY_INDEX", "underlying": "INDEX_US", "direction": "BUY", "quantity": 100,
         "counterparty": "Alpha Bank"}


def recorder(answer):
    """A fake API for the tools: it records every call and gives the same answer."""
    def call(method, path, body=None):
        call.calls.append((method, path, body))
        return answer
    call.calls = []
    return call


def test_the_assistant_answers(fake_model):
    agent = build_agent(model=fake_model("A bond is a loan to a government or a company."))
    answer = reply(agent, [{"role": "user", "content": "What is a bond?"}])
    assert answer["content"].startswith("A bond is a loan")
    assert answer["sql"] == [] and answer["lessons"] == [] and answer["draft"] is None     # no tools needed


def test_the_whole_conversation_is_sent_every_time(fake_model):
    """The model has no memory: the app sends the instructions, then the whole conversation, each time."""
    model = fake_model("It's the fixed interest the bond pays every year.")
    conversation = [
        {"role": "user", "content": "What is a bond?"},
        {"role": "assistant", "content": "A bond is a loan.", "sql": [], "lessons": [], "draft": None},
        {"role": "user", "content": "And its coupon?"},
    ]
    reply(build_agent(model=model), conversation)
    sent = model.received[0]
    assert isinstance(sent[0], SystemMessage) and sent[0].content == INSTRUCTIONS
    assert [message.content for message in sent[1:]] == [message["content"] for message in conversation]


def test_the_assistant_looks_up_numbers_in_the_database(fake_model, tool_call):
    """Look first, then query: the model lists the tables, runs SQL, then answers from the rows."""
    calls = []

    def database(method, path, body=None):
        calls.append((method, path, body))
        if path == "/assistant/tables":
            return [{"table": "analytics_marts.fct_daily_pnl_by_desk", "description": "Daily P&L per desk",
                     "columns": "valuation_date (date), desk (text), pnl_usd (numeric)"}]
        return {"columns": ["desk", "pnl_usd"], "rows": [["FX", -4449992.7]], "truncated": False}

    model = fake_model(tool_call("list_tables"), tool_call("run_sql", query=SQL),
                       "The FX desk lost $4.45 million.")
    answer = reply(build_agent(model=model, database=database),
                   [{"role": "user", "content": "Which desk lost the most?"}])
    assert calls == [("GET", "/assistant/tables", None), ("POST", "/assistant/query", {"sql": SQL})]
    assert answer["sql"] == [SQL]                          # the page shows it under the answer
    assert answer["content"] == "The FX desk lost $4.45 million."
    rows = model.received[-1][-1]                          # what the model read just before answering
    assert isinstance(rows, ToolMessage) and "-4449992.7" in rows.content


def test_a_busy_model_hands_over_to_the_backup(busy_model, fake_model):
    agent = build_agent(model=busy_model, backup=fake_model("A bond is a loan."))
    answer = reply(agent, [{"role": "user", "content": "What is a bond?"}])
    assert len(busy_model.received) == 1                   # the first model was asked, and failed
    assert answer["content"] == "A bond is a loan."


def test_the_assistant_explains_from_the_learn_notes(fake_model, tool_call, fake_embed):
    """For a concept, the model searches the notes and reads the closest paragraphs; the page gets the lessons."""
    model = fake_model(tool_call("search_notes", question="What is DV01?"),
                       "DV01 is how much a position loses when yields rise by 1 bp (Rate risk lesson).")
    answer = reply(build_agent(model=model, notes=Notes(load_chunks(), fake_embed)),
                   [{"role": "user", "content": "What is DV01?"}])
    assert answer["lessons"][0] == "Rate risk (DV01)" and answer["sql"] == []
    read = model.received[-1][-1]                          # what the model read just before answering
    assert isinstance(read, ToolMessage) and "[Rate risk (DV01)]" in read.content


def test_the_assistant_goes_on_when_the_notes_are_unavailable(fake_model, tool_call):
    def broken(texts):
        raise RuntimeError("503 UNAVAILABLE")

    model = fake_model(tool_call("search_notes", question="What is DV01?"), "From general knowledge: DV01 is…")
    answer = reply(build_agent(model=model, notes=Notes(load_chunks(), broken)),
                   [{"role": "user", "content": "What is DV01?"}])
    assert answer["content"].startswith("From general knowledge") and answer["lessons"] == []
    assert "can't be searched right now" in model.received[-1][-1].content


def test_the_assistant_drafts_a_trade_but_never_books_it(fake_model, tool_call):
    """Human in the loop: the AI only prepares the trade. Booking is the visitor's click, on the page."""
    desk = recorder([])
    model = fake_model(tool_call("draft_trade", **DRAFT), "Here is the trade: book it with the button.")
    answer = reply(build_agent(model=model, desk=desk),
                   [{"role": "user", "content": "Buy 100 INDEX_US with Alpha Bank"}])
    assert answer["draft"] == {**DRAFT, "trade_date": "2025-12-18", "tenor_months": None}  # the last day
    assert desk.calls == []                                # the AI called nothing that books
    assert "Nothing is booked yet" in model.received[-1][-1].content


def test_a_wrong_draft_goes_back_to_the_model(fake_model, tool_call):
    model = fake_model(tool_call("draft_trade", **{**DRAFT, "instrument_type": "BOND", "underlying": "GOV_7Y"}),
                       "There is no 7-year bond: choose 1, 2, 5, 10 or 30 years.")
    answer = reply(build_agent(model=model, desk=recorder([])),
                   [{"role": "user", "content": "Buy a 7-year bond"}])
    assert answer["draft"] is None
    assert "GOV_7Y is not a valid underlying for BOND" in model.received[-1][-1].content


def test_my_trades_asks_the_api_for_the_visitors_trades(fake_model, tool_call):
    desk = recorder([{"trade_id": "T90001", "underlying": "INDEX_US", "pnl": 120.0}])
    model = fake_model(tool_call("my_trades"), "You have one trade: T90001.")
    reply(build_agent(model=model, desk=desk), [{"role": "user", "content": "What did I book?"}])
    assert desk.calls == [("GET", "/desk/trades", None)]
    assert "T90001" in model.received[-1][-1].content


def test_the_model_knows_what_the_visitor_did_with_a_draft(fake_model):
    """The model only knows what the app sends it: the Book click's result must be part of the conversation."""
    model = fake_model("You booked T90004.")
    conversation = [
        {"role": "user", "content": "Buy 100 INDEX_US with Alpha Bank"},
        {"role": "assistant", "content": "Here is the trade: book it with the button.", "sql": [], "lessons": [],
         "draft": DRAFT, "status": "Booked T90004 at 4,665.11: see it on the Trade desk page."},
        {"role": "user", "content": "What did I book?"},
    ]
    reply(build_agent(model=model), conversation)
    assert "Booked T90004" in model.received[0][2].content
