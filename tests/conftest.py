"""Fixtures shared by several test files. pytest loads this file automatically."""
import os

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import Field
from sqlalchemy import create_engine, text

from api import app
from load_db import DATABASE_URL


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


class FakeChatModel(GenericFakeChatModel):
    """Stands in for Gemini in tests: gives prepared answers and records what it was sent. No internet."""
    received: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture
def fake_model():
    """Make a fake model that gives these answers, in order."""
    return lambda *answers: FakeChatModel(messages=iter([AIMessage(content=answer) for answer in answers]))
