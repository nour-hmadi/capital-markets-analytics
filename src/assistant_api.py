"""The AI assistant's access to the data: it writes SQL, and the API runs it as a read-only database user.

The database does the protecting, not the AI. The user assistant_reader (sql/assistant_reader.sql)
can only read the dbt marts: it can't change anything or see visitors' trades and emails. On top of that,
every query runs in a read-only transaction, is stopped after 5 seconds and is never committed.
Only one statement is accepted per request, and at most 50 rows and 20,000 characters come back:
PostgreSQL cuts the answer before sending it, so a huge value never reaches the API or the AI.
"""
import json
import os
import secrets
from typing import Optional

import psycopg2
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

import desk_api

READER_URL = os.environ.get("ASSISTANT_DATABASE_URL", "")    # the read-only user's connection; never in the code
SCHEMA = "analytics_marts"
MAX_ROWS = 50
MAX_CHARS = 20_000           # the most text one answer can send back: about 5,000 tokens for the AI
TIMEOUT = "5s"


def check_app_key(x_app_key: Optional[str] = Header(None)):
    """Only the Streamlit app may use these endpoints: it sends the key it shares with the API."""
    key = desk_api.APP_KEY
    if not (key and x_app_key and secrets.compare_digest(x_app_key.encode(), key.encode())):
        raise HTTPException(status_code=401, detail="Only the app can use the assistant's endpoints")


router = APIRouter(prefix="/assistant", tags=["assistant"], dependencies=[Depends(check_app_key)])


class Query(BaseModel):
    sql: str = Field(min_length=1, max_length=5000)


def connect():
    """A new connection for every request, so nothing one query changes can reach the next."""
    if not READER_URL:
        raise HTTPException(status_code=503, detail="The assistant's database user isn't set up")
    try:
        return psycopg2.connect(READER_URL.replace("postgresql+psycopg2://", "postgresql://", 1),
                                connect_timeout=10)
    except psycopg2.ProgrammingError:       # its message can quote the setting, password included: never show it
        raise HTTPException(status_code=503, detail="The assistant's database setting (ASSISTANT_DATABASE_URL) "
                                                    "is badly written")
    except psycopg2.OperationalError:
        raise HTTPException(status_code=503, detail="The database isn't reachable right now")


def explain(error):
    """The database's own words, so the AI can fix its query: column "pnl" does not exist."""
    message = error.diag.message_primary or str(error).strip()
    return f"{message}. Hint: {error.diag.message_hint}" if error.diag.message_hint else message


@router.get("/tables")
def tables():
    """The tables the assistant may read: what each one holds (from the dbt docs) and its columns."""
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_schema || '.' || table_name,
                       obj_description((quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass,
                                       'pg_class'),
                       string_agg(column_name || ' (' || data_type || ')', ', ' ORDER BY ordinal_position)
                FROM information_schema.columns
                WHERE table_schema = %s
                GROUP BY table_schema, table_name
                ORDER BY table_name
            """, (SCHEMA,))
            rows = cur.fetchall()
    except psycopg2.Error as error:
        raise HTTPException(status_code=503, detail=f"The tables couldn't be listed: {explain(error)}")
    finally:
        conn.close()
    return [{"table": name, "description": description, "columns": columns}
            for name, description, columns in rows]


@router.post("/query")
def query(body: Query):
    """Run one SELECT as the read-only user. Errors come back as text, so the AI can correct itself."""
    sql = body.sql.strip().rstrip(";").strip()
    if ";" in sql:
        raise HTTPException(status_code=400, detail="Send one SELECT statement at a time, without semicolons")
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(f"SET LOCAL statement_timeout = '{TIMEOUT}'")
        # 1. PostgreSQL checks the SQL alone (DECLARE ... FOR it): one complete query, or an error.
        #    So it can't close the parenthesis in step 2 early to get past the limits (SQL injection).
        with conn.cursor(name="assistant_query") as cur:
            cur.execute(sql)
        # 2. PostgreSQL runs it, turns the rows into one JSON text and cuts it: a huge answer never leaves it.
        with conn.cursor() as cur:
            cur.execute(f"SELECT left(json_agg(q)::text, {MAX_CHARS + 1}) "
                        f"FROM (SELECT * FROM ({sql}\n) AS ai LIMIT {MAX_ROWS + 1}) AS q")
            answer = cur.fetchone()[0] or "[]"                # no rows: json_agg gives NULL
    except psycopg2.Error as error:
        raise HTTPException(status_code=400, detail=explain(error))
    finally:
        conn.close()                                          # never committed: the database rolls it back
    if len(answer) > MAX_CHARS:
        raise HTTPException(status_code=400, detail=f"The answer is too big (over {MAX_CHARS:,} characters): "
                                                    "select fewer or shorter columns")
    rows = json.loads(answer, object_pairs_hook=list)         # each row: (column, value) pairs, in order
    return {"columns": [name for name, _ in rows[0]] if rows else [],
            "rows": [[value for _, value in row] for row in rows[:MAX_ROWS]],
            "truncated": len(rows) > MAX_ROWS}
