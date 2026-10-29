# Capital Markets Analytics

![Tests](https://github.com/nour-hmadi/capital-markets-analytics/actions/workflows/tests.yml/badge.svg)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://capital-markets-analytics.streamlit.app)

An end-to-end capital markets data platform: simulated market data, a 60-trade book valued every day
(P&L, DV01), a tested data pipeline (PostgreSQL, dbt, CI/CD), a REST API, and a live app where visitors
book their own trades.

- **Live app:** [capital-markets-analytics.streamlit.app](https://capital-markets-analytics.streamlit.app)
- **API docs:** [capital-markets-api.onrender.com/docs](https://capital-markets-api.onrender.com/docs)
  (free hosting: the first request can take up to a minute while the API wakes up)

All market data is synthetic, generated with a fixed seed. I built this project to learn how capital
markets work, and to practise the skills a test or data engineer uses on a trading platform.

## What the app shows

| Page | What you can do |
|---|---|
| **Market** | Equity indices, the yield curve on any date in 2025, FX rates and the 10y − 2y spread |
| **Portfolio** | P&L by desk over time, positions, and rate risk (DV01) by bond |
| **Pricing** | Price a bond or an FX forward yourself, and see the price–yield curve |
| **Trade desk** | Book, change and delete your own trades, priced at any 2025 market, and see each trade's XML message |
| **Learn** | The trading basics behind each page, with short quizzes |

Visitors can trade as guests (their trades are cleared every morning) or **sign in with Google** to keep them.

## Architecture

```
generate_data.py ─► trades.py ─► valuation.py ─► load_db.py ─► PostgreSQL (Neon) ─► dbt
 market data         60 trades     7,403 daily      raw tables     cloud database     staging → intermediate → marts
                                   valuations       + run log
                                                                                        │
     Streamlit app (Streamlit Cloud)  ◄──────  REST API (FastAPI on Render)  ◄──────────┘
     7 pages, Google sign-in                   15 endpoints, XML trade messages
```

Data flows in one direction: the pipeline loads the database, dbt builds the tested marts, the API serves
them, and the app only talks to the API.

## Key numbers

| | |
|---|---|
| Trade book | 60 trades on 3 desks (Equity, Rates, FX), valued every trading day: 7,403 valuations |
| Python tests | 215 (unit, data, database, API, XML, page and regression tests) |
| dbt | 9 models in 3 layers, 34 tests |
| API | 15 endpoints, documented with OpenAPI |

## How it is tested and deployed

- **Every pull request** runs in GitHub Actions: a fresh PostgreSQL container is loaded, `dbt build` runs
  the models and their tests, then all Python tests run. The `main` branch is protected: a pull request
  and green tests are required to merge.
- **Merging to `main`** redeploys the API (Render) and the app (Streamlit Community Cloud).
- **Every weekday morning** a scheduled workflow refreshes the cloud database: it runs the pipeline,
  rebuilds the dbt models, clears the guest trades and smoke-tests the live API. Each load is logged,
  and the Portfolio page shows when the data was last refreshed and by whom.
- **Page tests** open every page with Streamlit's AppTest against the real API and database, so a test
  fails if any link breaks: page → API → database.
- **The page tests caught a real deployment bug:** a newer `pyarrow` that crashed the cloud app. It is now
  pinned, and the tests run on every change.

## Trade desk and Google sign-in

- Visitors' trades live in their own table, `desk_trades` (IDs from T90001). The official book is
  read-only: changing it returns **403**.
- The API validates every trade (**400** for an invalid trade, **422** for a malformed request) and
  limits each person to 20 trades (**409**).
- Sign-in uses Google (OpenID Connect) through Streamlit. The app sends the user's email to the API
  together with a secret key that only the app and the API know, so nobody can act for another user by
  calling the API directly (**401**).

## XML trade messages

Banks keep trades in databases; XML is how one system **sends** a trade to another, for example from the
trading platform to settlement. Here the database is the source of truth, and XML messages are generated
from it on demand.

| File | Purpose |
|---|---|
| `schemas/trade.xsd` | the rules for a trade message: required fields, allowed values, formats, unique trade IDs |
| `src/export_xml.py` | converts trades into XML, validating every message before it is saved or sent |
| `tests/test_xml.py` | validation, 10 deliberately broken messages, a CSV → XML → CSV round trip, and business rules the XSD can't express |

## dbt transformation layer

```
public                  raw tables, loaded by src/load_db.py
analytics_staging       stg_* views: one clean model per raw table
analytics_intermediate  int_valuations_enriched: valuations joined to trades
analytics_marts         fct_daily_pnl_by_desk (incremental, enforced contract), fct_positions,
                        fct_daily_rates_risk (DV01 and a +10 bp shock), fct_market_prices
```

Generic and singular tests include reconciliations: the desk P&L mart must equal the sum of trade-level
valuations, and positions must reconcile with desk P&L.

## Run it locally

```bash
pip install -r requirements.txt
python src/pipeline.py                     # generate data, book and value trades, load PostgreSQL
python -m venv .dbt-venv && .dbt-venv/bin/pip install -r requirements-dbt.txt
.dbt-venv/bin/dbt build --project-dir dbt --profiles-dir dbt
python -m pytest

uvicorn api:app --app-dir src --port 8000             # API on http://localhost:8000/docs
API_URL=http://localhost:8000 streamlit run app/Home.py
```

## Project structure

```
src/          data generation, pricing, valuation, pipeline, API (api.py, desk_api.py)
app/          Streamlit app: Home and pages/
dbt/          dbt models, tests and macros
learn/        the Learn page's lessons and quizzes, one Markdown file per topic
schemas/      XSD for trade messages
sql/          database schema
tests/        pytest suite;  smoke/  tests against the live API
notebooks/    my learning notebooks (capital markets basics, bonds and FX)
.github/      CI and the scheduled data refresh
```

---

*Author: Nour Hmadi · [LinkedIn](https://www.linkedin.com/in/nour-hmadi-b86a29438) · [GitHub](https://github.com/nour-hmadi)*
