"""Database tests: load the star schema, then run row counts, SQL checks and a reconciliation."""
import os
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from load_db import DATABASE_URL, load_all

ROOT = Path(__file__).resolve().parent.parent
CHECKS_FILE = ROOT / "sql" / "checks.sql"
EXPECTED_ROWS = {"dim_date": 252, "dim_trade": 60, "fact_market_prices": 3024, "fact_valuations": 7403}


def parse_checks(sql):
    """Split checks.sql into {check_name: query} using the '-- check:' markers."""
    checks = {}
    for block in sql.split("-- check:")[1:]:
        name, query = block.split("\n", 1)
        checks[name.strip()] = query.strip().rstrip(";")
    return checks


CHECKS = parse_checks(CHECKS_FILE.read_text())


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect():
            pass
    except Exception:
        if os.environ.get("CI"):
            pytest.fail("PostgreSQL is required in CI")
        pytest.skip("PostgreSQL is not available")
    load_all(engine)          # fresh load before the tests
    return engine


def test_all_checks_were_found():
    assert len(CHECKS) == 7


@pytest.mark.parametrize("table, expected", EXPECTED_ROWS.items())
def test_row_counts(engine, table, expected):
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == expected


@pytest.mark.parametrize("name", list(CHECKS))
def test_data_quality_check(engine, name):
    with engine.connect() as conn:
        bad_rows = conn.execute(text(CHECKS[name])).scalar()
    assert bad_rows == 0, f"{name}: {bad_rows} bad rows"


def test_database_pnl_reconciles_with_csv(engine):
    csv_total = pd.read_csv(ROOT / "data" / "valuations.csv")["pnl"].sum()
    with engine.connect() as conn:
        db_total = conn.execute(text("SELECT SUM(pnl) FROM fact_valuations")).scalar()
    assert float(db_total) == pytest.approx(csv_total, abs=0.01)
