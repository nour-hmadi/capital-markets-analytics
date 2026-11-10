"""Fixtures shared by several test files. pytest loads this file automatically."""
import os
import secrets
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
