"""The AI assistant: a LangChain agent that answers in plain English, using Google Gemini.

Version 4: it reads the project's data (it writes SQL, and the API runs it as a read-only database user),
explains concepts from the Learn notes (RAG) and drafts trades. It never books one: the visitor does,
with a button (human in the loop).
"""
from datetime import date
from functools import lru_cache
from typing import Literal, Optional

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from desk import INSTRUMENTS, MAX_QUANTITY
from notes import Notes, gemini_embedder, load_chunks
from trades import COUNTERPARTIES, FX_TENORS_MONTHS

MODEL = "gemini-3.5-flash-lite"       # fast and free; gemini-3.8-flash was overloaded (503) and too slow (504)
BACKUP_MODEL = "gemini-3.1-flash-lite"   # takes over when the first model is busy
MAX_QUESTIONS = 15                    # per visit, so one visitor can't use up the free allowance
FIRST_TRADE_DATE, LAST_TRADE_DATE = "2025-01-01", "2025-12-18"     # the market data, as on the Trade desk page
INSTRUCTIONS = """You are the assistant of Capital Markets Analytics, a learning project by Nour Hmadi.
It simulates a small bank in 2025: equity indices, government bonds and FX forwards, with a 60-trade
book on three desks (Equity, Rates, FX), valued every day for P&L and DV01. All market data is synthetic.
Always answer in the language of the user's latest message; if you're not sure, answer in English.
Answer clearly and briefly.
For any number about the project, look it up: call list_tables first, then run_sql with one PostgreSQL
SELECT query, writing each table with its schema (analytics_marts.fct_positions). If a query fails, read
the error, fix the query and try again. Never guess a number: if the data can't answer, say so.
Amounts are in US dollars.
To explain a concept, call search_notes first and base your answer on the project's Learn notes, naming
the lesson. If the notes don't cover it, answer from general knowledge and say so.
To book a trade, call draft_trade. It only prepares the trade: the visitor books it with the Book button
under your answer, so never say a trade is booked. For the visitor's own trades, call my_trades."""


def data_tools(database):
    """The agent's tools. database(method, path, body) calls the API; tests pass a fake one."""

    @tool
    def list_tables():
        """List the tables you can query: what each one holds, and its columns with their types."""
        return database("GET", "/assistant/tables")

    @tool
    def run_sql(query: str):
        """Run one read-only PostgreSQL SELECT query on the project's database. Returns at most 50 rows."""
        return database("POST", "/assistant/query", {"sql": query})

    return [list_tables, run_sql]


def notes_tool(notes):
    """search_notes returns the closest chunks for the model, and their lessons for the page."""

    @tool(response_format="content_and_artifact")
    def search_notes(question: str):
        """Search the project's Learn notes (equities, bonds, DV01, FX forwards, trade lifecycle) to explain
        a concept. Returns the closest paragraphs, each with its lesson."""
        try:
            found = notes.search(question)
        except Exception as error:              # the assistant goes on without the notes
            return f"Error: the Learn notes can't be searched right now ({error.__class__.__name__})", []
        return "\n\n".join(f"[{chunk.lesson}] {chunk.text}" for chunk in found), [chunk.lesson for chunk in found]

    return search_notes


def check_draft(draft):
    """The first problem with a draft, or None. The API checks everything again when the visitor books it."""
    allowed = INSTRUMENTS[draft["instrument_type"]]["underlyings"]
    if draft["underlying"] not in allowed:
        return (f"{draft['underlying']} is not a valid underlying for {draft['instrument_type']}: "
                f"use one of {allowed}")
    if draft["counterparty"] not in COUNTERPARTIES:
        return f"{draft['counterparty']} is not a counterparty: use one of {COUNTERPARTIES}"
    if not 0 < draft["quantity"] <= MAX_QUANTITY:
        return f"The quantity must be from 1 to {MAX_QUANTITY:,}"
    if draft["instrument_type"] == "FX_FORWARD" and draft["tenor_months"] not in FX_TENORS_MONTHS:
        return f"An FX forward needs tenor_months, one of {FX_TENORS_MONTHS}"
    try:
        day = date.fromisoformat(draft["trade_date"]).isoformat()
    except ValueError:
        return "Write the trade date as YYYY-MM-DD"
    if not FIRST_TRADE_DATE <= day <= LAST_TRADE_DATE:
        return f"The trade date must be from {FIRST_TRADE_DATE} to {LAST_TRADE_DATE}"
    return None


