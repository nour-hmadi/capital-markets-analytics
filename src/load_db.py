"""Load the CSV files into the PostgreSQL star schema."""
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCHEMA_FILE = ROOT / "sql" / "schema.sql"
# Local socket + peer authentication by default; CI can override it with an environment variable
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2:///capital_markets")
# Cloud providers give "postgresql://...": name the driver explicitly, because the default
# PostgreSQL driver of SQLAlchemy differs between versions.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgresql://"):]
TABLES = ["dim_date", "dim_trade", "fact_market_prices", "fact_valuations"]


def read_market(name):
    return pd.read_csv(DATA_DIR / name, index_col="date", parse_dates=True)


def to_long(wide, asset_class):
    """One column per series -> one row per date and series."""
    long = wide.reset_index().melt(id_vars="date", var_name="series", value_name="value")
    long["asset_class"] = asset_class
    return long[["date", "asset_class", "series", "value"]]


def build_market_prices():
    return pd.concat([
        to_long(read_market("equities.csv"), "EQUITY"),
        to_long(read_market("yield_curves.csv"), "RATES"),
        to_long(read_market("fx_rates.csv"), "FX"),
    ], ignore_index=True)


def build_dim_date(dates):
    dim = pd.DataFrame({"date": pd.to_datetime(sorted(set(dates)))})
    dim["year"] = dim["date"].dt.year
    dim["quarter"] = dim["date"].dt.quarter
    dim["month"] = dim["date"].dt.month
    dim["month_name"] = dim["date"].dt.strftime("%b")
    dim["weekday"] = dim["date"].dt.strftime("%a")
    return dim


def load_all(engine):
    market = build_market_prices()
    trades = pd.read_csv(DATA_DIR / "trades.csv", parse_dates=["trade_date", "maturity_date"])
    trades["maturity_years"] = trades["maturity_years"].astype("Int64")   # whole numbers, NULL if missing
    valuations = pd.read_csv(DATA_DIR / "valuations.csv", parse_dates=["date"])
    tables = {
        "dim_date": build_dim_date(market["date"]),
        "dim_trade": trades,
        "fact_market_prices": market,
        "fact_valuations": valuations,
    }
    with engine.begin() as conn:                      # one transaction: all or nothing
        conn.execute(text(SCHEMA_FILE.read_text()))
        for name in TABLES:                           # dimensions first, then facts
            tables[name].to_sql(name, conn, if_exists="append", index=False,
                                method="multi", chunksize=1000)


def main():
    engine = create_engine(DATABASE_URL)
    load_all(engine)
    with engine.connect() as conn:
        for name in TABLES:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
            print(f"{name:<20} {count:>6} rows")


if __name__ == "__main__":
    main()
