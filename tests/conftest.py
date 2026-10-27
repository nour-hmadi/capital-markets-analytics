"""Fixtures shared by several test files. pytest loads this file automatically."""
import os

import pytest
from fastapi.testclient import TestClient
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
