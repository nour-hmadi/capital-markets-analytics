"""The AI assistant: a LangChain agent that answers in plain English, using Google Gemini.

Version 1 only chats. The next versions give it tools: SQL on the database, the Learn notes (RAG)
and booking trades.
"""
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

MODEL = "gemini-3.5-flash-lite"       # fast and free; gemini-3.8-flash was overloaded (503) and too slow (504)
MAX_QUESTIONS = 15                    # per visit, so one visitor can't use up the free allowance
INSTRUCTIONS = """You are the assistant of Capital Markets Analytics, a learning project by Nour Hmadi.
It simulates a small bank in 2025: equity indices, government bonds and FX forwards, with a 60-trade
book on three desks (Equity, Rates, FX), valued every day for P&L and DV01. All market data is synthetic.
Answer clearly and briefly, in the user's language.
You can't see the project's data yet. If you're asked for a number from the project, say so: never guess."""


def build_agent(api_key=None, model=None):
    """The agent: the model plus its tools (none yet). Tests pass a fake model instead of Gemini."""
    if model is None:
        model = ChatGoogleGenerativeAI(model=MODEL, google_api_key=api_key, thinking_level="minimal",
                                       max_retries=1, timeout=30)   # an answer or a clear error within a minute
    return create_agent(model, tools=[], system_prompt=INSTRUCTIONS)


def reply(agent, conversation):
    """The model has no memory, so the whole conversation is sent with every question."""
    result = agent.invoke({"messages": conversation})
    return result["messages"][-1].text
