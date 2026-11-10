"""The AI assistant: a LangChain agent that answers in plain English, using Google Gemini.

Version 3: it reads the project's data (it writes SQL, and the API runs it as a read-only database user)
and explains concepts from the Learn notes (RAG). Next: booking trades.
"""
from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from notes import Notes, gemini_embedder, load_chunks

MODEL = "gemini-3.5-flash-lite"       # fast and free; gemini-3.8-flash was overloaded (503) and too slow (504)
BACKUP_MODEL = "gemini-3.1-flash-lite"   # takes over when the first model is busy
MAX_QUESTIONS = 15                    # per visit, so one visitor can't use up the free allowance
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
the lesson. If the notes don't cover it, answer from general knowledge and say so."""


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


@lru_cache
def learn_notes(api_key):
    """One Notes for the whole app, so the chunks are turned into vectors only once."""
    return Notes(load_chunks(), gemini_embedder(api_key))


def gemini(name, api_key, **options):
    """A Gemini model that answers or fails within a minute: one retry, 30 seconds each."""
    return ChatGoogleGenerativeAI(model=name, google_api_key=api_key, max_retries=1, timeout=30, **options)


def build_agent(api_key=None, database=None, notes=None, model=None, backup=None):
    """The agent: a model, its tools and its instructions. Tests pass fake models, a fake database and notes."""
    if model is None:
        model = gemini(MODEL, api_key, thinking_level="minimal")
        backup = gemini(BACKUP_MODEL, api_key)
        notes = notes or learn_notes(api_key)
    tools = (data_tools(database) if database else []) + ([notes_tool(notes)] if notes else [])
    middleware = [ModelFallbackMiddleware(backup)] if backup else []
    return create_agent(model, tools=tools, system_prompt=INSTRUCTIONS, middleware=middleware)


def reply(agent, conversation):
    """The model has no memory, so the whole conversation is sent with every question.

    Returns the answer, the SQL queries the agent ran and the Learn lessons it read (the page shows them).
    """
    messages = [{"role": message["role"], "content": message["content"]} for message in conversation]
    result = agent.invoke({"messages": messages})
    new = result["messages"][len(messages):]
    queries = [call["args"].get("query", "") for message in new
               for call in getattr(message, "tool_calls", []) if call["name"] == "run_sql"]
    lessons = [lesson for message in new if getattr(message, "name", None) == "search_notes"
               for lesson in (message.artifact or [])]
    return result["messages"][-1].text, queries, list(dict.fromkeys(lessons))
