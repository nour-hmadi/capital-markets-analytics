"""Fixtures shared by several test files. pytest loads this file automatically."""
import os
import re
import secrets
import zlib
from pathlib import Path

import psycopg2
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import Field
from sqlalchemy import create_engine, make_url, text

from api import app
from load_db import DATABASE_URL

READER_SQL = Path(__file__).resolve().parent.parent / "sql" / "assistant_reader.sql"


def marts_problem():
    """Return None if the dbt marts are ready, otherwise the reason they aren't."""
    try:
        with create_engine(DATABASE_URL).connect() as conn:
            ready = conn.execute(text("SELECT to_regclass('analytics_marts.fct_positions')")).scalar()
    except Exception:
        return "PostgreSQL is not available"
    return None if ready else "dbt marts are missing: run load_db.py, then dbt build"


@pytest.fixture(scope="module")
def client():
    """The API, called in-process. Without the marts: skip locally, fail in CI."""
    problem = marts_problem()
    if problem:
        if os.environ.get("CI"):
            pytest.fail(problem)
        pytest.skip(problem)
    return TestClient(app)


@pytest.fixture(scope="module")
def reader_url(client):
    """The assistant's read-only database user, made by sql/assistant_reader.sql with a random password."""
    password = secrets.token_urlsafe(16)
    setup = READER_SQL.read_text().replace("choose-a-strong-password", password)
    url = make_url(DATABASE_URL)
    reader = url.set(username="assistant_reader", password=password,
                     host=url.host or "localhost").render_as_string(hide_password=False)
    try:
        conn = psycopg2.connect(DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://", 1))
        try:
            with conn, conn.cursor() as cur:            # one transaction: saved only if every statement works
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'assistant_reader'")
                if cur.fetchone():                      # made by an earlier test run: just set a new password
                    setup = setup.replace("CREATE ROLE", "ALTER ROLE")
                cur.execute(setup)
        finally:
            conn.close()
        psycopg2.connect(reader.replace("postgresql+psycopg2://", "postgresql://", 1)).close()   # can it log in?
    except psycopg2.Error as error:
        problem = f"The assistant's database user isn't available here: {error}"
        if os.environ.get("CI"):
            pytest.fail(problem)
        pytest.skip(problem)
    return reader


class FakeChatModel(GenericFakeChatModel):
    """Stands in for Gemini in tests: gives prepared answers and records what it was sent. No internet."""
    received: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class BusyChatModel(FakeChatModel):
    """Stands in for Gemini when Google is overloaded: every call fails, like a 503."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(messages)
        raise RuntimeError("503 UNAVAILABLE: This model is currently experiencing high demand")


@pytest.fixture
def busy_model():
    return BusyChatModel(messages=iter([]))


@pytest.fixture
def fake_model():
    """Make a fake model that gives these answers, in order: text, or prepared messages like tool calls."""
    return lambda *answers: FakeChatModel(messages=iter(
        [answer if isinstance(answer, AIMessage) else AIMessage(content=answer) for answer in answers]))


@pytest.fixture
def tool_call():
    """A model's message asking to run a tool, as Gemini sends it."""
    return lambda name, **args: AIMessage(content="", tool_calls=[{"name": name, "args": args,
                                                                    "id": f"call-{name}"}])


def word_vector(text, size=512):
    """A fake embedding: one dimension per word, so texts that share words point in the same direction."""
    vector = [0.0] * size
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vector[zlib.crc32(word.encode()) % size] += 1
    return vector


@pytest.fixture
def fake_embed():
    """Stands in for Gemini's embedding model: no internet, the same vectors every time. Records its calls."""
    def embed(texts):
        embed.calls.append(list(texts))
        return [word_vector(text) for text in texts]
    embed.calls = []
    return embed


# ---- Recording the AI evaluation (tests marked "eval") for the app's Evaluation page ----
EVAL_DIR = Path(__file__).resolve().parent.parent / "docs" / "eval"
CATEGORY = {"test_data_questions": "Data questions", "test_concept_questions": "Concept questions",
            "test_trade_requests": "Trade requests", "test_what_did_i_book": "The visitor's trades",
            "test_my_trade_pnl": "The visitor's trades", "test_requests_it_must_decline": "Must decline",
            "test_questions_without_an_answer": "No data to answer"}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Keep the outcome of every eval question: what was asked, what came back, pass or fail, and the time."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not item.get_closest_marker("eval"):
        return
    properties = dict(item.user_properties)
    results = item.session.__dict__.setdefault("eval_results", [])
    results.append({"id": item.name, "category": CATEGORY.get(item.originalname, item.originalname),
                    "question": properties.get("question", ""), "outcome": report.outcome,
                    "seconds": properties.get("seconds"), "answer": properties.get("answer", ""),
                    "why": str(call.excinfo.value)[:300] if call.excinfo else ""})


def pytest_sessionfinish(session, exitstatus):
    """After an eval run, save docs/eval/latest.json and add one line to docs/eval/history.csv."""
    import csv
    import json
    import statistics
    from datetime import datetime, timezone

    results = getattr(session, "eval_results", None)
    if not results:
        return
    import assistant
    seconds = [r["seconds"] for r in results if r["seconds"] is not None]
    counts = {status: sum(r["outcome"] == status for r in results) for status in ("passed", "failed", "skipped")}
    by_category = {}
    for r in results:
        bucket = by_category.setdefault(r["category"], {"passed": 0, "failed": 0, "skipped": 0})
        bucket[r["outcome"]] += 1
    run = {"ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "model": assistant.MODEL,
           "questions": len(results), **counts,
           "median_seconds": round(statistics.median(seconds), 2) if seconds else None,
           "slowest_seconds": round(max(seconds), 2) if seconds else None,
           "by_category": by_category, "results": results}
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    (EVAL_DIR / "latest.json").write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")
    history = EVAL_DIR / "history.csv"
    new = not history.exists()
    with history.open("a", newline="") as file:
        writer = csv.writer(file)
        if new:
            writer.writerow(["ran_at", "model", "questions", "passed", "failed", "skipped", "median_seconds",
                             "slowest_seconds"])
        writer.writerow([run["ran_at"], run["model"], run["questions"], counts["passed"], counts["failed"],
                         counts["skipped"], run["median_seconds"], run["slowest_seconds"]])
    print(f"\nEvaluation saved: {counts['passed']}/{len(results)} passed, {counts['skipped']} skipped, "
          f"median {run['median_seconds']} s -> docs/eval/latest.json")
