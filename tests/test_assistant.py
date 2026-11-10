"""The AI assistant with fake models and a fake database: no internet, no API key, the same answers every time."""
from langchain_core.messages import SystemMessage, ToolMessage

from assistant import INSTRUCTIONS, build_agent, reply
from notes import Notes, load_chunks

SQL = "SELECT desk, SUM(pnl_usd) AS pnl_usd FROM analytics_marts.fct_daily_pnl_by_desk GROUP BY desk"


def test_the_assistant_answers(fake_model):
    agent = build_agent(model=fake_model("A bond is a loan to a government or a company."))
    answer, queries, lessons = reply(agent, [{"role": "user", "content": "What is a bond?"}])
    assert answer.startswith("A bond is a loan")
    assert queries == [] and lessons == []                 # no tools needed


def test_the_whole_conversation_is_sent_every_time(fake_model):
    """The model has no memory: the app sends the instructions, then the whole conversation, each time."""
    model = fake_model("It's the fixed interest the bond pays every year.")
    conversation = [
        {"role": "user", "content": "What is a bond?"},
        {"role": "assistant", "content": "A bond is a loan.", "sql": []},
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
    answer, queries, _ = reply(build_agent(model=model, database=database),
                            [{"role": "user", "content": "Which desk lost the most?"}])
    assert calls == [("GET", "/assistant/tables", None), ("POST", "/assistant/query", {"sql": SQL})]
    assert queries == [SQL]                                # the page shows it under the answer
    assert answer == "The FX desk lost $4.45 million."
    rows = model.received[-1][-1]                          # what the model read just before answering
    assert isinstance(rows, ToolMessage) and "-4449992.7" in rows.content


def test_a_busy_model_hands_over_to_the_backup(busy_model, fake_model):
    agent = build_agent(model=busy_model, backup=fake_model("A bond is a loan."))
    answer, _, _ = reply(agent, [{"role": "user", "content": "What is a bond?"}])
    assert len(busy_model.received) == 1                   # the first model was asked, and failed
    assert answer == "A bond is a loan."


def test_the_assistant_explains_from_the_learn_notes(fake_model, tool_call, fake_embed):
    """For a concept, the model searches the notes and reads the closest paragraphs; the page gets the lessons."""
    model = fake_model(tool_call("search_notes", question="What is DV01?"),
                       "DV01 is how much a position loses when yields rise by 1 bp (Rate risk lesson).")
    answer, queries, lessons = reply(build_agent(model=model, notes=Notes(load_chunks(), fake_embed)),
                                     [{"role": "user", "content": "What is DV01?"}])
    assert lessons[0] == "Rate risk (DV01)" and queries == []
    read = model.received[-1][-1]                          # what the model read just before answering
    assert isinstance(read, ToolMessage) and "[Rate risk (DV01)]" in read.content


def test_the_assistant_goes_on_when_the_notes_are_unavailable(fake_model, tool_call):
    def broken(texts):
        raise RuntimeError("503 UNAVAILABLE")

    model = fake_model(tool_call("search_notes", question="What is DV01?"), "From general knowledge: DV01 is…")
    answer, _, lessons = reply(build_agent(model=model, notes=Notes(load_chunks(), broken)),
                               [{"role": "user", "content": "What is DV01?"}])
    assert answer.startswith("From general knowledge") and lessons == []
    assert "can't be searched right now" in model.received[-1][-1].content