def trade_tools(desk):
    """The trade desk tools. desk(method, path, body) calls the API for the visitor; tests pass a fake one.
    There is no tool that books: only the visitor's click on the page does."""
    choices = "; ".join(f"{kind}: {', '.join(spec['underlyings'])}" for kind, spec in INSTRUMENTS.items())

    @tool(response_format="content_and_artifact", description=(
        "Prepare a trade for the visitor to confirm. It books NOTHING: the visitor books it with a button. "
        f"Underlyings: {choices}. Counterparties: {', '.join(COUNTERPARTIES)}. FX forwards need tenor_months "
        f"({', '.join(map(str, FX_TENORS_MONTHS))}). Trade dates: trading days from {FIRST_TRADE_DATE} to "
        f"{LAST_TRADE_DATE} (YYYY-MM-DD); without a date, use the last one."))
    def draft_trade(instrument_type: Literal["EQUITY_INDEX", "BOND", "FX_FORWARD"], underlying: str,
                    direction: Literal["BUY", "SELL"], quantity: int, counterparty: str,
                    trade_date: str = LAST_TRADE_DATE, tenor_months: Optional[int] = None):
        draft = {"instrument_type": instrument_type, "underlying": underlying, "direction": direction,
                 "quantity": quantity, "trade_date": trade_date, "counterparty": counterparty,
                 "tenor_months": tenor_months if instrument_type == "FX_FORWARD" else None}
        problem = check_draft(draft)
        if problem:
            return f"Error: {problem}", None
        return ("Draft ready. Nothing is booked yet: the visitor can book it or cancel it with the buttons "
                "under your answer."), draft

    @tool
    def my_trades():
        """The visitor's own trades on the trade desk (from T90001), with their P&L on the last day.
        Signed-in visitors see theirs; guests see the shared guest trades, cleared every morning."""
        return desk("GET", "/desk/trades")

    return [draft_trade, my_trades]


@lru_cache
def learn_notes(api_key):
    """One Notes for the whole app, so the chunks are turned into vectors only once."""
    return Notes(load_chunks(), gemini_embedder(api_key))


def gemini(name, api_key, **options):
    """A Gemini model that answers or fails within a minute: one retry, 30 seconds each."""
    return ChatGoogleGenerativeAI(model=name, google_api_key=api_key, max_retries=1, timeout=30, **options)


def build_agent(api_key=None, database=None, desk=None, notes=None, model=None, backup=None):
    """The agent: a model, its tools and its instructions. Tests pass fakes for the model and the tools."""
    if model is None:
        model = gemini(MODEL, api_key, thinking_level="minimal")
        backup = gemini(BACKUP_MODEL, api_key)
        notes = notes or learn_notes(api_key)
    tools = ((data_tools(database) if database else []) + ([notes_tool(notes)] if notes else [])
             + (trade_tools(desk) if desk else []))
    middleware = [ModelFallbackMiddleware(backup)] if backup else []
    return create_agent(model, tools=tools, system_prompt=INSTRUCTIONS, middleware=middleware)


def reply(agent, conversation):
    """The model has no memory, so the whole conversation is sent with every question.

    Returns the assistant's message for the page: the answer, the SQL queries the agent ran, the Learn
    lessons it read and the trade it drafted, if any.
    """
    messages = [{"role": message["role"], "content": message["content"]} for message in conversation]
    result = agent.invoke({"messages": messages})
    new = result["messages"][len(messages):]
    queries = [call["args"].get("query", "") for message in new
               for call in getattr(message, "tool_calls", []) if call["name"] == "run_sql"]
    lessons = [lesson for message in new if getattr(message, "name", None) == "search_notes"
               for lesson in (message.artifact or [])]
    drafts = [message.artifact for message in new
              if getattr(message, "name", None) == "draft_trade" and message.artifact]
    return {"role": "assistant", "content": result["messages"][-1].text, "sql": queries,
            "lessons": list(dict.fromkeys(lessons)), "draft": drafts[-1] if drafts else None}
